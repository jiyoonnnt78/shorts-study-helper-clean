# 수정: YouTube 분석 시 file_path NOT NULL 오류 해결

## 증상
```
sqlite3.IntegrityError: NOT NULL constraint failed: videos.file_path
```
YouTube 링크 분석은 영상 파일을 저장하지 않아 file_path가 NULL인데,
기존 SQLite DB의 videos 테이블이 file_path를 NOT NULL로 만들어 INSERT가 실패.

## 원인
모델에서 file_path를 nullable로 바꿔도, **이미 NOT NULL로 생성된 기존 테이블**에는
반영되지 않음. SQLite는 ALTER COLUMN을 지원하지 않아 컬럼 제약을 직접 못 바꿈.

## 수정 파일 (3개)

### 1. app/models.py
- `Video.stored_filename`을 `nullable=True`로 변경 (file_path는 이미 nullable이었음)

### 2. app/database.py
- `_relax_videos_not_null()` 추가: 기존 videos 테이블이 file_path/stored_filename에
  NOT NULL 제약을 가진 경우에만 테이블을 재생성해 제약을 해제.
  데이터는 보존하며, NULL이던 필수 컬럼(created_at/updated_at/source_type)은 기본값으로 채움.
- video_summaries 마이그레이션에 초기 스키마 컬럼(purpose/difficulty 등) 보강(견고성).

### 3. app/api/youtube.py
- YouTube 분석 시 `stored_filename=None`으로 명시 (기존 `""` → `None`).

## 동작
- 새 DB: 처음부터 file_path/stored_filename nullable로 생성됨.
- 기존 DB: 서버 시작 시 자동으로 NOT NULL 제약 해제(데이터 보존).
- `source_type="youtube"` + file_path 없음 → analyzer가 메타데이터 전용 분석 수행.
- 기존 업로드 분석은 그대로 동작.

## 검증 완료
- 기존 NOT NULL DB로 마이그레이션 → 제약 해제 + 기존 데이터 보존 확인
- POST /api/youtube/analyze → **201** 성공 + 분석 완료 확인
- 새 DB 생성 + 업로드 경로 회귀(분석/삭제) 정상

## 적용 방법
아래 3개 파일을 덮어쓰고 서버를 재시작하면 됩니다. 별도 마이그레이션 명령 불필요
(서버 시작 시 자동). 기존 data/app.db는 그대로 두어도 됩니다.
```
backend/app/models.py
backend/app/database.py
backend/app/api/youtube.py
```
