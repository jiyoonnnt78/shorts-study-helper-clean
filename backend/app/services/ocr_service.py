"""
OCR 서비스 (EasyOCR) — 품질 개선판.

개선 내용
=========
1. segment마다 대표 프레임 1장이 아니라 2~3개 프레임을 샘플링해서 OCR
2. 여러 프레임의 OCR 결과를 합친 뒤 중복 제거
3. OCR 전처리: grayscale -> 대비 증가(CLAHE) -> 2배 확대 -> (옵션) 이진화
4. confidence가 낮은 텍스트 제거
5. 너무 짧은 문자열 제거
6. OCR 실패해도 전체 분석은 실패하지 않음 (segment별 빈 값으로 진행)

- Reader는 무거우므로 프로세스당 1번만 생성 (lazy singleton)
- 모델 다운로드/초기화 실패는 호출자(analyzer)가 잡아 "OCR 없이 계속"으로 처리
"""
from __future__ import annotations

import logging
import re
import subprocess
import shutil
import tempfile
from pathlib import Path

from sqlalchemy.orm import Session

from ..models import Segment

logger = logging.getLogger("ocr_service")

MIN_CONFIDENCE = 0.45     # 이보다 낮은 인식 결과는 버림 (0.3 -> 0.45로 강화)
MIN_TEXT_LEN = 2          # 1글자짜리 의미 없는 결과 제거
LARGE_TEXT_RATIO = 0.07   # 글자 상자 높이가 이미지 높이의 7% 이상이면 큰 글씨
FRAMES_PER_SEGMENT = 3    # segment당 샘플링할 프레임 수
OCR_UPSCALE = 2           # OCR 전처리 확대 배율

_reader = None


def _get_reader():
    """EasyOCR Reader lazy singleton. import/초기화 실패는 호출자가 처리."""
    global _reader
    if _reader is None:
        import easyocr  # 지연 import (미설치 환경에서도 서버는 떠야 함)

        logger.info("EasyOCR Reader 초기화 중 (ko, en)...")
        _reader = easyocr.Reader(["ko", "en"], gpu=False, verbose=False)
        logger.info("EasyOCR Reader 준비 완료")
    return _reader


# ---------------------------------------------------------------------------
# 프레임 샘플링
# ---------------------------------------------------------------------------
def _sample_times(start: float, end: float, n: int) -> list[float]:
    """[start, end] 구간을 n등분한 가운데 지점들을 반환."""
    dur = max(0.0, end - start)
    if dur <= 0.01 or n <= 1:
        return [start + dur / 2]
    return [start + dur * (i + 0.5) / n for i in range(n)]


def _extract_frame(file_path: str, at_sec: float, out_path: Path) -> bool:
    """FFmpeg로 at_sec 시점 프레임 1장을 저장 (OCR 입력용, 원본 크기)."""
    if shutil.which("ffmpeg") is None:
        return False
    cmd = [
        "ffmpeg", "-y", "-v", "error",
        "-ss", f"{max(0.0, at_sec):.2f}",
        "-i", file_path,
        "-frames:v", "1",
        "-q:v", "2",
        str(out_path),
    ]
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=60)
        return r.returncode == 0 and out_path.exists() and out_path.stat().st_size > 0
    except Exception:
        logger.warning("OCR용 프레임 추출 실패: %.2fs", at_sec)
        return False


# ---------------------------------------------------------------------------
# 전처리
# ---------------------------------------------------------------------------
def preprocess_for_ocr(image_path: str, threshold: bool = False):
    """
    grayscale -> 대비 증가(CLAHE) -> 2배 확대 -> (옵션) 이진화.
    cv2 오류 시 None 반환 -> 호출자가 원본 경로로 OCR.
    """
    try:
        import cv2

        img = cv2.imread(image_path)
        if img is None:
            return None
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        gray = clahe.apply(gray)
        gray = cv2.resize(
            gray, None, fx=OCR_UPSCALE, fy=OCR_UPSCALE, interpolation=cv2.INTER_CUBIC
        )
        if threshold:
            _, gray = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        return gray
    except Exception:
        logger.warning("OCR 전처리 실패 -> 원본으로 진행", exc_info=True)
        return None


