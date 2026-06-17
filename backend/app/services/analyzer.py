"""
전체 분석 파이프라인.

단계:
1. 영상 정보를 확인하는 중   (video_probe)      -> Part 2
2. 화면을 나누는 중           (scene_detector)   -> Part 2
3. 캡쳐를 만드는 중           (thumbnailer)      -> Part 2
4. 글자를 읽는 중             (ocr_service)      -> Part 3
5. 소리를 듣는 중             (stt_service)      -> Part 3
6. 쉬운 설명을 만드는 중       (explainer)        -> Part 3

설계 원칙:
- 각 단계는 실패해도 전체가 죽지 않게 try/except로 감싼다 (OCR/STT는 옵션).
- 단, 영상 정보 확인 실패는 영상 자체가 잘못된 것이므로 failed 처리.
- error_message에는 사용자에게 보여줘도 안전한 친절한 문장만 저장한다.
- 배경 스레드에서 실행되므로 자기 전용 DB 세션을 연다.
"""
import logging
import traceback

from ..config import get_settings
from ..database import SessionLocal
from ..models import Video, VideoStatus
from .storage import get_storage

logger = logging.getLogger("analyzer")

STEP_PROBE = "영상 정보를 확인하는 중"
STEP_SCENES = "화면을 나누는 중"
STEP_THUMBS = "캡쳐를 만드는 중"
STEP_OCR = "글자를 읽는 중"
STEP_STT = "소리를 듣는 중"
STEP_EXPLAIN = "쉬운 설명을 만드는 중"

FRIENDLY_FAIL = "영상을 분석하는 중에 문제가 생겼어요. 다른 영상으로 다시 시도해 주세요."


def _set_step(db, video: Video, step: str) -> None:
    video.current_step = step
    db.commit()
    logger.info("video=%s step=%s", video.id, step)


def run_analysis(video_id: str) -> None:
    """
    BackgroundTasks에서 호출되는 진입점.
    동기 함수이므로 FastAPI가 스레드풀에서 실행해준다.
    """
    settings = get_settings()
    storage = get_storage()
    db = SessionLocal()
    try:
        video = db.get(Video, video_id)
        if video is None:
            logger.warning("video not found: %s", video_id)
            return

        video.status = VideoStatus.ANALYZING
        db.commit()

        # YouTube 링크인데 영상 파일이 없으면(다운로드 비활성) -> 메타데이터 전용 분석
        if not video.file_path:
            _run_metadata_only(db, video, storage)
            return

        # ---------- 1. 영상 기본 정보 ----------
        _set_step(db, video, STEP_PROBE)
        from .video_probe import probe_video  # 지연 import (무거운 의존성 격리)

        info = probe_video(video.file_path)
        if info is None:
            raise AnalysisFailed("영상 정보를 읽을 수 없어요. 영상 파일이 맞는지 확인해 주세요.")

        if info.duration > settings.MAX_VIDEO_DURATION_SECONDS:
            raise AnalysisFailed(
                f"영상이 너무 길어요. {settings.MAX_VIDEO_DURATION_SECONDS}초 이하 영상을 올려주세요."
            )

        video.duration = info.duration
        video.width = info.width
        video.height = info.height
        video.fps = info.fps
        video.aspect_ratio = info.aspect_ratio_label
        db.commit()

        # ---------- 2. 장면 나누기 ----------
        _set_step(db, video, STEP_SCENES)
        from .scene_detector import detect_segments

        time_ranges = detect_segments(video.file_path, info.duration)

        # ---------- 3. 캡쳐 만들기 ----------
        _set_step(db, video, STEP_THUMBS)
        from .thumbnailer import create_thumbnails

        segments = create_thumbnails(db, video, time_ranges, storage)

        # ---------- 4. OCR (옵션) ----------
        if settings.ENABLE_OCR:
            _set_step(db, video, STEP_OCR)
            try:
                from .ocr_service import run_ocr_for_segments

                run_ocr_for_segments(db, segments, video=video)
            except Exception:
                logger.exception("OCR 실패 (전체 분석은 계속 진행)")

        # ---------- 5. STT (옵션) ----------
        if settings.ENABLE_STT and info.has_audio:
            _set_step(db, video, STEP_STT)
            try:
                from .stt_service import run_stt_for_segments

                run_stt_for_segments(db, video, segments)
            except Exception:
                logger.exception("STT 실패 (전체 분석은 계속 진행)")

        # ---------- 6. 쉬운 설명 ----------
        _set_step(db, video, STEP_EXPLAIN)
        from .explainer import get_explainer

        explainer = get_explainer()
        explainer.explain(db, video, segments)

        # ---------- 완료 ----------
        video.status = VideoStatus.COMPLETED
        video.current_step = None
        video.error_message = None
        db.commit()
        logger.info("video=%s 분석 완료", video.id)

    except AnalysisFailed as e:
        _mark_failed(db, video_id, e.message)
    except Exception:
        # 내부 경로/스택은 로그에만 남기고, 사용자에게는 친절한 문장만 보여준다.
        logger.error("video=%s 분석 실패\n%s", video_id, traceback.format_exc())
        _mark_failed(db, video_id, FRIENDLY_FAIL)
    finally:
        db.close()


class AnalysisFailed(Exception):
    """사용자에게 보여줘도 안전한 메시지를 담은 실패."""

    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


STEP_META = "영상 정보를 살펴보는 중"


def _run_metadata_only(db, video: Video, storage) -> None:
    """
    영상 파일 없이(YouTube 링크 + 다운로드 비활성) 제목/설명/해시태그만으로
    사전 분석을 수행한다. segment가 없으므로 OCR/STT는 건너뛰고,
    explainer가 메타데이터를 주 신호로 사용한다 (source_weights.metadata 우선).
    """
    _set_step(db, video, STEP_META)
    from .explainer import get_explainer

    # segment 없이 explainer 호출 -> 메타데이터 기반 요약/성공구조 생성
    explainer = get_explainer()
    explainer.explain(db, video, segments=[])

    video.status = VideoStatus.COMPLETED
    video.current_step = None
    video.error_message = None
    db.commit()
    logger.info("video=%s YouTube 메타데이터 분석 완료", video.id)


def _mark_failed(db, video_id: str, message: str) -> None:
    try:
        video = db.get(Video, video_id)
        if video is not None:
            video.status = VideoStatus.FAILED
            video.current_step = None
            video.error_message = message
            db.commit()
    except Exception:
        logger.exception("failed 상태 저장 중 오류")
