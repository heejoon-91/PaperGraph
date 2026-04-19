from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any


TARGETS: dict[str, dict[str, int]] = {
    "qasper": {
        "claims": 20,
        "methods": 25,
        "experiments": 25,
        "limitations": 10,
    },
    "scifact": {
        "supports": 35,
        "contradicts": 35,
    },
    "scier": {
        "methods": 40,
        "concepts": 30,
        "relations": 30,
    },
    "scirex": {
        "methods": 20,
        "concepts": 20,
        "relations": 10,
    },
}

REVIEW_COLUMNS = [
    "candidate_id",
    "source_dataset",
    "paper_id",
    "section",
    "chunk_text",
    "label_bucket",
    "label_text",
    "evidence_span",
    "relation_type",
    "source_id",
    "target_id",
    "review_status",
    "corrected_label_bucket",
    "corrected_label_text",
    "corrected_evidence_span",
    "notes",
]

LABEL_BUCKETS = ("claims", "methods", "experiments", "limitations", "concepts", "relations")

MAX_LABELS_PER_ROW_BUCKET: dict[str, dict[str, int]] = {
    "scirex": {
        "methods": 3,
        "concepts": 3,
        "relations": 5,
    }
}


@dataclass(frozen=True)
class Candidate:
    candidate_id: str
    source_dataset: str
    paper_id: str
    title: str
    section: str
    chunk_id: str
    chunk_text: str
    label_bucket: str
    target_bucket: str
    label_id: str
    label_text: str
    evidence_span: str
    relation_type: str
    source_id: str
    target_id: str
    seed_id: str
    question: str
    source_label: dict[str, Any]
    hard_cases: tuple[str, ...]

    def json_record(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "source_dataset": self.source_dataset,
            "paper_id": self.paper_id,
            "title": self.title,
            "section": self.section,
            "chunk_id": self.chunk_id,
            "chunk_text": self.chunk_text,
            "label_bucket": self.label_bucket,
            "target_bucket": self.target_bucket,
            "label_id": self.label_id,
            "label_text": self.label_text,
            "evidence_span": self.evidence_span,
            "relation_type": self.relation_type,
            "source_id": self.source_id,
            "target_id": self.target_id,
            "seed_id": self.seed_id,
            "question": self.question,
            "hard_cases": list(self.hard_cases),
            "source_label": self.source_label,
        }

    def review_row(self) -> dict[str, str]:
        return {
            "candidate_id": self.candidate_id,
            "source_dataset": self.source_dataset,
            "paper_id": self.paper_id,
            "section": self.section,
            "chunk_text": self.chunk_text,
            "label_bucket": self.label_bucket,
            "label_text": self.label_text,
            "evidence_span": self.evidence_span,
            "relation_type": self.relation_type,
            "source_id": self.source_id,
            "target_id": self.target_id,
            "review_status": "",
            "corrected_label_bucket": "",
            "corrected_label_text": "",
            "corrected_evidence_span": "",
            "notes": "",
        }


@dataclass(frozen=True)
class SamplingSummary:
    selected_count: int
    selected_by_dataset_bucket: dict[tuple[str, str], int]
    deficits: dict[tuple[str, str], int]
    backfilled_by_dataset: dict[str, int]


def stable_id(*parts: object) -> str:
    payload = "\x1f".join(str(part or "") for part in parts)
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()[:16]


def normalize_text(value: Any) -> str:
    return " ".join(str(value or "").split())


def label_text(label: dict[str, Any], bucket: str) -> str:
    if bucket == "relations" and isinstance(label.get("raw_relation"), dict):
        return json.dumps(label["raw_relation"], ensure_ascii=False, sort_keys=True)
    for key in ("text", "name", "claim", "type"):
        text = normalize_text(label.get(key))
        if text:
            return text
    return ""


def relation_claim_text(row: dict[str, Any], relation: dict[str, Any]) -> str:
    source_id = normalize_text(relation.get("source_id"))
    labels = row.get("labels") or {}
    for claim in labels.get("claims") or []:
        if isinstance(claim, dict) and normalize_text(claim.get("id")) == source_id:
            return label_text(claim, "claims")
    claims = [claim for claim in labels.get("claims") or [] if isinstance(claim, dict)]
    if claims:
        return label_text(claims[0], "claims")
    return label_text(relation, "relations")


