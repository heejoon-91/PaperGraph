from __future__ import annotations

from collections.abc import Iterable

from .models import ExtractedPaper, GraphEdge, GraphNode, KnowledgeGraph


def build_knowledge_graph(paper: ExtractedPaper) -> KnowledgeGraph:
    return build_corpus_knowledge_graph([paper])


def build_corpus_knowledge_graph(papers: Iterable[ExtractedPaper]) -> KnowledgeGraph:
    nodes: list[GraphNode] = []
    edges: list[GraphEdge] = []
    node_ids: set[str] = set()

    def add_node(
        node_id: str,
        label: str,
        node_type: str,
        paper_id: str = "",
        section: str = "",
        page: int | None = None,
        evidence_span: str = "",
        confidence: float | None = None,
    ) -> None:
        if node_id in node_ids:
            raise ValueError(f"duplicate graph node id: {node_id}")
        node_ids.add(node_id)
        nodes.append(
            GraphNode(
                id=node_id,
                label=label,
                type=node_type,
                paper_id=paper_id,
                section=section,
                page=page,
                evidence_span=evidence_span,
                confidence=confidence,
            )
        )

    def add_edge(
        source: str,
        target: str,
        edge_type: str,
        paper_id: str = "",
        section: str = "",
        page: int | None = None,
        evidence_span: str = "",
        confidence: float | None = None,
    ) -> None:
        if source not in node_ids:
            raise ValueError(f"edge source does not exist: {source}")
        if target not in node_ids:
            raise ValueError(f"edge target does not exist: {target}")
        edges.append(
            GraphEdge(
                source=source,
                target=target,
                type=edge_type,
                paper_id=paper_id,
                section=section,
                page=page,
                evidence_span=evidence_span,
                confidence=confidence,
            )
        )

    for paper in papers:
        add_node(paper.paper_id, paper.title, "Paper", paper_id=paper.paper_id)

        for claim in paper.claims:
            add_node(
                claim.id,
                claim.text,
                "Claim",
                claim.paper_id,
                claim.section,
                claim.page,
                claim.evidence_span,
                claim.confidence,
            )
            add_edge(paper.paper_id, claim.id, "paper_has_claim", paper_id=paper.paper_id)

        for method in paper.methods:
            add_node(
                method.id,
                method.name,
                "Method",
                method.paper_id,
                method.section,
                method.page,
                method.evidence_span,
                method.confidence,
            )
            add_edge(paper.paper_id, method.id, "paper_uses_method", paper_id=paper.paper_id)

        for experiment in paper.experiments:
            add_node(
                experiment.id,
                experiment.summary,
                "Experiment",
                experiment.paper_id,
                experiment.section,
                experiment.page,
                experiment.evidence_span,
                experiment.confidence,
            )
            add_edge(
                paper.paper_id,
                experiment.id,
                "paper_reports_experiment",
                paper_id=paper.paper_id,
            )

        for limitation in paper.limitations:
            add_node(
                limitation.id,
                limitation.text,
                "Limitation",
                limitation.paper_id,
                limitation.section,
                limitation.page,
                limitation.evidence_span,
                limitation.confidence,
            )
            add_edge(
                paper.paper_id,
                limitation.id,
                "paper_has_limitation",
                paper_id=paper.paper_id,
            )

        for concept in paper.concepts:
            add_node(
                concept.id,
                concept.name,
                "Concept",
                concept.paper_id,
                concept.section,
                concept.page,
                concept.evidence_span,
                concept.confidence,
            )

        for relation in paper.relations:
            add_edge(
                relation.source,
                relation.target,
                relation.type,
                relation.paper_id,
                relation.section,
                relation.page,
                relation.evidence_span,
                relation.confidence,
            )

    return KnowledgeGraph(nodes=nodes, edges=edges)
