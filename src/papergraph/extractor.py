from __future__ import annotations

from collections.abc import Iterable

from .models import (
    Claim,
    Concept,
    Experiment,
    ExtractedPaper,
    Limitation,
    Method,
    ParsedDocument,
    Relation,
)

PREFIXES = {
    "claim": ("claim", "Claim"),
    "method": ("method", "Method"),
    "experiment": ("experiment", "Experiment"),
    "result": ("result", "Experiment"),
    "limitation": ("limitation", "Limitation"),
    "concept": ("concept", "Concept"),
    "주장": ("claim", "Claim"),
    "방법": ("method", "Method"),
    "실험": ("experiment", "Experiment"),
    "결과": ("result", "Experiment"),
    "한계": ("limitation", "Limitation"),
    "개념": ("concept", "Concept"),
}


def extract_paper(document: ParsedDocument) -> ExtractedPaper:
    paper = ExtractedPaper(paper_id=document.paper_id, title=document.title)

    for section in document.sections:
        for line in _content_lines(section.text):
            prefix, value = _split_marker(line)
            if prefix is None:
                continue
            id_prefix, item_type = PREFIXES[prefix]
            item_id = _make_id(document.paper_id, id_prefix, _next_index(paper, item_type))
            provenance = {
                "paper_id": document.paper_id,
                "section": section.title,
                "page": section.page,
                "evidence_span": line,
                "confidence": 1.0,
            }

            if item_type == "Claim":
                paper.claims.append(Claim(id=item_id, text=value, **provenance))
            elif item_type == "Method":
                paper.methods.append(Method(id=item_id, name=value, **provenance))
            elif item_type == "Experiment":
                paper.experiments.append(Experiment(id=item_id, summary=value, **provenance))
            elif item_type == "Limitation":
                paper.limitations.append(Limitation(id=item_id, text=value, **provenance))
            elif item_type == "Concept":
                paper.concepts.append(Concept(id=item_id, name=value, **provenance))

    _extract_unmarked_pdf_sections(document, paper)
    _infer_method_concept_relations(paper)
    return paper


def extract_corpus(documents: Iterable[ParsedDocument]) -> list[ExtractedPaper]:
    return [extract_paper(document) for document in documents]


def _content_lines(text: str) -> list[str]:
    return [line.strip("-* \t") for line in text.splitlines() if line.strip()]


def _split_marker(line: str) -> tuple[str | None, str]:
    if ":" not in line:
        return None, line
    raw_prefix, value = line.split(":", 1)
    prefix = raw_prefix.strip().lower()
    if prefix not in PREFIXES:
        return None, value.strip()
    return prefix, value.strip()


def _next_index(paper: ExtractedPaper, item_type: str) -> int:
    if item_type == "Claim":
        return len(paper.claims) + 1
    if item_type == "Method":
        return len(paper.methods) + 1
    if item_type == "Experiment":
        return len(paper.experiments) + 1
    if item_type == "Limitation":
        return len(paper.limitations) + 1
    if item_type == "Concept":
        return len(paper.concepts) + 1
    raise ValueError(f"unsupported item type: {item_type}")


def _make_id(paper_id: str, item_type: str, index: int) -> str:
    return f"{paper_id}:{item_type}:{index}"


def _extract_unmarked_pdf_sections(document: ParsedDocument, paper: ExtractedPaper) -> None:
    for section in document.sections:
        summary = _first_sentence(section.text)
        if not summary:
            continue

        section_kind = _section_kind(section.title)
        provenance = {
            "paper_id": document.paper_id,
            "section": section.title,
            "page": section.page,
            "evidence_span": summary,
            "confidence": 0.35,
        }

        if section_kind == "claim" and not paper.claims:
            paper.claims.append(
                Claim(
                    id=_make_id(document.paper_id, "claim", _next_index(paper, "Claim")),
                    text=summary,
                    **provenance,
                )
            )
        elif section_kind == "method" and not paper.methods:
            paper.methods.append(
                Method(
                    id=_make_id(document.paper_id, "method", _next_index(paper, "Method")),
                    name=summary,
                    **provenance,
                )
            )
        elif section_kind == "experiment" and not paper.experiments:
            paper.experiments.append(
                Experiment(
                    id=_make_id(document.paper_id, "experiment", _next_index(paper, "Experiment")),
                    summary=summary,
                    **provenance,
                )
            )
        elif section_kind == "limitation" and not paper.limitations:
            paper.limitations.append(
                Limitation(
                    id=_make_id(document.paper_id, "limitation", _next_index(paper, "Limitation")),
                    text=summary,
                    **provenance,
                )
            )


def _first_sentence(text: str) -> str:
    for line in _content_lines(text):
        if _split_marker(line)[0] is not None:
            continue
        sentence = line.split(". ", 1)[0].strip()
        if sentence:
            return sentence[:500]
    return ""


def _section_kind(title: str) -> str:
    normalized = title.lower().strip()
    if normalized in {"abstract", "초록", "요약"}:
        return "claim"
    if normalized in {"method", "methods", "methodology", "방법", "approach"}:
        return "method"
    if normalized in {"experiment", "experiments", "evaluation", "result", "results", "실험", "평가", "결과"}:
        return "experiment"
    if normalized in {"limitation", "limitations", "한계"}:
        return "limitation"
    return ""


def _infer_method_concept_relations(paper: ExtractedPaper) -> None:
    for method in paper.methods:
        for concept in paper.concepts:
            if (
                concept.name.lower() in method.name.lower()
                or concept.name.lower() in method.evidence_span.lower()
            ):
                paper.relations.append(
                    Relation(
                        source=method.id,
                        target=concept.id,
                        type="uses",
                        paper_id=paper.paper_id,
                        section=method.section,
                        evidence_span=method.evidence_span,
                        confidence=0.6,
                    )
                )
