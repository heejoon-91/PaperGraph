from __future__ import annotations

from .graph_builder import build_knowledge_graph
from .models import ExtractedPaper, KnowledgeGraph
from .qa import answer_question


def run_pipeline(extracted_paper: ExtractedPaper) -> KnowledgeGraph:
    """Run minimal pipeline from extracted paper data to knowledge graph."""
    return build_knowledge_graph(extracted_paper)


def ask(question: str, graph: KnowledgeGraph) -> str:
    """Ask a question over generated knowledge graph."""
    return answer_question(question, graph)
