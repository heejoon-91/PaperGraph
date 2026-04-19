from __future__ import annotations

from .models import KnowledgeGraph


QUESTION_INTENTS = {
    "Claim": ("주장", "claim"),
    "Method": ("방법", "method"),
    "Experiment": ("실험", "experiment", "result", "performance"),
    "Limitation": ("한계", "limitation"),
    "Concept": ("개념", "concept"),
}


def answer_question(question: str, graph: KnowledgeGraph) -> str:
    q = question.lower()

    for node_type, keywords in QUESTION_INTENTS.items():
        if any(keyword in q for keyword in keywords):
            matching_nodes = [n for n in graph.nodes if n.type == node_type]
            if not matching_nodes:
                return f"추출된 {keywords[0]} 정보가 없습니다."
            return "\n".join(f"- {n.label}" for n in matching_nodes)

    return "질문 의도를 파악하지 못했습니다. '주장', '방법', '실험', '한계', '개념'처럼 질문해 보세요."
