# PaperGraph 아키텍처 설계

## 1) 파이프라인 단계

### A. 문서 파싱
- MVP 입력: 단일 또는 다중 `.pdf`, `.md`, `.txt` 논문 파일
- PDF 입력은 `pypdf`로 페이지별 텍스트를 추출한다.
- `.md`/`.txt` 입력은 marker 기반 테스트와 수동 전처리 입력으로 사용한다.
- 출력: 문서 구조화 결과
  - 메타데이터(title, authors, year)
  - 섹션(abstract, intro, method, experiment, conclusion)
  - 문단/문장 단위 텍스트

### B. 정보 추출
- 섹션별 프롬프트 또는 규칙 기반 파서로 다음 객체 추출
  - Claim
  - Method
  - Experiment
  - Limitation
  - Concept
- 추출 시 `evidence_span`(근거 문장) 필수화 권장
- 현재 기준 추출기는 `주장:`, `방법:`, `실험:`, `결과:`, `한계:`, `개념:` marker를 인식한다.
- 호환성을 위해 `Claim:`, `Method:`, `Experiment:`, `Result:`, `Limitation:`, `Concept:` marker도 인식한다.
- marker가 없는 PDF는 섹션 제목을 기준으로 초록, 방법, 실험/결과, 한계를 추정한다.

### C. 그래프 모델링
- 노드 타입
  - Paper
  - Claim
  - Method
  - Experiment
  - Limitation
  - Concept
- 엣지 타입
  - `paper_has_claim`
  - `paper_uses_method`
  - `paper_reports_experiment`
  - `paper_has_limitation`
  - `supports` / `contradicts`
  - `uses` / `compares_with`
  - `limited_by`

### D. 시각화와 내보내기
- MVP: JSON graph export + 근거 매트릭스 CSV + 평가 Markdown
- 확장: pyvis 렌더
- 확장: 웹 UI(cytoscape.js) 필터링(연도/도메인/키워드)

### E. QA
- 질문 의도 분류 예시
  - 방법 비교
  - 성능 근거 확인
  - 한계 요약
- 응답 포맷
  - 짧은 답
  - 근거 문장
  - 관련 노드/엣지

---

## 2) 데이터 계약 (JSON 예시)

```json
{
  "paper_id": "paper-001",
  "title": "예시 논문",
  "claims": [
    {"id": "c1", "text": "방법 A가 기준선보다 좋은 성능을 낸다."}
  ],
  "methods": [
    {"id": "m1", "name": "방법 A"}
  ],
  "experiments": [
    {"id": "e1", "summary": "데이터셋 X에서 F1이 3.2 상승했다."}
  ],
  "limitations": [
    {"id": "l1", "text": "저자원 환경에서는 실패한다."}
  ],
  "concepts": [
    {"id": "k1", "name": "GraphRAG"}
  ],
  "relations": [
    {"source": "m1", "target": "k1", "type": "uses"}
  ]
}
```

---

## 3) 포트폴리오 평가 포인트

- 파싱 정확도: 섹션 분리/참조 제거 품질
- 추출 품질: 사실성, 근거 연결성
- 그래프 품질: 관계 타입 일관성, 중복 정규화
- 그래프 빌더는 중복 노드 ID와 존재하지 않는 관계 endpoint를 오류로 처리
- QA 품질: 답변 + 근거 + 경로 제시 여부
- 엔지니어링: 모듈화, 테스트, 재현 가능성

