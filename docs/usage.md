# PaperGraph 사용법

이 문서는 PaperGraph를 설치하고, 예제 논문을 처리하고, Python 라이브러리로 사용하는 방법을 정리한다.

## 현재 가능한 일

현재 PaperGraph는 `.pdf`, `.md`, `.txt` 논문 파일을 읽어 다음 산출물을 만든다.

- `graph.json`: 논문, 주장, 방법, 실험, 한계, 개념을 노드와 엣지로 표현한 그래프
- `evidence_matrix.csv`: 각 추출 항목과 원문 근거 문장을 연결한 표
- `summary.md`: 논문별 주장, 방법, 실험/결과, 한계, 개념 요약
- `assessment.md`: 추출 항목 수, 근거 문장 커버리지, 부족한 항목 평가

PDF 입력은 `pypdf`로 텍스트를 추출한다. PDF의 표, 그림, 2단 레이아웃은 텍스트 추출 품질이 낮을 수 있으므로, 중요한 논문은 `evidence_matrix.csv`의 근거 문장을 확인해야 한다.

모델 기반 추출과 학습 전략은 `docs/model-strategy.md`에 정리되어 있다.

## 설치

Windows PowerShell:

```powershell
cd C:\workspace\papergraph
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
```

이미 `pip install -e .`가 성공했다면 다시 설치할 필요는 없다.

설치 확인:

```powershell
papergraph --help
```

## 빠른 실행

예제 논문 폴더를 처리한다.

```powershell
papergraph build examples\papers --question "GraphRAG는 과학 QA의 환각을 어떻게 줄이는가?" --out examples\output
```

실행 후 다음 파일이 생긴다.

```text
examples/output/graph.json
examples/output/evidence_matrix.csv
examples/output/summary.md
examples/output/assessment.md
```

## 내 논문 폴더 처리하기

1. 원하는 위치에 논문 폴더를 만든다.
2. 각 논문 PDF를 넣는다.
3. 더 정확한 추출 테스트가 필요하면 `.md` 또는 `.txt` 파일에 아래 형식처럼 추출할 항목을 marker로 표시할 수 있다.

```markdown
# 논문 제목

## 초록

- 주장: 이 논문의 핵심 주장
- 개념: GraphRAG

## 방법

- 방법: 사용한 방법
- 실험: 실험 설정 또는 비교 방식
- 결과: 핵심 결과

## 한계

- 한계: 논문에서 인정한 한계
```

4. CLI를 실행한다.

```powershell
papergraph build C:\path\to\papers --question "내 연구 질문" --out C:\path\to\output
```

입력 폴더에는 PDF와 `.md`, `.txt` 파일을 섞어 넣을 수 있다.

## 지원하는 marker

한글 marker:

- `주장:`
- `방법:`
- `실험:`
- `결과:`
- `한계:`
- `개념:`

호환용 영어 marker:

- `Claim:`
- `Method:`
- `Experiment:`
- `Result:`
- `Limitation:`
- `Concept:`

PDF 파일은 marker가 없어도 섹션 제목을 기준으로 초록, 방법, 실험/결과, 한계를 추정한다. 이 자동 추정은 확신도 `0.35`로 기록된다. 사람이 marker를 붙인 `.md`/`.txt` 입력은 확신도 `1.0`으로 기록된다.

## Python 라이브러리로 사용하기

설치 후에는 Python 코드에서 `papergraph`를 import할 수 있다.

```python
from pathlib import Path

from papergraph import parse_documents_directory, extract_corpus
from papergraph.graph_builder import build_corpus_knowledge_graph
from papergraph.export import (
    write_evidence_matrix,
    write_graph_json,
    write_summary_markdown,
)

documents = parse_documents_directory(Path("examples/papers"))
papers = extract_corpus(documents)
graph = build_corpus_knowledge_graph(papers)

write_graph_json(graph, Path("graph.json"))
write_evidence_matrix(papers, Path("evidence_matrix.csv"))
write_summary_markdown(papers, Path("summary.md"))
```

## editable 설치의 의미

`python -m pip install -e .`는 현재 폴더를 Python 환경에 개발 모드로 등록한다.

그래서 `src/papergraph/` 안의 코드를 고친 뒤 다시 설치하지 않아도 `papergraph build ...`에 바로 반영된다.

## 테스트

```powershell
python -m pytest
```

현재 테스트는 다음을 확인한다.

- 그래프 빌더가 중복 노드 ID를 거부하는지
- 존재하지 않는 관계 endpoint를 거부하는지
- QA가 주장, 방법, 실험, 한계, 개념 질문에 답하는지
- PDF 파일에서 페이지와 섹션을 읽는지
- CLI가 `graph.json`, `evidence_matrix.csv`, `summary.md`, `assessment.md`를 만드는지
- 추출된 주장에 `evidence_span`이 붙는지

## 문제 해결

`papergraph` 명령을 찾지 못하면 현재 Python 환경에 설치되지 않은 것이다.

```powershell
python -m pip install -e .
```

그래도 안 되면 설치 없이 직접 실행할 수 있다.

```powershell
$env:PYTHONPATH='src'
python -m papergraph.cli build examples\papers --out examples\output
```

`pip install -e .`에서 권한 오류가 나면 Windows 임시 폴더 권한 문제일 가능성이 높다. 이 경우 먼저 아래 명령으로 현재 Python과 pip 경로를 확인한다.

```powershell
where python
where pip
python -m pip --version
```
