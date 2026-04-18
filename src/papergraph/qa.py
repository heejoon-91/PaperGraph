from __future__ import annotations

from .models import KnowledgeGraph


def answer_question(question: str, graph: KnowledgeGraph) -> str:
    q = question.lower()

    if "한계" in q or "limitation" in q:
        limitation_nodes = [n for n in graph.nodes if n.type == "Limitation"]
        if not limitation_nodes:
            return "추출된 한계 정보가 없습니다."
        return "\n".join(f"- {n.label}" for n in limitation_nodes)

    if "방법" in q or "method" in q:
        method_nodes = [n for n in graph.nodes if n.type == "Method"]
        if not method_nodes:
            return "추출된 방법 정보가 없습니다."
        return "\n".join(f"- {n.label}" for n in method_nodes)

    return "질문 의도를 파악하지 못했습니다. '방법', '한계'처럼 질문해 보세요."
