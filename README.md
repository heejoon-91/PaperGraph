# PaperGraph: 근거 기반 논문 지식그래프 생성기

PaperGraph는 연구자가 가진 논문 PDF 묶음을 **근거가 남는 지식그래프**로 바꾸는 도구입니다. 현재 MVP는 `.pdf`, `.md`, `.txt` 논문 파일에서 주장, 방법, 실험, 한계, 개념을 추출하고 `graph.json`, `evidence_matrix.csv`, `summary.md`, `assessment.md`를 생성합니다.

## 왜 이 프로젝트인가

최근 AI 에이전트·지식구조화 수요가 커지면서, 단순 요약보다 **어떤 문장에서 나온 주장인지 추적 가능한 구조화**가 중요해졌습니다. 이 프로젝트는 아래 역량을 한 번에 보여줍니다.

- PDF/문서 파싱
- 정보 추출
- 그래프 모델링
- 근거 매트릭스 내보내기
- 문헌 기반 질의응답

---

## 목표 기능 (MVP)

1. **PDF/텍스트/마크다운 논문 입력**
2. **논문 구조 파싱** (title/sections)
3. **핵심 정보 추출**
   - Claim, 핵심 주장
   - Method, 방법
   - Experiment, 실험/결과
   - Limitation, 한계
4. **지식그래프/근거 매트릭스 생성**
   - Concept 노드
   - Relation 엣지, 예: `supports`, `uses`, `compares_with`, `limited_by`
   - `evidence_span` 기반 CSV
5. **질의응답**
   - 추출 결과 + 그래프 기반 근거 응답

---

## 시스템 아키텍처

```text
[PDF/텍스트/마크다운 논문]
    |
    v
[문서 파서]
    |
    v
[정보 추출]
    |
    v
[그래프 빌더] ---> [그래프 저장소 / 시각화]
    |
    v
[질의응답 엔진]
```

세부 설계는 `docs/architecture.md`, 사용법은 `docs/usage.md`, 모델 전략은 `docs/model-strategy.md`를 참고하세요. Gemma 4 평가는 `docs/gemma4-evaluation.md`, gold set/eval/튜닝 계획은 `docs/goldset-eval-gemma4-tuning.md`에 정리했습니다.

---

## 시작하기

### 요구사항

- Python 3.11+

### 설치

Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
```

macOS/Linux:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e .
```

### 테스트

```bash
pytest -q
```

### 예제 실행

```bash
papergraph build examples/papers --question "GraphRAG는 과학 QA의 환각을 어떻게 줄이는가?" --out examples/output
```

생성물:

- `examples/output/graph.json`: 논문/주장/방법/실험/한계/개념 노드와 관계
- `examples/output/evidence_matrix.csv`: 각 추출 항목의 원문 근거 문장
- `examples/output/summary.md`: 논문별 요약
- `examples/output/assessment.md`: 추출 항목 수, 근거 문장 커버리지, 보강 필요 항목 평가

---

## 코드 구조

```text
src/papergraph/
  models.py         # 도메인 데이터 모델
  parser.py         # .pdf/.md/.txt 논문 구조 파싱
  extractor.py      # marker 기반 정보 추출 baseline
  graph_builder.py  # 추출 결과 -> 지식그래프 변환
  export.py         # JSON/CSV/Markdown 산출물 생성
  cli.py            # papergraph build CLI
  qa.py             # 그래프/요약 기반 질의응답(간단 규칙 기반)
  pipeline.py       # end-to-end 파이프라인 골격

tests/
  test_cli_workflow.py
  test_graph_builder.py
  test_qa.py
```

---

## 다음 단계 제안

- PDF 파서: `unstructured`, `pymupdf`, `grobid` 어댑터 추가
- 정보추출: LLM + 규칙 기반 혼합 방식, 모든 추출값에 `evidence_span` 필수화
- 그래프 저장: Neo4j 또는 RDF triple store 검토
- 시각화: pyvis / cytoscape.js
- QA: GraphRAG 형태로 확장

