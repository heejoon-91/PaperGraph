import csv
import importlib.util
import json
import shutil
import sys
import uuid
from pathlib import Path


def load_sampler():
    script_path = Path("scripts/sample_gold_candidates.py")
    spec = importlib.util.spec_from_file_location("sample_gold_candidates", script_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def write_seed(seed_root: Path, dataset: str, rows: list[dict]) -> None:
    dataset_dir = seed_root / dataset
    dataset_dir.mkdir(parents=True)
    payload = "\n".join(json.dumps(row, ensure_ascii=False) for row in rows)
    (dataset_dir / "papergraph_seed.jsonl").write_text(payload + "\n", encoding="utf-8")


def base_row(dataset: str, row_id: str, labels: dict) -> dict:
    return {
        "id": row_id,
        "source_dataset": dataset,
        "paper_id": f"paper-{row_id}",
        "title": "Example paper",
        "section": "Abstract",
        "chunk_id": f"chunk-{row_id}",
        "chunk_text": "This method supports the claim with a clear evidence sentence.",
        "question": "What does the paper show?",
        "labels": labels,
    }


def test_sample_candidate_files_writes_jsonl_and_review_csv() -> None:
    sampler = load_sampler()
    work_dir = Path(".papergraph-test-output") / f"sample-gold-basic-{uuid.uuid4().hex}"
    shutil.rmtree(work_dir, ignore_errors=True)

    try:
        seed_root = work_dir / "processed"
        write_seed(
            seed_root,
            "qasper",
            [
                base_row(
                    "qasper",
                    "q1",
                    {
                        "claims": [
                            {
                                "id": "claim-1",
                                "text": "The method supports the claim",
                                "evidence_span": "clear evidence sentence",
                            }
                        ],
                        "methods": [
                            {
                                "id": "method-1",
                                "text": "Example method",
                                "evidence_span": "This method",
                            }
                        ],
                    },
                )
            ],
        )
        write_seed(
            seed_root,
            "scifact",
            [
                base_row(
                    "scifact",
                    "s1",
                    {
                        "claims": [{"id": "claim-s1", "text": "Claim text"}],
                        "relations": [
                            {
                                "id": "rel-s1",
                                "type": "supports",
                                "source_id": "claim-s1",
                                "target_id": "evidence-s1",
                                "evidence_span": "clear evidence sentence",
                            }
                        ],
                    },
                )
            ],
        )

        out = work_dir / "gold" / "candidates.jsonl"
        review_csv = work_dir / "gold" / "review.csv"
        summary = sampler.sample_candidate_files(
            seed_root=seed_root,
            out=out,
            review_csv=review_csv,
            targets={"qasper": {"claims": 1, "methods": 1}, "scifact": {"supports": 1}},
        )

        assert summary.selected_count == 3
        records = [json.loads(line) for line in out.read_text(encoding="utf-8").splitlines()]
        assert len(records) == 3
        assert {record["source_dataset"] for record in records} == {"qasper", "scifact"}
        assert [record for record in records if record["source_dataset"] == "scifact"][0]["target_bucket"] == "supports"

        with review_csv.open(encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))

        assert len(rows) == 3
        assert rows[0]["review_status"] == ""
        assert rows[0]["corrected_label_bucket"] == ""
        assert set(rows[0]) == set(sampler.REVIEW_COLUMNS)
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)


def test_sample_candidate_files_backfills_missing_bucket_from_same_dataset() -> None:
    sampler = load_sampler()
    work_dir = Path(".papergraph-test-output") / f"sample-gold-backfill-{uuid.uuid4().hex}"
    shutil.rmtree(work_dir, ignore_errors=True)

    try:
        seed_root = work_dir / "processed"
        write_seed(
            seed_root,
            "qasper",
            [
                base_row(
                    "qasper",
                    "q1",
                    {
                        "claims": [
                            {"id": "claim-1", "text": "First claim", "evidence_span": "clear evidence sentence"},
                            {"id": "claim-2", "text": "Second claim", "evidence_span": "clear evidence sentence"},
                        ]
                    },
                )
            ],
        )

        out = work_dir / "candidates.jsonl"
        summary = sampler.sample_candidate_files(
            seed_root=seed_root,
            out=out,
            review_csv=work_dir / "review.csv",
            targets={"qasper": {"claims": 1, "limitations": 1}},
        )
        records = [json.loads(line) for line in out.read_text(encoding="utf-8").splitlines()]

        assert summary.selected_count == 2
        assert summary.deficits == {("qasper", "limitations"): 1}
        assert summary.backfilled_by_dataset == {"qasper": 1}
        assert [record["label_bucket"] for record in records] == ["claims", "claims"]
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)
