# 수정: status 404 (row 수=1인데 같은 id로 404)

## 로그 해석
```
persisted=True
GET .../status 404
status 조회 실패(404): video_id=... (현재 videos row 수=1)
```
"row는 1개 있는데 그 id로 못 찾는다" = **POST를 처리한 프로세스/DB와
GET을 처리한 프로세스/DB가 다르다**는 강한 신호입니다.
거의 항상 **멀티워커 + SQLite** 또는 **워커별 ephemeral 디스크** 때문입니다.

## 이번 코드 변경

### app/api/videos.py
- 조회를 `db.query(Video).filter(Video.id == vid).first()` 로 통일 (요구 5).
- video_id를 strip() 해서 공백/개행 방어 (요구 2).
- source_type(upload/youtube) 구분 없이 동일 조회 (요구 6).
- 404 시 **DB에 실제로 있는 id 목록(최대 20개)을 로그 출력** (요구 3):
  `요청 video_id=... | DB row 수=N | DB ids=[...]`

### app/database.py
- SQLite에 **WAL 모드 + busy_timeout** 적용.
  여러 워커/요청이 같은 파일을 볼 때, 한쪽이 커밋한 row를 다른 쪽이 즉시 읽게 함.
  (멀티워커 stale-read 완화)

## 재배포 후 진단 (중요)
새 로그의 `DB ids=[...]` 를 확인하세요:

- **DB ids 안에 요청한 id가 있는데도 404** -> 거의 없음(코드로 해결됨).
- **DB ids 에 요청한 id가 없고 다른 id만 있음** -> POST와 GET이 **다른 DB**를 봄.
  => 멀티워커거나 디스크가 분리됨. 아래 "확실한 해결" 적용.
- **DB ids 가 매번 다름/비어감** -> ephemeral 디스크가 초기화됨.

## 확실한 해결 (둘 중 하나, 권장순)

### A) PostgreSQL 사용 (가장 확실, 무료 플랜 가능)
```
DATABASE_URL=postgresql+psycopg://user:pass@host:5432/db
```
requirements.txt 에 추가:
```
psycopg[binary]>=3.1
```
워커 수와 무관하게 모든 프로세스가 같은 DB를 봅니다.

### B) SQLite 유지 시: 워커 1개 + 영속 디스크
- 워커 1개:
  ```
  uvicorn app.main:app --host 0.0.0.0 --port $PORT --workers 1
  ```
  (gunicorn이면 -w 1)
- Render Persistent Disk 마운트 후 그 경로로:
  ```
  DATABASE_URL=sqlite:////var/data/app.db
  ```
  (슬래시 4개 = 절대경로)

## 적용
backend/app/api/videos.py, backend/app/database.py 덮어쓰고 재배포.
SQLite를 계속 쓸 거면 **반드시 워커 1개 + 영속 디스크**를, 아니면 PostgreSQL을.
