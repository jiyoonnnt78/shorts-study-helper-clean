"""
대표 캡쳐 생성 (Part 2 완전 구현).

- 각 segment의 중간 시점에서 FFmpeg로 jpg 캡쳐
- 캡쳐는 최대 720px로 줄여 저장 (용량 절약, OCR에는 충분)
- 중간 시점 캡쳐 실패 시 시작 시점에서 한 번 더 시도
- 시간 정보 기반 기본 특징(features)도 여기서 붙인다:
    fast_start  : 첫 구간이 3초 이하 (빠르게 시작)
    short_scene : 2초 미만의 짧은 장면
    long_scene  : 6초 초과의 긴 장면
  (large_text / speech 특징은 Part 3의 OCR/STT에서 추가)
"""
from __future__ import annotations

import logging
import shutil
import subprocess
from pathlib import Path

from sqlalchemy.orm import Session

from ..models import Segment, Video
from .storage import Storage

logger = logging.getLogger("thumbnailer")

MAX_THUMB_SIZE = 720  # 긴 변 기준 최대 픽셀


def _capture(file_path: str, at_sec: float, out_path: Path) -> bool:
    """FFmpeg로 at_sec 시점 프레임 1장을 jpg로 저장."""
    if shutil.which("ffmpeg") is None:
        logger.error("ffmpeg를 찾을 수 없어요")
        return False
    # 세로/가로 어느 쪽이든 긴 변을 MAX_THUMB_SIZE 이하로 축소 (비율 유지, 확대는 안 함)
    scale = (
        f"scale='if(gt(iw,ih),min({MAX_THUMB_SIZE},iw),-2)'"
        f":'if(gt(ih,iw),min({MAX_THUMB_SIZE},ih),-2)'"
    )
    cmd = [
        "ffmpeg", "-y", "-v", "error",
        "-ss", f"{max(0.0, at_sec):.2f}",
        "-i", file_path,
        "-frames:v", "1",
        "-vf", scale,
        "-q:v", "3",
        str(out_path),
    ]
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=60)
        return r.returncode == 0 and out_path.exists() and out_path.stat().st_size > 0
    except subprocess.TimeoutExpired:
        logger.warning("캡쳐 시간 초과: %.2fs", at_sec)
        return False
    except Exception:
        logger.exception("캡쳐 실패: %.2fs", at_sec)
        return False


def _timing_features(index: int, total: int, start: float, end: float) -> list[str]:
    length = end - start
    features: list[str] = []
    if index == 0 and end <= 3.0:
        features.append("fast_start")
    if length < 2.0:
        features.append("short_scene")
    elif length > 6.0:
        features.append("long_scene")
    return features


def create_thumbnails(
    db: Session,
    video: Video,
    time_ranges: list[tuple[float, float]],
    storage: Storage,
) -> list[Segment]:
    frame_dir = storage.frame_dir(video.id)
    segments: list[Segment] = []
    total = len(time_ranges)

    for i, (start, end) in enumerate(time_ranges):
        seg_name = f"segment_{i + 1:03d}"
        seg = Segment(
            id=f"{video.id}_{seg_name}",
            video_id=video.id,
            start_time=start,
            end_time=end,
        )
        seg.features = _timing_features(i, total, start, end)

        frame_file = f"{seg_name}.jpg"
        frame_path = frame_dir / frame_file

        mid = start + (end - start) / 2
        ok = _capture(video.file_path, mid, frame_path)
        if not ok:
            # 중간 시점이 영상 끝 경계에 걸리는 경우 등 -> 시작 직후로 재시도
            ok = _capture(video.file_path, start + 0.1, frame_path)

        if ok:
            seg.thumbnail_path = str(frame_path)
            seg.thumbnail_url = storage.frame_url(video.id, frame_file)
        else:
            logger.warning("캡쳐 생성 실패: video=%s %s", video.id, seg_name)

        db.add(seg)
        segments.append(seg)

    db.commit()
    return segments
