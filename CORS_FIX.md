# 수정: Vercel 프론트 -> Render 백엔드 CORS preflight 400 해결

## 증상
```
OPTIONS /api/youtube/analyze HTTP/1.1 400 Bad Request
```
CORS_ORIGINS=* 를 넣어도 preflight(OPTIONS)가 400.

## 원인 (두 가지가 겹침)
1. allow_methods에 OPTIONS가 없었음 (["GET","POST","DELETE"]만 허용)
   -> preflight의 OPTIONS 메서드가 막혀 400.
2. allow_credentials=True 와 allow_origins=["*"] 충돌
   -> 와일드카드 + credentials는 브라우저가 거부.

## 수정 (2개 파일)

### app/main.py
- CORS 미들웨어를 라우터 등록보다 먼저 적용 (기존도 먼저였지만 명확화).
- CORS_ORIGINS를 comma split, 비어 있으면 ["*"].
- allow_methods=["*"], allow_headers=["*"].
- allow_origins=["*"]이면 allow_credentials=False (충돌 방지).
  특정 출처를 지정하면 credentials=True 허용(쿠키 인증 확장 대비).

### app/config.py
- cors_origin_list가 빈 값일 때 ["*"]를 반환하도록 보강.

## 검증
- OPTIONS /api/youtube/analyze -> 200 OK (와일드카드/특정출처/빈값 모두)
- allow-methods 응답에 OPTIONS 포함
- 실제 POST 응답에도 access-control-allow-origin 헤더 정상

## Render 환경변수 권장 설정
와일드카드 대신 정확한 프론트 주소를 쓰는 걸 권장합니다(더 안전):
```
CORS_ORIGINS=https://shorts-study-helper-clean.vercel.app
```
여러 개면 콤마로:
```
CORS_ORIGINS=https://shorts-study-helper-clean.vercel.app,http://localhost:3000
```
* 로 둬도 동작하지만, 이 경우 credentials는 자동으로 꺼집니다.

## 적용
backend/app/main.py, backend/app/config.py 를 덮어쓰고 Render 재배포(또는 재시작).
