# PaperGraph Gemma 4 평가

조사일: 2026-04-19

## 결론

Gemma 4는 PaperGraph의 장기 전략에 들어갈 만하다.

하지만 지금 바로 기본 추출 모델로 쓰기보다, 먼저 `gpt-5.4-mini` 같은 강한 API 모델로 gold set과 eval을 만들고, 그다음 Gemma 4를 로컬 추출기 또는 사내 배포용 모델로 튜닝하는 순서가 맞다.

PaperGraph에서 중요한 것은 "긴 논문을 읽을 수 있느냐"보다 "추출한 claim, method, experiment, limitation이 원문 evidence span으로 돌아가느냐"다. Gemma 4가 아무리 좋아도 이 검증 루프가 없으면 제품 품질은 올라가지 않는다.

## Gemma 4가 좋은 이유

Google은 2026-04-02에 Gemma 4를 공개했고, 공식 블로그에서 open model family로 소개했다. 31B 모델은 공개 모델 기준 Arena AI text leaderboard 상위권, 26B MoE 모델은 더 적은 활성 파라미터로 빠른 추론을 목표로 한다고 설명한다.

PaperGraph 관점에서 강점은 네 가지다.

| 항목 | PaperGraph에서 의미 |
| --- | --- |
| Apache 2.0 | 연구용, 사내용, 상업용 배포 부담이 낮다. |
| 128K-256K context | 논문 한 편 또는 긴 섹션 묶음을 한 번에 처리하기 쉽다. |
| structured JSON output, function calling | `Claim`, `Method`, `Experiment`, `Limitation`, `Concept`, `Relation` schema 추출에 맞다. |
| 멀티모달/OCR/문서 이해 | 나중에 표, 그림, 차트, 스캔 PDF까지 확장할 여지가 있다. |

Hugging Face 모델 카드 기준 Gemma 4는 E2B, E4B, 26B A4B MoE, 31B Dense 계열로 제공된다. 작은 모델은 128K context, 큰 모델은 256K context를 지원한다. 문서/PDF parsing, OCR, chart comprehension 같은 시각 문서 작업도 핵심 capability로 명시되어 있다.

## PaperGraph에 맞는 포지션

### 지금 당장

Gemma 4를 제품 기본값으로 두지 않는다.

지금 필요한 것은 모델 교체가 아니라 다음 세 가지다.

1. PDF 파서가 page, section, chunk를 안정적으로 만든다.
2. 강한 모델이 schema-bound JSON을 생성한다.
3. 코드가 모든 `evidence_span`을 원문에서 검증한다.

이 단계에서는 클라우드 API 모델이 빠르다. gold set이 없을 때 로컬 모델을 튜닝하는 것은 방향을 모르는 상태에서 엔진을 만지는 일이다.

### 1차 도입

Gemma 4는 다음 위치부터 붙이는 것이 좋다.

- `gemma-4-E4B-it`: 로컬 smoke test, 저비용 extraction 후보, 개인정보 민감 문서 실험
- `gemma-4-26B-A4B-it`: 로컬/사내 GPU에서 실사용 extraction 후보
- `gemma-4-31B-it`: 높은 품질의 로컬 judge 또는 튜닝 base 후보

처음부터 PDF 전체를 이미지로 넣는 방식은 피한다. 비용과 latency가 커지고, evidence span 검증이 어려워진다.

권장 입력은 이렇다.

```json
{
  "paper_id": "paper-001",
  "title": "논문 제목",
  "section": "Methods",
  "page": 4,
  "chunk_text": "PDF에서 추출한 원문 chunk"
}
```

출력은 PaperGraph schema로 고정한다.

```json
{
  "claims": [],
  "methods": [
    {
      "name": "retrieval-augmented graph construction",
      "evidence_span": "원문에 실제 존재하는 문장",
      "confidence": 0.86
    }
  ],
  "experiments": [],
  "limitations": [],
  "concepts": [],
  "relations": []
}
```

## 장점

### 로컬/사내 배포가 가능하다

PaperGraph 사용자는 논문 PDF 묶음을 넣는다. 공개 논문만 있으면 문제가 작지만, 기업 R&D 문서나 미공개 원고가 들어오면 클라우드 API 사용을 꺼릴 수 있다.

Gemma 4는 open weights라서 이 경로를 열어준다.

### 긴 문서에 유리하다

