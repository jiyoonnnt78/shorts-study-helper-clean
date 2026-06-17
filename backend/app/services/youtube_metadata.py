"""
YouTube 메타데이터 provider (adapter 구조).

설계
====
- 무료 우선: YouTube Data API 키 없이도 동작하는 oEmbed를 기본 사용.
- 영상 다운로드는 별도 옵션(ENABLE_YOUTUBE_DOWNLOAD)으로 분리, 기본 꺼짐.
- 나중에 yt-dlp나 YouTube Data API를 붙이기 쉽게 MetadataProvider 인터페이스로 분리.

제공자 우선순위 (get_provider):
1. ENABLE_YOUTUBE_DOWNLOAD=true 이고 yt-dlp 설치됨 -> YtDlpProvider (제목/설명/해시태그/썸네일 풍부)
2. 그 외 -> OEmbedProvider (제목/썸네일만, 무료/무키)
3. 둘 다 실패 -> NoopProvider (video_id 기반 썸네일만)

주의: 영상 파일 다운로드는 약관 이슈가 있어 이 모듈에서 하지 않는다.
yt-dlp를 쓰더라도 메타데이터(정보)만 가져온다.
"""
from __future__ import annotations

import json
import logging
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from urllib.request import Request, urlopen
from urllib.parse import urlencode

from . import youtube_url as yu

logger = logging.getLogger("youtube_metadata")


@dataclass
class YoutubeMetadata:
    video_id: str
    title: str = ""
    description: str = ""
    hashtags: list[str] = field(default_factory=list)
    thumbnail_url: str = ""
    provider: str = "none"   # oembed / yt-dlp / noop

    def hashtags_str(self) -> str:
        return " ".join(self.hashtags)


def _extract_hashtags(text: str) -> list[str]:
    """설명/제목에서 #해시태그 추출 (중복 제거, 순서 유지)."""
    tags: list[str] = []
    for m in re.findall(r"#([0-9A-Za-z가-힣_]+)", text or ""):
        if m not in tags:
            tags.append(m)
    return tags


# ---------------------------------------------------------------------------
# 인터페이스
# ---------------------------------------------------------------------------
class MetadataProvider(ABC):
    name = "base"

    @abstractmethod
    def fetch(self, video_id: str) -> YoutubeMetadata:
        """메타데이터를 가져온다. 실패 시 예외를 올린다(호출자가 폴백)."""
        ...


# ---------------------------------------------------------------------------
# 1) oEmbed (무료, API 키 불필요) — 제목/썸네일 제공
# ---------------------------------------------------------------------------
class OEmbedProvider(MetadataProvider):
    name = "oembed"

    def fetch(self, video_id: str) -> YoutubeMetadata:
        watch = f"https://www.youtube.com/watch?v={video_id}"
        url = "https://www.youtube.com/oembed?" + urlencode(
            {"url": watch, "format": "json"}
        )
        req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        title = data.get("title", "") or ""
        return YoutubeMetadata(
            video_id=video_id,
            title=title,
            description="",  # oEmbed는 설명을 안 줌
            hashtags=_extract_hashtags(title),
            thumbnail_url=data.get("thumbnail_url") or yu.thumbnail_url(video_id),
            provider=self.name,
        )


# ---------------------------------------------------------------------------
# 2) yt-dlp (선택) — 제목/설명/해시태그/썸네일 풍부. 메타데이터만 추출.
# ---------------------------------------------------------------------------
class YtDlpProvider(MetadataProvider):
    name = "yt-dlp"

    def fetch(self, video_id: str) -> YoutubeMetadata:
        import yt_dlp  # 지연 import (미설치 환경 보호)

        watch = f"https://www.youtube.com/watch?v={video_id}"
        opts = {
            "quiet": True,
            "skip_download": True,   # 영상은 받지 않음 (정보만)
            "no_warnings": True,
            "extract_flat": False,
        }
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(watch, download=False)

        title = info.get("title", "") or ""
        desc = info.get("description", "") or ""
        tags = list(info.get("tags") or [])
        # 설명/제목의 #해시태그도 합침
        for t in _extract_hashtags(title + " " + desc):
            if t not in tags:
                tags.append(t)
        thumb = info.get("thumbnail") or yu.thumbnail_url(video_id)
        return YoutubeMetadata(
            video_id=video_id,
            title=title,
            description=desc,
            hashtags=tags,
            thumbnail_url=thumb,
            provider=self.name,
        )


# ---------------------------------------------------------------------------
# 3) Noop — 아무 외부 호출 없이 썸네일만 (오프라인/완전 실패 폴백)
# ---------------------------------------------------------------------------
class NoopProvider(MetadataProvider):
    name = "noop"

    def fetch(self, video_id: str) -> YoutubeMetadata:
        return YoutubeMetadata(
            video_id=video_id,
            title="",
            description="",
            hashtags=[],
            thumbnail_url=yu.thumbnail_url(video_id),
            provider=self.name,
        )


# ---------------------------------------------------------------------------
# provider 선택 + 폴백 체인
# ---------------------------------------------------------------------------
def _yt_dlp_available() -> bool:
    try:
        import yt_dlp  # noqa: F401
        return True
    except Exception:
        return False


def fetch_metadata(video_id: str, enable_download: bool = False) -> YoutubeMetadata:
    """
    설정에 따라 provider를 골라 메타데이터를 가져온다.
    각 provider 실패 시 다음 단계로 폴백하므로, 최소한 썸네일은 항상 반환한다.

    enable_download: True이고 yt-dlp가 있으면 yt-dlp를 먼저 시도(정보만).
                     (영상 파일 다운로드는 여기서 하지 않는다.)
    """
    providers: list[MetadataProvider] = []
    if enable_download and _yt_dlp_available():
        providers.append(YtDlpProvider())
    providers.append(OEmbedProvider())
    providers.append(NoopProvider())

    last_err: Exception | None = None
    for p in providers:
        try:
            meta = p.fetch(video_id)
            logger.info("YouTube 메타데이터 가져옴: provider=%s title=%r", p.name, meta.title[:40])
            return meta
        except Exception as e:
            last_err = e
            logger.warning("provider %s 실패 -> 다음으로 폴백: %s", p.name, e)
    # 이론상 NoopProvider에서 끝나지만 방어적으로
    logger.warning("모든 provider 실패, 빈 메타데이터 반환: %s", last_err)
    return YoutubeMetadata(video_id=video_id, thumbnail_url=yu.thumbnail_url(video_id), provider="none")
