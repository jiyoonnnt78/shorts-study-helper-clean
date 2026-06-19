"""
DB 연결.

- 개발: SQLite (DATABASE_URL 기본값)
- 운영: DATABASE_URL만 PostgreSQL로 바꾸면 동작하도록 설계
"""
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import get_settings

settings = get_settings()

# SQLite 파일 경로가 있으면 폴더를 먼저 만들어준다.
if settings.DATABASE_URL.startswith("sqlite"):
    db_path = settings.DATABASE_URL.split("///")[-1]
    if db_path and db_path != ":memory:":
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)

# SQLite는 멀티스레드(배경 분석 작업)에서 쓰기 위해 check_same_thread=False 필요
connect_args = {"check_same_thread": False} if settings.DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(settings.DATABASE_URL, connect_args=connect_args, pool_pre_ping=True)

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
    _sqlite_auto_migrate()


def _sqlite_auto_migrate() -> None:
    """
    개발용(SQLite) 미니 마이그레이션:
    기존 DB에 새로 추가된 컬럼이 없으면 ALTER TABLE로 채워준다.
    운영(PostgreSQL)에서는 Alembic 같은 정식 마이그레이션 도구 사용을 권장.
    """
    if not settings.DATABASE_URL.startswith("sqlite"):
        return
    from sqlalchemy import text

    additions = {
        "videos": {
            "source_type": "VARCHAR(20) DEFAULT 'upload'",
            "source_url": "TEXT",
            "youtube_video_id": "VARCHAR(20)",
            "youtube_title": "TEXT",
            "youtube_description": "TEXT",
            "youtube_hashtags": "TEXT",
            "youtube_thumbnail_url": "TEXT",
        },
        "video_summaries": {
            "purpose": "TEXT DEFAULT ''",
            "difficulty": "VARCHAR(20) DEFAULT '보통'",
            "recommended_audience_json": "TEXT DEFAULT '[]'",
            "try_points_json": "TEXT DEFAULT '[]'",
            "caution_points_json": "TEXT DEFAULT '[]'",
            "category": "VARCHAR(30) DEFAULT '기타'",
            "confidence": "FLOAT DEFAULT 0.0",
            "confidence_reason": "TEXT DEFAULT ''",
            "detected_keywords_json": "TEXT DEFAULT '[]'",
            "primary_source": "VARCHAR(20) DEFAULT 'none'",
            "source_weights_json": "TEXT DEFAULT '{}'",
            "metadata_used": "BOOLEAN DEFAULT 0",
            "metadata_keywords_json": "TEXT DEFAULT '[]'",
            "hook_type": "VARCHAR(40) DEFAULT ''",
            "hook_reason": "TEXT DEFAULT ''",
            "hook_strength": "INTEGER DEFAULT 0",
            "structure_json": "TEXT DEFAULT '[]'",
            "success_patterns_json": "TEXT DEFAULT '[]'",
            "creator_tips_json": "TEXT DEFAULT '[]'",
        },
    }
    with engine.connect() as conn:
        for table, cols in additions.items():
            existing = {row[1] for row in conn.execute(text(f"PRAGMA table_info({table})"))}
            if not existing:
                continue  # 테이블이 없으면 create_all이 새 스키마로 만들었음
            for name, ddl in cols.items():
                if name not in existing:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}"))
        conn.commit()

    # 기존 DB의 videos.file_path / stored_filename NOT NULL 제약 해제.
    # (SQLite는 ALTER COLUMN을 지원하지 않으므로 필요 시 테이블을 재생성한다.)
    _relax_videos_not_null()


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
