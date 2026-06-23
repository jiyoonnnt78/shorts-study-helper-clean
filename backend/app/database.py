"""
DB 연결.

- 개발: SQLite (DATABASE_URL 기본값)
- 운영: DATABASE_URL만 PostgreSQL로 바꾸면 동작하도록 설계
"""
from pathlib import Path
import logging

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import get_settings

settings = get_settings()

logger = logging.getLogger("database")

# SQLite 파일 경로가 있으면 폴더를 먼저 만들어준다.
if settings.DATABASE_URL.startswith("sqlite"):
    db_path = settings.DATABASE_URL.split("///")[-1]
    if db_path and db_path != ":memory:":
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)

# SQLite는 멀티스레드(배경 분석 작업)에서 쓰기 위해 check_same_thread=False 필요
connect_args = {"check_same_thread": False} if settings.DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(settings.DATABASE_URL, connect_args=connect_args, pool_pre_ping=True)

# SQLite: 여러 워커/요청이 같은 파일을 볼 때, 한 요청에서 커밋한 row를
# 다른 요청이 즉시 읽도록 WAL 모드 + 짧은 busy timeout을 설정한다.
# (멀티워커 환경에서 "방금 만든 row가 다른 요청에서 404" 문제를 줄인다.)
if settings.DATABASE_URL.startswith("sqlite"):
    from sqlalchemy import event

    @event.listens_for(engine, "connect")
    def _sqlite_pragmas(dbapi_conn, _record):  # noqa: ANN001
        cur = dbapi_conn.cursor()
        try:
            cur.execute("PRAGMA journal_mode=WAL")
            cur.execute("PRAGMA synchronous=NORMAL")
            cur.execute("PRAGMA busy_timeout=5000")
        finally:
            cur.close()

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def get_db():
    """FastAPI dependency: 요청 단위 세션."""
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_all_tables() -> None:
    from . import models  # noqa: F401  (모델 등록)

    Base.metadata.create_all(bind=engine)
    ensure_schema()


# 새로 추가된 컬럼들의 "DB 중립" 정의.
# 타입은 logical 이름으로 두고, DB 방언에 맞게 _column_ddl()에서 변환한다.
#   text   : 긴 문자열 (SQLite TEXT / PG TEXT)
#   json   : JSON 문자열 저장용 TEXT (양쪽 다 TEXT로 저장 — 코드가 json.dumps/loads로 처리)
#   bool   : SQLite INTEGER(0/1) / PG BOOLEAN
#   int / float / varchar(n)
_SCHEMA_ADDITIONS: dict[str, dict[str, tuple[str, str | None]]] = {
    "videos": {
        "duration": ("float", None),
        "width": ("int", None),
        "height": ("int", None),
        "fps": ("float", None),
        "aspect_ratio": ("varchar(50)", None),
        "error_message": ("text", None),
        "source_type": ("varchar(20)", "upload"),
        "source_url": ("text", None),
        "youtube_video_id": ("varchar(20)", None),
        "youtube_title": ("text", None),
        "youtube_description": ("text", None),
        "youtube_hashtags": ("text", None),
        "youtube_thumbnail_url": ("text", None),
    },
    "video_summaries": {
        "purpose": ("text", ""),
        "difficulty": ("varchar(20)", "보통"),
        "recommended_audience_json": ("json", "[]"),
        "try_points_json": ("json", "[]"),
        "caution_points_json": ("json", "[]"),
        "category": ("varchar(30)", "기타"),
        "confidence": ("float", "0.0"),
        "confidence_reason": ("text", ""),
        "detected_keywords_json": ("json", "[]"),
        "primary_source": ("varchar(20)", "none"),
        "source_weights_json": ("json", "{}"),
        "metadata_used": ("bool", "false"),
        "metadata_keywords_json": ("json", "[]"),
        "hook_type": ("varchar(40)", ""),
        "hook_reason": ("text", ""),
        "hook_strength": ("int", "0"),
        "hook_summary": ("text", ""),
        "hook_improvement_tip": ("text", ""),
        "structure_json": ("json", "[]"),
        "success_patterns_json": ("json", "[]"),
        "creator_tips_json": ("json", "[]"),
        "analysis_summary": ("text", ""),
        "engagement_factors_json": ("json", "[]"),
        "structure_detail_json": ("json", "{}"),
        "analysis_provider": ("varchar(20)", "rule"),
        "stage_samples_json": ("json", "[]"),
    },
}


