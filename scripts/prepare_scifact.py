from __future__ import annotations

import argparse
import json
import re
import tarfile
import urllib.request
from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import Any


SCIFACT_URL = "https://scifact.s3-us-west-2.amazonaws.com/release/latest/data.tar.gz"
CLAIM_FILES = {
    "train": "claims_train.jsonl",
    "validation": "claims_dev.jsonl",
    "test": "claims_test.jsonl",
}


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def download(url: str, destination: Path) -> None:
    if destination.exists() and destination.stat().st_size > 0:
        return

    destination.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(url, timeout=120) as response:
        destination.write_bytes(response.read())


def safe_extract_tarball(tarball: Path, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    root = destination.resolve()

    with tarfile.open(tarball, "r:gz") as archive:
        for member in archive.getmembers():
            target = (destination / member.name).resolve()
            if root not in target.parents and target != root:
                raise RuntimeError(f"Unsafe archive path: {member.name}")
        try:
            archive.extractall(destination, filter="data")
        except TypeError:
            archive.extractall(destination)


def ensure_scifact(raw_dir: Path) -> dict[str, Path]:
    raw_dir.mkdir(parents=True, exist_ok=True)
    tarball = raw_dir / "scifact-data.tar.gz"
    download(SCIFACT_URL, tarball)
    safe_extract_tarball(tarball, raw_dir)

    paths: dict[str, Path] = {}
    corpus_matches = list(raw_dir.rglob("corpus.jsonl"))
    if not corpus_matches:
        raise FileNotFoundError(f"Could not find corpus.jsonl under {raw_dir}")
    paths["corpus"] = corpus_matches[0]

    for split, filename in CLAIM_FILES.items():
        matches = list(raw_dir.rglob(filename))
        if not matches:
            raise FileNotFoundError(f"Could not find {filename} under {raw_dir}")
        paths[split] = matches[0]
    return paths


def read_jsonl(path: Path) -> Iterator[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as file:
        for line in file:
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)
            if isinstance(record, dict):
                yield record


def load_corpus(path: Path) -> dict[int, dict[str, Any]]:
    corpus: dict[int, dict[str, Any]] = {}
    for record in read_jsonl(path):
        doc_id = int(record["doc_id"])
        corpus[doc_id] = record
    return corpus


def evidence_text(abstract: list[Any], sentence_indexes: Iterable[int]) -> str:
    sentences: list[str] = []
    for index in sentence_indexes:
        if not isinstance(index, int):
            continue
        if 0 <= index < len(abstract):
            sentence = normalize_text(str(abstract[index]))
            if sentence:
                sentences.append(sentence)
    return " ".join(sentences)


def relation_type(label: str) -> str:
    normalized = label.strip().upper()
    if normalized == "SUPPORT":
        return "supports"
    if normalized == "CONTRADICT":
        return "contradicts"
    return normalized.lower() or "related_to"


def write_jsonl(path: Path, records: Iterable[dict[str, Any]]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with path.open("w", encoding="utf-8", newline="\n") as file:
        for record in records:
            file.write(json.dumps(record, ensure_ascii=False, sort_keys=True))
            file.write("\n")
            count += 1
    return count


def build_records(
    paths: dict[str, Path],
    max_claims_per_split: int | None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    corpus = load_corpus(paths["corpus"])
    chunk_records: list[dict[str, Any]] = []
    evidence_records: list[dict[str, Any]] = []
    seed_records: list[dict[str, Any]] = []
    used_doc_ids: set[int] = set()

    for split in ("train", "validation", "test"):
        for claim_number, claim_record in enumerate(read_jsonl(paths[split]), start=1):
            if max_claims_per_split is not None and claim_number > max_claims_per_split:
                break

            claim_id = int(claim_record["id"])
            claim_text = normalize_text(str(claim_record.get("claim") or ""))
            evidence_by_doc = claim_record.get("evidence") or {}
            if not isinstance(evidence_by_doc, dict) or not claim_text:
                continue

            for doc_id_text, rationales in evidence_by_doc.items():
                doc_id = int(doc_id_text)
                document = corpus.get(doc_id)
                if not document:
                    continue

                used_doc_ids.add(doc_id)
                title = normalize_text(str(document.get("title") or ""))
                abstract = document.get("abstract") or []
                if not isinstance(abstract, list):
                    continue

                for rationale_index, rationale in enumerate(rationales or [], start=1):
                    if not isinstance(rationale, dict):
                        continue
                    label = normalize_text(str(rationale.get("label") or ""))
                    sentence_indexes = [
                        index
                        for index in rationale.get("sentences", [])
                        if isinstance(index, int)
                    ]
                    span = evidence_text(abstract, sentence_indexes)
                    if not span:
                        continue

                    record_id = f"scifact-{split}-{claim_id}-{doc_id}-{rationale_index}"
                    relation = relation_type(label)
                    claim_node_id = f"claim-{record_id}"
                    evidence_node_id = f"evidence-{record_id}"
                    chunk_id = f"scifact:{doc_id}:abstract"

                    evidence_records.append(
                        {
                            "id": record_id,
                            "source_dataset": "scifact",
                            "split": split,
                            "claim_id": claim_id,
                            "paper_id": str(doc_id),
                            "title": title,
                            "section": "Abstract",
                            "page": None,
                            "chunk_id": chunk_id,
                            "sentence_indexes": sentence_indexes,
                            "label": label,
                            "relation_type": relation,
                            "claim": claim_text,
                            "evidence_span": span,
                            "chunk_text": " ".join(normalize_text(str(sentence)) for sentence in abstract),
                        }
                    )

                    seed_records.append(
                        {
                            "id": record_id,
                            "source_dataset": "scifact",
                            "status": "needs_human_review",
                            "paper_id": str(doc_id),
                            "title": title,
                            "source_pdf": None,
                            "section": "Abstract",
                            "page": None,
                            "chunk_id": chunk_id,
                            "chunk_text": " ".join(normalize_text(str(sentence)) for sentence in abstract),
                            "question": "Does the abstract evidence support or contradict the scientific claim?",
                            "labels": {
                                "claims": [
                                    {
                                        "id": claim_node_id,
                                        "text": claim_text,
                                        "evidence_span": span,
                                        "confidence": 0.7,
                                        "source": "scifact_claim_verification",
                                    }
                                ],
                                "methods": [],
                                "experiments": [],
                                "limitations": [],
                                "concepts": [],
                                "relations": [
                                    {
                                        "source_id": claim_node_id,
                                        "target_id": evidence_node_id,
                                        "type": relation,
                                        "evidence_span": span,
                                        "confidence": 0.85,
                                        "source": "scifact_rationale_label",
                                    }
                                ],
                            },
                            "negative_labels": {},
                            "annotator_notes": "Converted from SciFact claim verification. Verify claim scope, evidence span, and relation before using as gold data.",
                        }
                    )

    for doc_id in sorted(used_doc_ids):
        document = corpus[doc_id]
        abstract = document.get("abstract") or []
        if not isinstance(abstract, list):
            continue
        chunk_records.append(
            {
                "source_dataset": "scifact",
                "paper_id": str(doc_id),
                "title": normalize_text(str(document.get("title") or "")),
                "section": "Abstract",
                "page": None,
                "chunk_id": f"scifact:{doc_id}:abstract",
                "chunk_text": " ".join(normalize_text(str(sentence)) for sentence in abstract),
                "structured": bool(document.get("structured")),
            }
        )

    return chunk_records, evidence_records, seed_records


def main() -> None:
    parser = argparse.ArgumentParser(description="Download and clean SciFact into PaperGraph seed data.")
    parser.add_argument("--raw-dir", default="data/raw/scifact", help="Directory for downloaded SciFact source files.")
    parser.add_argument("--out-dir", default="data/processed/scifact", help="Directory for cleaned outputs.")
    parser.add_argument("--max-claims-per-split", type=int, default=0, help="Limit processed claims per split. Use 0 for all.")
    args = parser.parse_args()

    raw_dir = Path(args.raw_dir)
    out_dir = Path(args.out_dir)
    max_claims = None if args.max_claims_per_split == 0 else args.max_claims_per_split

    paths = ensure_scifact(raw_dir)
    chunk_records, evidence_records, seed_records = build_records(paths, max_claims)

    chunks_count = write_jsonl(out_dir / "chunks.jsonl", chunk_records)
    evidence_count = write_jsonl(out_dir / "evidence_candidates.jsonl", evidence_records)
    seed_count = write_jsonl(out_dir / "papergraph_seed.jsonl", seed_records)

    manifest = {
        "source_dataset": "scifact",
        "source_url": SCIFACT_URL,
        "licenses": {
            "claims_and_annotations": "CC BY 4.0",
            "corpus_abstracts": "ODC-By 1.0 via S2ORC",
            "code": "Apache 2.0",
        },
        "max_claims_per_split": max_claims,
        "files": {
            "chunks": str(out_dir / "chunks.jsonl"),
            "evidence_candidates": str(out_dir / "evidence_candidates.jsonl"),
            "papergraph_seed": str(out_dir / "papergraph_seed.jsonl"),
        },
        "counts": {
            "chunks": chunks_count,
            "evidence_candidates": evidence_count,
            "papergraph_seed": seed_count,
        },
        "warning": "papergraph_seed.jsonl is seed data, not a verified gold set. Human review is required before model training.",
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
