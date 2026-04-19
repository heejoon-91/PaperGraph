import csv
import json
import shutil
from pathlib import Path

from papergraph.cli import main
from papergraph.extractor import extract_paper
from papergraph.parser import parse_pdf_file, parse_text_file


def test_parse_extract_preserves_claim_evidence_span() -> None:
    parsed = parse_text_file(Path("examples/papers/graph-rag-overview.md"))
    paper = extract_paper(parsed)

    assert parsed.title == "과학 QA를 위한 근거 기반 GraphRAG"
    assert paper.claims
    assert all(claim.evidence_span for claim in paper.claims)
    assert paper.claims[0].section == "초록"


def test_parse_pdf_file_extracts_pages_and_sections(monkeypatch) -> None:
    import pypdf

    class FakeMetadata:
        title = "PDF 논문 제목"

    class FakePage:
        def __init__(self, text: str) -> None:
            self.text = text

        def extract_text(self) -> str:
            return self.text

    class FakeReader:
        metadata = FakeMetadata()
        pages = [
            FakePage(
                "\n".join(
                    [
                        "PDF 논문 제목",
                        "초록",
                        "이 논문은 PDF 입력을 읽어 근거 평가를 만든다.",
                        "방법",
                        "섹션 제목을 기준으로 텍스트를 나눈다.",
                    ]
                )
            )
        ]

        def __init__(self, path: str) -> None:
            self.path = path

    monkeypatch.setattr(pypdf, "PdfReader", FakeReader)

    parsed = parse_pdf_file(Path("fake.pdf"))

    assert parsed.title == "PDF 논문 제목"
    assert [section.title for section in parsed.sections] == ["초록", "방법"]
    assert parsed.sections[0].page == 1


def test_cli_build_writes_graph_matrix_and_summary() -> None:
    output_dir = Path(".papergraph-test-output")
    shutil.rmtree(output_dir, ignore_errors=True)

    try:
        exit_code = main(
            [
                "build",
                "examples/papers",
                "--question",
                "근거 연결은 어떻게 도움이 되는가?",
                "--out",
                str(output_dir),
            ]
        )

        assert exit_code == 0
        assert (output_dir / "graph.json").exists()
        assert (output_dir / "evidence_matrix.csv").exists()
        assert (output_dir / "summary.md").exists()
        assert (output_dir / "assessment.md").exists()

        graph = json.loads((output_dir / "graph.json").read_text(encoding="utf-8"))
        node_types = {node["type"] for node in graph["nodes"]}
        assert {"Paper", "Claim", "Method", "Experiment", "Limitation", "Concept"} <= node_types

        with (output_dir / "evidence_matrix.csv").open(encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))

        assert rows
        assert all(row["evidence_span"] for row in rows)
        assert "근거 연결은 어떻게 도움이 되는가?" in (
            output_dir / "summary.md"
        ).read_text(encoding="utf-8")
        assert "근거 문장 커버리지" in (
            output_dir / "assessment.md"
        ).read_text(encoding="utf-8")
    finally:
        shutil.rmtree(output_dir, ignore_errors=True)
