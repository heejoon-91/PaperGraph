# PaperGraph 모델 전략

마지막 조사일: 2026-04-19

## 결론

PaperGraph는 처음부터 모델을 학습시키면 안 된다.

먼저 해야 할 일은 다음이다.

1. PDF를 코드로 파싱한다.
2. 섹션별 텍스트 chunk를 만든다.
3. 강한 범용 모델로 `Claim`, `Method`, `Experiment`, `Limitation`, `Concept`, `Relation`을 JSON으로 추출한다.
4. 모델이 낸 `evidence_span`이 실제 PDF 텍스트에 존재하는지 코드로 검증한다.
5. 검증된 결과만 `graph.json`, `evidence_matrix.csv`, `summary.md`, `assessment.md`에 넣는다.
6. 100-500개 정도의 검증 샘플이 쌓이면 작은 모델 학습 또는 증류를 검토한다.

이 프로젝트의 품질은 모델이 "그럴듯하게 말하는 능력"이 아니라, **근거 문장을 실제 원문으로 되돌릴 수 있는 능력**에서 나온다.

## 추천 모델 구성

### 기본 추출 모델: `gpt-5.4-mini`

기본값은 `gpt-5.4-mini`가 맞다.

이유:

- 논문 섹션 단위 추출은 고빈도 작업이다.
- 비용과 속도가 중요하다.
- `gpt-5.4-mini`는 텍스트/이미지 입력, Structured Outputs, function calling, file search를 지원한다.
- 공식 설명상 high-volume workload용으로 설계되었고, 입력 비용도 `gpt-5.4`보다 낮다.

용도:

- 섹션별 claim/method/experiment/limitation/concept 추출
- chunk별 relation 후보 생성
- PDF 텍스트가 이미 추출된 상태에서 구조화 JSON 생성

### 고난도 판정 모델: `gpt-5.4`

어려운 문서, 긴 corpus 종합, 충돌 판정, 최종 평가에는 `gpt-5.4`를 쓴다.

이유:

- 공식 문서 기준 1.05M context window를 지원한다.
- 문서, 도구 사용, 전문 작업, 긴 맥락 작업에 더 강하다.
- `gpt-5.4`는 Structured Outputs와 file search를 지원한다.

용도:

- 여러 논문 사이의 주장 충돌 판정
- "이 주장이 실험으로 뒷받침되는가?" 같은 고난도 평가
- `gpt-5.4-mini` 결과의 referee
- 긴 related-work map 생성

### 저비용 라우팅 모델: `gpt-5.4-nano`

단순 분류와 라우팅에는 `gpt-5.4-nano`를 쓴다.

용도:

- 섹션 타입 분류
- chunk relevance ranking
- "이 chunk에 추출할 정보가 있는가?" 1차 필터
- 중복 후보 제거 전처리

### 지금 쓰지 말아야 할 것

처음부터 `gpt-5.4-pro`를 제품 기본값으로 쓰지 않는다.

이유:

- 비용이 높다.
- PaperGraph의 초기 병목은 최고 성능 모델이 아니라 schema, evidence 검증, eval dataset이다.
- pro급 모델은 gold set 제작, 어려운 샘플 검수, benchmark용 judge로 제한한다.

## 모델이 맡을 일과 코드가 맡을 일

| 단계 | 담당 | 이유 |
| --- | --- | --- |
| PDF 텍스트 추출 | 코드, GROBID/pypdf/OCR | 원문 보존과 재현성이 중요하다. |
| 섹션 분리 | 코드 우선, 모델 보조 | 섹션 제목과 페이지 정보는 deterministic하게 남겨야 한다. |
| 정보 추출 | 모델 | 주장/방법/실험/한계는 의미 이해가 필요하다. |
| JSON schema 검증 | 코드 | 모델 출력은 항상 검증해야 한다. |
| evidence span 존재 확인 | 코드 | hallucination 방지의 핵심이다. |
| 관계 후보 생성 | 모델 | 논문 간 의미 관계는 규칙만으로 부족하다. |
| 최종 평가 | 모델 + 코드 | 모델은 해석, 코드는 근거/누락/형식 검증을 담당한다. |

## 권장 아키텍처

```text
PDF 파일
  |
  v
PDF 파서
  - pypdf: 빠른 baseline
  - GROBID: 과학 논문 구조화
  - OCR: 스캔 PDF 대응
  |
  v
페이지/섹션/chunk
  |
  v
gpt-5.4-nano
  - chunk relevance filter
  - section classifier
  |
  v
gpt-5.4-mini
  - structured extraction
  - Claim/Method/Experiment/Limitation/Concept/Relation JSON
  |
  v
검증기
  - JSON schema 검증
  - evidence_span 원문 존재 확인
  - page/section provenance 확인
  |
  v
gpt-5.4
  - 충돌 판정
  - corpus-level synthesis
  - 평가 리포트
  |
  v
산출물
  - graph.json
  - evidence_matrix.csv
  - summary.md
  - assessment.md
```

