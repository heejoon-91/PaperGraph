# Gemma 4 Training Plan for PaperGraph

작성일: 2026-04-19

이 문서는 PaperGraph용 Gemma 4 모델을 어떻게 학습시킬지 정리한다.

핵심 결론:

- PaperGraph 모델은 한 가지 역할이 아니라 두 가지 역할로 나눠 학습하는 것이 안전하다.
- `Extractor`는 논문 chunk에서 PaperGraph JSON을 생성한다.
- `Judge`는 생성된 후보 label이 맞는지 검수한다.
- `reject` 데이터는 Extractor의 정답 출력으로 쓰면 안 된다.
- `reject` 데이터는 Judge 또는 hard negative 학습에 쓴다.

## Target Model Roles

### 1. Extractor

Extractor는 최종 제품에서 가장 중요한 모델이다.

역할:

```text
논문 chunk
  -> PaperGraph nodes and relations JSON
```

입력:

```text
논문 chunk text
```

출력:

```json
{
  "claims": [],
  "methods": [],
  "experiments": [],
  "limitations": [],
  "concepts": [],
  "relations": []
}
```

Extractor에는 positive gold만 넣어야 한다.

사용할 데이터:

```text
accept
+ 사람이 수정 완료한 edit
```

사용하면 안 되는 데이터:

```text
reject
수정 전 edit
```

이유:

```text
Extractor는 "무엇을 뽑아야 하는지"를 배우는 모델이다.
reject를 output 정답에 넣으면 오답을 그대로 따라 배운다.
```

### 2. Judge

Judge는 후보 label이 맞는지 판단하는 모델이다.

역할:

```text
논문 chunk + 후보 label
  -> accept / edit / reject
```

입력:

```json
{
  "chunk_text": "...",
  "candidate": {
    "label_bucket": "claims",
    "label_text": "...",
    "evidence_span": "...",
    "relation_type": "...",
    "source_id": "...",
    "target_id": "..."
  }
}
```

출력:

```json
{
  "verdict": "accept",
  "reason": "...",
  "corrected_label": null
}
```

Judge에는 accept, edit, reject를 모두 넣을 수 있다.

사용할 데이터:

```text
accept
edit
reject
```

이유:

```text
Judge는 좋은 후보와 나쁜 후보를 구분하는 모델이다.
reject는 "이 후보는 틀렸다"는 negative training signal로 유용하다.
```

## Current Data Status

현재 생성한 1,000개 후보 batch 기준 effective label 분포:

```text
accept: 740
edit: 47
reject: 213
```

파일:

```text
gold/candidates/papergraph-v1-candidates-1000.jsonl
gold/candidates/papergraph-v1-candidates-1000-autolabeled.jsonl
gold/candidates/papergraph-v1-candidates-1000-edit-strict.jsonl

gold/review/papergraph-v1-review-1000.csv
gold/review/papergraph-v1-review-1000-autolabeled.csv
gold/review/papergraph-v1-review-1000-edit-strict.csv
```

추천 사용처:

```text
accept 740
  -> Extractor positive
  -> Judge accept

edit 47
  -> Judge edit
  -> 사람이 고친 뒤 Extractor positive

reject 213
  -> Judge reject
  -> hard negative
  -> Extractor positive에는 넣지 않음
```

## Extractor SFT Format

Extractor fine-tuning 데이터는 instruction/input/output 형태로 만든다.

예시:

```json
{
  "instruction": "Extract PaperGraph nodes and relations from the research paper text. Include exact evidence spans copied from the text.",
  "input": "We found that a Ca2+ elevation in astrocytes correlates with both the initial development and the maintenance of a focal, seizure-like discharge.",
  "output": {
    "claims": [
      {
        "text": "Glial calcium waves influence seizures.",
        "evidence_span": "We found that a Ca2+ elevation in astrocytes correlates with both the initial development and the maintenance of a focal, seizure-like discharge."
      }
    ],
    "methods": [],
    "experiments": [],
    "limitations": [],
    "concepts": [],
    "relations": [
      {
        "type": "supports",
        "source_text": "Glial calcium waves influence seizures.",
        "target_text": "Ca2+ elevation in astrocytes correlates with seizure-like discharge",
        "evidence_span": "We found that a Ca2+ elevation in astrocytes correlates with both the initial development and the maintenance of a focal, seizure-like discharge."
      }
    ]
  }
}
```