# ---------------------------------------------------------------------------
# 결과 정리 (테스트 가능한 순수 로직)
# ---------------------------------------------------------------------------
def clean_ocr_results(results: list) -> list[str]:
    """신뢰도 낮은 것/너무 짧은 것/기호뿐인 것/중복 제거."""
    texts: list[str] = []
    seen: set[str] = set()
    for item in results:
        if len(item) < 3:
            continue
        _, text, conf = item[0], item[1], item[2]
        if conf < MIN_CONFIDENCE:
            continue
        cleaned = re.sub(r"\s+", " ", str(text)).strip()
        if len(cleaned) < MIN_TEXT_LEN:
            continue
        if not re.search(r"[가-힣A-Za-z]", cleaned):
            continue
        key = cleaned.lower()
        if key in seen:
            continue
        seen.add(key)
        texts.append(cleaned)
    return texts


def merge_frame_texts(frame_text_lists: list[list[str]]) -> list[str]:
    """여러 프레임 텍스트를 합치고 중복 제거 (등장 순서 유지)."""
    merged: list[str] = []
    seen: set[str] = set()
    for texts in frame_text_lists:
        for t in texts:
            key = t.lower()
            if key in seen:
                continue
            seen.add(key)
            merged.append(t)
    return merged


def has_large_text(results: list, image_height: int) -> bool:
    if image_height <= 0:
        return False
    for item in results:
        if len(item) < 3 or item[2] < MIN_CONFIDENCE:
            continue
        bbox = item[0]
        try:
            ys = [p[1] for p in bbox]
            if (max(ys) - min(ys)) / image_height >= LARGE_TEXT_RATIO:
                return True
        except (TypeError, IndexError):
            continue
    return False


def _readtext(reader, image_path: str):
    """전처리 후 OCR. 전처리 실패 시 원본 경로."""
    pre = preprocess_for_ocr(image_path)
    return reader.readtext(pre if pre is not None else image_path)


# ---------------------------------------------------------------------------
# 공개 API (analyzer가 호출)
# ---------------------------------------------------------------------------
def run_ocr_for_segments(db: Session, segments: list[Segment], video=None) -> None:
    """
    각 segment에서 여러 프레임을 샘플링해 OCR하고 결과를 합쳐 정리.
    Reader 초기화 실패는 예외를 올려 analyzer가 처리.
    개별 프레임/segment 실패는 빈 값으로 두고 계속.
    """
    reader = _get_reader()
    import cv2

    file_path = getattr(video, "file_path", None)

    with tempfile.TemporaryDirectory(prefix="ocr_frames_") as tmpdir:
        tmp = Path(tmpdir)
        for seg in segments:
            try:
                frame_paths: list[str] = []
                if file_path:
                    times = _sample_times(seg.start_time, seg.end_time, FRAMES_PER_SEGMENT)
                    for i, t in enumerate(times):
                        fp = tmp / f"{seg.id}_{i}.jpg"
                        if _extract_frame(file_path, t, fp):
                            frame_paths.append(str(fp))
                if not frame_paths and seg.thumbnail_path:
                    frame_paths = [seg.thumbnail_path]
                if not frame_paths:
                    seg.ocr_text = ""
                    continue

                per_frame_texts: list[list[str]] = []
                last_results = None
                last_img_h = 0
                for fp in frame_paths:
                    results = _readtext(reader, fp)
                    per_frame_texts.append(clean_ocr_results(results))
                    last_results = results
                    img = cv2.imread(fp)
                    if img is not None:
                        last_img_h = img.shape[0]

                merged = merge_frame_texts(per_frame_texts)
                seg.ocr_text = " / ".join(merged)

                if seg.ocr_text and last_results is not None and has_large_text(
                    last_results, last_img_h * OCR_UPSCALE
                ):
                    feats = seg.features
                    if "large_text" not in feats:
                        feats.append("large_text")
                        seg.features = feats
            except Exception:
                logger.exception("segment OCR 실패: %s (빈 값으로 계속)", seg.id)
                seg.ocr_text = ""

    db.commit()
    logger.info("OCR 완료: %d개 구간 (프레임 %d개 샘플링)", len(segments), FRAMES_PER_SEGMENT)
