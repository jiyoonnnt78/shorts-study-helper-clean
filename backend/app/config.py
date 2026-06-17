"""
앱 설정.

- 모든 비밀값/환경 의존 값은 환경변수로만 관리한다.
- 프론트엔드에는 어떤 비밀값도 전달하지 않는다.
"""
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- DB ---
    # 개발: SQLite / 운영: PostgreSQL URL로 교체 가능 (예: postgresql+psycopg://user:pw@host/db)
    DATABASE_URL: str = "sqlite:///./data/app.db"

    # --- 저장소 ---
    MEDIA_ROOT: str = "./media"
    # 브라우저가 캡쳐 이미지를 가져올 때 쓰는 공개 URL prefix
    PUBLIC_MEDIA_URL: str = "/media"

    # --- 업로드 제한 ---
    MAX_UPLOAD_MB: int = 100
    MAX_VIDEO_DURATION_SECONDS: int = 60

    # --- 분석 옵션 ---
    ENABLE_OCR: bool = True
    ENABLE_STT: bool = True
    WHISPER_MODEL: str = "tiny"  # tiny / base 권장
    # 한국어 형태소 분석기(Kiwi)로 명사 추출 정확도를 높인다.
    # true면 kiwipiepy 사용, 설치/실행 실패 시 자동으로 규칙 기반으로 fallback.
    ENABLE_KIWI: bool = True

    # --- YouTube 링크 분석 ---
    # 링크 분석 기능 자체를 켤지. 끄면 /api/youtube/analyze가 비활성 안내를 준다.
    ENABLE_YOUTUBE: bool = True
    # 영상 파일 다운로드(yt-dlp)를 허용할지. 약관 이슈가 있어 기본 꺼짐.
    # 꺼져 있으면 제목/설명/썸네일 등 메타데이터 기반 사전 분석만 수행한다.
    ENABLE_YOUTUBE_DOWNLOAD: bool = False

    # --- CORS ---
    # 쉼표로 구분. 개발 기본값은 Next.js dev 서버.
    CORS_ORIGINS: str = "http://localhost:3000"

    # ----- 파생 값 -----
    @property
    def media_root_path(self) -> Path:
        return Path(self.MEDIA_ROOT).resolve()

    @property
    def videos_dir(self) -> Path:
        return self.media_root_path / "videos"

    @property
    def frames_dir(self) -> Path:
        return self.media_root_path / "frames"

    @property
    def max_upload_bytes(self) -> int:
        return self.MAX_UPLOAD_MB * 1024 * 1024

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
