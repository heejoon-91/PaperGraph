from __future__ import annotations

import csv
import json
from dataclasses import asdict
from pathlib import Path

from .models import ExtractedPaper, KnowledgeGraph


def write_graph_json(graph: KnowledgeGraph, path: Path) -> None:
    path.write_text(json.dumps(asdict(graph), ensure_ascii=False, indent=2), encoding="utf-8")


def write_evidence_matrix(papers: list[ExtractedPaper], path: Path) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "paper_id",
                "title",
                "item_type",
                "item_id",
                "text",
                "section",
                "page",
                "evidence_span",
                "confidence",
            ],
        )
        writer.writeheader()
        for paper in papers:
            for row in _evidence_rows(paper):
                writer.writerow(row)


def write_summary_markdown(papers: list[ExtractedPaper], path: Path, question: str = "") -> None:
    lines = ["# PaperGraph 요약", ""]
    if question:
        lines.extend(["## 질문", "", question, ""])

    for paper in papers:
        lines.extend([f"## {paper.title}", "", f"논문 ID: `{paper.paper_id}`", ""])
        for heading, values in [
            ("주장", [claim.text for claim in paper.claims]),
            ("방법", [method.name for method in paper.methods]),
            ("실험/결과", [experiment.summary for experiment in paper.experiments]),
            ("한계", [limitation.text for limitation in paper.limitations]),
            ("개념", [concept.name for concept in paper.concepts]),
        ]:
            if not values:
                continue
            lines.append(f"### {heading}")
            lines.extend(f"- {value}" for value in values)
            lines.append("")

    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def write_assessment_markdown(papers: list[ExtractedPaper], path: Path) -> None:
    lines = ["# PaperGraph 평가", ""]
    for paper in papers:
        rows = _evidence_rows(paper)
        evidence_count = sum(1 for row in rows if row["evidence_span"])
        coverage = 0 if not rows else round(evidence_count / len(rows) * 100)
        missing = []
        if not paper.claims:
            missing.append("주장")
        if not paper.methods:
            missing.append("방법")
        if not paper.experiments:
            missing.append("실험/결과")
        if not paper.limitations:
            missing.append("한계")

        lines.extend(
            [
                f"## {paper.title}",
                "",
                f"- 논문 ID: `{paper.paper_id}`",
                f"- 추출 항목 수: {len(rows)}",
                f"- 근거 문장 커버리지: {coverage}%",
                f"- 추출된 주장 수: {len(paper.claims)}",
                f"- 추출된 방법 수: {len(paper.methods)}",
                f"- 추출된 실험/결과 수: {len(paper.experiments)}",
                f"- 추출된 한계 수: {len(paper.limitations)}",
                f"- 추출된 개념 수: {len(paper.concepts)}",
            ]
        )
        if missing:
            lines.append(f"- 보강 필요: {', '.join(missing)}")
        else:
            lines.append("- 보강 필요: 없음")
        lines.append("")

    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def _evidence_rows(paper: ExtractedPaper) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    items = [
        ("Claim", paper.claims, "text"),
        ("Method", paper.methods, "name"),
        ("Experiment", paper.experiments, "summary"),
        ("Limitation", paper.limitations, "text"),
        ("Concept", paper.concepts, "name"),
    ]
    for item_type, values, text_attr in items:
        for value in values:
            rows.append(
                {
                    "paper_id": paper.paper_id,
                    "title": paper.title,
                    "item_type": item_type,
                    "item_id": value.id,
                    "text": getattr(value, text_attr),
                    "section": value.section,
                    "page": "" if value.page is None else str(value.page),
                    "evidence_span": value.evidence_span,
                    "confidence": "" if value.confidence is None else str(value.confidence),
                }
            )
    return rows
