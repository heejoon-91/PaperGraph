from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


EXTRACTOR_SYSTEM = (
    "You extract evidence-grounded scientific paper facts for PaperGraph. "
    "Return only valid JSON. Every evidence_span must be copied exactly from the input text."
)

JUDGE_SYSTEM = (
    "You are a strict PaperGraph labeling judge. Review whether a proposed candidate is valid "
    "for the given paper text and return only valid JSON."
)

SCHEMA_KEYS = ("claims", "methods", "experiments", "limitations", "concepts", "relations")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build Gemma chat SFT data from PaperGraph candidates.")
    parser.add_argument(
        "--autolabeled",
        default="gold/candidates/papergraph-v1-candidates-1000-autolabeled.jsonl",
    )
    parser.add_argument(
        "--strict",
        default="gold/candidates/papergraph-v1-candidates-1000-edit-strict.jsonl",
    )
    parser.add_argument("--out-dir", default="train")
    parser.add_argument("--eval-ratio", type=float, default=0.1)
    parser.add_argument("--seed", type=int, default=17)
    return parser.parse_args()


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON in {path}:{line_number}: {exc}") from exc
            if not isinstance(record, dict):
                raise ValueError(f"Expected JSON object in {path}:{line_number}")
            records.append(record)
    return records


def effective_label(record: dict[str, Any]) -> dict[str, Any]:
    strict = record.get("strict_auto_label")
    if isinstance(strict, dict) and strict.get("status"):
        return strict
    auto = record.get("auto_label")
    if isinstance(auto, dict):
        return auto
    return {"status": "reject", "reason_codes": ["missing_auto_label"], "confidence": 0.0}


def corrected_or_original(record: dict[str, Any], field: str) -> str:
    label = effective_label(record)
    corrected_key = f"corrected_{field}"
    corrected = label.get(corrected_key)
    if corrected:
        return normalize(corrected)
    return normalize(record.get(field))


def normalize(value: Any) -> str:
    return " ".join(str(value or "").split())


def stable_split_key(paper_id: str, seed: int) -> int:
    digest = hashlib.sha256(f"{seed}:{paper_id}".encode("utf-8")).hexdigest()
    return int(digest[:8], 16) % 10_000


def split_name(record: dict[str, Any], eval_ratio: float, seed: int) -> str:
    threshold = int(eval_ratio * 10_000)
    return "eval" if stable_split_key(normalize(record.get("paper_id")), seed) < threshold else "train"


def empty_graph() -> dict[str, list[dict[str, Any]]]:
    return {key: [] for key in SCHEMA_KEYS}


