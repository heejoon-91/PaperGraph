# PaperGraph Gold Set, Eval, Gemma 4 튜닝 계획

조사일: 2026-04-19

## 결론

PaperGraph의 gold set은 공개 데이터셋을 그대로 가져와 만들 수 없다.

공개 데이터셋은 좋은 재료다. 하지만 최종 정답지는 PaperGraph의 실제 출력 schema에 맞춰 직접 만들어야 한다.

PaperGraph의 핵심 정답 단위는 다음이다.

- `Claim`
- `Method`
- `Experiment`
- `Limitation`
- `Concept`
- `Relation`
- `evidence_span`
- `paper_id`, `section`, `page`

따라서 공개 데이터는 warm-up, benchmark, 보조 annotation seed로 쓰고, 실제 gold set은 사용자가 넣을 논문 PDF에서 만든다.

## 어떤 자료로 만들 것인가

### 1. 실제 목표 corpus

가장 중요한 데이터는 실제 사용자가 넣을 PDF다.

처음에는 20개면 충분하다.

구성은 이렇게 잡는다.

| 묶음 | 수량 | 이유 |
| --- | ---: | --- |
| 같은 좁은 주제 논문 | 12개 | claim/method/experiment 비교의 기본 단위 |
| survey 또는 benchmark 논문 | 3개 | 분야 구조와 반복 한계를 잡기 좋음 |
| 방법은 비슷하지만 결과가 다른 논문 | 3개 | relation과 contradiction 평가에 필요 |
| PDF parsing이 어려운 논문 | 2개 | 2단 layout, 표, 수식, 그림, 스캔 품질 리스크 확인 |

PaperGraph의 첫 주제는 하나로 고정하는 편이 좋다. 예를 들면 GraphRAG, scientific QA, retrieval-augmented scientific reasoning 같은 좁은 주제다.

너무 넓게 섞으면 모델 평가가 아니라 annotation 기준 싸움이 된다.

### 2. QASPER

QASPER는 논문 full text 기반 QA와 evidence selection에 좋다.

쓸 부분:

- `full_text.section_name`
- `full_text.paragraphs`
- `qas.answers.evidence`
- `qas.answers.highlighted_evidence`
- `qas.answers.extractive_spans`

PaperGraph에 맞게 바꾸는 방법:

- QA의 evidence paragraph를 `evidence_span` 후보로 쓴다.
- answer span은 `Claim` 또는 `Experiment` 후보로만 쓴다.
- 질문이 method를 묻는 경우 `Method` 후보로 바꾼다.
- 모든 변환 샘플은 사람이 다시 검수한다.

QASPER는 "답변 근거를 찾아야 한다"는 점에서 PaperGraph와 잘 맞는다. 다만 label 체계가 다르므로 그대로 학습하면 안 된다.

### 3. SciERC

SciERC는 과학 문헌의 entity, relation, coreference annotation 데이터다.

쓸 부분:

- scientific entity extraction
- relation extraction
- coreference
- scientific knowledge graph construction 관점

PaperGraph에 맞게 바꾸는 방법:

- SciERC entity를 `Concept` 후보로 쓴다.
- relation을 PaperGraph `Relation` 후보 생성 훈련에 쓴다.
- claim/method/experiment/limitation 정답으로는 직접 쓰지 않는다.

SciERC는 abstract 중심이라 full paper extraction eval로는 부족하다.

### 4. SciREX

SciREX는 document-level scientific information extraction에 가깝다.

쓸 부분:

- 문서 전체를 봐야 하는 entity identification
- document-level N-ary relation identification
- paper-level relation 판단

PaperGraph에 맞게 바꾸는 방법:

- method, dataset, task 관계를 `Method`, `Experiment`, `Relation` 후보로 매핑한다.
- full-document relation 판단 eval에 일부 쓴다.
- `evidence_span`은 별도 검수로 붙인다.

SciREX는 PaperGraph의 corpus-level reasoning과 가까운 편이다.

