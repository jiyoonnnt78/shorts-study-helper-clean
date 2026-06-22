"""
RapidAPI "YouTube Video FAST Downloader 24/7" 연동 테스트.

목적: API가 실제로 응답을 반환하는지 검증하고, 응답 JSON 구조를 파악한다.
- 기존 분석 로직(OCR/STT/Kiwi/explainer/yt-dlp)과 완전히 독립.
- 키는 환경변수 RAPIDAPI_KEY로만 주입 (코드/깃에 키를 넣지 않음).

이 다운로더류 API는 보통 다음 중 하나의 패턴을 쓴다:
  (A) video_id를 받아 포맷 목록/다운로드 URL을 한 번에 반환
  (B) 1단계: 영상 정보 조회 -> 2단계: 특정 포맷 다운로드 URL 획득
서비스마다 경로가 달라서, 후보 엔드포인트를 순서대로 시도하고
"처음으로 성공(2xx)한 응답"을 그대로 반환한다. 실제 응답을 보고 다음 단계를 확정한다.
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


def _headers() -> dict:
    s = get_settings()
    return {
        "x-rapidapi-key": s.RAPIDAPI_KEY,
        "x-rapidapi-host": s.RAPIDAPI_HOST,
    }


def call_downloader(url: str, timeout: float = 30.0) -> dict:
    """
    여러 후보 엔드포인트를 순서대로 시도한다.
    각 시도의 상태코드와 응답을 로그로 남기고,
    처음 2xx 성공한 응답을 raw로 반환. 모두 실패하면 시도 내역을 반환.

    반환 형태:
      성공: {"success": True, "endpoint": "...", "status": 200, "raw_response": {...}}
      실패: {"success": False, "attempts": [ {endpoint,status,error/body}, ... ]}
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
    base = f"https://{host}"

    # 이 API에서 흔히 쓰는 후보 경로들 (GET 위주). 실제 동작하는 것만 성공 처리됨.
    # {vid}는 video_id로 치환.
    candidate_paths = [
        f"/get_video_info/{vid}",
        f"/get_available_quality/{vid}",
        f"/get_video_quality/{vid}",
        f"/download_video/{vid}",
        f"/video/{vid}",
        f"/get_video/{vid}",
        f"/info/{vid}",
    ]

    logger.info("RapidAPI 요청 시작: host=%s video_id=%s (후보 %d개)",
                host, vid, len(candidate_paths))

    attempts: list[dict] = []
    with httpx.Client(timeout=timeout, headers=_headers()) as client:
        for path in candidate_paths:
            full = base + path
            try:
                logger.info("→ 시도: GET %s", path)
                r = client.get(full)
                status = r.status_code
                logger.info("← 응답: %s (%s)", status, path)

                # 본문 파싱 시도 (JSON 우선, 아니면 텍스트 앞부분)
                try:
                    body = r.json()
                    is_json = True
                except Exception:
                    body = r.text[:1000]
                    is_json = False

                if 200 <= status < 300:
                    logger.info("✅ 성공 엔드포인트: %s | json=%s | 응답=%s",
                                path, is_json, _short(body))
                    return {
                        "success": True,
                        "endpoint": path,
                        "status": status,
                        "is_json": is_json,
                        "raw_response": body,
                    }

                # 실패는 기록만 하고 다음 후보로
                logger.info("✗ 비성공(%s): %s | 응답=%s", status, path, _short(body))
                attempts.append({"endpoint": path, "status": status, "body": _short(body)})

            except httpx.HTTPError as e:
                logger.warning("✗ 요청 오류: %s | %s", path, e)
                attempts.append({"endpoint": path, "error": str(e)})

    logger.error("모든 후보 엔드포인트 실패 (video_id=%s)", vid)
    return {
        "success": False,
        "video_id": vid,
        "message": "성공한 엔드포인트가 없어요. attempts의 status/body로 올바른 경로를 확인하세요.",
        "attempts": attempts,
    }


def _short(v) -> str:
    """로그/응답용 짧은 문자열."""
    try:
        import json
        s = v if isinstance(v, str) else json.dumps(v, ensure_ascii=False)
    except Exception:
        s = str(v)
    return s[:400]
