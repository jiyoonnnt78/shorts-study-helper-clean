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
            if (
                video.source_type == "youtube"
                and settings.ENABLE_YOUTUBE_DOWNLOAD
                and video.youtube_video_id
            ):
                # ANALYSIS_MODE=vision이면 프레임+OpenAI Vision (OCR/STT 없음)
                if getattr(settings, "ANALYSIS_MODE", "vision") == "vision":
                    _run_vision_analysis(db, video, storage)
                else:
                    _run_youtube_sampling(db, video, storage)
            else:
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
    vid = video.id
    logger.info("video=%s 메타데이터 전용 분석 시작", vid)
    _set_step(db, video, STEP_META)

    from .explainer import get_explainer

    # segment 없이 explainer 호출 -> 메타데이터 기반 요약/성공구조 생성
    explainer = get_explainer()
    logger.info("video=%s explainer.explain 호출 직전", vid)
    explainer.explain(db, video, segments=[])
    logger.info("video=%s explainer.explain 반환", vid)

    video.status = VideoStatus.COMPLETED
    video.current_step = None
    video.error_message = None
    db.commit()
    logger.info("video=%s YouTube 메타데이터 분석 완료(status=completed 저장)", vid)


STEP_DOWNLOAD = "영상을 받아오는 중"
STEP_SAMPLING = "핵심 장면을 살펴보는 중"

# 요청한 세분화 status (status API가 그대로 반환)
ST_DOWNLOADING = "downloading"
ST_DOWNLOAD_DONE = "download_completed"
ST_PROBING = "probing_video"
ST_EXTRACTING = "extracting_frames"
ST_OCR = "running_ocr"
ST_SUMMARY = "generating_summary"


def _step(db, video: Video, step: str) -> None:
    """current_step만 저장+commit (status는 analyzing 유지). 재시작 복구용."""
    try:
        video.current_step = step
        db.commit()
        logger.info("video=%s step=%s", video.id, step)
    except Exception:
        logger.warning("step 저장 실패: %s", step, exc_info=True)
        try:
            db.rollback()
        except Exception:
            pass


def _run_vision_analysis(db, video: Video, storage) -> None:
    """
    OpenAI Vision 기반 분석 (OCR/STT/Kiwi 미사용 -> Render OOM 회피).

    흐름:
      RapidAPI 다운로드 -> 대표 프레임 추출 -> 메타데이터 수집
      -> OpenAI Vision 호출 -> 기존 summary 구조에 매핑 -> completed

    timeout으로 중단하지 않음. 실패 시 메타데이터 전용 폴백.
    """
    vid = video.id
    logger.info("video=%s Vision 분석 시작 (OCR/STT 미사용)", vid)

    from pathlib import Path
    from .youtube_download import download_video
    from .frame_extractor import extract_representative_frames
    from .vision_analyzer import analyze_with_vision
    from .video_probe import probe_video

    settings = get_settings()
    try:
        # 1) 다운로드
        _step(db, video, ST_DOWNLOADING)
        if getattr(settings, "USE_RAPIDAPI_DOWNLOAD", False) and settings.RAPIDAPI_KEY:
            from .rapidapi_download import download_via_rapidapi
            logger.info("video=%s RapidAPI 다운로드 사용", vid)
            file_path = download_via_rapidapi(
                video.source_url or "", quality=settings.RAPIDAPI_QUALITY,
                video_id=video.youtube_video_id,
            )
        else:
            dl_dir = Path(settings.MEDIA_ROOT) / "videos"
            file_path = download_video(video.youtube_video_id, dl_dir, timeout=8)

        if not file_path:
            logger.info("video=%s 다운로드 실패 -> 메타데이터 전용 폴백", vid)
            _run_metadata_only(db, video, storage)
            return

        video.file_path = file_path
        video.stored_filename = Path(file_path).name
        db.commit()
        try:
            _fsize = Path(file_path).stat().st_size
        except Exception:
            _fsize = 0
        logger.info("video=%s 다운로드 완료: %s (%.2f MB)",
                    vid, Path(file_path).name, _fsize / 1e6)
        _step(db, video, ST_DOWNLOAD_DONE)

        # 2) ffprobe (길이)
        _step(db, video, ST_PROBING)
        try:
            info = probe_video(file_path)
            video.duration = getattr(info, "duration", 0.0) or 0.0
            video.width = getattr(info, "width", None)
            video.height = getattr(info, "height", None)
            db.commit()
            logger.info("video=%s ffprobe 완료: duration=%.1fs", vid, video.duration or 0)
        except Exception:
            logger.warning("video=%s ffprobe 실패(무시)", vid, exc_info=True)

        # 3) 대표 프레임 추출 (시간대별 N장)
        _step(db, video, ST_EXTRACTING)
        frame_count = getattr(settings, "FRAME_COUNT", 6) or 6
        frame_dir = Path(settings.MEDIA_ROOT) / "frames" / vid
        frames = extract_representative_frames(
            file_path, video.duration or 0.0, frame_dir,
            count=frame_count, max_width=getattr(settings, "FRAME_MAX_WIDTH", 512),
        )
        logger.info("video=%s 프레임 %d장 추출 완료", vid, len(frames))
        if not frames:
            logger.warning("video=%s 프레임 0장 -> 메타데이터 전용 폴백", vid)
            _run_metadata_only(db, video, storage)
            return

        # 4) OpenAI Vision 분석
        _step(db, video, "running_vision")
        meta = {
            "title": video.youtube_title or "",
            "description": video.youtube_description or "",
            "channel": getattr(video, "youtube_channel", "") or "",
            "duration": int(video.duration or 0),
            "hashtags": video.youtube_hashtags or "",
        }
        result = analyze_with_vision(frames, meta)
        if not result:
            logger.warning("video=%s Vision 실패 -> 메타데이터 전용 폴백", vid)
            _run_metadata_only(db, video, storage)
            return

        # 5) 결과를 기존 summary 구조에 매핑
        _step(db, video, ST_SUMMARY)
        _map_vision_to_summary(db, video, result, frames)

        video.status = VideoStatus.COMPLETED
        video.current_step = None
        video.error_message = None
        db.commit()
        logger.info("video=%s Vision 분석 완료(completed)", vid)

    except Exception:
        logger.warning("video=%s Vision 분석 실패 -> 폴백", vid, exc_info=True)
        try:
            _run_metadata_only(db, video, storage)
        except Exception:
            _mark_failed(db, vid, "분석 중 문제가 생겼어요. 잠시 후 다시 시도해 주세요.")