### 5. SciER

SciER는 full-text scientific article에서 dataset, method, task entity와 relation을 다룬다.

쓸 부분:

- full-text 기반 entity/relation extraction
- method/dataset/task 중심 relation
- out-of-distribution test 구성 아이디어

PaperGraph에 맞게 바꾸는 방법:

- `method` entity는 PaperGraph `Method` 후보로 쓴다.
- `dataset/task` entity는 `Concept` 또는 `Experiment` 보조 필드로 쓴다.
- relation은 `uses`, `evaluates_on`, `compares_with` 후보로 변환한다.

### 6. S2ORC

S2ORC는 대규모 scientific paper corpus다.

쓸 부분:

- 논문 metadata
- abstract/full text
- bibliography와 citation context
- figure/table mention

PaperGraph에 맞게 바꾸는 방법:

- 평가 데이터 자체보다 corpus source로 쓴다.
- 특정 주제 PDF 목록을 뽑거나, 공개 full text를 확보하는 데 쓴다.
- citation context는 relation 후보 생성에 쓴다.

S2ORC는 너무 크다. 바로 학습 데이터로 넣지 말고, 필요한 논문을 고르는 pool로 본다.

### 7. PubLayNet 또는 DocLayNet

PubLayNet과 DocLayNet은 정보 추출 label이 아니라 문서 layout label이다.

쓸 부분:

- PDF layout parser 평가
- title, text, list, table, figure 영역 탐지
- 2단 layout과 표/그림 처리 개선

PaperGraph에 맞게 바꾸는 방법:

- extraction 모델 학습이 아니라 PDF parser 성능 평가에 쓴다.
- `page -> layout block -> section/chunk` 파이프라인의 recall을 본다.

## Gold Set 스키마

권장 파일:

```text
gold/papergraph-v0.jsonl
gold/annotation-guidelines.md
gold/splits.yaml
eval/papergraph-v0.yaml
eval/fixtures/
```

JSONL 한 줄은 하나의 chunk 단위로 둔다.

```json
{
  "id": "pg-v0-000001",
  "paper_id": "paper-graph-rag-001",
  "title": "논문 제목",
  "source_pdf": "papers/paper-graph-rag-001.pdf",
  "section": "Methods",
  "page": 4,
  "chunk_id": "paper-graph-rag-001:p4:c2",
  "chunk_text": "PDF에서 추출한 원문 chunk",
  "labels": {
    "claims": [
      {
        "id": "claim-001",
        "text": "논문이 주장하는 내용",
        "evidence_span": "chunk_text 안에 그대로 존재하는 문장",
        "confidence": 1.0
      }
    ],
    "methods": [],
    "experiments": [],
    "limitations": [],
    "concepts": [],
    "relations": [
      {
        "source_id": "claim-001",
        "target_id": "experiment-001",
        "type": "supported_by",
        "evidence_span": "관계를 뒷받침하는 문장"
      }
    ]
  },
  "negative_labels": {
    "no_limitation_stated": true,
    "no_experiment_stated": false
  },
  "annotator_notes": "표 안의 수치는 아직 parser가 안정적으로 못 읽음"
}
```

## Annotation 규칙

### 공통 규칙

- `evidence_span`은 `chunk_text` 안에 그대로 있어야 한다.
- 원문에 없는 추론은 gold label로 만들지 않는다.
- 한 문장이 claim과 limitation을 동시에 담으면 둘 다 라벨링할 수 있다.
- 애매하면 label을 만들지 말고 `annotator_notes`에 남긴다.
- relation endpoint는 같은 JSONL 또는 같은 paper 안에 실제 label id로 존재해야 한다.

### Claim

Claim은 논문이 독자에게 믿게 하려는 핵심 주장이다.

포함:

- "we show that ..."
- "our approach improves ..."
- "the results demonstrate ..."

제외:

- 단순 배경 설명
- 관련 연구 소개
- 실험 설정 설명

