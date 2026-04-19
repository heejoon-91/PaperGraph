from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class Claim:
    id: str
    text: str
    paper_id: str = ""
    section: str = ""
    page: int | None = None
    evidence_span: str = ""
    confidence: float | None = None


@dataclass(slots=True)
class Method:
    id: str
    name: str
    paper_id: str = ""
    section: str = ""
    page: int | None = None
    evidence_span: str = ""
    confidence: float | None = None


@dataclass(slots=True)
class Experiment:
    id: str
    summary: str
    paper_id: str = ""
    section: str = ""
    page: int | None = None
    evidence_span: str = ""
    confidence: float | None = None


@dataclass(slots=True)
class Limitation:
    id: str
    text: str
    paper_id: str = ""
    section: str = ""
    page: int | None = None
    evidence_span: str = ""
    confidence: float | None = None


@dataclass(slots=True)
class Concept:
    id: str
    name: str
    paper_id: str = ""
    section: str = ""
    page: int | None = None
    evidence_span: str = ""
    confidence: float | None = None


@dataclass(slots=True)
class Relation:
    source: str
    target: str
    type: str
    paper_id: str = ""
    section: str = ""
    page: int | None = None
    evidence_span: str = ""
    confidence: float | None = None


@dataclass(slots=True)
class ExtractedPaper:
    paper_id: str
    title: str
    claims: list[Claim] = field(default_factory=list)
    methods: list[Method] = field(default_factory=list)
    experiments: list[Experiment] = field(default_factory=list)
    limitations: list[Limitation] = field(default_factory=list)
    concepts: list[Concept] = field(default_factory=list)
    relations: list[Relation] = field(default_factory=list)


@dataclass(slots=True)
class GraphNode:
    id: str
    label: str
    type: str
    paper_id: str = ""
    section: str = ""
    page: int | None = None
    evidence_span: str = ""
    confidence: float | None = None


@dataclass(slots=True)
class GraphEdge:
    source: str
    target: str
    type: str
    paper_id: str = ""
    section: str = ""
    page: int | None = None
    evidence_span: str = ""
    confidence: float | None = None


@dataclass(slots=True)
class KnowledgeGraph:
    nodes: list[GraphNode]
    edges: list[GraphEdge]


@dataclass(slots=True)
class ParsedSection:
    title: str
    text: str
    page: int | None = None


@dataclass(slots=True)
class ParsedDocument:
    paper_id: str
    title: str
    sections: list[ParsedSection]
