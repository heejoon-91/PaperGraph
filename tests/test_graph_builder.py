import pytest

from papergraph.graph_builder import build_knowledge_graph
from papergraph.models import Claim, Concept, Experiment, ExtractedPaper, Limitation, Method, Relation


def test_build_knowledge_graph_basic() -> None:
    paper = ExtractedPaper(
        paper_id="p1",
        title="Test Paper",
        claims=[Claim(id="c1", text="A is better than B")],
        methods=[Method(id="m1", name="Method A")],
        experiments=[Experiment(id="e1", summary="+2.0 accuracy")],
        limitations=[Limitation(id="l1", text="low-resource 취약")],
        concepts=[Concept(id="k1", name="GraphRAG")],
        relations=[Relation(source="m1", target="k1", type="uses")],
    )

    graph = build_knowledge_graph(paper)

    assert len(graph.nodes) == 6
    assert len(graph.edges) == 5
    assert any(edge.type == "uses" for edge in graph.edges)


def test_build_knowledge_graph_rejects_duplicate_node_ids() -> None:
    paper = ExtractedPaper(
        paper_id="p1",
        title="Test Paper",
        claims=[Claim(id="shared", text="A is better than B")],
        concepts=[Concept(id="shared", name="GraphRAG")],
    )

    with pytest.raises(ValueError, match="duplicate graph node id: shared"):
        build_knowledge_graph(paper)


def test_build_knowledge_graph_rejects_dangling_relations() -> None:
    paper = ExtractedPaper(
        paper_id="p1",
        title="Test Paper",
        methods=[Method(id="m1", name="Method A")],
        relations=[Relation(source="m1", target="missing", type="uses")],
    )

    with pytest.raises(ValueError, match="edge target does not exist: missing"):
        build_knowledge_graph(paper)
