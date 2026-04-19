# Gold Candidate Korean Sample

작성일: 2026-04-19

이 문서는 `gold/candidates/papergraph-v0-candidates.jsonl`에서 데이터셋과 라벨 유형이 섞이도록 10개를 골라 한국어로 풀어쓴 샘플이다.

목적은 후보 데이터가 어떤 내용을 담고 있는지 빠르게 파악하는 것이다. 아래 번역은 사람이 검수하기 위한 이해용이며, 아직 gold label 확정본이 아니다.

## 1. QASPER / Claim

- candidate_id: `cand-6ec91f5a5ac7d574`
- paper_id: `2001.02284`
- section: `Model ::: Dialogue Modules`
- label_bucket: `claims`
- 원래 label_text: `no`

한국어 내용:

- 이 논문 조각은 대화 시스템의 Dialogue Manager를 설명한다.
- Dialogue Manager는 현재 대화 상태를 유지하는 Dialogue State Tracker와, 다음 시스템 행동을 정하는 Policy Learner로 구성된다.
- 시스템은 Information Dictionary에 저장된 기존 정보를 보고 다음 행동을 결정한다.
- 예를 들어 학생이 기말고사를 공부 중이면 세부 주제를 더 물을 필요가 없다고 판단한다.
- 가능한 대화 흐름을 정하기 위해 Mutually Exclusive Rules, transition rules, mapping rules를 사용했고, 총 56개의 상태 전이를 만들었다.

검수 포인트:

- 후보 라벨이 `no`라서 그대로는 Claim으로 쓰기 어렵다.
- 이 샘플은 좋은 gold라기보다 seed noise 예시로 보인다.
- 사람이 검수한다면 `reject`하거나, "대화 관리자는 DST와 PL로 구성된다" 같은 명확한 claim으로 `edit`해야 한다.

## 2. QASPER / Method

- candidate_id: `cand-5362f8df256e8d0d`
- paper_id: `1909.04387`
- section: `Human Evaluation`
- label_bucket: `methods`
- 원래 label_text: `12`

한국어 내용:

- 이 논문 조각은 시스템 응답의 적절성을 평가하기 위한 인간 평가 방법을 설명한다.
- 연구자는 FigureEight 플랫폼에서 크라우드소싱 평가를 수행했다.
- 적절성은 "업무 환경에서 받아들일 수 있는 행동"으로 정의했다.
- 참가자에게 인간과 시스템 사이의 대화라는 점을 알려주었다.
- 문법적으로 틀린 응답과 비일관적인 응답은 평가에서 제외했다.
- 참가자는 prompt와 무작위로 뽑힌 네 개의 시스템 응답을 보고 상대 평가를 수행했다.
- 평점은 0에서 1 사이로 정규화했다.
- 스팸 작업자를 걸러내기 위해 adult-only bot 응답에 높은 점수를 반복적으로 주는 사용자를 제거했다.

검수 포인트:

- 후보 라벨 `12`는 Method 라벨로 부적절해 보인다.
- 실제 Method로는 "FigureEight 기반 크라우드소싱 인간 평가", "상대 평가 후 0-1 정규화", "adult-only bot 응답으로 스팸 작업자 필터링" 등이 가능하다.
- 사람이 검수한다면 `edit` 후보에 가깝다.

## 3. QASPER / Experiment

- candidate_id: `cand-5c43104303943e0f`
- paper_id: `1801.05147`
- section: `Main Results`
- label_bucket: `experiments`
- 원래 label_text: `F1 of 85.99 on the DL-PS dataset (dialog domain); 75.15 on EC-MT and 71.53 on EC-UQ (e-commerce domain)`

한국어 내용:

- 이 논문 조각은 제안한 크라우드소싱 학습 시스템 ALCrowd의 성능을 보여준다.
- 연구자는 ALCrowd를 다른 시스템들과 비교했다.
- DL-PS 데이터셋과 EC-MT, EC-UQ 데이터셋에서 실험 결과를 제시했다.
- 후보 라벨은 ALCrowd가 대화 도메인 DL-PS에서 F1 85.99, 전자상거래 도메인의 EC-MT에서 75.15, EC-UQ에서 71.53을 얻었다고 요약한다.

검수 포인트:

