from __future__ import annotations

import argparse
import csv
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


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

AUTO_LABEL_VERSION = "papergraph-auto-label-v1"
STRICT_EDIT_LABEL_VERSION = "papergraph-auto-label-v1-strict-edit-pass"
VALID_STATUSES = {"accept", "edit", "reject"}
VALID_BUCKETS = {"claims", "methods", "experiments", "limitations", "concepts", "relations"}
WEAK_ATOMIC_LABELS = {
    "",
    "n/a",
    "na",
    "none",
    "null",
    "yes",
    "no",
    "true",
    "false",
    "unanswerable",
    "unknown",
}
GENERIC_METHOD_TERMS = {
    "cnn",
    "rnn",
    "lstm",
    "mlp",
    "bert",
    "dropout",
    "attention",
    "transformer",
    "resnet",
    "vgg",
}
RELATION_TYPES_REQUIRING_ENDPOINTS = {
    "supports",
    "contradicts",
    "used-for",
    "part-of",
    "feature-of",
    "evaluated-with",
    "trained-with",
    "compare",
    "synonym-of",
}


@dataclass(frozen=True)
class HarnessDecision:
    status: str
    confidence: float
    reason_codes: tuple[str, ...]
    corrected_label_bucket: str = ""
    corrected_label_text: str = ""
    corrected_evidence_span: str = ""
    version: str = AUTO_LABEL_VERSION

    def notes(self) -> str:
        reasons = ",".join(self.reason_codes)
        return f"{self.version}; confidence={self.confidence:.2f}; reasons={reasons}"


def normalize_text(value: Any) -> str:
    return " ".join(str(value or "").split())


def normalize_key(value: Any) -> str:
    return normalize_text(value).lower()


def is_numeric_only(value: str) -> bool:
    return bool(re.fullmatch(r"[\d.,%+\- ]+", normalize_text(value)))


def is_weak_atomic_label(value: str) -> bool:
    text = normalize_key(value)
    return text in WEAK_ATOMIC_LABELS or is_numeric_only(text)


def evidence_in_chunk(evidence_span: str, chunk_text: str) -> bool:
    evidence = normalize_key(evidence_span)
    chunk = normalize_key(chunk_text)
    return bool(evidence and evidence in chunk)


def parse_raw_relation(label_text: str) -> dict[str, Any] | None:
    text = normalize_text(label_text)
    if not text.startswith("{"):
        return None
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def relation_type(candidate: dict[str, Any]) -> str:
    return normalize_key(candidate.get("relation_type") or candidate.get("source_label", {}).get("type"))


def source_label(candidate: dict[str, Any]) -> dict[str, Any]:
    label = candidate.get("source_label")
    return label if isinstance(label, dict) else {}


def candidate_to_review_row(candidate: dict[str, Any], decision: HarnessDecision) -> dict[str, str]:
    return {
        "candidate_id": normalize_text(candidate.get("candidate_id")),
        "source_dataset": normalize_text(candidate.get("source_dataset")),
        "paper_id": normalize_text(candidate.get("paper_id")),
        "section": normalize_text(candidate.get("section")),
        "chunk_text": normalize_text(candidate.get("chunk_text")),
        "label_bucket": normalize_text(candidate.get("label_bucket")),
        "label_text": normalize_text(candidate.get("label_text")),
        "evidence_span": normalize_text(candidate.get("evidence_span")),
        "relation_type": normalize_text(candidate.get("relation_type")),
        "source_id": normalize_text(candidate.get("source_id")),
        "target_id": normalize_text(candidate.get("target_id")),
        "review_status": decision.status,
        "corrected_label_bucket": decision.corrected_label_bucket,
        "corrected_label_text": decision.corrected_label_text,
        "corrected_evidence_span": decision.corrected_evidence_span,
        "notes": decision.notes(),
    }


def with_reason(existing: list[str], reason: str) -> None:
    if reason not in existing:
        existing.append(reason)


def has_metric_signal(value: str) -> bool:
    text = normalize_key(value)
    return any(token in text for token in ("f1", "accuracy", "score", "dataset", "%", "ap", "map"))


def is_list_like_label(value: str) -> bool:
    text = normalize_text(value)
    return "|" in text or text.count(",") >= 3 or text.count(";") >= 2


def has_claim_verb(value: str) -> bool:
    text = f" {normalize_key(value)} "
    return any(
        token in text
        for token in (
            " is ",
            " are ",
            " was ",
            " were ",
            " has ",
            " have ",
            " had ",
            " shows ",
            " show ",
            " improves ",
            " achieves ",
            " outperforms ",
            " reduces ",
            " increases ",
            " supports ",
            " contradicts ",
            " proposes ",
            " uses ",
            " requires ",
            " enables ",
        )
    )