def _map_vision_to_summary(db, video: Video, r: dict, frames: list[dict]) -> None:
    """Vision 결과(dict)를 VideoSummary 필드에 매핑 (프론트 스키마 유지)."""
    summary = video.summary
    if summary is None:
        # summary가 없으면 만든다 (explainer의 생성 방식과 동일하게)
        from ..models import VideoSummary
        summary = VideoSummary(video_id=video.id)
        db.add(summary)
        db.flush()

    def _s(key, default=""):
        v = r.get(key)
        return v if isinstance(v, str) else default

    def _l(key):
        v = r.get(key)
        return [str(x) for x in v] if isinstance(v, list) else []

    summary.topic = _s("topic") or "영상 분석 결과"
    summary.purpose = _s("purpose")
    summary.category = _s("category", "기타") or "기타"
    summary.analysis_summary = _s("analysis_summary") or _s("core_message")
    summary.hook_type = _s("hook_type")
    summary.hook_reason = _s("hook_reason")
    summary.recommended_audience = _l("audience")
    summary.engagement_factors = _l("persuasion")
    summary.success_patterns = _l("success_patterns")
    summary.creator_tips = _l("creator_tips")
    summary.confidence = 0.8  # Vision은 실제 화면을 봤으므로 비교적 높게
    summary.primary_source = "vision"
    summary.analysis_provider = "openai_vision"

    # 구조(structure) 매핑
    st = r.get("structure") or {}
    if isinstance(st, dict):
        detail = {}
        for k in ("opening", "development", "climax", "ending"):
            seg = st.get(k) or {}
            if isinstance(seg, dict):
                detail[k] = {
                    "content": str(seg.get("content", "")),
                    "purpose": str(seg.get("purpose", "")),
                }
        summary.structure_detail = detail

    # 장면 -> stage_samples 매핑 (Vision이 장면별 observation/role/purpose 직접 생성)
    scenes = r.get("scenes")
    key_scenes = _l("key_scenes")  # 구버전 폴백
    samples = []
    for i, fr in enumerate(frames):
        observation = ""
        role = ""
        purpose = ""
        # 우선: Vision의 구조화된 scenes 배열
        if isinstance(scenes, list) and i < len(scenes) and isinstance(scenes[i], dict):
            sc = scenes[i]
            observation = str(sc.get("observation", "") or "")
            role = str(sc.get("role", "") or "")
            purpose = str(sc.get("purpose", "") or "")
        # 폴백: 옛 key_scenes(문자열 배열)
        if not observation and i < len(key_scenes):
            observation = key_scenes[i]

        samples.append({
            "key": f"scene_{i}",
            "label": f"{int(fr.get('ratio', 0) * 100)}% 지점",
            "at_sec": fr.get("at_sec", 0),
            "screenshot": f"/api/videos/{video.id}/frames/{fr['name']}",
            "observation": observation,
            "role": role,
            "purpose": purpose,
            "keep_watching": purpose,  # 프론트 호환(역할/효과 표시)
            "tip": "",
            "example": "",
        })
    summary.stage_samples = samples
    db.commit()