### Method

Method는 논문이 제안하거나 사용하는 절차, 모델, 알고리즘, 파이프라인이다.

포함:

- 제안 방법 이름
- retrieval 방식
- graph construction 방식
- training/inference pipeline

제외:

- 일반적인 도메인 단어
- 단순 tool 이름만 언급된 경우

### Experiment

Experiment는 주장 검증을 위해 수행한 실험, 평가, 결과다.

포함:

- dataset
- metric
- baseline
- result value
- ablation

제외:

- 미래 실험 계획
- 정량 결과 없는 기대 효과

### Limitation

Limitation은 논문이 인정한 한계 또는 결과에서 드러나는 약점이다.

포함:

- explicit limitation section
- "fails when ..."
- "does not handle ..."
- "future work should ..."

제외:

- 우리가 외부에서 추론한 약점

### Concept

Concept는 여러 논문을 연결할 수 있는 핵심 용어다.

포함:

- GraphRAG
- retrieval augmentation
- citation graph
- hallucination
- scientific QA

제외:

- 너무 일반적인 단어, 예: model, data, result

### Relation

Relation은 두 label 사이의 검증 가능한 관계다.

권장 type:

- `supports`
- `uses`
- `evaluates_on`
- `compares_with`
- `contradicts`
- `limited_by`
- `extends`

관계는 evidence span이 있어야 한다.

## Eval 데이터 구성

초기 v0는 작게 만든다.

```text
논문: 20개
chunk: 200개
gold label: 500-1000개
```

분할:

| split | 비율 | 용도 |
| --- | ---: | --- |
| train | 60% | prompt 개발, Gemma 4 튜닝 후보 |
| validation | 20% | prompt 선택, hyperparameter 선택 |
| test | 20% | 최종 비교, 절대 학습 금지 |

중요하다. test set은 prompt를 고칠 때도 보면 안 된다.

## Eval 지표

### 형식 지표

- JSON parse success rate
- schema valid rate
- required field completeness
- duplicate id rate
- dangling relation endpoint rate

### 근거 지표

- evidence span exact match rate
- evidence span fuzzy match rate
- page match rate
- section match rate
- hallucinated evidence rate

### 추출 지표

- Claim precision, recall, F1
- Method precision, recall, F1
- Experiment precision, recall, F1
- Limitation precision, recall, F1
- Concept precision, recall, F1
- Relation precision, recall, F1

### 제품 지표

- 사람이 수정한 label 비율
- 사람이 삭제한 hallucinated label 비율
- 논문 1편당 처리 시간
- 논문 20개당 총 비용
- `assessment.md`가 사람이 보기에 쓸모 있었는지

## Eval Runner 설계

권장 명령:

```powershell
papergraph eval gold/papergraph-v0.jsonl --model rule-based --out eval/runs/rule-based-v0
papergraph eval gold/papergraph-v0.jsonl --model gpt-5.4-mini --out eval/runs/gpt-5.4-mini-v0
papergraph eval gold/papergraph-v0.jsonl --model gemma4-e4b --out eval/runs/gemma4-e4b-v0
papergraph eval gold/papergraph-v0.jsonl --model gemma4-26b --out eval/runs/gemma4-26b-v0
```

출력:

```text
eval/runs/<run-id>/
  predictions.jsonl
  metrics.json
  errors.csv
  hallucinated_evidence.csv
  report.md
```

`errors.csv`는 튜닝보다 중요하다. 어떤 label이 왜 틀렸는지 알아야 데이터가 좋아진다.

## Gemma 4 튜닝 전략

### 튜닝 전에 해야 할 일

아래 조건을 만족하기 전에는 튜닝하지 않는다.

- gold label 500개 이상
- test split 고정
- 현재 rule-based baseline metric 존재
- strong model baseline metric 존재
- annotation guideline 존재
- evidence verifier 존재

이것이 없으면 튜닝 성능 향상을 측정할 방법이 없다.

