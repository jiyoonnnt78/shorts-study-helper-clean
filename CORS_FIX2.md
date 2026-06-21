# 수정: CORS preflight 400 (Vercel preview 도메인 대응)

## 변경
CORSMiddleware를 정규식(regex) 방식으로 보강. Vercel은 배포마다 preview 도메인이
바뀌므로 목록만으로는 부족 -> allow_origin_regex로 *.vercel.app 전체를 커버.

### app/main.py
- allow_credentials=False
- allow_methods=["*"], allow_headers=["*"]
- allow_origins = CORS_ORIGINS(comma split). 비어 있고 regex가 있으면 [] (regex로 매칭),
  regex도 없으면 ["*"].
- allow_origin_regex = CORS_ORIGIN_REGEX (기본 https://.*\.vercel\.app)
- 라우터 등록보다 먼저 add_middleware 실행 (기존도 먼저였음)

### app/config.py
- CORS_ORIGIN_REGEX 설정 추가 (기본값 https://.*\.vercel\.app)

## Render 환경변수 (권장)
가장 간단하게는 둘 중 하나:
```
# 방법 1: regex로 vercel 전체 허용 (CORS_ORIGINS는 비워도 됨)
CORS_ORIGIN_REGEX=https://.*\.vercel\.app

# 방법 2: 모든 출처 허용
CORS_ORIGINS=*
```
기본값이 이미 CORS_ORIGIN_REGEX=https://.*\.vercel\.app 이므로,
환경변수를 따로 안 넣어도 vercel.app 도메인은 통과합니다.

## 검증 (OPTIONS /api/youtube/analyze)
- 운영 도메인 / preview 도메인(목록에 없는) 모두 -> 200, 정확한 origin 반영
- CORS_ORIGINS=* -> 200, allow-origin=*
- allow-methods에 OPTIONS 포함

## 적용
backend/app/main.py, backend/app/config.py 덮어쓰고 Render 재배포.
재배포 로그에 'CORS allow_origins=... allow_origin_regex=...' 가 찍히면 새 코드 적용됨.

## 그래도 400이면 (체크리스트)
1. Render가 새 커밋으로 재배포됐는지 (로그의 CORS 라인 확인)
2. 프론트가 https로 요청하는지 (http->https 리다이렉트 시 preflight 깨질 수 있음)
3. 요청 경로가 정확히 /api/youtube/analyze 인지 (끝 슬래시 redirect 주의)
