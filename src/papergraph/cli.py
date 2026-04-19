from __future__ import annotations

import argparse
from pathlib import Path

from .export import (
    write_assessment_markdown,
    write_evidence_matrix,
    write_graph_json,
    write_summary_markdown,
)
from .extractor import extract_corpus
from .graph_builder import build_corpus_knowledge_graph
from .parser import parse_documents_directory


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="papergraph")
    subparsers = parser.add_subparsers(dest="command", required=True)

    build_parser = subparsers.add_parser("build", help="Build evidence graph artifacts from paper files.")
    build_parser.add_argument("input_dir", type=Path)
    build_parser.add_argument("--question", default="")
    build_parser.add_argument("--out", type=Path, default=Path("papergraph-output"))

    args = parser.parse_args(argv)
    if args.command == "build":
        return build_command(args.input_dir, args.out, args.question)
    return 1


def build_command(input_dir: Path, output_dir: Path, question: str = "") -> int:
    documents = parse_documents_directory(input_dir)
    if not documents:
        raise SystemExit(f"No .pdf, .txt, or .md papers found in {input_dir}")

    papers = extract_corpus(documents)
    graph = build_corpus_knowledge_graph(papers)

    output_dir.mkdir(parents=True, exist_ok=True)
    write_graph_json(graph, output_dir / "graph.json")
    write_evidence_matrix(papers, output_dir / "evidence_matrix.csv")
    write_summary_markdown(papers, output_dir / "summary.md", question=question)
    write_assessment_markdown(papers, output_dir / "assessment.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