def _run_youtube_sampling(db, video: Video, storage) -> None:
    """
    YouTube 영상을 받아 핵심 구간 샘플링 분석한다.

    설계 (대회 시연용, OOM 방지 우선):
    - timeout으로 중단하지 않음. 시간이 걸려도 끝까지 진행해 completed를 보장.
    - 각 단계마다 current_step을 DB에 저장 (재시작/조회 대비).
    - OCR은 메모리 안전 모드(프레임 먼저, reader 1회, gc). STT는 사용 안 함.
    - 긴 영상은 프레임 수/해상도로만 제어 (분석 자체는 끝까지).
    - 어떤 단계가 실패해도 메타데이터 전용으로 폴백하거나 failed 저장.
    """
    vid = video.id
    logger.info("video=%s YouTube 샘플링 분석 시작 (timeout 없음, 끝까지 진행)", vid)

    from pathlib import Path
    from .youtube_download import download_video
    from .sampling_analyzer import sample_segments, fill_stage_narratives
    from .video_probe import probe_video

    settings = get_settings()
    file_path = None
    samples = []
    try:
        # ---------- 1) 다운로드 ----------
        _step(db, video, ST_DOWNLOADING)
        dl_dir = Path(settings.MEDIA_ROOT) / "videos"

        if getattr(settings, "USE_RAPIDAPI_DOWNLOAD", False) and settings.RAPIDAPI_KEY:
            from .rapidapi_download import download_via_rapidapi
            logger.info("video=%s RapidAPI 다운로드 사용", vid)
            file_path = download_via_rapidapi(
                video.source_url or "", quality=settings.RAPIDAPI_QUALITY,
                video_id=video.youtube_video_id,
            )
        else:
            file_path = download_video(video.youtube_video_id, dl_dir, timeout=8)

        if not file_path:
            logger.info("video=%s 다운로드 실패 -> 메타데이터 전용 폴백", vid)
            _run_metadata_only(db, video, storage)
            return

        video.file_path = file_path
        video.stored_filename = Path(file_path).name
        db.commit()

        # 다운로드 완료 + 크기 검증
        try:
            _fsize = Path(file_path).stat().st_size
        except Exception:
            _fsize = 0
        logger.info("video=%s 다운로드 완료: %s (%.2f MB)",
                    vid, Path(file_path).name, _fsize / 1e6)
        _step(db, video, ST_DOWNLOAD_DONE)
        if _fsize < 1024:
            logger.warning("video=%s 파일이 너무 작음(%d bytes) -> 폴백", vid, _fsize)
            _run_metadata_only(db, video, storage)
            return

        # ---------- 2) ffprobe 영상 검증 ----------
        _step(db, video, ST_PROBING)
        logger.info("video=%s ffprobe 시작", vid)
        try:
            info = probe_video(file_path)
            video.duration = getattr(info, "duration", 0.0) or 0.0
            video.width = getattr(info, "width", None)
            video.height = getattr(info, "height", None)
            db.commit()
            if video.duration and video.duration > 0:
                logger.info("video=%s ffprobe 완료: duration=%.1fs %sx%s (실제 영상 확인)",
                            vid, video.duration, video.width, video.height)
            else:
                logger.warning("video=%s ffprobe: duration=0 (영상이 아닐 수 있음)", vid)
        except Exception:
            logger.warning("video=%s ffprobe 실패(무시)", vid, exc_info=True)

        # 너무 긴 영상은 프레임만 추출하고 OCR은 줄임 (메모리/시간 보호, 중단은 안 함)
        max_len = getattr(settings, "SAMPLING_MAX_DURATION", 0) or 0
        too_long = max_len > 0 and (video.duration or 0) > max_len
        if too_long:
            logger.info("video=%s 긴 영상(%.0fs > %ds): OCR 프레임 수 축소",
                        vid, video.duration or 0, max_len)

        # ---------- 3) 프레임 추출 + OCR (메모리 안전) ----------
        logger.info("video=%s scene/frame 추출 시작", vid)
        frame_dir = Path(settings.MEDIA_ROOT) / "frames" / vid
        max_frames = getattr(settings, "SAMPLING_MAX_FRAMES", 4) or 4
        if too_long:
            max_frames = min(max_frames, 2)
        enable_ocr = getattr(settings, "ENABLE_OCR", True)

        def _on_step(name: str) -> None:
            _step(db, video, name)
            if name == "extracting_frames":
                logger.info("video=%s thumbnail/frame 추출 단계", vid)
            elif name == "running_ocr":
                logger.info("video=%s OCR 시작 (enable_ocr=%s)", vid, enable_ocr)

        samples = sample_segments(
            file_path, video.duration or 0.0, frame_dir,
            deadline=None,            # timeout 없음: 끝까지 진행
            max_frames=max_frames,
            enable_ocr=enable_ocr,
            on_step=_on_step,
        )
        logger.info("video=%s scene/frame + OCR 완료 (구간 %d개)", vid, len(samples))

        # ---------- 4) explainer (요약/구조/팁 생성) ----------
        _step(db, video, ST_SUMMARY)
        logger.info("video=%s explainer 시작", vid)
        ocr_blob = " ".join(t for s in samples for t in s.ocr_texts)
        _run_metadata_with_ocr(db, video, ocr_blob)
        logger.info("video=%s explainer 완료", vid)
        summary = video.summary
        hook_type = summary.hook_type if summary else ""
        topic = (summary.detected_keywords[0] if summary and summary.detected_keywords else "")
        fill_stage_narratives(samples, hook_type, topic)

        # 6) 샘플 저장 (스크린샷은 노출용 상대경로로)
        summary_samples = []
        for s in samples:
            summary_samples.append({
                "key": s.key,
                "label": s.label,
                "at_sec": s.at_sec,
                "screenshot": f"/api/videos/{vid}/frames/{s.screenshot_name}" if s.screenshot_name else None,
                "observation": s.observation(),
                "role": s.role,
                "keep_watching": s.keep_watching,
                "tip": s.tip,
                "example": s.example,
            })
        video.summary.stage_samples = summary_samples
        video.status = VideoStatus.COMPLETED
        video.current_step = None
        video.error_message = None
        db.commit()
        logger.info("video=%s YouTube 샘플링 분석 완료(구간 %d개)", vid, len(samples))

    except Exception:
        logger.warning("video=%s 샘플링 분석 실패 -> 메타데이터 전용 폴백", vid, exc_info=True)
        try:
            _run_metadata_only(db, video, storage)
        except Exception:
            _mark_failed(db, vid, "분석 중 문제가 생겼어요. 잠시 후 다시 시도해 주세요.")