## 학습은 언제 하는가

바로 학습하지 않는다.

학습보다 먼저 필요한 것은 eval이다.

### 1단계: 학습 없음

목표:

- prompt + JSON schema + evidence 검증으로 baseline을 만든다.

데이터:

- 실제 사용자가 넣는 PDF 20-50개
- 사람이 검수한 `evidence_matrix.csv`
- 실패 케이스 목록

평가 지표:

- 추출 recall: 중요한 주장/방법/실험/한계를 얼마나 놓치지 않았는가
- evidence precision: 근거 문장이 실제 원문에 존재하는가
- relation precision: 관계가 실제 논문 내용과 맞는가
- citation/provenance completeness: paper/page/section이 채워졌는가
- user correction rate: 사용자가 CSV에서 고쳐야 하는 비율

### 2단계: 증류 데이터 만들기

목표:

- 강한 모델 결과를 사람이 검수해서 작은 모델 학습 데이터로 바꾼다.

과정:

1. `gpt-5.4` 또는 `gpt-5.4-pro`로 어려운 논문 chunk를 추출한다.
2. 사람이 `evidence_span`, label, relation을 검수한다.
3. 틀린 예시는 failure category를 붙인다.
4. 최종 JSONL 학습 데이터를 만든다.

좋은 샘플 형식:

```json
{
  "input": {
    "paper_id": "paper-001",
    "title": "논문 제목",
    "section": "방법",
    "page": 4,
    "text": "원문 chunk..."
  },
  "output": {
    "claims": [],
    "methods": [
      {
        "name": "방법 이름",
        "evidence_span": "원문에 실제 존재하는 문장",
        "confidence": 0.92
      }
    ],
    "experiments": [],
    "limitations": [],
    "concepts": [],
    "relations": []
  }
}
```

### 3단계: supervised fine-tuning

OpenAI 공식 문서 기준 supervised fine-tuning은 예시 입력과 정답 출력을 제공해 특정 형식과 동작을 더 잘 따르게 만드는 방식이다.

적합한 경우:

- 출력 schema가 안정적이다.
- 같은 종류의 논문을 많이 처리한다.
- prompt만으로 자꾸 같은 형식 오류가 난다.
- 비용 절감을 위해 작은 모델이 강한 모델처럼 동작해야 한다.

학습 데이터 규모:

- 최소 10개 예시부터 가능하다.
- 실무적으로는 50개 잘 만든 예시로 시작한다.
- 효과가 있으면 100-500개로 늘린다.

주의:

- `gpt-5.4`, `gpt-5.4-mini`, `gpt-5.4-nano`는 현재 모델 문서 기준 fine-tuning이 지원되지 않는다.
- fine-tuning이 필요한 경우 OpenAI fine-tuning 지원 모델을 별도로 선택해야 한다.
- 지금 시점에서는 `gpt-5.4` 계열을 직접 튜닝하기보다, 강한 모델로 데이터를 만들고 fine-tuning 지원 모델에 증류하는 전략이 더 현실적이다.

### 4단계: RFT는 나중

Reinforcement fine-tuning은 복잡한 domain reasoning에 쓸 수 있지만, PaperGraph 초기에는 과하다.

적합해지는 시점:

- programmable grader가 있다.
- "좋은 추출"과 "나쁜 추출"을 자동 점수화할 수 있다.
- 전문가 검수 데이터가 충분하다.

예시 grader:

- JSON schema valid 여부
- 모든 evidence span이 원문에 존재하는지
- 근거 문장과 label이 semantic하게 맞는지
- 주장과 실험 relation이 실제로 support 관계인지

## 데이터는 무엇으로 만들 것인가

### 공개 데이터

초기 benchmark와 pretraining 참고용으로 쓸 수 있는 데이터:

| 데이터셋 | 용도 |
| --- | --- |
| SciERC | 과학 문헌의 entity, relation, coreference 추출 학습/평가 |
| SciREX | 문서 단위 scientific information extraction |
| SciER | full-text scientific article에서 dataset/method/task entity와 relation 추출 |
| QASPER | 논문 full text 기반 QA와 evidence selection |
| S2ORC | 대규모 과학 논문 원문/메타데이터 corpus |
| PubLayNet | 과학 논문 PDF layout 분석 |

하지만 PaperGraph의 핵심 label은 `Claim`, `Method`, `Experiment`, `Limitation`, `Concept`, `Relation`, `EvidenceSpan`이다. 공개 데이터만으로는 부족하다.

결국 프로젝트 전용 gold set이 필요하다.