def _column_ddl(logical_type: str, default: str | None, is_sqlite: bool) -> str:
    """logical 타입 정의를 현재 DB 방언의 ALTER 절로 변환한다."""
    t = logical_type.lower()
    if t == "json" or t == "text":
        sql_type = "TEXT"
    elif t == "bool":
        sql_type = "INTEGER" if is_sqlite else "BOOLEAN"
    elif t == "int":
        sql_type = "INTEGER"
    elif t == "float":
        sql_type = "DOUBLE PRECISION" if not is_sqlite else "FLOAT"
    elif t.startswith("varchar"):
        sql_type = t.upper()
    else:
        sql_type = "TEXT"

    ddl = sql_type
    if default is not None:
        if t == "bool":
            # SQLite는 0/1, PG는 true/false
            val = ("0" if default in ("false", "0", "") else "1") if is_sqlite else default
            ddl += f" DEFAULT {val}"
        elif t in ("int", "float"):
            ddl += f" DEFAULT {default}"
        else:
            # 문자열/JSON 기본값은 따옴표로 감싼다 (작은따옴표 이스케이프)
            safe = default.replace("'", "''")
            ddl += f" DEFAULT '{safe}'"
    return ddl


def ensure_schema() -> None:
    """
    DB 종류(SQLite/PostgreSQL)에 무관하게, 모델에 새로 생긴 컬럼이
    실제 테이블에 없으면 ALTER TABLE ADD COLUMN으로 채운다.

    - SQLAlchemy Inspector로 기존 컬럼을 조회하므로 PG/SQLite 모두 동작.
    - 운영(PostgreSQL)에서도 앱 시작 시 누락 컬럼을 자동 보강한다.
    """
    from sqlalchemy import inspect, text

    is_sqlite = settings.DATABASE_URL.startswith("sqlite")
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())

    with engine.begin() as conn:  # begin() = 자동 commit/rollback
        for table, cols in _SCHEMA_ADDITIONS.items():
            if table not in existing_tables:
                continue  # create_all이 최신 스키마로 새로 만들었음
            existing_cols = {c["name"] for c in inspector.get_columns(table)}
            for name, (logical_type, default) in cols.items():
                if name in existing_cols:
                    continue
                ddl = _column_ddl(logical_type, default, is_sqlite)
                logger.info("스키마 보강: ALTER TABLE %s ADD COLUMN %s %s", table, name, ddl)
                conn.execute(text(f'ALTER TABLE {table} ADD COLUMN {name} {ddl}'))

    # SQLite 전용: 기존 videos.file_path NOT NULL 제약 해제 (PG는 불필요)
    if is_sqlite:
        _relax_videos_not_null()


def _sqlite_auto_migrate() -> None:
    """하위호환 별칭 (기존 호출처가 있을 경우)."""
    ensure_schema()


def _relax_videos_not_null() -> None:
    """
    YouTube 링크 분석은 영상 파일이 없어 file_path/stored_filename이 NULL이다.
    기존 SQLite DB의 videos 테이블이 이 컬럼을 NOT NULL로 만들었다면 INSERT가 실패하므로,
    NOT NULL 제약을 가진 경우에만 테이블을 재생성해 제약을 푼다.
    데이터는 그대로 보존한다.
    """
    if not settings.DATABASE_URL.startswith("sqlite"):
        return
    from sqlalchemy import text

    with engine.connect() as conn:
        info = list(conn.execute(text("PRAGMA table_info(videos)")))
        if not info:
            return  # 테이블 없음 (create_all이 새 스키마로 생성)
        # PRAGMA table_info: (cid, name, type, notnull, dflt_value, pk)
        notnull = {row[1]: row[3] for row in info}
        needs_fix = notnull.get("file_path") == 1 or notnull.get("stored_filename") == 1
        if not needs_fix:
            return

        cols = [row[1] for row in info]
        col_list = ", ".join(cols)
        # 외래키 체크를 잠시 끄고 안전하게 테이블 교체
        conn.execute(text("PRAGMA foreign_keys=OFF"))
        try:
            conn.execute(text("ALTER TABLE videos RENAME TO videos_old"))
            # 새 스키마(현재 모델 기준, file_path/stored_filename nullable)로 재생성
            Base.metadata.tables["videos"].create(bind=conn)
            # 공통 컬럼만 복사. 구버전에서 NULL이던 필수 컬럼은 기본값으로 채운다.
            new_cols = {c.name for c in Base.metadata.tables["videos"].columns}
            copy_cols = [c for c in cols if c in new_cols]
            # SELECT 시 일부 컬럼은 NULL 방어 (구 데이터 호환)
            now_expr = "CURRENT_TIMESTAMP"
            select_exprs = []
            for c in copy_cols:
                if c in ("created_at", "updated_at"):
                    select_exprs.append(f"COALESCE({c}, {now_expr})")
                elif c == "source_type":
                    select_exprs.append(f"COALESCE({c}, 'upload')")
                else:
                    select_exprs.append(c)
            copy_list = ", ".join(copy_cols)
            select_list = ", ".join(select_exprs)
            conn.execute(
                text(f"INSERT INTO videos ({copy_list}) SELECT {select_list} FROM videos_old")
            )
            conn.execute(text("DROP TABLE videos_old"))
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.execute(text("PRAGMA foreign_keys=ON"))
