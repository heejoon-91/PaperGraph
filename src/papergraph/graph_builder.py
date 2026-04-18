from __future__ import annotations

from .models import ExtractedPaper, GraphEdge, GraphNode, KnowledgeGraph


def build_knowledge_graph(paper: ExtractedPaper) -> KnowledgeGraph:
    nodes: list[GraphNode] = [GraphNode(id=paper.paper_id, label=paper.title, type="Paper")]
    edges: list[GraphEdge] = []

    for claim in paper.claims:
        nodes.append(GraphNode(id=claim.id, label=claim.text, type="Claim"))
        edges.append(GraphEdge(source=paper.paper_id, target=claim.id, type="paper_has_claim"))

    for method in paper.methods:
        nodes.append(GraphNode(id=method.id, label=method.name, type="Method"))
        edges.append(GraphEdge(source=paper.paper_id, target=method.id, type="paper_uses_method"))

    for experiment in paper.experiments:
        nodes.append(GraphNode(id=experiment.id, label=experiment.summary, type="Experiment"))
        edges.append(
            GraphEdge(source=paper.paper_id, target=experiment.id, type="paper_reports_experiment")
        )

    for limitation in paper.limitations:
        nodes.append(GraphNode(id=limitation.id, label=limitation.text, type="Limitation"))
        edges.append(GraphEdge(source=paper.paper_id, target=limitation.id, type="paper_has_limitation"))

    for concept in paper.concepts:
        nodes.append(GraphNode(id=concept.id, label=concept.name, type="Concept"))

    for relation in paper.relations:
        edges.append(GraphEdge(source=relation.source, target=relation.target, type=relation.type))

    return KnowledgeGraph(nodes=nodes, edges=edges)
