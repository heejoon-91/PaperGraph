# PaperGraph 제품 방향성

상태: 초안  
검토 경로: `office-hours` -> `plan-ceo-review`  
마지막 수정일: 2026-04-18

## 결정

PaperGraph는 넓은 범용 AI 논문 검색 제품으로 경쟁하면 안 된다.

가장 강한 시작점은 다음이다.

> PaperGraph는 연구자가 이미 모아둔 논문 묶음을 증거 그래프로 컴파일하는 도구다. PDF 폴더를 넣으면 주장, 방법, 실험, 한계, 개념, 근거 문장이 연결된 추적 가능한 그래프를 만든다.

이 방향은 "AI 논문 요약기"보다 좁고, "시각적 논문 지도"보다 방어 가능하다.

## 왜 이 방향인가

넓은 연구 보조 도구 시장은 이미 붐빈다.

- Elicit은 대규모 논문 데이터베이스를 바탕으로 systematic review workflow, screening, data extraction, report, sentence-level citation에 집중한다: <https://elicit.com/solutions/literature-review>
- Consensus는 peer-reviewed paper 데이터베이스 기반 AI academic search와 grounded answer에 집중한다: <https://help.consensus.app/en/articles/9922673-how-consensus-works>
- ResearchRabbit은 visual literature discovery, citation trail, topic exploration에 집중한다: <https://www.researchrabbit.ai/>
- Connected Papers 계열 제품은 Semantic Scholar 같은 scholarly graph infrastructure를 기반으로 논문 관계를 시각적으로 보여주는 데 집중한다: <https://www.semanticscholar.org/product/api>

PaperGraph는 이 제품들과 "누가 더 잘 검색하나"로 싸우면 안 된다.

열려 있는 공간은 사용자가 이미 중요하다고 판단한 제한된 corpus를 로컬에서 감사 가능하게 종합하는 일이다.

## 첫 사용자

첫 사용자는 "모든 연구자"가 아니다.

첫 사용자는 다음이다.

> 좁은 주제 하나에 대해 이미 20-80개의 PDF를 모아둔 대학원 연구자 또는 R&D 연구자. 각 논문이 어떤 주장을 하는지, 어떤 방법을 썼는지, 어떤 실험이 주장을 뒷받침하는지, 어디에서 한계가 충돌하는지 비교해야 하는 사람.

구체적인 예:

- 직접 모은 PDF 폴더로 related work 섹션을 준비하는 석사 또는 박사 과정 학생
- 어떤 기법을 프로토타입으로 만들 가치가 있는지 판단하기 전에 논문을 비교하는 산업 R&D 연구자
- 내부 문서나 특정 도메인 논문 위에 GraphRAG pipeline을 만들려는 research engineer

## 사용자 고통

고통스러운 작업은 "이 논문 요약해줘"가 아니다.

진짜 고통은 다음이다.

> "논문 더미가 있다. 이 분야가 실제로 무엇을 말하는지, 어떤 주장이 어떤 실험으로 뒷받침되는지, 방법들이 어떻게 다른지, 어떤 한계가 반복되는지 알아야 한다."

현재 대안:

- PDF를 직접 읽는다.
- Notion, Obsidian, Excel, Google Sheets에 수동으로 메모한다.
- 주장과 한계를 일관성 없이 추적한다.
- 메모를 literature review로 바꾸는 과정에서 출처와 근거를 잃는다.
- 챗봇에게 물어본 뒤, 답변이 실제 문장에 매핑되는지 다시 수동 검증한다.

## 제품 약속

PaperGraph가 약속해야 할 것은 다음이다.

> 논문을 넣으면, 검사하고 질문하고 내보낼 수 있는 신뢰 가능한 증거 그래프가 나온다.

여기서 신뢰란 모든 그래프 노드가 원본 논문, 섹션, 페이지, 근거 문장으로 돌아갈 수 있다는 뜻이다.

근거 문장이 없으면 PaperGraph는 예쁜 hallucination machine일 뿐이다.

## 하지 않을 것

처음부터 만들지 말아야 할 것:

- 범용 academic search engine
- 논문용 generic chatbot
- 제품의 중심 기능으로서의 화려한 graph visualization
- 완전한 systematic review platform
- 웹 규모의 citation recommendation

이것들은 더 크고, 더 붐비고, 첫 검증에 필요하지 않다.

## MVP

MVP는 웹 앱이 아니라 CLI와 산출물이어야 한다.

### 입력

- PDF 폴더 또는 추출된 text file 폴더
- 선택적 project question. 예: "GraphRAG systems reduce hallucination in scientific QA?"

### 처리

- 각 논문을 title, abstract, section, paragraph, sentence span으로 파싱한다.
- 다음을 추출한다.
  - claims
  - methods
  - experiments/results
  - limitations
  - concepts
  - relations
- 모든 추출 항목에 provenance를 붙인다.
  - paper id
  - section
  - page, 가능할 경우
  - evidence span

### 출력

- `graph.json`
- `evidence_matrix.csv`
- `summary.md`

### 질의

첫 QA layer는 제한된 질문에 답해야 한다.

- "이 논문들에서 어떤 방법들이 등장하는가?"
- "어떤 주장들이 실험으로 뒷받침되는가?"
- "어떤 한계가 반복되는가?"
- "어떤 논문들이 GraphRAG를 사용하는가?"
- "결과가 충돌하는 지점은 어디인가?"

