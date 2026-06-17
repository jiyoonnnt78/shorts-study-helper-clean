"""
장면 구간 나누기 (Part 2 완전 구현).

우선순위:
1. PySceneDetect(ContentDetector)로 장면 경계 찾기
2. 실패 시 OpenCV 히스토그램 비교로 장면 경계 찾기
3. 둘 다 실패하거나 장면이 너무 적으면 영상 길이 기준 균등 분할 (3~5개)

후처리 규칙:
- segment 최소 길이 1.0초 미만 -> 이웃과 병합
- segment 최대 길이 8.0초 초과 -> 균등 분할
- segment 개수 8개 초과 -> 가장 짧은 이웃 쌍부터 병합
- 장면이 3개 미만으로 감지되면 균등 분할 fallback
"""
from __future__ import annotations

import logging
import math

logger = logging.getLogger("scene_detector")

MIN_SEG = 1.0
MAX_SEG = 8.0
MIN_COUNT = 3
MAX_COUNT = 8

# OpenCV fallback 설정
_SAMPLE_FPS = 2.0          # 0.5초 간격으로 프레임 샘플링
_HIST_CORREL_CUT = 0.6     # 이 값보다 상관도가 낮으면 장면이 바뀐 것으로 판단


# ---------------------------------------------------------------------------
# 1단계: PySceneDetect
# ---------------------------------------------------------------------------
def _detect_pyscenedetect(file_path: str) -> list[tuple[float, float]] | None:
    try:
        from scenedetect import ContentDetector, detect
    except ImportError:
        logger.warning("scenedetect 미설치 -> OpenCV fallback 사용")
        return None
    try:
        scene_list = detect(file_path, ContentDetector(threshold=27.0), start_in_scene=True)
        ranges = []
        for s, e in scene_list:
            # scenedetect 0.7은 .seconds, 0.6.x는 .get_seconds()
            start = s.seconds if hasattr(s, "seconds") else s.get_seconds()
            end = e.seconds if hasattr(e, "seconds") else e.get_seconds()
            ranges.append((float(start), float(end)))
        return ranges or None
    except Exception:
        logger.exception("PySceneDetect 실패 -> OpenCV fallback 사용")
        return None


# ---------------------------------------------------------------------------
# 2단계: OpenCV 히스토그램 비교 fallback
# ---------------------------------------------------------------------------
def _detect_opencv(file_path: str, duration: float) -> list[tuple[float, float]] | None:
    try:
        import cv2
    except ImportError:
        return None
    try:
        cap = cv2.VideoCapture(file_path)
        if not cap.isOpened():
            return None

        boundaries: list[float] = [0.0]
        prev_hist = None
        t = 0.0
        step = 1.0 / _SAMPLE_FPS
        while t < duration:
            cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
            ok, frame = cap.read()
            if not ok:
                break
            small = cv2.resize(frame, (160, 284))
            hsv = cv2.cvtColor(small, cv2.COLOR_BGR2HSV)
            hist = cv2.calcHist([hsv], [0, 1], None, [30, 32], [0, 180, 0, 256])
            cv2.normalize(hist, hist)
            if prev_hist is not None:
                correl = cv2.compareHist(prev_hist, hist, cv2.HISTCMP_CORREL)
                if correl < _HIST_CORREL_CUT:
                    boundaries.append(round(t, 2))
            prev_hist = hist
            t += step
        cap.release()

        boundaries.append(duration)
        ranges = [
            (boundaries[i], boundaries[i + 1])
            for i in range(len(boundaries) - 1)
            if boundaries[i + 1] - boundaries[i] > 0.05
        ]
        return ranges or None
    except Exception:
        logger.exception("OpenCV 장면 감지 실패")
        return None


