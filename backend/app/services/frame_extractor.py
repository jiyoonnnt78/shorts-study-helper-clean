"""
대표 프레임 추출 (ffmpeg 전용, OCR/easyocr 의존 없음).

영상 전체를 대표하도록 시간 비율(0%, 20%, ... 95%)로 N장 추출한다.
Vision 분석 입력용이므로 적당히 리사이즈해서 용량/비용을 줄인다.
"""
from __future__ import annotations

import logging
import shutil
import subprocess
from pathlib import Path

logger = logging.getLogger("frame_extractor")

# 기본 추출 비율 (영상 전체 흐름 대표). FRAME_COUNT에 맞춰 잘라서 사용.
_DEFAULT_RATIOS = [0.0, 0.2, 0.4, 0.6, 0.8, 0.95, 0.1, 0.5]


def _ratios_for(count: int) -> list[float]:
    count = max(1, min(count, len(_DEFAULT_RATIOS)))
    base = _DEFAULT_RATIOS[:count]
    return sorted(base)


def extract_frame(file_path: str, at_sec: float, out_path: Path,
                  max_width: int = 512) -> bool:
    """at_sec 시점 프레임 1장을 추출하고 가로 max_width로 축소 저장."""
    if shutil.which("ffmpeg") is None:
        logger.warning("ffmpeg 없음 -> 프레임 추출 불가")
        return False
    out_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg", "-y", "-v", "error",
        "-ss", f"{max(0.0, at_sec):.2f}",
        "-i", file_path,
        "-frames:v", "1",
        # 가로 max_width로 축소(세로 비율 유지). Vision 비용/메모리 절감.
        "-vf", f"scale='min({max_width},iw)':-2",
        "-q:v", "3",
        str(out_path),
    ]
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=60)
        ok = r.returncode == 0 and out_path.exists() and out_path.stat().st_size > 0
        if not ok:
            logger.warning("프레임 추출 실패 at=%.1fs: %s", at_sec,
                           r.stderr.decode("utf-8", "ignore")[:200])
        return ok
    except Exception:
        logger.warning("프레임 추출 예외 at=%.1fs", at_sec, exc_info=True)
        return False


def extract_representative_frames(
    file_path: str, duration: float, frame_dir: Path,
    count: int = 6, max_width: int = 512,
) -> list[dict]:
    """
    영상 전체를 대표하는 프레임 count장을 시간순으로 추출.
    반환: [{"index", "at_sec", "ratio", "path", "name"}], 시간순.
    """
    frame_dir.mkdir(parents=True, exist_ok=True)
    d = max(duration, 1.0)
    ratios = _ratios_for(count)
    frames: list[dict] = []
    for i, ratio in enumerate(ratios):
        at = round(d * ratio, 2)
        name = f"frame_{i:02d}.jpg"
        out = frame_dir / name
        if extract_frame(file_path, at, out, max_width=max_width):
            frames.append({
                "index": i, "at_sec": at, "ratio": ratio,
                "path": str(out), "name": name,
            })
            logger.info("프레임 추출 완료: #%d at=%.1fs (%.0f%%)", i, at, ratio * 100)
    logger.info("대표 프레임 %d/%d장 추출 완료", len(frames), len(ratios))
    return frames