def _run_metadata_with_ocr(db, video: Video, ocr_blob: str) -> None:
    """
    OCR로 얻은 화면 글자를 메타데이터에 보태서 explainer를 돌린다.
    segment는 없지만 ocr_blob을 임시 메타데이터로 합쳐 키워드 품질을 높인다.
    """
    from .explainer import get_explainer

    # 제목+설명+해시태그+OCR을 합친 텍스트를 youtube_description에 임시 보강
    # (explainer가 metadata_text로 사용 -> 키워드에 OCR 반영)
    if ocr_blob.strip():
        base = video.youtube_description or ""
        video.youtube_description = (base + " " + ocr_blob).strip()
        db.commit()

    get_explainer().explain(db, video, segments=[])


def _mark_failed(db, video_id: str, message: str) -> None:
    # DB 오류로 트랜잭션이 깨진 상태일 수 있으므로 먼저 rollback해서 세션을 복구한다.
    try:
        db.rollback()
    except Exception:
        logger.warning("rollback 실패(무시)", exc_info=True)
    try:
        video = db.get(Video, video_id)
        if video is not None:
            video.status = VideoStatus.FAILED
            video.current_step = None
            video.error_message = message
            db.commit()
            logger.info("video=%s status=failed 저장: %s", video_id, message)
    except Exception:
        logger.exception("failed 상태 저장 중 오류")
        try:
            db.rollback()
        except Exception:
            pass
