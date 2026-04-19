from __future__ import annotations

import argparse
import json
import re
import tarfile
import urllib.request
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any


TRAIN_DEV_URL = "https://qasper-dataset.s3.us-west-2.amazonaws.com/qasper-train-dev-v0.3.tgz"
TEST_URL = "https://qasper-dataset.s3.us-west-2.amazonaws.com/qasper-test-and-evaluator-v0.3.tgz"

DATA_FILES = {
    "train": "qasper-train-v0.3.json",
    "validation": "qasper-dev-v0.3.json",
    "test": "qasper-test-v0.3.json",
}


@dataclass(frozen=True)
class Chunk:
    paper_id: str
    title: str
    split: str
    section: str
    paragraph_index: int
    chunk_id: str
    text: str


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", value.lower()).strip("-")
    return slug or "item"


def download(url: str, destination: Path) -> None:
    if destination.exists() and destination.stat().st_size > 0:
        return

    destination.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(url, timeout=120) as response:
        destination.write_bytes(response.read())


def safe_extract_tarball(tarball: Path, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    root = destination.resolve()

    with tarfile.open(tarball, "r:gz") as archive:
        for member in archive.getmembers():
            target = (destination / member.name).resolve()
            if root not in target.parents and target != root:
                raise RuntimeError(f"Unsafe archive path: {member.name}")
        try:
            archive.extractall(destination, filter="data")
        except TypeError:
            archive.extractall(destination)


def ensure_qasper(raw_dir: Path) -> dict[str, Path]:
    raw_dir.mkdir(parents=True, exist_ok=True)
    train_dev_tarball = raw_dir / "qasper-train-dev-v0.3.tgz"
    test_tarball = raw_dir / "qasper-test-and-evaluator-v0.3.tgz"

    download(TRAIN_DEV_URL, train_dev_tarball)
    download(TEST_URL, test_tarball)
    safe_extract_tarball(train_dev_tarball, raw_dir)
    safe_extract_tarball(test_tarball, raw_dir)

    paths: dict[str, Path] = {}
    for split, filename in DATA_FILES.items():
        matches = list(raw_dir.rglob(filename))
        if not matches:
            raise FileNotFoundError(f"Could not find {filename} under {raw_dir}")
        paths[split] = matches[0]
    return paths


def load_qasper_file(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as file:
        data = json.load(file)
    if not isinstance(data, dict):
        raise ValueError(f"Expected object at top level in {path}")
    return data


def iter_section_chunks(split: str, paper_id: str, paper: dict[str, Any]) -> Iterator[Chunk]:
    title = normalize_text(str(paper.get("title") or ""))
    full_text = paper.get("full_text") or {}

    if isinstance(full_text, list):
        section_items = [
            item
            for item in full_text
            if isinstance(item, dict)
        ]
    elif isinstance(full_text, dict):
        section_names = full_text.get("section_name") or []
        paragraphs_by_section = full_text.get("paragraphs") or []
        section_items = [
            {
                "section_name": section_names[index] if index < len(section_names) else f"Section {index + 1}",
                "paragraphs": paragraphs,
            }
            for index, paragraphs in enumerate(paragraphs_by_section)
        ]
    else:
        section_items = []

    for section_index, section_item in enumerate(section_items):
        section_name = section_item.get("section_name") or f"Section {section_index + 1}"
        section = normalize_text(str(section_name))
        paragraphs = listify(section_item.get("paragraphs"))
        for paragraph_index, paragraph in enumerate(paragraphs):
            text = normalize_text(str(paragraph or ""))
            if not text:
                continue
            chunk_id = f"{paper_id}:s{section_index + 1}:p{paragraph_index + 1}"
            yield Chunk(
                paper_id=paper_id,
                title=title,
                split=split,
                section=section,
                paragraph_index=paragraph_index + 1,
                chunk_id=chunk_id,
                text=text,
            )


def listify(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def iter_qas(paper: dict[str, Any]) -> Iterator[dict[str, Any]]:
    qas = paper.get("qas") or []
    if isinstance(qas, list):
        for qa in qas:
            if isinstance(qa, dict):
                yield qa
        return

    if not isinstance(qas, dict):
        return

    questions = listify(qas.get("question"))
    question_ids = listify(qas.get("question_id"))
    answers = listify(qas.get("answers"))
    for index, question in enumerate(questions):
        yield {
            "question": question,
            "question_id": question_ids[index] if index < len(question_ids) else f"q{index + 1}",
            "answers": answers[index] if index < len(answers) else [],
        }


def iter_answer_bodies(qa: dict[str, Any]) -> Iterator[dict[str, Any]]:
    for answer_entry in listify(qa.get("answers")):
        if not isinstance(answer_entry, dict):
            continue
        answer = answer_entry.get("answer", answer_entry)
        if isinstance(answer, dict):
            yield answer


def answer_text(answer: dict[str, Any]) -> str:
    spans = [normalize_text(str(span)) for span in listify(answer.get("extractive_spans"))]
    spans = [span for span in spans if span]
    if spans:
        return " | ".join(spans)

    free_form = normalize_text(str(answer.get("free_form_answer") or ""))
    if free_form:
        return free_form

    if answer.get("yes_no") is True:
        return "yes"
    if answer.get("yes_no") is False:
        return "no"
    if answer.get("unanswerable") is True:
        return "unanswerable"
    return ""


def evidence_spans(answer: dict[str, Any]) -> list[str]:
    spans: list[str] = []
    for key in ("highlighted_evidence", "evidence", "extractive_spans"):
        for value in listify(answer.get(key)):
            span = normalize_text(str(value or ""))
            if span and span not in spans:
                spans.append(span)
    return spans


def label_type_for_question(question: str) -> str:
    q = question.lower()
    if any(token in q for token in ("method", "approach", "algorithm", "model", "how")):
        return "methods"
    if any(token in q for token in ("result", "performance", "score", "accuracy", "improvement", "experiment")):
        return "experiments"
    if any(token in q for token in ("limitation", "fail", "error", "weakness", "future work")):
        return "limitations"
    return "claims"


def find_chunk_for_evidence(chunks: Iterable[Chunk], evidence: str) -> Chunk | None:
    normalized_evidence = normalize_text(evidence).lower()
    if not normalized_evidence:
        return None

    for chunk in chunks:
        if normalized_evidence in chunk.text.lower():
            return chunk

    evidence_words = set(re.findall(r"[a-zA-Z0-9]+", normalized_evidence))
    if len(evidence_words) < 5:
        return None

    best_chunk: Chunk | None = None
    best_overlap = 0.0
    for chunk in chunks:
        chunk_words = set(re.findall(r"[a-zA-Z0-9]+", chunk.text.lower()))
        if not chunk_words:
            continue
        overlap = len(evidence_words & chunk_words) / len(evidence_words)
        if overlap > best_overlap:
            best_overlap = overlap
            best_chunk = chunk
    return best_chunk if best_overlap >= 0.65 else None


def write_jsonl(path: Path, records: Iterable[dict[str, Any]]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with path.open("w", encoding="utf-8", newline="\n") as file:
        for record in records:
            file.write(json.dumps(record, ensure_ascii=False, sort_keys=True))
            file.write("\n")
            count += 1
    return count


def build_records(paths: dict[str, Path], max_papers_per_split: int | None) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    chunk_records: list[dict[str, Any]] = []
    evidence_records: list[dict[str, Any]] = []
    seed_records: list[dict[str, Any]] = []

    for split, path in paths.items():
        papers = load_qasper_file(path)
        for paper_number, (paper_id, paper) in enumerate(papers.items(), start=1):
            if max_papers_per_split is not None and paper_number > max_papers_per_split:
                break
            if not isinstance(paper, dict):
                continue

            chunks = list(iter_section_chunks(split, paper_id, paper))
            for chunk in chunks:
                chunk_records.append(
                    {
                        "source_dataset": "qasper",
                        "split": split,
                        "paper_id": chunk.paper_id,
                        "title": chunk.title,
                        "section": chunk.section,
                        "page": None,
                        "chunk_id": chunk.chunk_id,
                        "chunk_text": chunk.text,
                    }
                )

            for qa_index, qa in enumerate(iter_qas(paper), start=1):
                question = normalize_text(str(qa.get("question") or ""))
                question_id = normalize_text(str(qa.get("question_id") or f"q{qa_index}"))
                label_type = label_type_for_question(question)

                for answer_index, answer in enumerate(iter_answer_bodies(qa), start=1):
                    output_text = answer_text(answer)
                    if not output_text:
                        continue

                    for evidence_index, evidence in enumerate(evidence_spans(answer), start=1):
                        chunk = find_chunk_for_evidence(chunks, evidence)
                        if chunk is None:
                            continue

                        record_id = f"qasper-{split}-{slugify(paper_id)}-{qa_index}-{answer_index}-{evidence_index}"
                        evidence_record = {
                            "id": record_id,
                            "source_dataset": "qasper",
                            "split": split,
                            "paper_id": paper_id,
                            "title": chunk.title,
                            "question_id": question_id,
                            "question": question,
                            "answer_text": output_text,
                            "label_hint": label_type,
                            "section": chunk.section,
                            "page": None,
                            "chunk_id": chunk.chunk_id,
                            "evidence_span": normalize_text(evidence),
                            "chunk_text": chunk.text,
                        }
                        evidence_records.append(evidence_record)

                        labels = {
                            "claims": [],
                            "methods": [],
                            "experiments": [],
                            "limitations": [],
                            "concepts": [],
                            "relations": [],
                        }
                        labels[label_type].append(
                            {
                                "id": f"{label_type[:-1]}-{record_id}",
                                "text": output_text,
                                "evidence_span": normalize_text(evidence),
                                "confidence": 0.6,
                                "source": "qasper_qa_evidence_heuristic",
                            }
                        )

                        seed_records.append(
                            {
                                "id": record_id,
                                "source_dataset": "qasper",
                                "status": "needs_human_review",
                                "paper_id": paper_id,
                                "title": chunk.title,
                                "source_pdf": None,
                                "section": chunk.section,
                                "page": None,
                                "chunk_id": chunk.chunk_id,
                                "chunk_text": chunk.text,
                                "question": question,
                                "labels": labels,
                                "negative_labels": {},
                                "annotator_notes": "Converted from QASPER QA evidence. Verify label type and evidence before using as gold data.",
                            }
                        )

    return chunk_records, evidence_records, seed_records


def main() -> None:
    parser = argparse.ArgumentParser(description="Download and clean QASPER into PaperGraph seed data.")
    parser.add_argument("--raw-dir", default="data/raw/qasper", help="Directory for downloaded QASPER source files.")
    parser.add_argument("--out-dir", default="data/processed/qasper", help="Directory for cleaned outputs.")
    parser.add_argument("--max-papers-per-split", type=int, default=25, help="Limit processed papers per split. Use 0 for all.")
    args = parser.parse_args()

    raw_dir = Path(args.raw_dir)
    out_dir = Path(args.out_dir)
    max_papers = None if args.max_papers_per_split == 0 else args.max_papers_per_split

    paths = ensure_qasper(raw_dir)
    chunk_records, evidence_records, seed_records = build_records(paths, max_papers)

    chunks_count = write_jsonl(out_dir / "chunks.jsonl", chunk_records)
    evidence_count = write_jsonl(out_dir / "evidence_candidates.jsonl", evidence_records)
    seed_count = write_jsonl(out_dir / "papergraph_seed.jsonl", seed_records)

    manifest = {
        "source_dataset": "qasper",
        "source_urls": [TRAIN_DEV_URL, TEST_URL],
        "license": "CC BY 4.0",
        "max_papers_per_split": max_papers,
        "files": {
            "chunks": str(out_dir / "chunks.jsonl"),
            "evidence_candidates": str(out_dir / "evidence_candidates.jsonl"),
            "papergraph_seed": str(out_dir / "papergraph_seed.jsonl"),
        },
        "counts": {
            "chunks": chunks_count,
            "evidence_candidates": evidence_count,
            "papergraph_seed": seed_count,
        },
        "warning": "papergraph_seed.jsonl is seed data, not a verified gold set. Human review is required before model training.",
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
