# PaperGraph: 연구/논문 요약 + 지식그래프 생성기

PaperGraph는 PDF 논문을 구조적으로 파싱하고, 핵심 정보(주장/방법/실험/한계)를 추출한 뒤, 개념 간 관계를 지식그래프로 시각화하고 QA를 지원하는 프로젝트입니다.

## 왜 이 프로젝트인가

최근 AI 에이전트·지식구조화 수요가 커지면서, 단순 요약을 넘어 **근거 기반 지식 연결**이 중요해졌습니다.  
이 프로젝트는 아래 포트폴리오 역량을 한 번에 보여줍니다.

- PDF 파싱
- 정보 추출(IE)
- Graph modeling
- 시각화
- 문헌 기반 질의응답

---

## 목표 기능 (MVP)

1. **PDF 업로드**
2. **논문 구조 파싱** (title/abstract/sections/references)
3. **핵심 정보 추출**
   - Claim(핵심 주장)
   - Method(방법)
   - Experiment(실험/결과)
   - Limitation(한계)
4. **지식그래프 생성/시각화**
   - Concept 노드
   - Relation 엣지 (supports, uses, compares_with, limited_by ...)
5. **질의응답**
   - 추출 결과 + 그래프 기반 근거 응답

---

## 시스템 아키텍처

```text
[PDF Upload]
    |
    v
[Document Parser]
    |
    v
[Information Extraction]
    |
    v
[Graph Builder] ---> [Graph Store / Visualization]
    |
    v
[QA Engine]
```

세부 설계는 `docs/architecture.md`를 참고하세요.

---

## 시작하기

### 요구사항

- Python 3.11+

### 설치

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

### 테스트

```bash
pytest -q
```

---

## 코드 구조

```text
src/papergraph/
  models.py         # 도메인 데이터 모델
  graph_builder.py  # 추출 결과 -> 지식그래프 변환
  qa.py             # 그래프/요약 기반 질의응답(간단 규칙 기반)
  pipeline.py       # end-to-end 파이프라인 골격

tests/
  test_graph_builder.py
```

---

## 다음 단계 제안

- PDF parser: `unstructured`, `pymupdf`, `grobid` 결합
- 정보추출: LLM + rule hybrid (section-aware)
- 그래프 저장: Neo4j 또는 RDF triple store
- 시각화: pyvis / cytoscape.js
- QA: GraphRAG 형태로 확장

