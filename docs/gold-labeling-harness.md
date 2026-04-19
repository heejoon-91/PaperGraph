# PaperGraph Gold Candidate Labeling Harness

작성일: 2026-04-19

이 문서는 `gold/candidates/papergraph-v0-candidates.jsonl` 후보에 일관된 1차 label을 붙이기 위한 기준이다.

중요한 전제:

- 이 하네스의 label은 human gold가 아니다.
- 목적은 후보를 `accept`, `edit`, `reject`로 일관되게 triage해서 사람이 검수할 순서를 줄이는 것이다.
- 최종 `gold/papergraph-v0.jsonl`에는 사람이 확인한 `accept`와 `edit`만 들어가야 한다.

## Output Label

### accept

후보가 거의 그대로 gold로 승격될 수 있는 상태다.

기준:

- label text가 구체적이다.
- evidence span이 비어 있지 않다.
- evidence span이 chunk text 안에 실제 substring으로 들어 있다.
- relation이면 relation type이 명확하다.
- relation endpoint가 필요한 유형은 source/target이 있다.

대표 예시:

- SciFact `supports`/`contradicts` claim relation
- SciER method/concept entity with exact evidence
- SciER typed relation with source_id, target_id, evidence_span
- QASPER experiment result with metric/dataset context

### edit

정보는 유용하지만 사람이 정리해야 하는 상태다.

기준:

- label은 의미 있지만 evidence span이 비어 있거나 chunk와 정확히 맞지 않는다.
- label text가 너무 generic해서 PaperGraph 정책 결정이 필요하다.
- QASPER table/float 기반 label이라 사람이 문장형 label로 정리해야 한다.
- SciREX raw document relation이라 Method/Task/Dataset/Metric/Score를 PaperGraph endpoint로 매핑해야 한다.
- relation type은 있지만 endpoint나 evidence가 불완전하다.

대표 예시:

- `dropout`, `CNN`, `LSTM` 같은 generic method entity
- `{"Material": "...", "Method": "...", "Metric": "...", "Task": "...", "score": "..."}` 형태의 SciREX raw relation
- evidence span이 chunk 안의 정확한 substring이 아닌 후보

### reject

gold로 쓰기 어렵고 수정해도 근거가 약한 상태다.

기준:

- label text가 `yes`, `no`, `12`, 빈 문자열처럼 의미 없는 atomic 값이다.
- claim label이 너무 짧아 명제 형태가 아니다.
- bucket이 유효하지 않다.
- chunk text가 없다.
- relation type이 없다.
- raw relation의 핵심 필드가 빠져 있다.

대표 예시:

- QASPER claim label이 `no`인 후보
- QASPER method label이 단순 숫자인 후보
- relation인데 type이 비어 있는 후보

## Harness Rule Order

하네스는 다음 순서로 판단한다.

1. 구조 검증: bucket, chunk, relation type, endpoint 존재 여부를 본다.
2. 라벨 품질 검증: 빈 값, yes/no, 숫자-only, 너무 짧은 claim을 거른다.
3. evidence 검증: evidence span이 존재하고 chunk 안에 정확히 들어 있는지 본다.
4. bucket별 검증: claims, methods, experiments, concepts, relations마다 다른 기준을 적용한다.
5. dataset별 보정: QASPER table label, SciREX raw relation 같은 데이터셋 고유 문제를 edit로 보낸다.

reject 조건이 하나라도 강하게 걸리면 reject가 우선한다.

reject가 없고 edit 조건이 있으면 edit다.

reject/edit 조건이 없고 accept 조건이 있으면 accept다.

그 외는 `edit`과 `needs_human_confirmation`으로 둔다.

## Generated Files

스크립트:

```powershell
python scripts\label_gold_candidates.py `
  --candidates gold\candidates\papergraph-v0-candidates.jsonl `
  --out-csv gold\review\papergraph-v0-review-autolabeled.csv `
  --out-jsonl gold\candidates\papergraph-v0-candidates-autolabeled.jsonl
```

생성 파일:

- `gold/review/papergraph-v0-review-autolabeled.csv`
- `gold/candidates/papergraph-v0-candidates-autolabeled.jsonl`

원본 `gold/review/papergraph-v0-review.csv`는 비워 둔다. 이 파일은 사람이 직접 검수할 때 쓰는 원본 큐다.

## Strict Edit Pass

1차 하네스의 `edit`은 "유용할 수 있지만 자동 확정하기 어렵다"는 중간층이다. 이 중간층을 더 엄격하게 줄이기 위해 `strict-edit-pass`를 사용한다.

실행 예:

```powershell
python scripts\label_gold_candidates.py `
  --candidates gold\candidates\papergraph-v1-candidates-1000-autolabeled.jsonl `
  --harness strict-edit-pass `
  --only-auto-status edit `
  --out-csv gold\review\papergraph-v1-review-1000-edit-strict.csv `
  --out-jsonl gold\candidates\papergraph-v1-candidates-1000-edit-strict.jsonl
```

strict 기준:

- `accept`: exact evidence가 있고, 구조가 완전한 후보만 허용한다.
- `edit`: 기계적으로 매핑 작업이 남은 후보만 남긴다. 예: SciREX raw document relation, generic method entity.
- `reject`: evidence mismatch, list-like QASPER label, metric context 없는 experiment, endpoint/evidence 불완전 relation은 버린다.

strict pass는 1차 `edit` 후보만 대상으로 한다. 1차 `accept`와 `reject`는 다시 평가하지 않는다.

strict pass 결과는 `strict_auto_label` 필드에 저장된다. 기존 `auto_label`은 보존된다.

## Notes Format

CSV의 `notes`에는 다음 형태로 자동 판정 근거가 들어간다.

```text
papergraph-auto-label-v1; confidence=0.80; reasons=claim_relation_with_evidence
```

이 값은 사람이 검수할 때 참고용이다. 최종 gold 변환에서는 사람이 확정한 값만 신뢰해야 한다.