def previous_auto_status(candidate: dict[str, Any]) -> str:
    auto_label = candidate.get("auto_label")
    if isinstance(auto_label, dict):
        return normalize_key(auto_label.get("status"))
    return ""


def decide_candidate(candidate: dict[str, Any]) -> HarnessDecision:
    dataset = normalize_key(candidate.get("source_dataset"))
    bucket = normalize_key(candidate.get("label_bucket"))
    label_text = normalize_text(candidate.get("label_text"))
    evidence_span = normalize_text(candidate.get("evidence_span"))
    chunk_text = normalize_text(candidate.get("chunk_text"))
    rel_type = relation_type(candidate)
    src_id = normalize_text(candidate.get("source_id"))
    tgt_id = normalize_text(candidate.get("target_id"))
    label = source_label(candidate)

    accept_reasons: list[str] = []
    edit_reasons: list[str] = []
    reject_reasons: list[str] = []

    if bucket not in VALID_BUCKETS:
        with_reason(reject_reasons, "invalid_bucket")

    if not chunk_text:
        with_reason(reject_reasons, "missing_chunk_text")

    if is_weak_atomic_label(label_text) and bucket != "relations":
        with_reason(reject_reasons, "weak_atomic_label")

    if bucket != "relations" and not evidence_span:
        with_reason(edit_reasons, "missing_evidence_span")

    if evidence_span and not evidence_in_chunk(evidence_span, chunk_text):
        with_reason(edit_reasons, "evidence_span_not_exact_substring")

    if bucket == "claims" and len(label_text.split()) < 4:
        with_reason(reject_reasons, "claim_too_short")

    if bucket in {"methods", "concepts"}:
        if len(label_text) < 3:
            with_reason(reject_reasons, "entity_too_short")
        elif normalize_key(label_text) in GENERIC_METHOD_TERMS:
            with_reason(edit_reasons, "generic_entity_needs_policy")
        elif evidence_span and evidence_in_chunk(evidence_span, chunk_text):
            with_reason(accept_reasons, "entity_with_exact_evidence")

    if bucket == "experiments":
        if is_numeric_only(label_text):
            with_reason(edit_reasons, "metric_without_context")
        elif has_metric_signal(label_text):
            with_reason(accept_reasons, "experiment_metric_result")

    if bucket == "limitations":
        if not any(token in normalize_key(label_text + " " + evidence_span) for token in ("limit", "weak", "fail", "future", "however", "challenge")):
            with_reason(edit_reasons, "limitation_needs_human_confirmation")

    if bucket == "relations":
        if not rel_type:
            with_reason(reject_reasons, "missing_relation_type")

        raw_relation = parse_raw_relation(label_text)
        if dataset == "scirex" and raw_relation:
            if raw_relation.get("Method") and raw_relation.get("Task"):
                with_reason(edit_reasons, "raw_document_relation_needs_endpoint_mapping")
            else:
                with_reason(reject_reasons, "raw_relation_missing_core_fields")
        elif rel_type in {"supports", "contradicts"}:
            if label_text and evidence_span and not is_weak_atomic_label(label_text):
                with_reason(accept_reasons, "claim_relation_with_evidence")
            else:
                with_reason(edit_reasons, "claim_relation_needs_text_or_evidence")
        elif rel_type in RELATION_TYPES_REQUIRING_ENDPOINTS:
            if src_id and tgt_id and evidence_span:
                with_reason(accept_reasons, "typed_relation_with_endpoints")
            else:
                with_reason(edit_reasons, "typed_relation_missing_endpoint_or_evidence")
        elif label.get("raw_relation"):
            with_reason(edit_reasons, "raw_relation_needs_mapping")
        else:
            with_reason(edit_reasons, "relation_needs_human_confirmation")

    if dataset == "qasper" and bucket in {"claims", "methods", "experiments"}:
        if label_text.startswith("FLOAT SELECTED:") or label_text.startswith("Table "):
            with_reason(edit_reasons, "table_or_float_label_needs_cleanup")

    if reject_reasons:
        return HarnessDecision(
            status="reject",
            confidence=0.90 if "weak_atomic_label" in reject_reasons else 0.80,
            reason_codes=tuple(reject_reasons + edit_reasons + accept_reasons),
        )

    if edit_reasons:
        corrected_bucket = bucket if bucket in VALID_BUCKETS else ""
        corrected_text = label_text if not is_weak_atomic_label(label_text) else ""
        corrected_evidence = evidence_span if evidence_span and evidence_in_chunk(evidence_span, chunk_text) else ""
        return HarnessDecision(
            status="edit",
            confidence=0.70,
            reason_codes=tuple(edit_reasons + accept_reasons),
            corrected_label_bucket=corrected_bucket,
            corrected_label_text=corrected_text,
            corrected_evidence_span=corrected_evidence,
        )

    if accept_reasons:
        return HarnessDecision(
            status="accept",
            confidence=0.80,
            reason_codes=tuple(accept_reasons),
        )

    return HarnessDecision(
        status="edit",
        confidence=0.55,
        reason_codes=("needs_human_confirmation",),
        corrected_label_bucket=bucket if bucket in VALID_BUCKETS else "",
        corrected_label_text=label_text,
        corrected_evidence_span=evidence_span if evidence_in_chunk(evidence_span, chunk_text) else "",
    )


