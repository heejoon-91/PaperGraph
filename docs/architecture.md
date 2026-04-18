# PaperGraph 아키텍처 설계

## 1) 파이프라인 단계

### A. PDF Parsing
- 입력: 단일 또는 다중 논문 PDF
- 출력: 문서 구조화 결과
  - 메타데이터(title, authors, year)
  - 섹션(abstract, intro, method, experiment, conclusion)
  - 문단/문장 단위 텍스트

### B. Information Extraction
- 섹션별 프롬프트 또는 규칙 기반 파서로 다음 객체 추출
  - Claim
  - Method
  - Experiment
  - Limitation
  - Concept
- 추출 시 `evidence_span`(근거 문장) 필수화 권장

### C. Graph Modeling
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

### D. Visualization
- MVP: JSON graph export + pyvis 렌더
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
  "title": "Example Paper",
  "claims": [
    {"id": "c1", "text": "Method A outperforms baseline."}
  ],
  "methods": [
    {"id": "m1", "name": "Method A"}
  ],
  "experiments": [
    {"id": "e1", "summary": "+3.2 F1 on dataset X"}
  ],
  "limitations": [
    {"id": "l1", "text": "Fails on low-resource settings"}
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
- QA 품질: 답변 + 근거 + 경로 제시 여부
- 엔지니어링: 모듈화, 테스트, 재현 가능성