- 성능 수치가 명확해서 Experiment gold 후보로 비교적 좋아 보인다.
- 다만 evidence가 표 선택 문구라서, 실제 chunk 안에서 해당 숫자가 직접 보이는지 확인해야 한다.

## 4. SciFact / Supports Relation

- candidate_id: `cand-959d79f4d8df4f40`
- paper_id: `14717500`
- section: `Abstract`
- label_bucket: `relations`
- relation_type: `supports`
- 원래 label_text: `1,000 genomes project enables mapping of genetic sequence variation consisting of rare variants with larger penetrance effects than common variants.`

한국어 내용:

- 이 논문은 GWAS에서 발견되는 흔한 변이가 실제 원인 변이를 직접 반영하지 않을 수도 있다고 설명한다.
- 저자들은 흔한 변이보다 훨씬 드문 변이들이 특정 흔한 allele과 우연히 더 자주 함께 나타나면서 "synthetic association"을 만들 수 있다고 제안한다.
- 시뮬레이션을 통해 이런 synthetic association이 가능할 뿐 아니라 불가피할 수 있고, 최근 GWAS 신호 중 많은 부분에 기여할 수 있다고 주장한다.

검수 포인트:

- 라벨 텍스트는 "1000 Genomes Project가 rare variant mapping을 가능하게 한다"는 내용인데, evidence는 synthetic association 설명에 가깝다.
- `supports`로 되어 있지만 claim과 evidence가 정확히 맞는지 의심스럽다.
- 사람이 검수할 때 `reject` 또는 claim/evidence 수정이 필요할 수 있다.

## 5. SciFact / Supports Relation

- candidate_id: `cand-ed52a84c2a018950`
- paper_id: `1410197`
- section: `Abstract`
- label_bucket: `relations`
- relation_type: `supports`
- 원래 label_text: `Glial calcium waves influence seizures.`

한국어 내용:

- 이 논문은 국소 뇌전증에서 발작이 어떻게 시작되고 유지되는지 다룬다.
- 저자들은 별아교세포와 뉴런의 협력이 발작 유사 방전과 발작 사이 epileptiform event를 지지하는 데 필요한지 실험했다.
- 쥐 entorhinal cortex slice에서 NMDA를 국소 적용해 focal seizure 모델을 만들고, patch-clamp recording과 Ca2+ imaging을 동시에 수행했다.
- 결과적으로 astrocyte의 Ca2+ 상승이 focal seizure-like discharge의 초기 발생 및 유지와 관련된다는 것을 발견했다.
- 뉴런과 astrocyte가 반복적인 흥분 루프를 만들고, 이것이 발작 시작과 ictal discharge 유지를 촉진한다는 해석을 제시한다.

검수 포인트:

- Claim과 evidence가 꽤 잘 맞는다.
- `supports` gold 후보로 적합해 보인다.

## 6. SciER / Method

- candidate_id: `cand-3face741d7db5787`
- paper_id: `202719492`
- section: `Sentence`
- label_bucket: `methods`
- 원래 label_text: `dropout`

한국어 내용:

- 문장은 Weibo 데이터셋에서 Glynn CNN과 strided CNN을 각각 20번, 30 epoch씩 실험했다고 말한다.
- Glynn CNN은 기본 설정과 더 높은 dropout 설정을 모두 사용했다.
- 후보 라벨은 이 문장 안의 `dropout`을 Method로 잡았다.

검수 포인트:

- `dropout`은 모델/방법 구성요소이므로 Method로 볼 수 있다.
- 다만 단독 라벨로 너무 일반적인 기법이라, PaperGraph에서 Method로 유지할지 Concept로 옮길지 기준이 필요하다.

## 7. SciER / Concept

- candidate_id: `cand-1ecddfce61ef6af1`
- paper_id: `210702798`
- section: `Sentence`
- label_bucket: `concepts`
- 원래 label_text: `real - time segmentation`

한국어 내용:

- 문장은 dilated convolution이 real-time segmentation 분야에서 많이 쓰였고, 최근 많은 논문이 이 기법의 사용을 보고한다고 설명한다.
- 후보 라벨은 `real-time segmentation`을 Concept로 잡았다.

검수 포인트:

- real-time segmentation은 task 또는 연구 주제에 가깝다.
- PaperGraph schema에서 `Concept`로 둘지, 더 세분화해 `Task` 성격으로 다룰지 결정해야 한다.

## 8. SciER / Relation