def decide_candidate_strict_edit_pass(candidate: dict[str, Any]) -> HarnessDecision:
    dataset = normalize_key(candidate.get("source_dataset"))
    bucket = normalize_key(candidate.get("label_bucket"))
    label_text = normalize_text(candidate.get("label_text"))
    evidence_span = normalize_text(candidate.get("evidence_span"))
    chunk_text = normalize_text(candidate.get("chunk_text"))
    rel_type = relation_type(candidate)
    src_id = normalize_text(candidate.get("source_id"))
    tgt_id = normalize_text(candidate.get("target_id"))
    exact_evidence = evidence_in_chunk(evidence_span, chunk_text)
    raw_relation = parse_raw_relation(label_text)

    def decision(
        status: str,
        confidence: float,
        reasons: tuple[str, ...],
        corrected_bucket: str = "",
        corrected_text: str = "",
        corrected_evidence: str = "",
    ) -> HarnessDecision:
        return HarnessDecision(
            status=status,
            confidence=confidence,
            reason_codes=reasons,
            corrected_label_bucket=corrected_bucket,
            corrected_label_text=corrected_text,
            corrected_evidence_span=corrected_evidence,
            version=STRICT_EDIT_LABEL_VERSION,
        )

    if bucket not in VALID_BUCKETS:
        return decision("reject", 0.95, ("strict_invalid_bucket",))
    if not chunk_text:
        return decision("reject", 0.95, ("strict_missing_chunk_text",))
    if is_weak_atomic_label(label_text) and bucket != "relations":
        return decision("reject", 0.95, ("strict_weak_atomic_label",))

    if bucket == "relations":
        if dataset == "scirex" and raw_relation:
            if raw_relation.get("Method") and raw_relation.get("Task"):
                return decision(
                    "edit",
                    0.85,
                    ("strict_scirex_raw_relation_requires_endpoint_mapping",),
                    "relations",
                    label_text,
                    evidence_span if exact_evidence else "",
                )
            return decision("reject", 0.95, ("strict_raw_relation_missing_core_fields",))

        if not rel_type:
            return decision("reject", 0.95, ("strict_missing_relation_type",))

        if rel_type in {"supports", "contradicts"}:
            if label_text and evidence_span and exact_evidence and not is_weak_atomic_label(label_text):
                return decision("accept", 0.90, ("strict_claim_relation_exact_evidence",))
            return decision("reject", 0.90, ("strict_claim_relation_without_exact_evidence",))

        if src_id and tgt_id and evidence_span and exact_evidence:
            return decision("accept", 0.90, ("strict_typed_relation_exact_endpoints_evidence",))
        return decision("reject", 0.90, ("strict_relation_without_exact_endpoint_evidence",))

    if bucket in {"methods", "concepts"}:
        if len(label_text) < 3:
            return decision("reject", 0.95, ("strict_entity_too_short",))
        if normalize_key(label_text) in GENERIC_METHOD_TERMS:
            if exact_evidence:
                return decision(
                    "edit",
                    0.80,
                    ("strict_generic_entity_requires_schema_policy",),
                    bucket,
                    label_text,
                    evidence_span,
                )
            return decision("reject", 0.90, ("strict_generic_entity_without_exact_evidence",))
        if exact_evidence:
            return decision("accept", 0.90, ("strict_entity_exact_evidence",))
        return decision("reject", 0.90, ("strict_entity_without_exact_evidence",))

    if bucket == "experiments":
        if has_metric_signal(label_text) and exact_evidence and not is_numeric_only(label_text):
            return decision("accept", 0.90, ("strict_experiment_metric_exact_evidence",))
        return decision("reject", 0.90, ("strict_experiment_without_metric_exact_evidence",))

    if bucket == "claims":
        if (
            exact_evidence
            and len(label_text.split()) >= 8
            and has_claim_verb(label_text)
            and not is_list_like_label(label_text)
        ):
            return decision("accept", 0.88, ("strict_sentence_claim_exact_evidence",))
        return decision("reject", 0.88, ("strict_claim_not_sentence_or_exact_evidence",))

    if bucket == "limitations":
        text = normalize_key(label_text + " " + evidence_span)
        if exact_evidence and any(token in text for token in ("limit", "weak", "fail", "future", "however", "challenge")):
            return decision("accept", 0.88, ("strict_limitation_exact_evidence",))
        return decision("reject", 0.88, ("strict_limitation_without_explicit_signal",))

    return decision("reject", 0.85, ("strict_unhandled_candidate",))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
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