논문은 abstract만으로 끝나지 않는다. 방법, 실험 설정, ablation, limitation은 본문 여러 섹션에 흩어져 있다.

Gemma 4의 긴 context는 한 논문 안의 멀리 떨어진 정보를 함께 보게 하는 데 유리하다.

### structured extraction과 잘 맞는다

PaperGraph는 자유 답변 제품이 아니다.

정답은 JSON이어야 한다. 누락된 필드, 잘못된 enum, 원문에 없는 evidence span은 실패다. Gemma 4의 structured JSON output과 function calling 방향은 이 요구와 잘 맞는다.

## 리스크

### 평가 없이 쓰면 품질을 모른다

Gemma 4의 일반 benchmark 성능이 좋아도 PaperGraph extraction 성능을 보장하지 않는다.

PaperGraph의 eval은 별도다.

- claim recall
- method/experiment extraction F1
- limitation recall
- evidence span exact match
- relation precision
- page/section provenance completeness

이 지표가 없으면 "좋아 보임"밖에 말할 수 없다.

### PDF를 직접 이미지로 읽히는 방식은 조심해야 한다

Gemma 4는 문서 이미지 이해와 OCR capability가 있다. 그래도 PaperGraph의 첫 구현은 PDF를 텍스트와 layout token으로 분리한 뒤 모델에 넣는 방식이 낫다.

이유는 간단하다.

- evidence span 검증이 쉽다.
- page/section provenance가 유지된다.
- 같은 입력을 다시 처리해도 결과 추적이 쉽다.
- 실패 원인을 PDF 파싱 문제와 모델 추출 문제로 나눌 수 있다.

표, 그림, 수식은 나중에 multimodal path로 추가한다.

### 작은 모델은 누락이 생길 수 있다

E2B/E4B는 빠르고 싸지만, 논문에서 미묘한 limitation이나 실험 조건을 놓칠 가능성이 크다.

초기에는 E4B를 final extractor로 보지 말고, candidate generator나 routing 모델로 본다.

## 추천 도입 순서

1. 현재 `pypdf` baseline 위에 GROBID adapter를 추가한다.
2. `gpt-5.4-mini`로 schema-bound extractor를 만든다.
3. `evidence_span` verifier와 eval runner를 만든다.
4. PDF 20개로 gold set v0를 만든다.
5. 같은 gold set에서 Gemma 4 E4B, 26B, 31B를 비교한다.
6. 26B 또는 31B가 비용/프라이버시 이점 대비 충분하면 LoRA/QLoRA 튜닝을 시작한다.
7. 튜닝 모델은 cloud extractor의 대체가 아니라, `--model local-gemma4` 옵션으로 먼저 출시한다.

## 채택 기준

Gemma 4를 PaperGraph 기본값으로 올리려면 아래 기준을 통과해야 한다.

| 기준 | 최소선 |
| --- | --- |
| JSON schema valid rate | 99% 이상 |
| evidence span exact match | 95% 이상 |
| claim/method/experiment/limitation macro F1 | `gpt-5.4-mini` 대비 90% 이상 |
| relation precision | 85% 이상 |
| hallucinated evidence rate | 2% 이하 |
| 20개 PDF corpus 처리 비용 | API 대비 명확히 낮거나 프라이버시 이점이 있어야 함 |

## 지금 결정

Gemma 4는 "나중에 튜닝할 로컬/프라이빗 extractor 후보"로 둔다.

다음 구현은 Gemma 4 튜닝이 아니다. 다음 구현은 eval이다.

> 먼저 `gold/papergraph-v0.jsonl`과 `eval/papergraph-v0.yaml`을 만들고, strong model baseline과 현재 rule-based baseline을 같은 지표로 비교한다.

그다음 Gemma 4를 넣는다.

## 참고 자료

- Google Gemma 4 공식 발표: <https://blog.google/innovation-and-ai/technology/developers-tools/gemma-4/>
- Hugging Face Gemma 4 E4B 모델 카드: <https://huggingface.co/google/gemma-4-E4B>
- Hugging Face PEFT 문서: <https://huggingface.co/docs/peft/index>
- Hugging Face LoRA 문서: <https://huggingface.co/docs/peft/main/en/developer_guides/lora>
- Hugging Face TRL SFTTrainer 문서: <https://huggingface.co/docs/trl/sft_trainer>
- Hugging Face bitsandbytes/QLoRA 문서: <https://huggingface.co/docs/transformers/en/quantization/bitsandbytes>