### 모델 선택

권장 순서:

1. `google/gemma-4-E4B-it`
2. `google/gemma-4-26B-A4B-it`
3. `google/gemma-4-31B-it`

E4B로 먼저 튜닝 pipeline을 검증한다. 26B는 실사용 후보, 31B는 비용이 허용될 때 품질 후보로 둔다.

### 학습 방식

첫 튜닝은 full fine-tuning이 아니라 LoRA 또는 QLoRA가 맞다.

이유:

- trainable parameter가 적다.
- VRAM 요구량이 낮다.
- 여러 실험 adapter를 만들기 쉽다.
- base model을 건드리지 않고 되돌릴 수 있다.

Hugging Face PEFT 문서는 PEFT가 소수의 추가 파라미터만 학습해 대형 모델 튜닝 비용과 저장 비용을 낮춘다고 설명한다. LoRA는 low-rank decomposition 방식으로 trainable parameter를 줄이는 대표 방법이다. bitsandbytes/QLoRA는 4-bit quantization과 LoRA adapter를 함께 써서 제한된 GPU에서도 튜닝을 가능하게 한다.

### 학습 데이터 형식

Gemma 4 instruction-tuned 모델은 conversational SFT 형식으로 시작한다.

```json
{
  "messages": [
    {
      "role": "system",
      "content": "You extract evidence-grounded scientific paper facts. Return only valid JSON matching the schema."
    },
    {
      "role": "user",
      "content": "paper_id: paper-001\nsection: Methods\npage: 4\nchunk_text:\n..."
    },
    {
      "role": "assistant",
      "content": "{\"claims\": [], \"methods\": [{\"name\": \"...\", \"evidence_span\": \"...\"}], \"experiments\": [], \"limitations\": [], \"concepts\": [], \"relations\": []}"
    }
  ]
}
```

중요한 점:

- assistant content는 JSON 문자열만 둔다.
- reasoning trace는 학습 데이터에 넣지 않는다.
- evidence_span이 원문에 없는 샘플은 학습 데이터에서 제외한다.
- 틀린 예시를 그대로 넣어 "이건 틀림"이라고 가르치지 않는다. 별도 preference/RFT 단계로 미룬다.

### Hyperparameter 시작점

초기값:

```yaml
model: google/gemma-4-E4B-it
method: qlora
load_in_4bit: true
lora_r: 16
lora_alpha: 32
lora_dropout: 0.05
target_modules:
  - q_proj
  - k_proj
  - v_proj
  - o_proj
learning_rate: 0.0001
epochs: 2
batch_size: 1
gradient_accumulation_steps: 16
max_seq_length: 8192
completion_only_loss: true
```

이 값은 출발점이다. validation set에서 schema valid rate와 evidence exact match가 떨어지면 즉시 중단한다.

### 학습 명령 형태

처음에는 repo 안에 학습 코드를 넣지 말고 별도 `training/` 디렉터리로 분리한다.

```powershell
python training/prepare_sft.py gold/papergraph-v0.jsonl --out training/data/papergraph-sft-v0.jsonl
python training/train_gemma4_lora.py --config training/configs/gemma4-e4b-qlora.yaml
python training/eval_adapter.py --adapter training/runs/gemma4-e4b-v0 --gold gold/papergraph-v0.jsonl
```

`prepare_sft.py`는 반드시 verifier를 통과한 샘플만 내보내야 한다.

### 비교 기준

튜닝된 Gemma 4는 아래 네 개와 비교한다.

| baseline | 목적 |
| --- | --- |
| current rule-based extractor | 현재 구현 대비 개선 확인 |
| `gpt-5.4-mini` | 제품 기본 후보 대비 품질 확인 |
| untuned Gemma 4 | 튜닝 효과 확인 |
| ablated prompt-only Gemma 4 | 프롬프트만으로 되는지 확인 |

