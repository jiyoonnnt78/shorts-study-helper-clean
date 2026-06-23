# 구조/장면 분석을 OpenAI Vision이 직접 생성하도록 변경

## 문제
- 구조 분석(structure_v3)이 규칙 기반이라 실제 영상 맥락과 따로 놂.
- 핵심 장면의 role/설명 필드가 비어 있었음 (key_scenes가 문자열뿐이라 role/purpose 공백).

## 변경
Vision이 장면마다 observation/role/purpose를 직접 생성하고,
구조(오프닝/전개/하이라이트/마무리)도 Vision이 생성. 규칙 기반은 사용 안 함(폴백만).

### vision_analyzer.py (프롬프트)
- 기존 key_scenes(문자열 배열) -> scenes(구조화 객체 배열)로 변경.
- 각 scene: {at_sec, observation(실제 보이는 것), role(장면 역할), purpose(효과)}
- "일반론 금지, 실제 화면 근거" 지시 추가.
- scenes는 프레임 개수와 1:1, 시간순.
- structure의 content도 "실제로 보이는 것" 기준으로 작성하도록 강화.

### analyzer.py (_map_vision_to_summary)
- scenes 배열을 stage_samples의 observation/role/purpose에 직접 매핑.
- keep_watching에 purpose를 넣어 프론트(역할/효과)가 표시.
- key_scenes(문자열)는 구버전 폴백으로만 사용.
- structure_detail은 Vision의 structure로만 채움(규칙 기반 덮어쓰기 없음).

## 규칙 기반 제거 확인
- Vision 경로(_run_vision_analysis)는 explainer/success_analyzer(규칙기반)를
  전혀 호출하지 않음. _map_vision_to_summary만 호출.
- 규칙 기반 로직은 ANALYSIS_MODE=ocr 또는 Vision 실패 폴백에서만 동작.

## 프론트 호환
- StageSamplesCard가 observation/role/keep_watching 렌더링 -> 그대로 표시됨.
- types.ts에 role/purpose/observation 존재 -> 스키마 호환.

## 검증 (로컬, mock)
- scenes 6개 -> 각 프레임에 observation/role/purpose 정상 매핑.
- structure 4단계 Vision 생성.
- 규칙 기반 호출 없음, completed.
* 실제 Vision 품질은 배포 후 OPENAI_API_KEY로 확인.

## 변경 파일
- app/services/vision_analyzer.py
- app/services/analyzer.py
환경변수/requirements 변경 없음 (이전 Vision 전환과 동일).