### PaperGraph 전용 gold set

최소 스키마:

```json
{
  "paper_id": "string",
  "title": "string",
  "section": "string",
  "page": 1,
  "chunk_text": "string",
  "labels": {
    "claims": [
      {
        "text": "string",
        "evidence_span": "string"
      }
    ],
    "methods": [],
    "experiments": [],
    "limitations": [],
    "concepts": [],
    "relations": []
  }
}
```

annotation rule:

- `evidence_span`은 원문에 그대로 존재해야 한다.
- 근거 없는 추론은 label로 만들지 않는다.
- 한 문장에 claim과 limitation이 같이 있으면 둘 다 달 수 있다.
- relation은 양쪽 endpoint가 같은 paper 또는 corpus 안에 실제 node로 존재해야 한다.
- 논문 전체 요약보다 "검증 가능한 정보 단위"를 우선한다.

## 평가 세트 구성

처음에는 작게 간다.

```text
논문 20개
섹션 chunk 200개
gold extraction 500-1000개
```

분할:

- train 후보: 60%
- validation: 20%
- test: 20%

테스트 세트는 절대 prompt 수정이나 학습에 쓰지 않는다.

필수 포함 케이스:

- 2단 PDF
- 표가 많은 논문
- 수식이 많은 논문
- 한계가 명시되지 않은 논문
- 실험 결과가 여러 데이터셋에 나뉜 논문
- 서로 충돌하는 논문 쌍
- abstract에는 강한 주장이 있지만 본문 근거가 약한 논문

## 추천 구현 순서

1. OpenAI API adapter를 만든다.
2. Pydantic 또는 JSON Schema로 추출 출력 형식을 고정한다.
3. `gpt-5.4-mini`로 section/chunk extraction을 붙인다.
4. evidence span verifier를 만든다.
5. `assessment.md`에 모델 confidence와 검증 실패 이유를 추가한다.
6. 20개 PDF gold set을 만든다.
7. `gpt-5.4`를 referee로 붙여 어려운 판단만 맡긴다.
8. eval 결과가 쌓이면 fine-tuning 또는 distillation을 검토한다.

## 지금 결정

PaperGraph의 다음 모델 작업은 fine-tuning이 아니다.

다음 작업은 이것이다.

> `gpt-5.4-mini`를 이용한 schema-bound extractor를 추가하고, 모델이 낸 모든 `evidence_span`을 PDF 원문에서 검증한다.

이게 되어야 진짜 "논문 PDF를 읽고 평가해주는 앱"이 된다.

Gemma 4만 따로 평가한 내용은 `docs/gemma4-evaluation.md`, gold set과 eval 데이터 구성 및 Gemma 4 튜닝 절차는 `docs/goldset-eval-gemma4-tuning.md`에 분리했다.

## 참고 자료

- OpenAI GPT-5.4 발표: <https://openai.com/index/introducing-gpt-5-4/>
- OpenAI GPT-5.4 API 모델 문서: <https://developers.openai.com/api/docs/models/gpt-5.4>
- OpenAI GPT-5.4 mini/nano 발표: <https://openai.com/index/introducing-gpt-5-4-mini-and-nano/>
- OpenAI GPT-5.4 mini 모델 문서: <https://developers.openai.com/api/docs/models/gpt-5.4-mini>
- OpenAI GPT-5.4 nano 모델 문서: <https://developers.openai.com/api/docs/models/gpt-5.4-nano>
- OpenAI Structured Outputs 소개: <https://openai.com/index/introducing-structured-outputs-in-the-api/>
- OpenAI File Search 문서: <https://platform.openai.com/docs/guides/tools-file-search/>
- OpenAI Supervised Fine-tuning 문서: <https://platform.openai.com/docs/guides/supervised-fine-tuning>
- OpenAI Reinforcement Fine-tuning 문서: <https://platform.openai.com/docs/guides/reinforcement-fine-tuning>
- GROBID 원리 문서: <https://grobid.readthedocs.io/en/latest/Principles/>
- SciERC: <https://nlp.cs.washington.edu/sciIE/>
- SciREX: <https://a11y2.apps.allenai.org/paper?id=e99a259299d4d555ee4c354f2095ab4401369c82>
- SciER: <https://aclanthology.org/2024.emnlp-main.726/>
- QASPER dataset card: <https://huggingface.co/datasets/allenai/qasper>
- S2ORC paper: <https://huggingface.co/papers/1911.02782>
- LayoutLMv3: <https://www.microsoft.com/en-us/research/publication/layoutlmv3-pre-training-for-document-ai-with-unified-text-and-image-masking/>
- PubLayNet: <https://research.ibm.com/publications/publaynet-largest-dataset-ever-for-document-layout-analysis>
