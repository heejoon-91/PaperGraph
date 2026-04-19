from __future__ import annotations

import argparse
import json
import re
import urllib.request
import zipfile
from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import Any


SCIER_ZIP_URL = "https://github.com/edzq/SciER/archive/refs/heads/main.zip"
SPLIT_FILES = {
    "train": "train.jsonl",
    "validation": "dev.jsonl",
    "test": "test.jsonl",
    "test_ood": "test_ood.jsonl",
}


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def download(url: str, destination: Path) -> None:
    if destination.exists() and destination.stat().st_size > 0:
        return

    destination.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(url, timeout=120) as response:
        destination.write_bytes(response.read())


def safe_extract_zip(zip_path: Path, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    root = destination.resolve()
    with zipfile.ZipFile(zip_path) as archive:
        for member in archive.infolist():
            target = (destination / member.filename).resolve()
            if root not in target.parents and target != root:
                raise RuntimeError(f"Unsafe archive path: {member.filename}")
        archive.extractall(destination)


def ensure_scier(raw_dir: Path) -> dict[str, Path]:
    raw_dir.mkdir(parents=True, exist_ok=True)
    zip_path = raw_dir / "scier-main.zip"
    download(SCIER_ZIP_URL, zip_path)
    safe_extract_zip(zip_path, raw_dir)

    paths: dict[str, Path] = {}
    for split, filename in SPLIT_FILES.items():
        matches = list(raw_dir.rglob(f"SciER/LLM/{filename}"))
        if not matches:
            raise FileNotFoundError(f"Could not find SciER/LLM/{filename} under {raw_dir}")
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


def papergraph_bucket(entity_type: str) -> str:
    normalized = entity_type.strip().lower()
    if normalized == "method":
        return "methods"
    if normalized == "task":
        return "concepts"
    if normalized == "dataset":
        return "concepts"
    return "concepts"


def stable_id(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9]+", "-", value.lower()).strip("-") or "item"


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
        for row_index, record in enumerate(read_jsonl(path), start=1):
            doc_id = normalize_text(str(record.get("doc_id") or f"{split}-{row_index}"))
            sentence = normalize_text(str(record.get("sentence") or ""))
            if not sentence:
                continue

            chunk_id = f"scier:{doc_id}:sent-{row_index}"
            chunk_records.append(
                {
                    "source_dataset": "scier",
                    "split": split,
                    "paper_id": doc_id,
                    "title": "",
                    "section": "Sentence",
                    "page": None,
                    "chunk_id": chunk_id,
                    "chunk_text": sentence,
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

            entity_id_by_text: dict[str, str] = {}
            for entity_index, entity in enumerate(record.get("ner") or [], start=1):
                if not isinstance(entity, list) or len(entity) < 2:
                    continue
                text = normalize_text(str(entity[0]))
                entity_type = normalize_text(str(entity[1]))
                if not text or not entity_type:
                    continue

                bucket = papergraph_bucket(entity_type)
                entity_id = f"{bucket[:-1]}-scier-{stable_id(doc_id)}-{row_index}-{entity_index}"
                entity_id_by_text[text.lower()] = entity_id
                payload = {
                    "id": entity_id,
                    "name": text,
                    "text": text,
                    "type": entity_type,
                    "evidence_span": text,
                    "confidence": 0.8,
                    "source": "scier_ner",
                }
                labels[bucket].append(payload)
                entity_records.append(
                    {
                        "id": entity_id,
                        "source_dataset": "scier",
                        "split": split,
                        "paper_id": doc_id,
                        "chunk_id": chunk_id,
                        "entity_text": text,
                        "entity_type": entity_type,
                        "papergraph_bucket": bucket,
                        "evidence_span": text,
                        "chunk_text": sentence,
                    }
                )

            for relation_index, relation in enumerate(record.get("rel_plus") or record.get("rel") or [], start=1):
                if not isinstance(relation, list) or len(relation) < 3:
                    continue
                source_text = normalize_text(str(relation[0]).split(":")[0])
                relation_type = normalize_text(str(relation[1]))
                target_text = normalize_text(str(relation[2]).split(":")[0])
                source_id = entity_id_by_text.get(source_text.lower())
                target_id = entity_id_by_text.get(target_text.lower())
                if not source_id or not target_id or not relation_type:
                    continue
                labels["relations"].append(
                    {
                        "source_id": source_id,
                        "target_id": target_id,
                        "type": relation_type,
                        "evidence_span": sentence,
                        "confidence": 0.85,
                        "source": "scier_relation",
                    }
                )

            if any(labels[key] for key in labels):
                seed_records.append(
                    {
                        "id": f"scier-{split}-{stable_id(doc_id)}-{row_index}",
                        "source_dataset": "scier",
                        "status": "needs_human_review",
                        "paper_id": doc_id,
                        "title": "",
                        "source_pdf": None,
                        "section": "Sentence",
                        "page": None,
                        "chunk_id": chunk_id,
                        "chunk_text": sentence,
                        "question": "Which scientific methods, datasets, tasks, and relations appear in this sentence?",
                        "labels": labels,
                        "negative_labels": {},
                        "annotator_notes": "Converted from SciER sentence-level entity/relation annotations. Verify PaperGraph bucket mapping before using as gold data.",
                    }
                )

    return chunk_records, entity_records, seed_records


def main() -> None:
    parser = argparse.ArgumentParser(description="Download and clean SciER into PaperGraph seed data.")
    parser.add_argument("--raw-dir", default="data/raw/scier", help="Directory for downloaded SciER source files.")
    parser.add_argument("--out-dir", default="data/processed/scier", help="Directory for cleaned outputs.")
    args = parser.parse_args()

    raw_dir = Path(args.raw_dir)
    out_dir = Path(args.out_dir)

    paths = ensure_scier(raw_dir)
    chunk_records, entity_records, seed_records = build_records(paths)

    chunks_count = write_jsonl(out_dir / "chunks.jsonl", chunk_records)
    entities_count = write_jsonl(out_dir / "entity_relation_candidates.jsonl", entity_records)
    seed_count = write_jsonl(out_dir / "papergraph_seed.jsonl", seed_records)

    manifest = {
        "source_dataset": "scier",
        "source_url": SCIER_ZIP_URL,
        "license": "GPL-3.0 repository license",
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
