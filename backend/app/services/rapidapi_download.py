"""
RapidAPI "YouTube Video FAST Downloader 24/7"로 실제 mp4를 받아 저장한다.

흐름:
  1) RapidAPI 호출 -> raw_response.file (없으면 reserved_file) = 다운로드 URL 획득
  2) 그 URL이 바로 준비 안 될 수 있음 -> 404면 10초 간격, 최대 5분 polling
  3) 200 + 실제 파일 바디가 오면 media/videos/{video_id}.mp4 로 저장
  4) 저장 경로 반환

기존 분석 로직과 독립. analyzer는 이 함수가 반환한 mp4 경로를 그대로 쓰면 된다.
"""
from __future__ import annotations

import logging
import time
from pathlib import Path

import httpx

from ..config import get_settings
from .rapidapi_test import call_downloader, extract_video_id

logger = logging.getLogger("rapidapi_download")

# polling 설정
POLL_INTERVAL = 10       # 초
POLL_MAX_SECONDS = 300   # 5분


def _pick_file_url(raw: dict) -> tuple[str | None, str | None]:
    """raw_response에서 (file, reserved_file)을 뽑는다."""
    if not isinstance(raw, dict):
        return None, None
    return raw.get("file"), raw.get("reserved_file")


def _download_with_polling(
    file_url: str, dest: Path, deadline: float, label: str
) -> bool:
    """
    file_url을 polling하며 받는다.
    - 200 + 바디 -> dest에 저장 후 True
    - 404 -> 아직 준비 안 됨, POLL_INTERVAL 대기 후 재시도
    - 기타 -> 실패로 보고 False (호출자가 fallback 시도)
    deadline(time.monotonic 기준)을 넘기면 False.
    """
    attempt = 0
    while time.monotonic() < deadline:
        attempt += 1
        try:
            logger.info("[%s] 파일 준비 확인 #%d: GET %s", label, attempt, file_url)
            with httpx.Client(timeout=120.0, follow_redirects=True) as client:
                with client.stream("GET", file_url) as r:
                    status = r.status_code
                    logger.info("[%s] 응답 status=%s", label, status)

                    if status == 200:
                        logger.info("[%s] 다운로드 시작 -> %s", label, dest)
                        dest.parent.mkdir(parents=True, exist_ok=True)
                        total = 0
                        with open(dest, "wb") as f:
                            for chunk in r.iter_bytes(chunk_size=1 << 16):
                                if chunk:
                                    f.write(chunk)
                                    total += len(chunk)
                        if total > 0:
                            logger.info("[%s] 다운로드 완료: %s (%.2f MB)",
                                        label, dest.name, total / 1e6)
                            return True
                        logger.warning("[%s] 빈 파일 수신 -> 실패", label)
                        return False

                    if status == 404:
                        # 아직 준비 안 됨 -> 대기 후 재시도
                        remain = int(deadline - time.monotonic())
                        logger.info("[%s] 아직 준비 안 됨(404). %d초 후 재시도 (남은 %d초)",
                                    label, POLL_INTERVAL, max(0, remain))
                        time.sleep(POLL_INTERVAL)
                        continue

                    # 그 외 상태코드는 이 URL로는 실패
                    logger.warning("[%s] 예상치 못한 status=%s -> 이 URL 실패", label, status)
                    return False

        except httpx.HTTPError as e:
            logger.warning("[%s] 다운로드 요청 오류: %s (대기 후 재시도)", label, e)
            time.sleep(POLL_INTERVAL)
            continue

    logger.error("[%s] 시간 초과(5분) -> 실패", label)
    return False


def download_via_rapidapi(
    url: str, quality: str = "247", video_id: str | None = None
) -> str | None:
    """
    YouTube URL을 RapidAPI로 받아 media/videos/{id}.mp4 로 저장하고 경로 반환.
    실패하면 None.
    """
    s = get_settings()
    vid = video_id or extract_video_id(url)
    if not vid:
        logger.error("video_id 추출 실패: %r", url)
        return None

    # 1) RapidAPI 호출로 file URL 획득
    logger.info("RapidAPI 다운로드 요청 시작: video_id=%s quality=%s", vid, quality)
    result = call_downloader(url, quality=quality)
    if not result.get("success"):
        logger.error("RapidAPI 호출 실패: %s", result)
        return None

    raw = result.get("raw_response")
    file_url, reserved_url = _pick_file_url(raw)
    logger.info("file URL 수신: file=%s reserved=%s",
                _short(file_url), _short(reserved_url))

    if not file_url and not reserved_url:
        logger.error("응답에 file/reserved_file 없음: %s", _short(raw))
        return None

    # 2) 저장 경로
    dest = s.videos_dir / f"{vid}.mp4"

    deadline = time.monotonic() + POLL_MAX_SECONDS

    # 3) file 먼저, 실패하면 reserved_file
    if file_url:
        if _download_with_polling(file_url, dest, deadline, label="file"):
            logger.info("저장 경로: %s", dest)
            return str(dest)
        logger.info("file URL 실패 -> reserved_file로 폴백")

    if reserved_url:
        # 남은 시간 동안 reserved로 재시도 (deadline 연장 없이 동일 마감)
        if _download_with_polling(reserved_url, dest, deadline, label="reserved"):
            logger.info("저장 경로: %s", dest)
            return str(dest)

    logger.error("file/reserved 모두 실패 (video_id=%s)", vid)
    return None


def _short(v) -> str:
    try:
        s = str(v)
    except Exception:
        return "?"
    return s[:120]