- candidate_id: `cand-b233549610fb59b4`
- paper_id: `35249701`
- section: `Sentence`
- label_bucket: `relations`
- relation_type: `Trained-With`
- 원래 label_text: `Trained-With`

한국어 내용:

- 문장은 ImageNet으로 학습된 단일 VGG-16 네트워크를 사용하고, 여기에 세 가지 세밀 분류 작업을 추가했다고 설명한다.
- 추가된 작업은 CUBS birds, Stanford Cars, Oxford Flowers이다.
- 각 작업별로 따로 학습한 네트워크와 거의 비슷한 정확도를 달성했다고 말한다.

검수 포인트:

- `Trained-With` 관계는 "VGG-16이 ImageNet으로 학습되었다" 또는 "네트워크가 세 가지 fine-grained classification task와 함께 학습되었다"는 구조로 해석될 수 있다.
- source_id와 target_id를 확인해서 관계 endpoint가 의도한 방향인지 봐야 한다.

## 9. SciREX / Method

- candidate_id: `cand-74479a274d12fe31`
- paper_id: `2138a7127429d67746ec78de46d6820fee0e548e`
- section: `Document`
- label_bucket: `methods`
- 원래 label_text: `Graph2Seq`

한국어 내용:

- 이 논문은 그래프 형태의 입력을 sequence로 변환하는 Graph2Seq 모델을 제안한다.
- 기존 Seq2Seq 모델은 많은 작업에서 좋은 성능을 보이지만, 입력이 자연스럽게 그래프로 표현되는 경우에는 한계가 있다.
- Graph2Seq는 end-to-end graph-to-sequence neural encoder-decoder 모델이다.
- 입력 그래프를 벡터 시퀀스로 매핑하고, attention 기반 LSTM으로 target sequence를 디코딩한다.
- 노드 및 그래프 embedding을 만들 때 edge direction 정보를 반영하는 새로운 aggregation 전략을 사용한다.
- bAbI, Shortest Path, Natural Language Generation 작업에서 state-of-the-art 성능을 보였다고 주장한다.

검수 포인트:

- `Graph2Seq`는 명확한 Method 후보이다.
- evidence도 방법 설명과 잘 맞는다.

## 10. SciREX / Document-Level Relation

- candidate_id: `cand-0d364e5370e63e0c`
- paper_id: `40eb1e54cb5382dfd3b7efd16dc7df826262ea52`
- section: `Document`
- label_bucket: `relations`
- relation_type: `document_level_relation`
- 원래 label_text: `{"Material": "SUN-RGBD", "Method": "Frustum_PointNets", "Metric": "MAP", "Task": "3D_Object_Detection", "score": "54.0%"}`

한국어 내용:

- 이 논문은 RGB-D 데이터에서 3D 객체 검출을 수행하는 Frustum PointNets를 다룬다.
- 기존 방식은 이미지나 3D voxel에 초점을 맞췄지만, 이 방법은 raw point cloud를 직접 사용한다.
- 큰 장면의 point cloud에서 객체를 효율적으로 localize하는 것이 핵심 문제다.
- 저자들은 2D object detector와 3D deep learning을 함께 사용해 객체 위치를 찾는다.
- KITTI와 SUN RGB-D 3D detection benchmark에서 기존 최고 성능을 크게 넘고, 실시간 처리도 가능하다고 주장한다.
- 후보 relation은 SUN-RGBD 데이터셋에서 Frustum PointNets가 3D Object Detection task에 대해 MAP 54.0%를 기록했다는 문서 수준 관계다.

검수 포인트:

- 이 후보는 PaperGraph relation으로 매우 유용하지만, raw payload를 최종 node/relation endpoint로 어떻게 매핑할지 정해야 한다.
- 예: Method `Frustum PointNets` -> evaluated_on -> Dataset `SUN-RGBD`, metric `MAP`, score `54.0%`, task `3D Object Detection`.

## 빠른 결론

- 좋은 후보: 3, 5, 7, 9, 10
- 수정하면 좋은 후보: 2, 6, 8
- 의심스럽거나 reject 가능성이 큰 후보: 1, 4

현재 candidates는 "바로 학습 가능한 정답"이라기보다, 사람이 빠르게 보고 `accept`, `edit`, `reject`를 결정해야 하는 검수 큐에 가깝다.