튜닝 모델이 untuned Gemma 4보다 좋지만 `gpt-5.4-mini`보다 너무 낮으면, 제품 기본값이 아니라 로컬 옵션으로만 둔다.

## 실패 케이스 분류

`errors.csv`에는 최소한 아래 category를 넣는다.

| category | 의미 |
| --- | --- |
| `schema_invalid` | JSON 또는 필드 구조가 깨짐 |
| `evidence_missing` | evidence span이 원문에 없음 |
| `wrong_label_type` | claim을 method로 분류함 |
| `missed_key_claim` | 중요한 claim 누락 |
| `missed_limitation` | limitation 누락 |
| `relation_endpoint_missing` | relation source/target이 없음 |
| `relation_unsupported` | 관계 근거가 약함 |
| `page_section_wrong` | page 또는 section provenance 오류 |
| `over_extraction` | 너무 일반적인 문장을 label로 만듦 |

튜닝 데이터는 이 실패 케이스를 줄이는 방향으로 추가한다.

## 단계별 로드맵

### v0

- `gold/papergraph-v0.jsonl` 20개 논문, 500-1000개 label
- annotation guideline 작성
- eval runner 작성
- current rule-based와 `gpt-5.4-mini` 비교

### v1

- Gemma 4 E4B untuned baseline 추가
- Gemma 4 26B untuned baseline 추가
- GROBID parser와 pypdf parser 비교
- evidence verifier 강화

### v2

- Gemma 4 E4B QLoRA 튜닝
- 26B LoRA 또는 QLoRA 튜닝 검토
- failure-driven data augmentation
- `--model local-gemma4` CLI 옵션 추가

### v3

- relation-specific eval 분리
- table/figure evidence path 추가
- multimodal Gemma 4 OCR path 실험
- private corpus deployment 문서화

## 지금 해야 할 작업

바로 만들 파일:

```text
gold/annotation-guidelines.md
gold/papergraph-v0.sample.jsonl
eval/metrics.md
eval/README.md
```

바로 구현할 코드:

```text
src/papergraph/eval.py
src/papergraph/evidence.py
tests/test_evidence_verifier.py
tests/test_eval_metrics.py
```

첫 번째 목표는 튜닝이 아니다.

첫 번째 목표는 "모델을 바꿨을 때 더 좋아졌는지 숫자로 말할 수 있는 상태"다.

## 참고 자료

- QASPER dataset card: <https://huggingface.co/datasets/allenai/qasper>
- SciERC project page: <https://nlp.cs.washington.edu/sciIE/>
- SciREX paper page: <https://a11y2.apps.allenai.org/paper?id=e99a259299d4d555ee4c354f2095ab4401369c82>
- SciER paper page: <https://huggingface.co/papers/2410.21155>
- S2ORC paper page: <https://huggingface.co/papers/1911.02782>
- PubLayNet IBM Research page: <https://research.ibm.com/publications/publaynet-largest-dataset-ever-for-document-layout-analysis>
- DocLayNet IBM Research page: <https://research.ibm.com/publications/doclaynet-a-large-human-annotated-dataset-for-document-layout-segmentation>
- GROBID 원리 문서: <https://grobid.readthedocs.io/en/latest/Principles/>
- GROBID training 원칙: <https://grobid.readthedocs.io/en/latest/training/General-principles/>
- Google Gemma 4 공식 발표: <https://blog.google/innovation-and-ai/technology/developers-tools/gemma-4/>
- Hugging Face Gemma 4 E4B 모델 카드: <https://huggingface.co/google/gemma-4-E4B>
- Hugging Face PEFT 문서: <https://huggingface.co/docs/peft/index>
- Hugging Face LoRA 문서: <https://huggingface.co/docs/peft/main/en/developer_guides/lora>
- Hugging Face TRL SFTTrainer 문서: <https://huggingface.co/docs/trl/sft_trainer>
- Hugging Face bitsandbytes/QLoRA 문서: <https://huggingface.co/docs/transformers/en/quantization/bitsandbytes>
