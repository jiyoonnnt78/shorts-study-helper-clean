"""
YouTube URL 파싱.

지원 형식:
- https://www.youtube.com/shorts/VIDEOID
- https://youtube.com/shorts/VIDEOID?feature=share
- https://www.youtube.com/watch?v=VIDEOID
- https://youtu.be/VIDEOID
- https://m.youtube.com/watch?v=VIDEOID
"""
from __future__ import annotations

import re
from urllib.parse import urlparse, parse_qs

# YouTube video_id는 보통 11자 (영문/숫자/-/_)
_VIDEO_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")


def extract_video_id(url: str) -> str | None:
    """
    다양한 YouTube URL에서 video_id(11자)를 뽑는다.
    실패하면 None.
    """
    if not url or not isinstance(url, str):
        return None
    url = url.strip()

    # 스킴 없으면 붙여서 파싱 가능하게
    if not re.match(r"^https?://", url, re.IGNORECASE):
        url = "https://" + url

    try:
        parsed = urlparse(url)
    except ValueError:
        return None

    host = (parsed.hostname or "").lower().removeprefix("www.").removeprefix("m.")
    path = parsed.path or ""

    # youtu.be/VIDEOID
    if host == "youtu.be":
        candidate = path.lstrip("/").split("/")[0]
        return candidate if _VIDEO_ID_RE.match(candidate) else None

    if host not in ("youtube.com", "youtube-nocookie.com"):
        return None

    # /shorts/VIDEOID  또는 /embed/VIDEOID  또는 /v/VIDEOID
    m = re.match(r"^/(shorts|embed|v)/([A-Za-z0-9_-]{11})", path)
    if m:
        return m.group(2)

    # /watch?v=VIDEOID
    if path == "/watch":
        vid = parse_qs(parsed.query).get("v", [None])[0]
        if vid and _VIDEO_ID_RE.match(vid):
            return vid

    return None


def is_youtube_url(url: str) -> bool:
    return extract_video_id(url) is not None


def canonical_shorts_url(video_id: str) -> str:
    return f"https://www.youtube.com/shorts/{video_id}"


def thumbnail_url(video_id: str) -> str:
    """API 없이 쓸 수 있는 공개 썸네일 URL (항상 존재하는 hqdefault)."""
    return f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"
