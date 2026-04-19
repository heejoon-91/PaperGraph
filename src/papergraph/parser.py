from __future__ import annotations

import re
from pathlib import Path

from .models import ParsedDocument, ParsedSection

SUPPORTED_TEXT_SUFFIXES = {".md", ".txt"}
SUPPORTED_PDF_SUFFIXES = {".pdf"}
SUPPORTED_DOCUMENT_SUFFIXES = SUPPORTED_TEXT_SUFFIXES | SUPPORTED_PDF_SUFFIXES

SECTION_HEADINGS = {
    "abstract",
    "초록",
    "요약",
    "introduction",
    "서론",
    "background",
    "관련 연구",
    "related work",
    "method",
    "methods",
    "methodology",
    "방법",
    "approach",
    "experiment",
    "experiments",
    "evaluation",
    "실험",
    "평가",
    "result",
    "results",
    "결과",
    "discussion",
    "논의",
    "limitation",
    "limitations",
    "한계",
    "conclusion",
    "결론",
    "references",
    "참고문헌",
}


def parse_text_file(path: Path) -> ParsedDocument:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    title = _first_title(lines) or path.stem.replace("-", " ").replace("_", " ").title()
    sections = _split_markdown_sections(lines)
    if not sections:
        sections = [ParsedSection(title="Document", text=text.strip())]
    return ParsedDocument(paper_id=path.stem, title=title, sections=sections)


def parse_pdf_file(path: Path) -> ParsedDocument:
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise RuntimeError(
            "PDF 입력을 읽으려면 pypdf가 필요합니다. "
            "`python -m pip install pypdf`를 실행하세요."
        ) from exc

    reader = PdfReader(str(path))
    metadata_title = ""
    if reader.metadata and reader.metadata.title:
        metadata_title = str(reader.metadata.title).strip()

    pages: list[tuple[int, str]] = []
    for index, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        if text.strip():
            pages.append((index, text))

    title = metadata_title or _first_title_from_text_pages(pages) or _title_from_path(path)
    sections = _split_pdf_sections(pages, document_title=title)
    if not sections:
        sections = [
            ParsedSection(
                title="문서",
                text="\n\n".join(text.strip() for _, text in pages if text.strip()),
            )
        ]
    return ParsedDocument(paper_id=path.stem, title=title, sections=sections)


def parse_document_file(path: Path) -> ParsedDocument:
    suffix = path.suffix.lower()
    if suffix in SUPPORTED_TEXT_SUFFIXES:
        return parse_text_file(path)
    if suffix in SUPPORTED_PDF_SUFFIXES:
        return parse_pdf_file(path)
    raise ValueError(f"지원하지 않는 문서 형식입니다: {path.suffix}")


def parse_text_directory(path: Path) -> list[ParsedDocument]:
    return [
        parse_text_file(child)
        for child in _supported_files(path)
        if child.suffix.lower() in SUPPORTED_TEXT_SUFFIXES
    ]


def parse_documents_directory(path: Path) -> list[ParsedDocument]:
    return [parse_document_file(child) for child in _supported_files(path)]


def _supported_files(path: Path) -> list[Path]:
    files = [
        child
        for child in sorted(path.iterdir())
        if child.is_file() and child.suffix.lower() in SUPPORTED_DOCUMENT_SUFFIXES
    ]
    return files


def _first_title(lines: list[str]) -> str:
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("#"):
            return stripped.lstrip("#").strip()
        return stripped
    return ""


def _first_title_from_text_pages(pages: list[tuple[int, str]]) -> str:
    for _, text in pages:
        for line in text.splitlines():
            stripped = line.strip()
            if stripped and not _looks_like_page_number(stripped):
                return stripped[:160]
    return ""


def _title_from_path(path: Path) -> str:
    return path.stem.replace("-", " ").replace("_", " ").title()


def _split_markdown_sections(lines: list[str]) -> list[ParsedSection]:
    sections: list[ParsedSection] = []
    current_title = ""
    current_lines: list[str] = []

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("#"):
            if current_title or current_lines:
                sections.append(
                    ParsedSection(
                        title=current_title or "Document",
                        text="\n".join(current_lines).strip(),
                    )
                )
            current_title = stripped.lstrip("#").strip()
            current_lines = []
        else:
            current_lines.append(line)

    if current_title or current_lines:
        sections.append(
            ParsedSection(
                title=current_title or "Document",
                text="\n".join(current_lines).strip(),
            )
        )

    return [section for section in sections if section.text]


def _split_pdf_sections(
    pages: list[tuple[int, str]],
    document_title: str = "",
) -> list[ParsedSection]:
    sections: list[ParsedSection] = []
    current_title = ""
    current_page: int | None = None
    current_lines: list[str] = []

    for page_number, text in pages:
        for line in text.splitlines():
            stripped = line.strip()
            if not stripped or _looks_like_page_number(stripped):
                continue
            if not current_title and not current_lines and stripped == document_title:
                continue
            if _looks_like_section_heading(stripped):
                if current_title or current_lines:
                    sections.append(
                        ParsedSection(
                            title=current_title or "문서",
                            text="\n".join(current_lines).strip(),
                            page=current_page,
                        )
                    )
                current_title = _clean_section_heading(stripped)
                current_page = page_number
                current_lines = []
            else:
                current_lines.append(stripped)
                if current_page is None:
                    current_page = page_number

    if current_title or current_lines:
        sections.append(
            ParsedSection(
                title=current_title or "문서",
                text="\n".join(current_lines).strip(),
                page=current_page,
            )
        )

    return [section for section in sections if section.text]


def _looks_like_section_heading(line: str) -> bool:
    if len(line) > 80:
        return False
    normalized = _normalize_heading(line)
    return normalized in SECTION_HEADINGS


def _clean_section_heading(line: str) -> str:
    cleaned = re.sub(r"^\d+(\.\d+)*\s*", "", line.strip())
    return cleaned.rstrip(".").strip()


def _normalize_heading(line: str) -> str:
    cleaned = _clean_section_heading(line).lower()
    return re.sub(r"\s+", " ", cleaned)


def _looks_like_page_number(line: str) -> bool:
    return bool(re.fullmatch(r"\d+", line.strip()))