def graph_item(record: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    bucket = corrected_or_original(record, "label_bucket") or normalize(record.get("label_bucket"))
    label_text = corrected_or_original(record, "label_text")
    evidence_span = corrected_or_original(record, "evidence_span")
    base = {
        "id": normalize(record.get("label_id")) or normalize(record.get("candidate_id")),
        "evidence_span": evidence_span,
        "section": normalize(record.get("section")),
    }
    if bucket == "claims":
        return bucket, {**base, "text": label_text}
    if bucket == "methods":
        return bucket, {**base, "name": label_text}
    if bucket == "experiments":
        return bucket, {**base, "summary": label_text}
    if bucket == "limitations":
        return bucket, {**base, "text": label_text}
    if bucket == "concepts":
        return bucket, {**base, "name": label_text}
    if bucket == "relations":
        return bucket, {
            **base,
            "type": normalize(record.get("relation_type")) or "related-to",
            "source_id": normalize(record.get("source_id")),
            "target_id": normalize(record.get("target_id")),
            "source_text": label_text,
        }
    return bucket, {**base, "text": label_text}


def build_extractor_examples(records: list[dict[str, Any]], eval_ratio: float, seed: int) -> dict[str, list[dict[str, Any]]]:
    accepted_by_chunk: dict[str, list[dict[str, Any]]] = defaultdict(list)
    first_by_chunk: dict[str, dict[str, Any]] = {}
    for record in records:
        if effective_label(record).get("status") != "accept":
            continue
        chunk_id = normalize(record.get("chunk_id")) or normalize(record.get("candidate_id"))
        accepted_by_chunk[chunk_id].append(record)
        first_by_chunk.setdefault(chunk_id, record)

    examples = {"train": [], "eval": []}
    for chunk_id, chunk_records in sorted(accepted_by_chunk.items()):
        first = first_by_chunk[chunk_id]
        graph = empty_graph()
        for record in chunk_records:
            bucket, item = graph_item(record)
            if bucket in graph:
                graph[bucket].append(item)
        user = {
            "paper_id": normalize(first.get("paper_id")),
            "title": normalize(first.get("title")),
            "section": normalize(first.get("section")),
            "chunk_text": normalize(first.get("chunk_text")),
        }
        assistant = json.dumps(graph, ensure_ascii=False, sort_keys=True)
        example = {
            "task": "extractor",
            "source": "papergraph-v1",
            "paper_id": user["paper_id"],
            "chunk_id": chunk_id,
            "messages": [
                {"role": "system", "content": EXTRACTOR_SYSTEM},
                {"role": "user", "content": json.dumps(user, ensure_ascii=False, sort_keys=True)},
                {"role": "assistant", "content": assistant},
            ],
        }
        examples[split_name(first, eval_ratio, seed)].append(example)
    return examples


def judge_candidate(record: dict[str, Any]) -> dict[str, str]:
    return {
        "label_bucket": normalize(record.get("label_bucket")),
        "label_text": normalize(record.get("label_text")),
        "evidence_span": normalize(record.get("evidence_span")),
        "relation_type": normalize(record.get("relation_type")),
        "source_id": normalize(record.get("source_id")),
        "target_id": normalize(record.get("target_id")),
    }


def build_judge_examples(records: list[dict[str, Any]], eval_ratio: float, seed: int) -> dict[str, list[dict[str, Any]]]:
    examples = {"train": [], "eval": []}
    for record in records:
        label = effective_label(record)
        status = normalize(label.get("status"))
        reason_codes = label.get("reason_codes") if isinstance(label.get("reason_codes"), list) else []
        corrected = {
            "label_bucket": normalize(label.get("corrected_label_bucket")),
            "label_text": normalize(label.get("corrected_label_text")),
            "evidence_span": normalize(label.get("corrected_evidence_span")),
        }
        output = {
            "verdict": status,
            "reason_codes": reason_codes,
            "corrected_candidate": corrected if status == "edit" else None,
        }
        user = {
            "chunk_text": normalize(record.get("chunk_text")),
            "candidate": judge_candidate(record),
        }
        example = {
            "task": "judge",
            "source": "papergraph-v1",
            "paper_id": normalize(record.get("paper_id")),
            "candidate_id": normalize(record.get("candidate_id")),
            "messages": [
                {"role": "system", "content": JUDGE_SYSTEM},
                {"role": "user", "content": json.dumps(user, ensure_ascii=False, sort_keys=True)},
                {"role": "assistant", "content": json.dumps(output, ensure_ascii=False, sort_keys=True)},
            ],
        }
        examples[split_name(record, eval_ratio, seed)].append(example)
    return examples


def write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


def count_statuses(records: list[dict[str, Any]]) -> Counter[str]:
    return Counter(normalize(effective_label(record).get("status")) for record in records)


def main() -> None:
    args = parse_args()
    autolabeled = read_jsonl(Path(args.autolabeled))
    strict_by_id = {normalize(record.get("candidate_id")): record for record in read_jsonl(Path(args.strict))}
    records = []
    for record in autolabeled:
        candidate_id = normalize(record.get("candidate_id"))
        if candidate_id in strict_by_id:
            merged = dict(record)
            merged["strict_auto_label"] = strict_by_id[candidate_id]["strict_auto_label"]
            records.append(merged)
        else:
            records.append(record)

    extractor = build_extractor_examples(records, args.eval_ratio, args.seed)
    judge = build_judge_examples(records, args.eval_ratio, args.seed)
    out_dir = Path(args.out_dir)
    for split, examples in extractor.items():
        write_jsonl(out_dir / f"extractor_sft_{split}.jsonl", examples)
    for split, examples in judge.items():
        write_jsonl(out_dir / f"judge_sft_{split}.jsonl", examples)

    stats = {
        "input_records": len(records),
        "effective_status_counts": dict(count_statuses(records)),
        "extractor": {split: len(items) for split, items in extractor.items()},
        "judge": {split: len(items) for split, items in judge.items()},
    }
    (out_dir / "sft_stats.json").write_text(
        json.dumps(stats, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(stats, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