# ---------------------------------------------------------------------------
# 3단계: 길이 기준 균등 분할 fallback
# ---------------------------------------------------------------------------
def fallback_segments(duration: float) -> list[tuple[float, float]]:
    """영상 길이 기준 3~5개 균등 분할 (짧은 영상은 더 적게)."""
    if duration <= 0:
        return []
    n = max(1, min(5, round(duration / 4) or 1))
    if duration >= 4:
        n = max(MIN_COUNT, n)
    # 최소 길이(1.0초)를 지킬 수 있는 개수로 제한
    n = min(n, max(1, int(duration // MIN_SEG)))
    seg_len = duration / n
    ranges = []
    for i in range(n):
        start = i * seg_len
        end = duration if i == n - 1 else (i + 1) * seg_len
        ranges.append((round(start, 2), round(end, 2)))
    return ranges


# ---------------------------------------------------------------------------
# 후처리 규칙
# ---------------------------------------------------------------------------
def _sanitize(ranges: list[tuple[float, float]], duration: float) -> list[tuple[float, float]]:
    """영상 범위 밖 자르기 + 길이 0 구간 제거 + 정렬."""
    out = []
    for s, e in sorted(ranges):
        s = max(0.0, min(s, duration))
        e = max(0.0, min(e, duration))
        if e - s > 0.05:
            out.append((s, e))
    return out


def _merge_short(ranges: list[tuple[float, float]]) -> list[tuple[float, float]]:
    """MIN_SEG보다 짧은 구간을 이웃(앞 구간 우선)과 병합."""
    if not ranges:
        return ranges
    out: list[list[float]] = [list(ranges[0])]
    for s, e in ranges[1:]:
        if (e - s) < MIN_SEG or (out[-1][1] - out[-1][0]) < MIN_SEG:
            out[-1][1] = e  # 앞 구간에 붙이기
        else:
            out.append([s, e])
    # 첫 구간이 여전히 짧고 뒤가 있으면 뒤와 병합
    if len(out) >= 2 and (out[0][1] - out[0][0]) < MIN_SEG:
        out[1][0] = out[0][0]
        out.pop(0)
    return [(s, e) for s, e in out]


def _split_long(ranges: list[tuple[float, float]]) -> list[tuple[float, float]]:
    """MAX_SEG보다 긴 구간을 균등하게 쪼개기."""
    out: list[tuple[float, float]] = []
    for s, e in ranges:
        length = e - s
        if length <= MAX_SEG:
            out.append((s, e))
            continue
        parts = math.ceil(length / MAX_SEG)
        part_len = length / parts
        for i in range(parts):
            ps = s + i * part_len
            pe = e if i == parts - 1 else s + (i + 1) * part_len
            out.append((ps, pe))
    return out


def _reduce_count(ranges: list[tuple[float, float]], max_count: int) -> list[tuple[float, float]]:
    """개수가 너무 많으면 가장 짧은 이웃 쌍부터 병합 (가능하면 MAX_SEG를 넘지 않게)."""
    ranges = [list(r) for r in ranges]
    while len(ranges) > max_count:
        best_i, best_len = None, None
        for i in range(len(ranges) - 1):
            merged_len = ranges[i + 1][1] - ranges[i][0]
            if merged_len <= MAX_SEG and (best_len is None or merged_len < best_len):
                best_i, best_len = i, merged_len
        if best_i is None:
            # MAX_SEG 안에서 합칠 수 없으면 가장 짧은 쌍을 그냥 병합 (개수 우선)
            best_i = min(
                range(len(ranges) - 1),
                key=lambda i: ranges[i + 1][1] - ranges[i][0],
            )
        ranges[best_i][1] = ranges[best_i + 1][1]
        ranges.pop(best_i + 1)
    return [(s, e) for s, e in ranges]


def _round(ranges: list[tuple[float, float]]) -> list[tuple[float, float]]:
    return [(round(s, 2), round(e, 2)) for s, e in ranges]


# ---------------------------------------------------------------------------
# 공개 API (analyzer가 호출)
# ---------------------------------------------------------------------------
def detect_segments(file_path: str, duration: float) -> list[tuple[float, float]]:
    if duration <= 0:
        return []

    ranges = _detect_pyscenedetect(file_path)
    source = "pyscenedetect"
    if ranges is None:
        ranges = _detect_opencv(file_path, duration)
        source = "opencv"

    if ranges:
        ranges = _sanitize(ranges, duration)
        ranges = _merge_short(ranges)
        ranges = _split_long(ranges)
        ranges = _reduce_count(ranges, MAX_COUNT)

    # 장면이 너무 적게 감지되면 길이 기준 분할이 더 보기 좋다
    if not ranges or len(ranges) < MIN_COUNT:
        ranges = fallback_segments(duration)
        source = "fallback"

    ranges = _round(ranges)
    logger.info("장면 감지 완료: %d개 구간 (방법=%s)", len(ranges), source)
    return ranges
