"""
4구간 샘플링 상세 분석.

전체 영상을 정밀 분석하지 않고, 핵심 4구간의 대표 프레임 1장씩만 뽑아
OCR + 제목/설명으로 "가볍지만 자세한" 구조 분석을 만든다.

구간:
- 오프닝   : 0~3초 (대표 1.5초)
- 전개     : 전체의 25~35% (대표 30%)
- 클라이맥스: 전체의 60~75% (대표 67%)
- 마무리   : 마지막 3~5초 (대표 끝-2초)

각 구간 산출물:
- 대표 스크린샷 1장 (frames 디렉토리에 저장, screenshot_url로 노출)
- 화면 주요 문구 OCR
- 구간 역할 / 시청 지속 이유 / 제작 팁 / 예시 문장

STT/torch/whisper는 사용하지 않는다 (메모리 절약).
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger("sampling_analyzer")

# 구간 정의: (key, 라벨, 대표 위치 계산 함수)
STAGE_KEYS = ["opening", "development", "climax", "ending"]
STAGE_LABELS = {
    "opening": "오프닝",
    "development": "전개",
    "climax": "클라이맥스",
    "ending": "마무리",
}


@dataclass
class StageSample:
    key: str
    label: str
    at_sec: float
    screenshot_path: str | None = None  # 서버 내부 경로
    screenshot_name: str | None = None  # 노출용 파일명
    ocr_texts: list[str] = field(default_factory=list)
    role: str = ""
    keep_watching: str = ""
    tip: str = ""
    example: str = ""

    def observation(self) -> str:
        if self.ocr_texts:
            return " / ".join(self.ocr_texts[:4])
        return "화면에 뚜렷한 글자는 없어요. 장면·표정·동작으로 전달돼요."


def _stage_times(duration: float) -> dict[str, float]:
    """구간별 대표 타임스탬프(초)."""
    d = max(duration, 1.0)
    return {
        "opening": min(1.5, d * 0.1),
        "development": d * 0.30,
        "climax": d * 0.67,
        "ending": max(0.0, d - 2.0),
    }


def sample_segments(
    file_path: str,
    duration: float,
    frame_dir: Path,
    deadline: float | None = None,
    max_frames: int = 4,
    enable_ocr: bool = True,
    on_step=None,
) -> list[StageSample]:
    """
    핵심 구간 대표 프레임을 뽑아 OCR한다.

    메모리 안전 설계 (Render Free OOM 방지):
    - 프레임을 먼저 전부 추출(가벼움)한 뒤, OCR reader를 1번만 로드해 순차 처리.
    - 각 OCR 직후 gc로 메모리 즉시 회수.
    - 마지막에 reader 명시적 해제.
    - enable_ocr=False면 프레임만 추출(OCR 생략) -> 가장 가벼움.

    on_step(step_name): 단계 진행을 알리는 콜백 (DB status 저장용).
    deadline: None이면 시간 제한 없음(끝까지 진행). 값이 있으면 그 이후 OCR 생략.
    """
    import gc

    from .ocr_service import (
        _extract_frame, _get_reader, _readtext, clean_ocr_results,
    )

    frame_dir.mkdir(parents=True, exist_ok=True)
    times = _stage_times(duration)
    keys = STAGE_KEYS[:max_frames] if max_frames else STAGE_KEYS
    samples: list[StageSample] = []

    # ---------- 1) 프레임 추출 (가벼움, OCR 전에 전부) ----------
    if on_step:
        on_step("extracting_frames")
    for key in keys:
        at = times[key]
        s = StageSample(key=key, label=STAGE_LABELS[key], at_sec=round(at, 2))
        out = frame_dir / f"{key}.jpg"
        try:
            if _extract_frame(file_path, at, out):
                s.screenshot_path = str(out)
                s.screenshot_name = out.name
                logger.info("프레임 추출 완료: %s (%.1fs)", key, at)
        except Exception:
            logger.warning("%s 구간 프레임 추출 실패", key, exc_info=True)
        samples.append(s)

    # ---------- 2) OCR (옵션, reader 1회 로드 -> 순차 -> 해제) ----------
    if not enable_ocr:
        logger.info("OCR 비활성화 -> 프레임만 사용")
        return samples

    if on_step:
        on_step("running_ocr")
    reader = None
    reader_failed = False
    try:
        for s in samples:
            if not s.screenshot_path:
                continue
            if reader_failed:
                break  # reader 로드가 한 번 실패하면 더 시도하지 않음
            if deadline is not None and time.monotonic() > deadline:
                logger.info("deadline 초과 -> %s 이후 OCR 생략", s.key)
                break
            try:
                if reader is None:
                    logger.info("OCR reader 로딩 시작 (easyocr)")
                    try:
                        reader = _get_reader()
                    except Exception:
                        logger.warning("OCR reader 로드 실패 -> OCR 생략(프레임은 유지)",
                                       exc_info=True)
                        reader_failed = True
                        break
                    if reader is None:
                        logger.warning("OCR reader None -> OCR 생략(프레임은 유지)")
                        reader_failed = True
                        break
                    logger.info("OCR reader 로딩 완료")
                raw = _readtext(reader, s.screenshot_path)
                s.ocr_texts = clean_ocr_results(raw)
                logger.info("OCR 완료: %s (%d개 텍스트)", s.key, len(s.ocr_texts))
            except Exception:
                logger.warning("%s 구간 OCR 실패", s.key, exc_info=True)
            finally:
                gc.collect()  # 각 프레임 OCR 후 메모리 즉시 회수
    finally:
        # reader 명시적 해제 (easyocr 모델 메모리 반환)
        reader = None
        gc.collect()
        logger.info("OCR reader 해제 완료")

    return samples


# ---------------------------------------------------------------------------
# 구간별 서술 생성 (역할/지속이유/팁/예시) — 훅 유형 + 주제 + OCR 활용
# ---------------------------------------------------------------------------
def fill_stage_narratives(
    samples: list[StageSample], hook_type: str, topic: str
) -> None:
    t = topic or "핵심 소재"

    role = {
        "opening": "영상의 첫인상을 만들고 '계속 볼까?'를 결정하게 하는 구간이에요.",
        "development": "본격적인 내용을 풀어내며 기대를 채워주는 구간이에요.",
        "climax": "가장 인상적인 장면·정보로 영상의 핵심을 전하는 구간이에요.",
        "ending": "내용을 정리하고 다음 행동(저장·구독)을 유도하는 구간이에요.",
    }
    keep = {
        "opening": "첫 3초에 궁금증이나 결과를 보여주면 스크롤을 멈추게 돼요.",
        "development": "정보를 짧은 컷으로 끊어 보여주면 지루할 틈 없이 보게 돼요.",
        "climax": "여기서 '하이라이트'라는 느낌을 주면 끝까지 보고 공유하고 싶어져요.",
        "ending": "마지막 한마디나 반전이 있으면 여운이 남아 다시 보게 돼요.",
    }
    tip = {
        "opening": f"\"{t}\"의 결론이나 가장 센 장면을 0~2초에 먼저 보여주세요.",
        "development": f"{t}를 2~3개 포인트로 나눠 각 컷에 자막을 달아보세요.",
        "climax": "가장 중요한 순간을 0.5초 느리게(슬로우모션) 강조해보세요.",
        "ending": "마지막에 '저장해두세요' 같은 한마디를 자막으로 넣어보세요.",
    }
    example = {
        "opening": f"\"{t}, 이거 하나면 끝나요\"",
        "development": "\"첫 번째는요…\" (포인트를 번호로 끊기)",
        "climax": "\"여기가 진짜 중요해요!\"",
        "ending": "\"도움 됐다면 저장 꾹!\"",
    }

    # 훅 유형별 오프닝 예시 문장 덮어쓰기 (더 구체적)
    hook_open_example = {
        "궁금증 유발형": f"\"{t}, 진짜일까요?\"",
        "결과 먼저 보여주기형": f"\"이게 {t}의 결과예요\"",
        "리스트·순위형": f"\"{t} TOP3, 3위부터!\"",
        "재미·반전형": "\"이런 건 처음 보죠?\"",
        "공감·감정형": "\"저만 이런가요?\"",
        "정보 제시형": f"\"{t}, 사실 이거였어요\"",
    }.get(hook_type)
    if hook_open_example:
        example["opening"] = hook_open_example

    for s in samples:
        s.role = role.get(s.key, "")
        s.keep_watching = keep.get(s.key, "")
        s.tip = tip.get(s.key, "")
        s.example = example.get(s.key, "")
