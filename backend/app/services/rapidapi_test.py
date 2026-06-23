"""
RapidAPI "YouTube Video FAST Downloader 24/7" 연동 테스트.

목적: API가 실제로 응답을 반환하는지 검증하고, 응답 JSON 구조를 파악한다.
- 기존 분석 로직(OCR/STT/Kiwi/explainer/yt-dlp)과 완전히 독립.
- 키는 환경변수 RAPIDAPI_KEY로만 주입 (코드/깃에 키를 넣지 않음).

RapidAPI Playground Code Snippet 기준 (추측 아님):
  GET /download_video/{video_id}?quality={quality}
  headers: x-rapidapi-key, x-rapidapi-host, Content-Type: application/json
"""
from __future__ import annotations

import logging
import re

import httpx

from ..config import get_settings

logger = logging.getLogger("rapidapi_test")

_YT_ID_RE = re.compile(
    r"(?:v=|/shorts/|youtu\.be/|/embed/|/v/)([A-Za-z0-9_-]{11})"
)


def extract_video_id(url: str) -> str | None:
    """YouTube URL에서 11자 video_id를 뽑는다. 이미 id면 그대로."""
    url = (url or "").strip()
    if re.fullmatch(r"[A-Za-z0-9_-]{11}", url):
        return url
    m = _YT_ID_RE.search(url)
    return m.group(1) if m else None


def call_downloader(url: str, quality: str = "247", timeout: float = 60.0) -> dict:
    """
    RapidAPI Playground의 실제 명세 그대로 호출한다 (추측 없음).

      GET /download_video/{video_id}?quality={quality}
      headers: x-rapidapi-key, x-rapidapi-host, Content-Type: application/json

    응답 JSON(또는 텍스트)을 그대로 raw_response로 반환한다.
    """
    s = get_settings()
    if not s.RAPIDAPI_KEY:
        logger.error("RAPIDAPI_KEY가 비어 있음 (환경변수 미설정)")
        return {"success": False, "error": "RAPIDAPI_KEY 환경변수가 설정되지 않았어요."}

    vid = extract_video_id(url)
    if not vid:
        logger.error("video_id 추출 실패: url=%r", url)
        return {"success": False, "error": "유효한 YouTube URL이 아니에요.", "input_url": url}

    host = s.RAPIDAPI_HOST
    path = f"/download_video/{vid}?quality={quality}"
    full_url = f"https://{host}{path}"

    headers = {
        "x-rapidapi-key": s.RAPIDAPI_KEY,
        "x-rapidapi-host": host,
        "Content-Type": "application/json",
    }

    logger.info("RapidAPI 호출 시작: GET %s (video_id=%s quality=%s)",
                full_url, vid, quality)

    try:
        with httpx.Client(timeout=timeout, headers=headers) as client:
            r = client.get(full_url)
        status = r.status_code
        text = r.text
        logger.info("RapidAPI 응답: status=%s", status)
        logger.info("RapidAPI 응답 본문(앞 1000자): %s", text[:1000])

        # JSON 우선 파싱, 실패하면 텍스트 그대로
        try:
            body = r.json()
            is_json = True
        except Exception:
            body = text
            is_json = False

        success = 200 <= status < 300
        if not success:
            logger.error("RapidAPI 비성공: status=%s url=%s", status, full_url)

        return {
            "success": success,
            "request_url": full_url,
            "status": status,
            "is_json": is_json,
            "raw_response": body,
        }

    except httpx.HTTPError as e:
        logger.error("RapidAPI 요청 오류: %s | url=%s", e, full_url, exc_info=True)
        return {
            "success": False,
            "request_url": full_url,
            "error": str(e),
        }


def get_available_quality(url: str, timeout: float = 60.0) -> dict:
    """
    영상에서 받을 수 있는 화질 목록을 조회한다 (추측 없음, 실제 명세).

      GET /get_available_quality/{video_id}?response_mode=default

    응답을 그대로 raw_response로 반환. 응답 구조를 보고 360p id를 확정한다.
    """
    s = get_settings()
    if not s.RAPIDAPI_KEY:
        logger.error("RAPIDAPI_KEY 미설정")
        return {"success": False, "error": "RAPIDAPI_KEY 환경변수가 설정되지 않았어요."}

    vid = extract_video_id(url)
    if not vid:
        logger.error("video_id 추출 실패: %r", url)
        return {"success": False, "error": "유효한 YouTube URL이 아니에요.", "input_url": url}

    host = s.RAPIDAPI_HOST
    path = f"/get_available_quality/{vid}?response_mode=default"
    full_url = f"https://{host}{path}"
    headers = {
        "x-rapidapi-key": s.RAPIDAPI_KEY,
        "x-rapidapi-host": host,
        "Content-Type": "application/json",
    }

    logger.info("화질 목록 조회 시작: GET %s (video_id=%s)", full_url, vid)
    try:
        with httpx.Client(timeout=timeout, headers=headers) as client:
            r = client.get(full_url)
        status = r.status_code
        text = r.text
        logger.info("화질 목록 응답: status=%s", status)
        logger.info("화질 목록 본문(앞 1500자): %s", text[:1500])
        try:
            body = r.json()
            is_json = True
        except Exception:
            body = text
            is_json = False
        return {
            "success": 200 <= status < 300,
            "request_url": full_url,
            "status": status,
            "is_json": is_json,
            "raw_response": body,
        }
    except httpx.HTTPError as e:
        logger.error("화질 목록 조회 오류: %s | url=%s", e, full_url, exc_info=True)
        return {"success": False, "request_url": full_url, "error": str(e)}
