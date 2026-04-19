import csv
import importlib.util
import json
import shutil
import sys
import uuid
from pathlib import Path


def load_labeler():
    script_path = Path("scripts/label_gold_candidates.py")
    spec = importlib.util.spec_from_file_location("label_gold_candidates", script_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def candidate(**overrides):
    base = {
        "candidate_id": "cand-1",
        "source_dataset": "scifact",
        "paper_id": "paper-1",
        "section": "Abstract",
        "chunk_text": "We found that astrocyte calcium elevation correlates with focal seizure-like discharge.",
        "label_bucket": "relations",
        "label_text": "Glial calcium waves influence seizures.",
        "evidence_span": "astrocyte calcium elevation correlates with focal seizure-like discharge",
        "relation_type": "supports",
        "source_id": "claim-1",
        "target_id": "evidence-1",
        "source_label": {"type": "supports"},
    }
    base.update(overrides)
    return base


def test_decide_candidate_accepts_claim_relation_with_evidence() -> None:
    labeler = load_labeler()

    decision = labeler.decide_candidate(candidate())

    assert decision.status == "accept"
    assert "claim_relation_with_evidence" in decision.reason_codes


def test_decide_candidate_rejects_weak_atomic_non_relation_label() -> None:
    labeler = load_labeler()

    decision = labeler.decide_candidate(
        candidate(
            source_dataset="qasper",
            label_bucket="claims",
            label_text="no",
            relation_type="",
            source_id="",
            target_id="",
            source_label={},
        )
    )

    assert decision.status == "reject"
    assert "weak_atomic_label" in decision.reason_codes


def test_decide_candidate_marks_scirex_raw_relation_for_edit() -> None:
    labeler = load_labeler()

    decision = labeler.decide_candidate(
        candidate(
            source_dataset="scirex",
            label_bucket="relations",
            label_text=json.dumps(
                {
                    "Material": "SUN-RGBD",
                    "Method": "Frustum_PointNets",
                    "Metric": "MAP",
                    "Task": "3D_Object_Detection",
                    "score": "54.0%",
                }
            ),
            relation_type="document_level_relation",
            source_label={"raw_relation": {"Method": "Frustum_PointNets", "Task": "3D_Object_Detection"}},
        )
    )

    assert decision.status == "edit"
    assert "raw_document_relation_needs_endpoint_mapping" in decision.reason_codes


def test_decide_candidate_strict_edit_pass_accepts_typed_relation_with_exact_evidence() -> None:
    labeler = load_labeler()

    decision = labeler.decide_candidate_strict_edit_pass(
        candidate(
            source_dataset="scier",
            relation_type="Benchmark-For",
            source_label={"type": "Benchmark-For"},
        )
    )

    assert decision.status == "accept"
    assert decision.version == labeler.STRICT_EDIT_LABEL_VERSION
    assert "strict_typed_relation_exact_endpoints_evidence" in decision.reason_codes


def test_decide_candidate_strict_edit_pass_rejects_ambiguous_qasper_claim() -> None:
    labeler = load_labeler()

    decision = labeler.decide_candidate_strict_edit_pass(
        candidate(
            source_dataset="qasper",
            label_bucket="claims",
            label_text="DOSPERT, BSSS and VIAS",
            evidence_span="",
            relation_type="",
            source_id="",
            target_id="",
            source_label={},
        )
    )

    assert decision.status == "reject"
    assert "strict_claim_not_sentence_or_exact_evidence" in decision.reason_codes


def test_label_candidate_files_writes_csv_and_jsonl() -> None:
    labeler = load_labeler()
    work_dir = Path(".papergraph-test-output") / f"label-gold-{uuid.uuid4().hex}"
    shutil.rmtree(work_dir, ignore_errors=True)

    try:
        candidates_path = work_dir / "candidates.jsonl"
        candidates_path.parent.mkdir(parents=True, exist_ok=True)
        rows = [
            candidate(candidate_id="cand-accept"),
            candidate(
                candidate_id="cand-reject",
                source_dataset="qasper",
                label_bucket="claims",
                label_text="12",
                relation_type="",
                source_id="",
                target_id="",
                source_label={},
            ),
        ]
        candidates_path.write_text(
            "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n",
            encoding="utf-8",
        )

        out_csv = work_dir / "review.csv"
        out_jsonl = work_dir / "labeled.jsonl"
        counts = labeler.label_candidate_files(candidates_path, out_csv, out_jsonl)

        assert counts == {"accept": 1, "edit": 0, "reject": 1}
        with out_csv.open(encoding="utf-8", newline="") as handle:
            review_rows = list(csv.DictReader(handle))
        assert [row["review_status"] for row in review_rows] == ["accept", "reject"]
        assert all(row["notes"].startswith(labeler.AUTO_LABEL_VERSION) for row in review_rows)

        labeled_rows = [json.loads(line) for line in out_jsonl.read_text(encoding="utf-8").splitlines()]
        assert [row["auto_label"]["status"] for row in labeled_rows] == ["accept", "reject"]
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)


def test_label_candidate_files_can_filter_previous_edits_for_strict_pass() -> None:
    labeler = load_labeler()
    work_dir = Path(".papergraph-test-output") / f"label-gold-strict-{uuid.uuid4().hex}"
    shutil.rmtree(work_dir, ignore_errors=True)

    try:
        candidates_path = work_dir / "candidates.jsonl"
        candidates_path.parent.mkdir(parents=True, exist_ok=True)
        rows = [
            {
                **candidate(candidate_id="cand-edit"),
                "auto_label": {"status": "edit"},
            },
            {
                **candidate(candidate_id="cand-accept"),
                "auto_label": {"status": "accept"},
            },
        ]
        candidates_path.write_text(
            "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n",
            encoding="utf-8",
        )

        out_csv = work_dir / "review.csv"
        out_jsonl = work_dir / "labeled.jsonl"
        counts = labeler.label_candidate_files(
            candidates_path,
            out_csv,
            out_jsonl,
            harness="strict-edit-pass",
            only_auto_status="edit",
        )

        assert counts == {"accept": 1, "edit": 0, "reject": 0}
        with out_csv.open(encoding="utf-8", newline="") as handle:
            review_rows = list(csv.DictReader(handle))
        assert len(review_rows) == 1
        assert review_rows[0]["candidate_id"] == "cand-edit"

        labeled_rows = [json.loads(line) for line in out_jsonl.read_text(encoding="utf-8").splitlines()]
        assert list(labeled_rows[0]["strict_auto_label"]) == [
            "confidence",
            "corrected_evidence_span",
            "corrected_label_bucket",
            "corrected_label_text",
            "reason_codes",
            "status",
            "version",
        ]
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)
