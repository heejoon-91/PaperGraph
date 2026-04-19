# PaperGraph Seed 샘플링 계획

작성일: 2026-04-19

## 목적

현재 `data/processed/*/papergraph_seed.jsonl`은 gold set이 아니다.

이 파일들은 공개 데이터셋에서 PaperGraph schema에 맞춰 변환한 **학습 후보 데이터**다. 실제 Gemma 4 fine-tuning이나 eval에 쓰려면 사람이 검수한 gold set으로 승격해야 한다.

목표 흐름은 다음이다.

```text
data/processed/*/papergraph_seed.jsonl
  |
  v
gold/candidates/papergraph-v0-candidates.jsonl
  |
  v
gold/review/papergraph-v0-review.csv
  |
  v
gold/papergraph-v0.jsonl
  |
  v
eval
```

## 현재 seed 데이터

| 데이터셋 | 성격 | PaperGraph에 유용한 부분 |
| --- | --- | --- |
| QASPER | 논문 full text 기반 QA + evidence | evidence span, QA 기반 claim/method/experiment 후보 |
| SciFact | 과학 claim verification | claim, supports/contradicts relation, evidence sentence |
| SciER | Dataset/Method/Task entity + relation | Method, Concept, Relation 후보 |
| SciREX | 문서 단위 scientific information extraction | Method, Task, Dataset, Metric, 문서 단위 relation 후보 |

## v0 샘플링 규모

처음부터 크게 가지 않는다.

추천 v0:

```text
총 300개 seed 샘플 검수
목표 gold label 500-1000개
```

분배:

| 데이터셋 | 샘플 수 | 이유 |
| --- | ---: | --- |
| QASPER | 80 | evidence span과 QA 기반 extraction 후보 확보 |
| SciFact | 70 | claim + supports/contradicts relation 확보 |
| SciER | 100 | method/concept/relation 후보가 가장 직접적 |
| SciREX | 50 | 문서 단위 IE와 긴 문맥 케이스 확보 |

## 데이터셋별 샘플링 기준

### QASPER

QASPER는 질문과 답변 evidence를 제공한다.

샘플링 목표:

```text
methods 후보 25개
experiments 후보 25개
claims 후보 20개
limitations 후보 10개
```

주의:

- QASPER의 limitation 라벨은 직접적인 것이 아니라 질문 기반 추정이다.
- `label_hint`는 참고만 하고, 사람이 최종 label type을 검수해야 한다.

### SciFact

SciFact는 claim이 abstract evidence로 지지되는지 반박되는지 제공한다.

샘플링 목표:

```text
supports 35개
contradicts 35개
```

주의:

- `supports`와 `contradicts`를 균형 있게 뽑아야 한다.
- PaperGraph의 핵심 기능 중 하나가 "논문들이 충돌하는 지점 찾기"이므로 contradict 샘플이 중요하다.

### SciER

SciER는 Dataset, Method, Task entity와 relation을 문장 단위로 제공한다.

샘플링 목표:

```text
method entity 포함 40개
dataset/task concept 포함 30개
relation 포함 30개
```

주의:

- SciER는 PaperGraph의 `Method`, `Concept`, `Relation`에 가장 직접적이다.
- repository license가 GPL-3.0으로 표시되어 있으므로 모델 학습/재배포 전 license review가 필요하다.

### SciREX

SciREX는 문서 단위 scientific information extraction 데이터다.

샘플링 목표:

```text
method 포함 문서 20개
dataset/task/metric 포함 문서 20개
relation raw payload 포함 문서 10개
```

주의:

- SciREX는 한 샘플이 크다.
- relation은 raw payload로 보존되어 있으므로 PaperGraph node endpoint 매핑은 검수 단계에서 해야 한다.

## 반드시 넣을 hard cases

랜덤만으로 뽑으면 eval이 쉬워진다.

아래 케이스는 일부러 포함한다.

```text
긴 chunk
evidence_span이 chunk_text와 정확히 안 맞는 후보
relation이 여러 개 있는 후보
method와 concept가 같은 문장에 같이 있는 후보
contradicts relation
label이 비어 있거나 애매한 후보
```

이 케이스들이 실제 제품에서 모델을 깨뜨린다.

## 생성할 파일 구조

