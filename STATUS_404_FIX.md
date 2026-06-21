# 수정: YouTube 분석 후 GET /status 404

## 증상
```
POST /api/youtube/analyze 201 Created
GET  /api/videos/{id}/status 404 Not Found   <- 화면이 "살펴보고 있어요"에서 멈춤
```

## 결론 먼저
**코드 로직은 정상입니다.** 로컬에서 POST 201 직후 GET status가 200으로 동작함을
확인했습니다(분석 완료까지 정상). Render에서만 404가 난다면 원인은 **배포 환경**입니다.

## 가장 흔한 원인 2가지 (Render)

### 1) Uvicorn/Gunicorn 워커가 여러 개 + SQLite
워커가 2개 이상이면 POST를 처리한 워커와 GET을 처리한 워커가 다를 수 있고,
SQLite 파일이 공유돼도 프로세스별 커넥션/캐시 때문에 갓 만든 row를 못 볼 수 있습니다.
-> **워커를 1개로 두거나, DB를 PostgreSQL로 바꾸세요.**

start command 예:
```
uvicorn app.main:app --host 0.0.0.0 --port $PORT --workers 1
```

### 2) Ephemeral 디스크에 SQLite
Render 기본 파일시스템은 재시작 시 초기화됩니다. 배포/재시작이 끼면 row가 사라집니다.
-> **Persistent Disk를 붙이고 DATABASE_URL을 그 경로로**, 또는 PostgreSQL 사용.

PostgreSQL이 가장 확실 (무료 플랜 가능):
```
DATABASE_URL=postgresql+psycopg://user:pass@host:5432/dbname
```
(psycopg 설치 필요: requirements에 psycopg[binary] 추가)

## 이번 코드 변경 (진단 + 견고성)

### app/api/youtube.py
- row 생성 -> commit -> refresh 후, 같은 세션에서 **재조회로 영속 확인**.
- 로그: `YouTube 분석 row 생성: id=... status=... persisted=True/False`
- BackgroundTask에 **방금 만든 id를 명시적으로 전달**, 응답도 그 id 반환.

### app/api/videos.py
- status 404 시 로그에 **video_id와 현재 videos row 수**를 출력.
  `status 조회 실패(404): video_id=xxx (현재 videos row 수=N)`

### app/services/analyzer.py (확인)
- 배경 분석 실패 시 status="failed" + error_message 저장 (_mark_failed) — 이미 동작.

## 로그로 원인 진단하는 법
재배포 후 한 번 더 시도하고 Render 로그를 보세요.

- POST 직후 `persisted=True` 인데 GET에서 `row 수=0` 이면
  -> **다른 워커/다른 DB를 보고 있음** (위 원인 1 또는 2). 워커 1개 또는 Postgres로.
- `persisted=False` 면 -> commit 자체가 안 됨 (DB 권한/경로 문제).
- POST의 row 수와 GET의 row 수가 다르면 -> 워커/디스크 분리 확정.

## 적용
backend/app/api/youtube.py, backend/app/api/videos.py 덮어쓰고 재배포.
가능하면 위 "워커 1개" 또는 "PostgreSQL" 중 하나를 함께 적용하세요.
