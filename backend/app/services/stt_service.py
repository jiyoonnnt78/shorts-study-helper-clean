"""
STT 서비스 (Part 3 완전 구현, faster-whisper).

핵심 설계:
- 전체 오디오를 한 번에 변환해서 timestamp가 있는 transcript를 얻는다.
- 각 segment의 start/end와 "겹치는" transcript 조각을 segment.speech_text에 넣는다.
- 모델은 프로세스당 1번만 로드 (lazy singleton), WHISPER_MODEL 환경변수 사용 (tiny/base 권장)
- 모델 로드/변환 실패는 예외를 올리고 analyzer가 잡아서 "STT 없이 계속" 처리
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import Segment, Video

logger = logging.getLogger("stt_service")

_model = None


@dataclass
class TranscriptPiece:
    start: float
    end: float
    text: str


def _get_model():
    """faster-whisper 모델 lazy singleton."""
    global _model
    if _model is None:
        from faster_whisper import WhisperModel  # 지연 import

        settings = get_settings()
        logger.info("Whisper 모델 로딩 중: %s (cpu/int8)...", settings.WHISPER_MODEL)
        _model = WhisperModel(settings.WHISPER_MODEL, device="cpu", compute_type="int8")
        logger.info("Whisper 모델 준비 완료")
    return _model


def transcribe(file_path: str) -> list[TranscriptPiece]:
    """전체 오디오 -> timestamp transcript. (faster-whisper는 mp4를 직접 읽을 수 있음)"""
    model = _get_model()
    segments_iter, info = model.transcribe(
        file_path,
        vad_filter=True,          # 말이 없는 구간은 건너뜀
        beam_size=1,              # 속도 우선 (쇼츠는 짧아서 충분)
    )
    pieces = [
        TranscriptPiece(start=float(s.start), end=float(s.end), text=s.text.strip())
        for s in segments_iter
        if s.text and s.text.strip()
    ]
    logger.info("STT 완료: 언어=%s, 조각 %d개", getattr(info, "language", "?"), len(pieces))
    return pieces


# ---------------------------------------------------------------------------
# 순수 로직 (테스트 가능): transcript -> segment 매핑
# ---------------------------------------------------------------------------
def assign_transcript(pieces: list[TranscriptPiece], start: float, end: float) -> str:
    """segment 구간 [start, end)와 겹치는 transcript 조각을 시간순으로 합친다."""
    overlapped = [p.text for p in pieces if p.start < end and p.end > start]
    return " ".join(overlapped).strip()


# ---------------------------------------------------------------------------
# 공개 API (analyzer가 호출)
# ---------------------------------------------------------------------------
def run_stt_for_segments(db: Session, video: Video, segments: list[Segment]) -> None:
    pieces = transcribe(video.file_path)

    for seg in segments:
        text = assign_transcript(pieces, seg.start_time, seg.end_time)
        seg.speech_text = text
        if text:
            feats = seg.features
            if "speech" not in feats:
                feats.append("speech")
                seg.features = feats

    db.commit()
    logger.info("STT 구간 매핑 완료: %d개 구간", len(segments))
