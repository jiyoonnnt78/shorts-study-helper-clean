"""
YouTube 영상 다운로드 (yt-dlp adapter).

목적: 4구간 샘플링 OCR을 위해 영상을 받되, 메모리·시간 부담을 최소화한다.
- 저화질(360p 이하) 단일 파일로 받아 용량/디스크 절약.
- STT/torch/whisper와 무관. OCR용 프레임 추출만을 위한 다운로드.
- 다운로드 자체가 실패하면 호출자가 메타데이터 전용으로 폴백한다.

주의: 영상 다운로드는 약관 이슈가 있어 ENABLE_YOUTUBE_DOWNLOAD=true일 때만 호출되어야 한다.
"""
from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger("youtube_download")


def yt_dlp_available() -> bool:
    try:
        import yt_dlp  # noqa: F401
        return True
    except Exception:
        return False


def download_video(video_id: str, dest_dir: Path, timeout: int = 25) -> str | None:
    """
    video_id 영상을 저화질로 dest_dir에 받아 파일 경로를 반환. 실패하면 None.

    - format: 360p 이하 mp4 우선 (작고 빠름)
    - 짧은 쇼츠 대상이므로 보통 수 MB.
    """
    if not yt_dlp_available():
        logger.warning("yt-dlp 미설치 -> 영상 다운로드 불가")
        return None

    import yt_dlp

    dest_dir.mkdir(parents=True, exist_ok=True)
    out_tmpl = str(dest_dir / f"{video_id}.%(ext)s")
    url = f"https://www.youtube.com/watch?v={video_id}"

    opts = {
        "outtmpl": out_tmpl,
        "format": "best[height<=360][ext=mp4]/best[height<=480]/best",
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "socket_timeout": timeout,
        # 메모리/시간 절약: 자막·썸네일·메타파일 따로 받지 않음
        "writesubtitles": False,
        "writethumbnail": False,
        "writeinfojson": False,
    }
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            # 실제 저장된 파일 경로
            path = ydl.prepare_filename(info)
        p = Path(path)
        if p.exists() and p.stat().st_size > 0:
            logger.info("영상 다운로드 완료: %s (%.1fMB)", p.name, p.stat().st_size / 1e6)
            return str(p)
        # 확장자가 바뀌었을 수 있으니 폴더에서 탐색
        for f in dest_dir.glob(f"{video_id}.*"):
            if f.suffix.lower() in (".mp4", ".webm", ".mkv") and f.stat().st_size > 0:
                return str(f)
        logger.warning("다운로드 후 파일을 찾지 못함: %s", video_id)
        return None
    except Exception:
        logger.warning("영상 다운로드 실패: %s", video_id, exc_info=True)
        return None