Extractor 학습 규칙:

```text
evidence_span은 input에 있는 문장을 그대로 복사해야 한다.
없는 정보를 만들면 안 된다.
뽑을 게 없으면 빈 배열을 출력해야 한다.
```

## Judge SFT Format

Judge fine-tuning 데이터는 후보 검수 task로 만든다.

reject 예시:

```json
{
  "instruction": "Review whether the proposed PaperGraph candidate is valid for the given paper text.",
  "input": {
    "chunk_text": "We evaluate the model on SST-2, MNLI, QQP.",
    "candidate": {
      "label_bucket": "claims",
      "label_text": "SST-2 | MNLI | QQP",
      "evidence_span": "SST-2, MNLI, QQP"
    }
  },
  "output": {
    "verdict": "reject",
    "reason": "The candidate is a list of datasets, not a scientific claim.",
    "corrected_label": null
  }
}
```

edit 예시:

```json
{
  "instruction": "Review whether the proposed PaperGraph candidate is valid for the given paper text.",
  "input": {
    "chunk_text": "Our method achieves an F1 score of 85.99 on DL-PS.",
    "candidate": {
      "label_bucket": "experiments",
      "label_text": "85.99",
      "evidence_span": "achieves an F1 score of 85.99 on DL-PS"
    }
  },
  "output": {
    "verdict": "edit",
    "reason": "The metric is valid, but the label needs dataset and metric context.",
    "corrected_label": {
      "label_bucket": "experiments",
      "label_text": "The method achieves an F1 score of 85.99 on the DL-PS dataset.",
      "evidence_span": "Our method achieves an F1 score of 85.99 on DL-PS."
    }
  }
}
```

accept 예시:

```json
{
  "instruction": "Review whether the proposed PaperGraph candidate is valid for the given paper text.",
  "input": {
    "chunk_text": "We found that astrocyte calcium elevation correlates with focal seizure-like discharge.",
    "candidate": {
      "label_bucket": "relations",
      "label_text": "Glial calcium waves influence seizures.",
      "relation_type": "supports",
      "evidence_span": "astrocyte calcium elevation correlates with focal seizure-like discharge"
    }
  },
  "output": {
    "verdict": "accept",
    "reason": "The claim relation is supported by an exact evidence span.",
    "corrected_label": null
  }
}
```

## Preference Training

나중에 품질을 더 올릴 때는 preference 데이터도 만들 수 있다.

형태:

```json
{
  "input": "논문 chunk",
  "chosen": {
    "claims": [
      {
        "text": "The model improves F1 on DL-PS.",
        "evidence_span": "..."
      }
    ]
  },
  "rejected": {
    "claims": [
      {
        "text": "DL-PS | EC-MT | EC-UQ"
      }
    ]
  }
}
```

이 방식은 "chosen output이 rejected output보다 낫다"를 학습시키는 데 쓴다.

현재 단계에서는 우선순위가 낮다. 먼저 Extractor SFT와 Judge SFT를 만든다.

## Train / Validation / Test Split

분할은 candidate 단위가 아니라 `paper_id` 기준으로 해야 한다.

이유:

```text
같은 논문이 train과 test에 동시에 들어가면 평가가 부풀려진다.
```

추천 분할:

```text
train: 70
validation: 15
test: 15
```

또는 기존 계획의 분할:

```text
train: 60
validation: 20
test: 20
```

규칙:

```text
같은 paper_id는 하나의 split에만 들어가야 한다.
test set은 prompt 수정이나 하네스 수정에 쓰면 안 된다.
```

## Required Pre-Training Work

### 1. Schema 고정

Extractor output schema를 먼저 고정해야 한다.

초안:

