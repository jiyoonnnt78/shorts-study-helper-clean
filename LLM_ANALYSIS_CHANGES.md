# LLM 분석 adapter 추가 (선택형)

기존 무료·규칙 기반 분석을 기본으로 유지하면서, 선택적으로 외부 LLM을 붙여
더 풍부한 분석(요약·구성·몰입 요소·맞춤 제작 팁)을 받을 수 있게 했습니다.

## 동작
- 기본값: **규칙 기반(무료)**. `ENABLE_LLM_ANALYSIS=false`.
- LLM 켜고 API 키가 있으면: 지정한 JSON 스키마로 LLM 분석을 받아 사용.
- 키 없음·타임아웃·파싱 실패 시: **자동으로 규칙 기반으로 fallback** (분석은 항상 완료).
- 두 경로 모두 같은 결과 형태(AnalysisResult)를 반환 → 프론트는 동일하게 렌더링.

## 출력(요구 스키마)
summary, topic, structure(opening/development/climax/ending {content,purpose}),
hook_analysis(hook_type,hook_strength,reason), engagement_factors,
success_pattern, creator_tips(최소 5개, 서로 다른 전략, 일반론 금지).

규칙 기반도 structure_detail(opening/development/climax/ending)과 맞춤 creator_tips를
동일 형태로 생성하므로, LLM 없이도 화면 구성은 같습니다.

## 변경 파일

### 백엔드 — 신규
- `app/services/analysis_provider.py` : Provider adapter (RuleBased/LLM) + 프롬프트 + 파싱/fallback

### 백엔드 — 수정
- `app/config.py` : ENABLE_LLM_ANALYSIS, LLM_PROVIDER/API_KEY/MODEL/BASE_URL/TIMEOUT 추가
- `app/models.py` : analysis_summary, engagement_factors_json, structure_detail_json, analysis_provider 추가
- `app/database.py` : 위 컬럼 마이그레이션 + videos 원본 컬럼(duration 등) 보강
- `app/schemas.py` : SummaryOut에 analysis_summary/engagement_factors/structure_detail/analysis_provider + StructureDetailOut
- `app/api/videos.py` : 신규 필드 응답 매핑
- `app/services/explainer.py` : provider adapter 호출로 분석 생성
- `app/services/success_analyzer.py` : creator_tips를 훅×카테고리×주제 맞춤형으로 재작성 + structure_detail 빌더 + AnalysisResult 변환기
- `.env.example` : LLM 설정 문서화

### 프론트엔드 — 신규
- `src/components/StructureDetailCard.tsx` : 오프닝/전개/킬링파트/마무리 content+purpose 카드

### 프론트엔드 — 수정
- `src/lib/types.ts` : StructureDetail 등 타입 추가
- `src/app/videos/[id]/page.tsx` : 구성 분석·몰입 요소 카드 배치
- `src/components/SummaryCard.tsx` : LLM 요약문 표시

## LLM 켜는 법
```
# backend/.env
ENABLE_LLM_ANALYSIS=true
LLM_PROVIDER=openai          # 또는 anthropic
LLM_API_KEY=sk-...
LLM_MODEL=gpt-4o-mini        # anthropic이면 claude-3-5-haiku-latest 등
```
서버 재시작만 하면 됩니다. 끄면(기본) 추가 비용 없이 규칙 기반으로 동작합니다.

## 검증 완료
- 규칙 기반: structure_detail 4단계 + 맞춤 creator_tips 5개+ (일반론 없음) 생성
- LLM: 응답 파싱·hook_type 매핑·structure_detail 추출 정상
- 키 없음/호출 실패 → 규칙 기반 자동 fallback
- 구버전 DB 마이그레이션(신규 컬럼 + duration 등 보강)
- 프론트 빌드 통과