def hard_cases_for(row: dict[str, Any], label: dict[str, Any], bucket: str) -> tuple[str, ...]:
    cases: list[str] = []
    chunk_text = normalize_text(row.get("chunk_text"))
    evidence_span = normalize_text(label.get("evidence_span"))
    labels = row.get("labels") or {}

    if len(chunk_text) >= 1600:
        cases.append("long_chunk")
    if evidence_span and evidence_span not in chunk_text:
        cases.append("evidence_span_mismatch")
    if bucket == "relations":
        if label.get("source_id") or label.get("target_id"):
            cases.append("relation_endpoints")
        if normalize_text(label.get("type")).lower() == "contradicts":
            cases.append("contradicts_relation")
    if labels.get("methods") and labels.get("concepts"):
        cases.append("method_and_concept_same_chunk")
    if not label_text(label, bucket):
        cases.append("empty_or_ambiguous_label")

    return tuple(dict.fromkeys(cases))


def iter_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON in {path}:{line_number}: {exc}") from exc
            if not isinstance(row, dict):
                raise ValueError(f"Expected JSON object in {path}:{line_number}")
            rows.append(row)
    return rows


def representative_labels(labels: list[Any], limit: int | None) -> list[Any]:
    if limit is None or limit <= 0 or len(labels) <= limit:
        return labels
    if limit == 1:
        return [labels[0]]

    last_index = len(labels) - 1
    indexes = sorted({round(index * last_index / (limit - 1)) for index in range(limit)})
    return [labels[index] for index in indexes]


def build_candidate(
    row: dict[str, Any],
    bucket: str,
    target_bucket: str,
    label: dict[str, Any],
    text: str | None = None,
) -> Candidate:
    source_dataset = normalize_text(row.get("source_dataset"))
    paper_id = normalize_text(row.get("paper_id"))
    chunk_id = normalize_text(row.get("chunk_id"))
    seed_id = normalize_text(row.get("id"))
    label_id = normalize_text(label.get("id"))
    relation_type = normalize_text(label.get("type")) if bucket == "relations" else ""
    source_id = normalize_text(label.get("source_id")) if bucket == "relations" else ""
    target_id = normalize_text(label.get("target_id")) if bucket == "relations" else ""
    resolved_text = normalize_text(text) if text is not None else label_text(label, bucket)
    evidence_span = normalize_text(label.get("evidence_span"))
    candidate_id = "cand-" + stable_id(
        source_dataset,
        paper_id,
        chunk_id,
        seed_id,
        bucket,
        target_bucket,
        label_id,
        resolved_text,
        relation_type,
        source_id,
        target_id,
        evidence_span,
    )

    return Candidate(
        candidate_id=candidate_id,
        source_dataset=source_dataset,
        paper_id=paper_id,
        title=normalize_text(row.get("title")),
        section=normalize_text(row.get("section")),
        chunk_id=chunk_id,
        chunk_text=normalize_text(row.get("chunk_text")),
        label_bucket=bucket,
        target_bucket=target_bucket,
        label_id=label_id,
        label_text=resolved_text,
        evidence_span=evidence_span,
        relation_type=relation_type,
        source_id=source_id,
        target_id=target_id,
        seed_id=seed_id,
        question=normalize_text(row.get("question")),
        source_label=dict(label),
        hard_cases=hard_cases_for(row, label, bucket),
    )


def iter_candidates(row: dict[str, Any]) -> list[Candidate]:
    source_dataset = normalize_text(row.get("source_dataset"))
    labels = row.get("labels") or {}
    candidates: list[Candidate] = []

    if source_dataset == "scifact":
        for relation in labels.get("relations") or []:
            if not isinstance(relation, dict):
                continue
            relation_type = normalize_text(relation.get("type")).lower()
            if relation_type not in {"supports", "contradicts"}:
                continue
            candidates.append(
                build_candidate(
                    row,
                    bucket="relations",
                    target_bucket=relation_type,
                    label=relation,
                    text=relation_claim_text(row, relation),
                )
            )
        return candidates

    row_limits = MAX_LABELS_PER_ROW_BUCKET.get(source_dataset, {})
    for bucket in LABEL_BUCKETS:
        bucket_labels = representative_labels(labels.get(bucket) or [], row_limits.get(bucket))
        for label in bucket_labels:
            if not isinstance(label, dict):
                continue
            candidates.append(build_candidate(row, bucket=bucket, target_bucket=bucket, label=label))
    return candidates


