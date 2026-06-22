# 수정: PostgreSQL에서 stage_samples_json 등 컬럼 누락 오류

## 증상
```
psycopg2.errors.UndefinedColumn:
column video_summaries.stage_samples_json does not exist
```

## 원인
기존 마이그레이션(_sqlite_auto_migrate)이 **SQLite 전용**이라,
함수 첫 줄에서 `if not sqlite: return` 으로 PostgreSQL을 건너뜀.
SQLAlchemy create_all은 "없는 테이블"만 만들고 "기존 테이블의 새 컬럼"은 추가하지 않음.
-> PG의 기존 video_summaries 테이블에 신규 컬럼이 안 생김.

## 수정 (요구사항 1~4)
### app/database.py
- 새 함수 **ensure_schema()**: DB 종류 무관(SQLite/PostgreSQL 모두) 동작.
  - SQLAlchemy `inspect(engine)`으로 기존 컬럼 조회 (PG/SQLite 공통 API).
  - 모델에 있는데 테이블에 없는 컬럼을 ALTER TABLE ADD COLUMN으로 보강.
  - **_column_ddl()**: logical 타입을 DB 방언에 맞게 변환
    - json/text -> TEXT
    - bool -> SQLite INTEGER(0/1) / PG BOOLEAN(true/false)
    - float -> SQLite FLOAT / PG DOUBLE PRECISION
    - varchar(n), int 등
- 보강 대상: stage_samples_json, structure_detail_json, engagement_factors_json,
  analysis_summary, analysis_provider, 그리고 그 이전에 추가된 모든 컬럼(누락 여부 모두 확인).
- create_all_tables()가 ensure_schema()를 호출.
- 멱등성: 이미 있으면 건너뜀(재시작 안전).
- engine.begin() 사용으로 실패 시 자동 rollback.

### app/services/analyzer.py (요구사항 5)
- _mark_failed(): commit 전에 **db.rollback()** 먼저 실행.
  DB 오류로 트랜잭션이 깨진 상태에서도 세션을 복구한 뒤 failed 상태 저장 가능.

### requirements.txt
- psycopg2-binary 명시 (PG 드라이버).

## PostgreSQL ALTER 예시 (실제 생성되는 문장)
```
ALTER TABLE video_summaries ADD COLUMN stage_samples_json TEXT DEFAULT '[]'
ALTER TABLE video_summaries ADD COLUMN structure_detail_json TEXT DEFAULT '{}'
ALTER TABLE video_summaries ADD COLUMN engagement_factors_json TEXT DEFAULT '[]'
ALTER TABLE video_summaries ADD COLUMN metadata_used BOOLEAN DEFAULT false
ALTER TABLE video_summaries ADD COLUMN confidence DOUBLE PRECISION DEFAULT 0.0
```
※ JSON 컬럼을 TEXT로 두는 이유: 코드가 json.dumps/loads로 직접 처리하기 때문.
   JSONB로 바꾸고 싶으면 _column_ddl에서 json -> "JSONB"로 변경 가능(단 모델 property도 조정 필요).

## 검증
- SQLite: 구버전 DB에 신규 컬럼 전부 자동 추가 확인.
- PostgreSQL DDL 문법 검증 (BOOLEAN/DOUBLE PRECISION/따옴표 처리).
- ensure_schema 멱등성(재호출 무에러).
- 전체 분석 흐름 정상.

## 적용
backend/app/database.py, backend/app/services/analyzer.py, requirements.txt
덮어쓰고 재배포. 앱 시작 시 자동으로 누락 컬럼이 보강됨 (수동 SQL 불필요).

재배포 로그에 "스키마 보강: ALTER TABLE video_summaries ADD COLUMN stage_samples_json ..."
가 찍히면 정상 적용된 것.
