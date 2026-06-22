"""
RapidAPI 연동 테스트 전용 라우터.

기존 분석 API와 독립. API가 실제 응답을 반환하는지 검증하는 용도.
- GET  /api/test/downloader?url=...   (브라우저에서 바로 확인 가능)
- POST /api/test/downloader  {"url": "..."}
"""
from __future__ import annotations

import logging

from fastapi import APIRouter
from pydantic import BaseModel

from ..services.rapidapi_test import call_downloader, extract_video_id

logger = logging.getLogger("test_api")

router = APIRouter(prefix="/api/test", tags=["test"])


class DownloaderRequest(BaseModel):
    url: str


@router.get("/downloader")
def test_downloader_get(url: str):
    """브라우저에서 ?url=... 로 바로 테스트."""
    logger.info("테스트 요청(GET): url=%s", url)
    result = call_downloader(url)
    return result


@router.post("/downloader")
def test_downloader_post(body: DownloaderRequest):
    """JSON 바디로 테스트."""
    logger.info("테스트 요청(POST): url=%s", body.url)
    result = call_downloader(body.url)
    return result


@router.get("/downloader/ping")
def ping():
    """키/호스트 설정 여부만 빠르게 확인 (키 값은 노출하지 않음)."""
    from ..config import get_settings
    s = get_settings()
    return {
        "rapidapi_key_set": bool(s.RAPIDAPI_KEY),
        "rapidapi_host": s.RAPIDAPI_HOST,
        "sample_video_id": extract_video_id(
            "https://www.youtube.com/watch?v=jNQXAC9IVRw"
        ),
    }