def filter_candidates(candidates: list[dict[str, Any]], only_auto_status: str | None) -> list[dict[str, Any]]:
    if not only_auto_status:
        return candidates
    status = normalize_key(only_auto_status)
    return [candidate for candidate in candidates if previous_auto_status(candidate) == status]


def decision_function(harness: str):
    if harness == "standard":
        return decide_candidate
    if harness == "strict-edit-pass":
        return decide_candidate_strict_edit_pass
    raise ValueError(f"Unknown harness: {harness}")


def auto_label_key(harness: str) -> str:
    if harness == "standard":
        return "auto_label"
    if harness == "strict-edit-pass":
        return "strict_auto_label"
    raise ValueError(f"Unknown harness: {harness}")


def write_review_csv(path: Path, candidates: list[dict[str, Any]], harness: str = "standard") -> dict[str, int]:
    path.parent.mkdir(parents=True, exist_ok=True)
    counts = {status: 0 for status in sorted(VALID_STATUSES)}
    decide = decision_function(harness)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=REVIEW_COLUMNS)
        writer.writeheader()
        for candidate in candidates:
            decision = decide(candidate)
            counts[decision.status] += 1
            writer.writerow(candidate_to_review_row(candidate, decision))
    return counts


def write_labeled_jsonl(path: Path, candidates: list[dict[str, Any]], harness: str = "standard") -> dict[str, int]:
    path.parent.mkdir(parents=True, exist_ok=True)
    counts = {status: 0 for status in sorted(VALID_STATUSES)}
    decide = decision_function(harness)
    label_key = auto_label_key(harness)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for candidate in candidates:
            decision = decide(candidate)
            counts[decision.status] += 1
            payload = dict(candidate)
            payload[label_key] = {
                "version": decision.version,
                "status": decision.status,
                "confidence": decision.confidence,
                "reason_codes": list(decision.reason_codes),
                "corrected_label_bucket": decision.corrected_label_bucket,
                "corrected_label_text": decision.corrected_label_text,
                "corrected_evidence_span": decision.corrected_evidence_span,
            }
            handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")
    return counts


def label_candidate_files(
    candidates_path: Path,
    out_csv: Path,
    out_jsonl: Path | None = None,
    harness: str = "standard",
    only_auto_status: str | None = None,
) -> dict[str, int]:
    candidates = filter_candidates(load_jsonl(candidates_path), only_auto_status)
    counts = write_review_csv(out_csv, candidates, harness=harness)
    if out_jsonl is not None:
        jsonl_counts = write_labeled_jsonl(out_jsonl, candidates, harness=harness)
        if jsonl_counts != counts:
            raise RuntimeError(f"CSV/JSONL label count mismatch: {counts} != {jsonl_counts}")
    return counts


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Apply a deterministic review harness to PaperGraph candidates.")
    parser.add_argument("--candidates", type=Path, required=True)
    parser.add_argument("--out-csv", type=Path, required=True)
    parser.add_argument("--out-jsonl", type=Path)
    parser.add_argument("--harness", choices=("standard", "strict-edit-pass"), default="standard")
    parser.add_argument(
        "--only-auto-status",
        choices=tuple(sorted(VALID_STATUSES)),
        help="Only label rows whose existing auto_label.status matches this value.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    counts = label_candidate_files(
        args.candidates,
        args.out_csv,
        args.out_jsonl,
        harness=args.harness,
        only_auto_status=args.only_auto_status,
    )
    print("auto_label_counts:")
    for status, count in sorted(counts.items()):
        print(f"  {status}: {count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
