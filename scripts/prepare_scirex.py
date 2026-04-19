from __future__ import annotations

import argparse
import json
import re
import tarfile
import urllib.request
from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import Any


SCIREX_URL = "https://github.com/allenai/SciREX/raw/master/scirex_dataset/release_data.tar.gz"
SPLIT_FILES = {
    "train": "train.jsonl",
    "validation": "dev.jsonl",
    "test": "test.jsonl",
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


def ensure_scirex(raw_dir: Path) -> dict[str, Path]:
    raw_dir.mkdir(parents=True, exist_ok=True)
    tarball = raw_dir / "scirex-release-data.tar.gz"
    download(SCIREX_URL, tarball)
    safe_extract_tarball(tarball, raw_dir)

    paths: dict[str, Path] = {}
    for split, filename in SPLIT_FILES.items():
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


def span_text(words: list[str], span: list[int] | tuple[int, ...]) -> str:
    if len(span) < 2:
        return ""
    start = int(span[0])
    end = int(span[1])
    if start < 0 or end < start:
        return ""
    if end <= len(words):
        # SciREX spans are commonly half-open.
        selected = words[start:end]
    else:
        selected = words[start : min(end + 1, len(words))]
    return normalize_text(" ".join(selected))


def type_to_bucket(entity_type: str) -> str:
    normalized = entity_type.strip().lower()
    if normalized == "method":
        return "methods"
    if normalized in {"metric", "dataset", "task", "material"}:
        return "concepts"
    return "concepts"


def stable_id(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9]+", "-", value.lower()).strip("-") or "item"


def relation_records(record: dict[str, Any]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for field in ("n_ary_relations", "relations", "relation"):
        value = record.get(field)
        if isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    output.append(item)
                elif isinstance(item, list):
                    output.append({"raw": item})
    return output


def write_jsonl(path: Path, records: Iterable[dict[str, Any]]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with path.open("w", encoding="utf-8", newline="\n") as file:
        for record in records:
            file.write(json.dumps(record, ensure_ascii=False, sort_keys=True))
            file.write("\n")
            count += 1
    return count


def build_records(paths: dict[str, Path]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    chunk_records: list[dict[str, Any]] = []
    entity_records: list[dict[str, Any]] = []
    seed_records: list[dict[str, Any]] = []

    for split, path in paths.items():
        for doc_index, record in enumerate(read_jsonl(path), start=1):
            doc_id = normalize_text(str(record.get("doc_id") or record.get("doc_key") or f"{split}-{doc_index}"))
            words = [str(word) for word in record.get("words", [])]
            if not words:
                sentences = record.get("sentences") or []
                if sentences and all(isinstance(sentence, list) for sentence in sentences):
                    words = [str(token) for sentence in sentences for token in sentence]
            if not words:
                continue

            full_text = normalize_text(" ".join(words))
            chunk_id = f"scirex:{doc_id}:document"
            chunk_records.append(
                {
                    "source_dataset": "scirex",
                    "split": split,
                    "paper_id": doc_id,
                    "title": "",
                    "section": "Document",
                    "page": None,
                    "chunk_id": chunk_id,
                    "chunk_text": full_text,
                }
            )

            labels = {
                "claims": [],
                "methods": [],
                "experiments": [],
                "limitations": [],
                "concepts": [],
                "relations": [],
            }

            span_id_by_key: dict[tuple[int, int], str] = {}
            ner_items = record.get("ner") or []
            flattened_ner: list[Any] = []
            if ner_items and all(isinstance(item, list) for item in ner_items):
                for item in ner_items:
                    if item and all(isinstance(nested, list) for nested in item):
                        flattened_ner.extend(item)
                    else:
                        flattened_ner.append(item)

            for entity_index, entity in enumerate(flattened_ner, start=1):
                if not isinstance(entity, list) or len(entity) < 3:
                    continue
                start = int(entity[0])
                end = int(entity[1])
                entity_type = normalize_text(str(entity[2]))
                text = span_text(words, [start, end])
                if not text:
                    continue

                bucket = type_to_bucket(entity_type)
                entity_id = f"{bucket[:-1]}-scirex-{stable_id(doc_id)}-{entity_index}"
                span_id_by_key[(start, end)] = entity_id
                payload = {
                    "id": entity_id,
                    "name": text,
                    "text": text,
                    "type": entity_type,
                    "evidence_span": text,
                    "confidence": 0.75,
                    "source": "scirex_ner",
                }
                labels[bucket].append(payload)
                entity_records.append(
                    {
                        "id": entity_id,
                        "source_dataset": "scirex",
                        "split": split,
                        "paper_id": doc_id,
                        "chunk_id": chunk_id,
                        "entity_text": text,
                        "entity_type": entity_type,
                        "papergraph_bucket": bucket,
                        "evidence_span": text,
                    }
                )

            for relation_index, relation in enumerate(relation_records(record), start=1):
                labels["relations"].append(
                    {
                        "source_id": f"document-{stable_id(doc_id)}",
                        "target_id": f"relation-{stable_id(doc_id)}-{relation_index}",
                        "type": "document_level_relation",
                        "evidence_span": full_text[:800],
                        "confidence": 0.5,
                        "source": "scirex_relation_raw",
                        "raw_relation": relation,
                    }
                )

            if any(labels[key] for key in labels):
                seed_records.append(
                    {
                        "id": f"scirex-{split}-{stable_id(doc_id)}",
                        "source_dataset": "scirex",
                        "status": "needs_human_review",
                        "paper_id": doc_id,
                        "title": "",
                        "source_pdf": None,
                        "section": "Document",
                        "page": None,
                        "chunk_id": chunk_id,
                        "chunk_text": full_text,
                        "question": "Which document-level scientific methods, tasks, datasets, metrics, and relations appear in this paper?",
                        "labels": labels,
                        "negative_labels": {},
                        "annotator_notes": "Converted from SciREX document-level IE annotations. Relation endpoints are raw until mapped into PaperGraph nodes.",
                    }
                )

    return chunk_records, entity_records, seed_records


def main() -> None:
    parser = argparse.ArgumentParser(description="Download and clean SciREX into PaperGraph seed data.")
    parser.add_argument("--raw-dir", default="data/raw/scirex", help="Directory for downloaded SciREX source files.")
    parser.add_argument("--out-dir", default="data/processed/scirex", help="Directory for cleaned outputs.")
    args = parser.parse_args()

    raw_dir = Path(args.raw_dir)
    out_dir = Path(args.out_dir)

    paths = ensure_scirex(raw_dir)
    chunk_records, entity_records, seed_records = build_records(paths)

    chunks_count = write_jsonl(out_dir / "chunks.jsonl", chunk_records)
    entities_count = write_jsonl(out_dir / "entity_relation_candidates.jsonl", entity_records)
    seed_count = write_jsonl(out_dir / "papergraph_seed.jsonl", seed_records)

    manifest = {
        "source_dataset": "scirex",
        "source_url": SCIREX_URL,
        "license": "See upstream allenai/SciREX repository",
        "files": {
            "chunks": str(out_dir / "chunks.jsonl"),
            "entity_relation_candidates": str(out_dir / "entity_relation_candidates.jsonl"),
            "papergraph_seed": str(out_dir / "papergraph_seed.jsonl"),
        },
        "counts": {
            "chunks": chunks_count,
            "entity_relation_candidates": entities_count,
            "papergraph_seed": seed_count,
        },
        "warning": "papergraph_seed.jsonl is seed data, not a verified gold set. Human review and license review are required before model training or redistribution.",
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