답변은 자유로운 장문 prose가 아니라, 출처가 붙은 bullet이어야 한다.

## 권장 기술 형태

### 핵심 패키지

Python package는 작고 deterministic하게 유지한다.

```text
papergraph/
  models.py
  parser.py
  extractor.py
  graph_builder.py
  export.py
  qa.py
  cli.py
```

### 데이터 모델 업그레이드

현재 모델은 본격적인 extraction 전에 evidence field가 필요하다.

추출 entity에 공통 provenance field를 추가한다.

```text
paper_id
section
page
evidence_span
confidence
```

가능하면 relation에도 evidence를 붙여야 한다.

### 추출 전략

처음에는 hybrid approach가 맞다.

- 문서 구조는 deterministic parsing으로 처리한다.
- 테스트용 baseline extraction은 rule-based로 둔다.
- LLM extraction은 optional interface 뒤에 둔다.

LLM boundary는 반드시 typed여야 한다. LLM output은 graph에 들어가기 전에 structured data로 검증되어야 한다.

## 10점짜리 제품

10점짜리 버전은 "그래프가 보인다"가 아니다.

10점짜리 버전은 다음이다.

> 연구자가 40개 논문을 올리면 related-work map이 이렇게 말해준다. "이 7개 논문은 같은 주장을 합니다. 3개는 근거가 약합니다. 2개는 그 주장과 충돌합니다. 이 한계는 분야 전반에서 반복됩니다. 여기 정확한 문장들이 있습니다."

이건 쓸모 있다.

그래프는 기능이 아니다. 근거가 붙은 비교가 기능이다.

## 첫 검증 테스트

UI를 더 만들기 전에 이 테스트를 수동으로 먼저 한다.

1. 최근 literature review를 썼거나 지금 쓰고 있는 사람 3명을 찾는다.
2. 각자에게 좁은 주제 하나에 대한 10-20개 논문 폴더 또는 목록을 달라고 한다.
3. 현재 workflow를 보여달라고 한다. 노트, spreadsheet, Zotero, Obsidian, Notion, PDF annotation 등.
4. 5개 논문에 대해 작은 `evidence_matrix.csv`를 손으로 만든다.
5. 그 산출물이 2시간 이상을 아껴줬을지 묻는다.

그들이 matrix에 관심이 없다면 graph UI부터 만들면 안 된다.

## 범위 축소

다음 구현은 "PDF upload + visualization + GraphRAG QA"가 아니어야 한다.

다음 구현은 이것이어야 한다.

> `papergraph build ./papers --question "..."` 명령이 3-5개 sample paper에 대해 `graph.json`, `evidence_matrix.csv`, `summary.md`를 만든다.

이것이 가장 좁고 쓸모 있는 wedge다.

## 다음 빌드 계획

1. model에 provenance field를 추가한다.
2. JSON export와 CSV export를 추가한다.
3. CLI entry point를 추가한다.
4. 전체 PDF parsing 전에 2-3개의 작은 text paper fixture를 추가한다.
5. 모든 추출 claim에 evidence span이 있음을 증명하는 테스트를 추가한다.
6. `examples/` 아래에 sample output을 추가한다.

## 현재 구현 상태

2026-04-18 기준으로 가장 좁은 wedge는 구현됐다.

- `papergraph build` CLI가 `.pdf`, `.md`, `.txt` 논문 폴더를 입력으로 받는다.
- marker 기반 baseline extractor가 `Claim`, `Method`, `Experiment`, `Result`, `Limitation`, `Concept`를 추출한다.
- 모든 추출 entity는 `paper_id`, `section`, `page`, `evidence_span`, `confidence` provenance field를 가진다.
- 산출물은 `graph.json`, `evidence_matrix.csv`, `summary.md`, `assessment.md`로 고정했다.
- 예제 입력은 `examples/papers/`, 예제 출력은 `examples/output/` 아래에 있다.
- 회귀 테스트는 CLI 산출물 생성과 claim evidence span 보존을 검증한다.

## 리스크

| 리스크 | 왜 중요한가 | 대응 |
| --- | --- | --- |
| Elicit/Consensus와 경쟁 | 이들은 이미 broad search와 review workflow를 장악하고 있다. | local bounded corpus와 auditable graph artifact에 집중한다. |
| 예쁜 그래프, 약한 효용 | 연구자는 어려운 질문에 답하지 못하는 시각화를 하나 더 필요로 하지 않는다. | `evidence_matrix.csv`를 첫 산출물로 삼는다. |
| hallucinated extraction | 과학적 사용에는 source-backed claim이 필요하다. | evidence span과 structured validation을 필수로 둔다. |
| PDF parsing 지옥 | 완전한 PDF parsing은 어렵고 몇 주를 태울 수 있다. | text/markdown fixture로 시작한 뒤 PDF parsing은 adapter 뒤에 붙인다. |
| 너무 넓은 사용자 | "연구자"는 사용자가 아니다. | 고정된 PDF set으로 related work를 실제 작성 중인 사람부터 시작한다. |

## 과제

다음 큰 기능을 만들기 전에 이것부터 한다.

> 좁은 주제의 5개 논문에 대해 evidence matrix를 손으로 하나 만들고, 실제 연구자 1명에게 보여준 뒤 묻는다. "이게 이번 주에 2시간 이상을 아껴줬을까요?"

답이 yes라면, 그 matrix를 자동 생성하는 CLI를 만든다.

답이 no라면, PaperGraph는 다른 wedge가 필요하다.