def load_candidates(seed_root: Path) -> list[Candidate]:
    candidates: list[Candidate] = []
    for seed_file in sorted(seed_root.glob("*/papergraph_seed.jsonl")):
        for row in iter_jsonl(seed_file):
            candidates.extend(iter_candidates(row))
    return dedupe_candidates(candidates)


def dedupe_candidates(candidates: list[Candidate]) -> list[Candidate]:
    seen: set[tuple[str, ...]] = set()
    deduped: list[Candidate] = []
    for candidate in candidates:
        key = (
            candidate.source_dataset,
            candidate.paper_id,
            candidate.chunk_id,
            candidate.label_bucket,
            candidate.target_bucket,
            candidate.label_id,
            candidate.label_text,
            candidate.evidence_span,
            candidate.relation_type,
            candidate.source_id,
            candidate.target_id,
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(candidate)
    return deduped


def ordered_pool(candidates: list[Candidate], rng: random.Random) -> list[Candidate]:
    decorated = [(rng.random(), candidate) for candidate in candidates]
    decorated.sort(
        key=lambda item: (
            -len(item[1].hard_cases),
            item[0],
            item[1].paper_id,
            item[1].candidate_id,
        )
    )
    return [candidate for _, candidate in decorated]


def select_diverse(
    pool: list[Candidate],
    count: int,
    selected_ids: set[str],
    rng: random.Random,
) -> list[Candidate]:
    ordered = [candidate for candidate in ordered_pool(pool, rng) if candidate.candidate_id not in selected_ids]
    selected: list[Candidate] = []
    used_papers: set[str] = set()

    for candidate in ordered:
        if len(selected) >= count:
            break
        if candidate.paper_id in used_papers:
            continue
        selected.append(candidate)
        used_papers.add(candidate.paper_id)

    if len(selected) < count:
        already = {candidate.candidate_id for candidate in selected}
        for candidate in ordered:
            if len(selected) >= count:
                break
            if candidate.candidate_id in already:
                continue
            selected.append(candidate)
            already.add(candidate.candidate_id)

    return selected


def sample_candidates(
    candidates: list[Candidate],
    targets: dict[str, dict[str, int]],
    seed: int = 13,
    backfill_deficits: bool = True,
) -> tuple[list[Candidate], SamplingSummary]:
    rng = random.Random(seed)
    by_dataset_bucket: dict[tuple[str, str], list[Candidate]] = defaultdict(list)
    by_dataset: dict[str, list[Candidate]] = defaultdict(list)
    for candidate in candidates:
        by_dataset_bucket[(candidate.source_dataset, candidate.target_bucket)].append(candidate)
        by_dataset[candidate.source_dataset].append(candidate)

    selected: list[Candidate] = []
    selected_ids: set[str] = set()
    deficits: dict[tuple[str, str], int] = {}

    for dataset, bucket_targets in targets.items():
        for bucket, count in bucket_targets.items():
            pool = by_dataset_bucket.get((dataset, bucket), [])
            picked = select_diverse(pool, count, selected_ids, rng)
            selected.extend(picked)
            selected_ids.update(candidate.candidate_id for candidate in picked)
            if len(picked) < count:
                deficits[(dataset, bucket)] = count - len(picked)

    backfilled_by_dataset: dict[str, int] = {}
    if backfill_deficits:
        for dataset, bucket_targets in targets.items():
            expected = sum(bucket_targets.values())
            current = sum(1 for candidate in selected if candidate.source_dataset == dataset)
            missing = expected - current
            if missing <= 0:
                continue
            picked = select_diverse(by_dataset.get(dataset, []), missing, selected_ids, rng)
            selected.extend(picked)
            selected_ids.update(candidate.candidate_id for candidate in picked)
            if picked:
                backfilled_by_dataset[dataset] = len(picked)

    expected_total = sum(sum(bucket_targets.values()) for bucket_targets in targets.values())
    if backfill_deficits and len(selected) < expected_total:
        missing = expected_total - len(selected)
        picked = select_diverse(candidates, missing, selected_ids, rng)
        selected.extend(picked)
        selected_ids.update(candidate.candidate_id for candidate in picked)
        if picked:
            backfilled_by_dataset["__global__"] = len(picked)

    selected_by_dataset_bucket: dict[tuple[str, str], int] = defaultdict(int)
    for candidate in selected:
        selected_by_dataset_bucket[(candidate.source_dataset, candidate.label_bucket)] += 1

    summary = SamplingSummary(
        selected_count=len(selected),
        selected_by_dataset_bucket=dict(selected_by_dataset_bucket),
        deficits=deficits,
        backfilled_by_dataset=backfilled_by_dataset,
    )
    return selected, summary


def write_jsonl(path: Path, candidates: list[Candidate]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for candidate in candidates:
            handle.write(json.dumps(candidate.json_record(), ensure_ascii=False, sort_keys=True) + "\n")


def write_review_csv(path: Path, candidates: list[Candidate]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=REVIEW_COLUMNS)
        writer.writeheader()
        for candidate in candidates:
            writer.writerow(candidate.review_row())


def parse_target_override(value: str) -> tuple[str, str, int]:
    if "=" not in value or "." not in value.split("=", 1)[0]:
        raise argparse.ArgumentTypeError("Expected DATASET.BUCKET=COUNT")
    key, raw_count = value.split("=", 1)
    dataset, bucket = key.split(".", 1)
    try:
        count = int(raw_count)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("COUNT must be an integer") from exc
    if count < 0:
        raise argparse.ArgumentTypeError("COUNT must be non-negative")
    return dataset, bucket, count


def resolve_targets(overrides: list[tuple[str, str, int]] | None) -> dict[str, dict[str, int]]:
    targets = {dataset: dict(bucket_targets) for dataset, bucket_targets in TARGETS.items()}
    for dataset, bucket, count in overrides or []:
        targets.setdefault(dataset, {})[bucket] = count
    return targets


def sample_candidate_files(
    seed_root: Path,
    out: Path,
    review_csv: Path,
    targets: dict[str, dict[str, int]] | None = None,
    seed: int = 13,
    backfill_deficits: bool = True,
    dry_run: bool = False,
) -> SamplingSummary:
    resolved_targets = targets or TARGETS
    candidates = load_candidates(seed_root)
    selected, summary = sample_candidates(
        candidates,
        resolved_targets,
        seed=seed,
        backfill_deficits=backfill_deficits,
    )
    if not dry_run:
        write_jsonl(out, selected)
        write_review_csv(review_csv, selected)
    return summary


def format_summary(summary: SamplingSummary) -> str:
    lines = [f"selected: {summary.selected_count}"]
    lines.append("selected_by_dataset_bucket:")
    for (dataset, bucket), count in sorted(summary.selected_by_dataset_bucket.items()):
        lines.append(f"  {dataset}.{bucket}: {count}")
    if summary.deficits:
        lines.append("target_deficits:")
        for (dataset, bucket), count in sorted(summary.deficits.items()):
            lines.append(f"  {dataset}.{bucket}: {count}")
    if summary.backfilled_by_dataset:
        lines.append("backfilled_by_dataset:")
        for dataset, count in sorted(summary.backfilled_by_dataset.items()):
            lines.append(f"  {dataset}: {count}")
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Sample PaperGraph gold review candidates from seed JSONL files.")
    parser.add_argument("--seed-root", type=Path, default=Path("data/processed"))
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--review-csv", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=13)
    parser.add_argument(
        "--target",
        action="append",
        type=parse_target_override,
        help="Override or add a target as DATASET.BUCKET=COUNT. May be repeated.",
    )
    parser.add_argument("--no-backfill", action="store_true", help="Do not backfill unavailable target buckets.")
    parser.add_argument("--dry-run", action="store_true", help="Print the sampling summary without writing files.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    summary = sample_candidate_files(
        seed_root=args.seed_root,
        out=args.out,
        review_csv=args.review_csv,
        targets=resolve_targets(args.target),
        seed=args.seed,
        backfill_deficits=not args.no_backfill,
        dry_run=args.dry_run,
    )
    print(format_summary(summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
