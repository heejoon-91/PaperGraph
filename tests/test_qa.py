from papergraph import answer_question, build_knowledge_graph
from papergraph.models import (
    Claim,
    Concept,
    Experiment,
    ExtractedPaper,
    KnowledgeGraph,
    Limitation,
    Method,
)


def make_graph() -> KnowledgeGraph:
    return build_knowledge_graph(
        ExtractedPaper(
            paper_id="p1",
            title="Test Paper",
            claims=[Claim(id="c1", text="A is better than B")],
            methods=[Method(id="m1", name="Method A")],
            experiments=[Experiment(id="e1", summary="+2.0 accuracy")],
            limitations=[Limitation(id="l1", text="low-resource 취약")],
            concepts=[Concept(id="k1", name="GraphRAG")],
        )
    )


def test_answer_question_supports_all_mvp_node_types() -> None:
    graph = make_graph()

    assert "- A is better than B" == answer_question("핵심 주장은?", graph)
    assert "- Method A" == answer_question("What method is used?", graph)
    assert "- +2.0 accuracy" == answer_question("experiment result?", graph)
    assert "- low-resource 취약" == answer_question("한계는?", graph)
    assert "- GraphRAG" == answer_question("관련 concept?", graph)


def test_answer_question_reports_missing_intent_data() -> None:
    graph = build_knowledge_graph(ExtractedPaper(paper_id="p1", title="Test Paper"))

    assert answer_question("방법은?", graph) == "추출된 방법 정보가 없습니다."