```json
{
  "claims": [
    {
      "text": "...",
      "evidence_span": "..."
    }
  ],
  "methods": [
    {
      "text": "...",
      "evidence_span": "..."
    }
  ],
  "experiments": [
    {
      "text": "...",
      "metric": "...",
      "score": "...",
      "dataset": "...",
      "evidence_span": "..."
    }
  ],
  "limitations": [
    {
      "text": "...",
      "evidence_span": "..."
    }
  ],
  "concepts": [
    {
      "text": "...",
      "type": "...",
      "evidence_span": "..."
    }
  ],
  "relations": [
    {
      "type": "...",
      "source_text": "...",
      "target_text": "...",
      "evidence_span": "..."
    }
  ]
}
```

### 2. Edit 데이터 사람 검수

`edit`은 그냥 Extractor에 넣지 않는다.

처리:

```text
edit
  -> 사람이 corrected_label_* 작성
  -> corrected 값만 Extractor positive로 승격
```

### 3. Limitation 보강

현재 seed에는 limitation 후보가 거의 없다.

이 상태로 학습하면 Gemma 4는 limitation 추출을 잘 배우기 어렵다.

보강 방법:

```text
limitation
weakness
fail
future work
however
challenge
cannot
we leave
```

같은 신호를 이용해 limitation 후보를 별도로 만들고 사람이 검수한다.

### 4. Empty / Negative Examples 추가

뽑을 것이 없는 chunk도 Extractor 학습에 넣어야 한다.

예시:

```json
{
  "instruction": "Extract PaperGraph nodes and relations from the research paper text. Include exact evidence spans copied from the text.",
  "input": "This section describes the organization of the paper.",
  "output": {
    "claims": [],
    "methods": [],
    "experiments": [],
    "limitations": [],
    "concepts": [],
    "relations": []
  }
}
```

이걸 넣지 않으면 모델이 모든 chunk에서 뭔가를 억지로 뽑으려 한다.

## Recommended File Layout

최종 학습 전 파일 구조:

```text
gold/
  papergraph-v1-positive.jsonl
  papergraph-v1-judge.jsonl
  papergraph-v1-hard-negatives.jsonl
  splits.yaml

train/
  extractor_sft_train.jsonl
  extractor_sft_validation.jsonl
  extractor_sft_test.jsonl
  judge_sft_train.jsonl
  judge_sft_validation.jsonl
  judge_sft_test.jsonl
```

역할:

```text
papergraph-v1-positive.jsonl
  Extractor 학습용 positive gold

papergraph-v1-judge.jsonl
  Judge 학습용 accept/edit/reject 데이터

papergraph-v1-hard-negatives.jsonl
  Reject 중 모델이 헷갈리기 쉬운 negative 후보

extractor_sft_*.jsonl
  Gemma 4 extractor fine-tuning 입력

judge_sft_*.jsonl
  Gemma 4 judge fine-tuning 입력
```

## Recommended Pipeline

```text
gold/candidates/papergraph-v1-candidates-1000-autolabeled.jsonl
gold/candidates/papergraph-v1-candidates-1000-edit-strict.jsonl
  |
  v
accept 후보 추출
  |
  v
edit 후보 중 사람이 고칠 수 있는 것만 수정
  |
  v
extractor_sft.jsonl 생성
  |
  v
accept/edit/reject 전체로 judge_sft.jsonl 생성
  |
  v
paper_id 기준 train/validation/test split
  |
  v
Gemma 4 fine-tuning
  |
  v
held-out test로 extractor와 judge 따로 평가
```

## Practical Recommendation

지금 단계에서 바로 해야 할 일:

```text
1. Extractor output schema 확정
2. accept 740개로 extractor positive 초안 생성
3. strict edit 47개를 사람이 검수해서 positive로 승격
4. reject 213개로 judge negative 생성
5. limitation 후보 생성기 추가
6. paper_id 기준 split 생성
7. extractor_sft_*.jsonl과 judge_sft_*.jsonl 생성
```

최종 원칙:

```text
Extractor:
  논문 chunk -> PaperGraph JSON
  학습 데이터: accept + 사람이 고친 edit

Judge:
  논문 chunk + 후보 label -> accept/edit/reject
  학습 데이터: accept + edit + reject
```
