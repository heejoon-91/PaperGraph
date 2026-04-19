# PaperGraph 데이터 작업 디렉터리

이 디렉터리는 학습과 평가 데이터 준비용입니다.

## 추적 정책

- `data/raw/`는 다운로드한 원천 데이터를 둡니다. git에는 올리지 않습니다.
- `data/processed/`는 정제 결과를 둡니다. git에는 올리지 않습니다.
- 사람이 검수해 확정한 작은 gold set만 나중에 `gold/` 같은 별도 디렉터리로 승격합니다.

## 현재 파이프라인

QASPER 원천 데이터를 받아 PaperGraph 학습 후보 데이터로 정제합니다.

```powershell
python scripts/prepare_qasper.py --max-papers-per-split 25
```

생성물:

- `data/raw/qasper/`: QASPER 원본 tarball과 추출 JSON
- `data/processed/qasper/chunks.jsonl`: 논문 섹션/문단 chunk
- `data/processed/qasper/evidence_candidates.jsonl`: QA evidence 기반 후보 label
- `data/processed/qasper/papergraph_seed.jsonl`: PaperGraph schema에 맞춘 학습 후보 샘플
- `data/processed/qasper/manifest.json`: 처리 통계와 출처 정보

주의: `papergraph_seed.jsonl`은 gold set이 아닙니다. 사람이 `evidence_span`, label type, relation을 검수한 뒤에만 학습 정답으로 써야 합니다.

SciFact 원천 데이터도 받을 수 있습니다. SciFact는 scientific claim verification 데이터라서 `supports`/`contradicts` relation 후보를 만들 때 유용합니다.

```powershell
python scripts/prepare_scifact.py
```

생성물:

- `data/raw/scifact/`: SciFact 원본 tarball과 추출 JSONL
- `data/processed/scifact/chunks.jsonl`: abstract 기반 chunk
- `data/processed/scifact/evidence_candidates.jsonl`: claim과 evidence sentence 후보
- `data/processed/scifact/papergraph_seed.jsonl`: PaperGraph schema에 맞춘 claim/relation 후보 샘플
- `data/processed/scifact/manifest.json`: 처리 통계와 license 정보

주의: SciFact의 claims/annotations는 CC BY 4.0, corpus abstracts는 S2ORC 기반 ODC-By 1.0입니다. 재배포와 학습 모델 카드에 attribution을 남겨야 합니다.

SciER 원천 데이터도 받을 수 있습니다. SciER는 Dataset/Method/Task 엔티티와 relation을 문장 단위로 제공합니다.

```powershell
python scripts/prepare_scier.py
```

생성물:

- `data/raw/scier/`: SciER GitHub archive
- `data/processed/scier/chunks.jsonl`: 문장 chunk
- `data/processed/scier/entity_relation_candidates.jsonl`: entity 후보
- `data/processed/scier/papergraph_seed.jsonl`: PaperGraph schema에 맞춘 method/concept/relation 후보 샘플
- `data/processed/scier/manifest.json`: 처리 통계와 license 정보

주의: SciER repository license는 GPL-3.0으로 표시되어 있습니다. 학습 데이터 재배포와 모델 배포 전에 별도 license review가 필요합니다.

SciREX 원천 데이터도 받을 수 있습니다. SciREX는 문서 단위 scientific information extraction 데이터라서 Method/Task/Metric/Material 중심 후보를 만들 때 유용합니다.

```powershell
python scripts/prepare_scirex.py
```

생성물:

- `data/raw/scirex/`: SciREX release tarball과 추출 JSONL
- `data/processed/scirex/chunks.jsonl`: 문서 chunk
- `data/processed/scirex/entity_relation_candidates.jsonl`: entity 후보
- `data/processed/scirex/papergraph_seed.jsonl`: PaperGraph schema에 맞춘 method/concept/relation 후보 샘플
- `data/processed/scirex/manifest.json`: 처리 통계와 license 정보

주의: SciREX relation은 문서 단위 n-ary relation 성격이 강합니다. 현재 변환기는 relation raw payload를 보존하고, PaperGraph endpoint 매핑은 사람 검수 단계로 남겨둡니다.

## 큰 데이터셋

S2ORC, PubLayNet, DocLayNet은 목적이 다릅니다.

- S2ORC는 대규모 scientific paper corpus입니다. 전체 다운로드/정제 대상이라기보다 필요한 논문을 고르는 corpus source입니다.
- PubLayNet과 DocLayNet은 claim/method/experiment/limitation/concept 데이터가 아니라 PDF layout 데이터입니다.
- DocLayNet v1.2는 Hugging Face 기준 약 39.8GB입니다. PaperGraph 학습 label에는 직접 쓰지 않고, PDF parser/layout 모델을 만들 때 별도로 샘플링해야 합니다.

따라서 현재 자동 정제 대상은 QASPER, SciFact, SciER, SciREX입니다. 이 네 개가 PaperGraph extraction seed를 만드는 데 직접적인 데이터입니다.