```text
gold/
  candidates/
    papergraph-v0-candidates.jsonl
  review/
    papergraph-v0-review.csv
  papergraph-v0.jsonl
  splits.yaml
```

### `papergraph-v0-candidates.jsonl`

seed에서 뽑은 원본 후보다.

아직 gold가 아니다.

### `papergraph-v0-review.csv`

사람이 검수하기 쉬운 표다.

권장 컬럼:

```text
candidate_id
source_dataset
paper_id
section
chunk_text
label_bucket
label_text
evidence_span
relation_type
source_id
target_id
review_status
corrected_label_bucket
corrected_label_text
corrected_evidence_span
notes
```

`review_status` 값:

```text
accept
reject
edit
```

- `accept`: 그대로 gold로 승격
- `reject`: 학습에서 제외
- `edit`: label/evidence를 고쳐서 gold로 승격

### `papergraph-v0.jsonl`

사람이 검수 완료한 최종 gold set이다.

Gemma 4 튜닝과 eval에는 이 파일만 사용한다.

### `splits.yaml`

train/validation/test 분할 정보다.

권장 분할:

```yaml
train: 60
validation: 20
test: 20
```

test set은 prompt 수정이나 모델 튜닝에 쓰면 안 된다.

## 필요한 스크립트

다음 작업에서 만들 스크립트:

```text
scripts/sample_gold_candidates.py
scripts/review_to_gold.py
```

### `sample_gold_candidates.py`

seed에서 층화 샘플링으로 후보 300개를 뽑는다.

예상 실행:

```powershell
python scripts\sample_gold_candidates.py `
  --out gold\candidates\papergraph-v0-candidates.jsonl `
  --review-csv gold\review\papergraph-v0-review.csv
```

내부 목표:

```python
TARGETS = {
    "qasper": {
        "claims": 20,
        "methods": 25,
        "experiments": 25,
        "limitations": 10,
    },
    "scifact": {
        "supports": 35,
        "contradicts": 35,
    },
    "scier": {
        "methods": 40,
        "concepts": 30,
        "relations": 30,
    },
    "scirex": {
        "methods": 20,
        "concepts": 20,
        "relations": 10,
    },
}
```

### `review_to_gold.py`

검수 완료 CSV를 gold JSONL로 변환한다.

예상 실행:

```powershell
python scripts\review_to_gold.py `
  --candidates gold\candidates\papergraph-v0-candidates.jsonl `
  --review-csv gold\review\papergraph-v0-review.csv `
  --out gold\papergraph-v0.jsonl `
  --splits gold\splits.yaml
```

## 다음에 시킬 때 이렇게 말하면 됨

다음 세션에서 그대로 아래처럼 요청하면 된다.

```text
PaperGraph 이어서 작업하자.
docs/seed-sampling-plan.md에 적은 계획대로 seed 데이터에서 gold 후보를 샘플링하는 스크립트를 만들어줘.

해야 할 일:
1. scripts/sample_gold_candidates.py 만들기
2. data/processed/qasper, scifact, scier, scirex의 papergraph_seed.jsonl을 읽기
3. 문서에 적은 TARGETS 기준으로 300개 후보를 층화 샘플링하기
4. gold/candidates/papergraph-v0-candidates.jsonl 생성하기
5. gold/review/papergraph-v0-review.csv 생성하기
6. review CSV를 사람이 수정할 수 있게 컬럼 구성하기
7. 테스트 추가하고 python -m pytest로 검증하기
```

검수까지 자동화하고 싶으면 이렇게 말하면 된다.

```text
이어서 review_to_gold.py도 만들어줘.
gold/review/papergraph-v0-review.csv에서 review_status가 accept 또는 edit인 행만 읽어서 gold/papergraph-v0.jsonl로 변환하고, train/validation/test split도 만들어줘.
```

## 다음 작업의 완료 기준

다음 작업은 아래가 되면 끝난다.

```text
gold/candidates/papergraph-v0-candidates.jsonl 존재
gold/review/papergraph-v0-review.csv 존재
샘플 수가 300개 근처
QASPER/SciFact/SciER/SciREX가 모두 포함됨
review_status 컬럼이 비어 있음
python -m pytest 통과
git diff --check 통과
```

  PaperGraph 이어서 작업하자.
  docs/seed-sampling-plan.md에 적은 계획대로 seed 데이터에서 gold 후보를 샘플링하는 스크립트를 만들어줘.