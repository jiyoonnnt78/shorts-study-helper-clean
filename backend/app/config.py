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
    # STT(whisper)는 메모리가 무거워 기본 비활성. 필요시 ENABLE_STT=true로.
    ENABLE_STT: bool = False
    WHISPER_MODEL: str = "tiny"  # tiny / base 권장
    # 한국어 형태소 분석기(Kiwi)로 명사 추출 정확도를 높인다.
    # true면 kiwipiepy 사용, 설치/실행 실패 시 자동으로 규칙 기반으로 fallback.
    ENABLE_KIWI: bool = True
    # 메타데이터 전용 분석(YouTube 링크, 영상 파일 없음)에서는 Kiwi를 건너뛸 수 있다.
    # Kiwi 모델 로드는 메모리를 크게 쓰므로, 메모리가 빠듯한 환경(예: 512MB)에서
    # 메타데이터(짧은 텍스트) 분석 시 Kiwi 없이 규칙 기반 추출만 사용하면 안정적이다.
    KIWI_FOR_METADATA_ONLY: bool = False

    # --- YouTube 링크 분석 ---
    # 링크 분석 기능 자체를 켤지. 끄면 /api/youtube/analyze가 비활성 안내를 준다.
    ENABLE_YOUTUBE: bool = True
    # 영상 파일 다운로드(yt-dlp)를 허용할지. 약관 이슈가 있어 기본 꺼짐.
    # 꺼져 있으면 제목/설명/썸네일 등 메타데이터 기반 사전 분석만 수행한다.
    ENABLE_YOUTUBE_DOWNLOAD: bool = False

    # --- RapidAPI (YouTube Video FAST Downloader 24/7) 연동 테스트용 ---
    # 키는 환경변수 RAPIDAPI_KEY로 주입 (코드/깃에 넣지 않음).
    RAPIDAPI_KEY: str = ""
    RAPIDAPI_HOST: str = "youtube-video-fast-downloader-24-7.p.rapidapi.com"
    # analyzer가 yt-dlp 대신 RapidAPI로 영상을 받게 할지 (true면 RapidAPI 사용)
    USE_RAPIDAPI_DOWNLOAD: bool = False
    RAPIDAPI_QUALITY: str = "247"
    # --- 샘플링 분석 메모리/길이 제어 (Render Free OOM 방지) ---
    SAMPLING_MAX_FRAMES: int = 4       # OCR할 프레임 수 (4~6)
    SAMPLING_MAX_DURATION: int = 0     # 이 초과 영상은 프레임 축소 (0=제한없음)

    # --- LLM 분석 (선택) ---
    # true이고 API 키가 있으면 LLM으로 더 풍부한 분석을 시도한다.
    # 키가 없거나 호출 실패 시 자동으로 규칙 기반 분석으로 fallback.
    ENABLE_LLM_ANALYSIS: bool = False
    LLM_PROVIDER: str = "openai"          # openai / anthropic (확장 가능)
    LLM_API_KEY: str = ""                  # 비어 있으면 LLM 사용 안 함
    LLM_MODEL: str = "gpt-4o-mini"         # 제공자별 모델명
    LLM_BASE_URL: str = ""                 # 커스텀/호환 엔드포인트 (비우면 기본값)
    LLM_TIMEOUT_SECONDS: int = 30

    # --- CORS ---
    # 쉼표로 구분. 개발 기본값은 Next.js dev 서버.
    CORS_ORIGINS: str = "http://localhost:3000"
    # Vercel preview 도메인 등 패턴 매칭이 필요할 때 사용 (예: https://.*\.vercel\.app)
    # 비우면 사용 안 함. CORS_ORIGINS와 함께 동작한다.
    CORS_ORIGIN_REGEX: str = r"https://.*\.vercel\.app"

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
        origins = [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]
        # 비어 있으면 모든 출처 허용 (운영에서 CORS_ORIGINS 미설정 대비)
        return origins or ["*"]


@lru_cache
def get_settings() -> Settings:
    return Settings()
