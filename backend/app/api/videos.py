"""
영상 API.

POST   /api/videos                업로드 + 분석 시작
GET    /api/videos/{id}           상세 (completed면 결과 포함)
GET    /api/videos/{id}/status    상태만 빠르게
DELETE /api/videos/{id}           파일/캡쳐/결과 삭제 (개인정보 보호)
"""
from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

import logging

from ..config import get_settings
from ..database import get_db
from ..models import Video, VideoStatus
from ..schemas import (
    SourceWeightsOut,
    DeleteResponse,
    SegmentOut,
    StatusResponse,
    StructureStageOut,
    StructureDetailOut,
    StageSampleOut,
    SummaryOut,
    UploadResponse,
    VideoDetailResponse,
    YoutubeInfo,
)
from ..services.analyzer import run_analysis
from ..services.storage import get_storage
from ..utils.files import (
    UploadValidationError,
    ensure_inside,
    make_stored_filename,
    save_upload_streaming,
    validate_upload_meta,
)

router = APIRouter(prefix="/api/videos", tags=["videos"])

logger = logging.getLogger("videos_api")


@router.post("", response_model=UploadResponse, status_code=201)
async def upload_video(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    settings = get_settings()
    storage = get_storage()

    # 1. 검증 (확장자 + MIME)
    try:
        ext = validate_upload_meta(file)
        stored_filename = make_stored_filename(ext)
        dest = ensure_inside(settings.media_root_path, storage.video_path(stored_filename))
        # 2. 스트리밍 저장 (용량 초과 시 즉시 중단)
        await save_upload_streaming(file, dest, settings.max_upload_bytes)
    except UploadValidationError as e:
        raise HTTPException(status_code=400, detail=e.message)

    # 3. DB record 생성
    video = Video(
        original_filename=(file.filename or "video")[:255],
        stored_filename=stored_filename,
        file_path=str(dest),
        status=VideoStatus.UPLOADED,
    )
    db.add(video)
    db.commit()
    db.refresh(video)

    # 4. 분석 시작 (응답 반환 후 배경에서 실행)
    background_tasks.add_task(run_analysis, video.id)

    return UploadResponse(id=video.id, status=video.status)


def _get_video_or_404(db: Session, video_id: str) -> Video:
    # 앞뒤 공백/개행이 섞여 들어오는 경우를 방어 (URL 인코딩, 복붙 등)
    vid = (video_id or "").strip()

    # source_type(upload/youtube)과 무관하게 Video.id == vid 로 통일 조회.
    video = db.query(Video).filter(Video.id == vid).first()
    if video is None:
        # 진단: 실제 DB에 어떤 id들이 있는지 로그로 남긴다 (최대 20개).
        try:
            ids = [row[0] for row in db.query(Video.id).limit(20).all()]
            total = db.query(Video.id).count()
        except Exception:
            ids, total = [], -1
        logger.warning(
            "status 조회 실패(404): 요청 video_id=%r (len=%d) | DB row 수=%s | DB ids=%s",
            vid, len(vid), total, ids,
        )
        raise HTTPException(status_code=404, detail="영상을 찾을 수 없어요.")
    return video


@router.get("/{video_id}", response_model=VideoDetailResponse)
def get_video(video_id: str, db: Session = Depends(get_db)):
    video = _get_video_or_404(db, video_id)

    summary = None
    segments: list[SegmentOut] = []
    if video.status == VideoStatus.COMPLETED:
        if video.summary:
            sw_raw = video.summary.source_weights or {}
            summary = SummaryOut(
                topic=video.summary.topic,
                purpose=video.summary.purpose,
                difficulty=video.summary.difficulty,
                category=video.summary.category,
                confidence=video.summary.confidence,
                confidence_reason=video.summary.confidence_reason,
                detected_keywords=video.summary.detected_keywords,
                primary_source=video.summary.primary_source,
                source_weights=SourceWeightsOut(
                    ocr=sw_raw.get("ocr", 0.0),
                    stt=sw_raw.get("stt", 0.0),
                    metadata=sw_raw.get("metadata", sw_raw.get("filename", 0.0)),
                ),
                metadata_used=video.summary.metadata_used,
                metadata_keywords=video.summary.metadata_keywords,
                recommended_audience=video.summary.recommended_audience,
                try_points=video.summary.try_points,
                caution_points=video.summary.caution_points,
                hook_type=video.summary.hook_type,
                hook_reason=video.summary.hook_reason,
                hook_strength=video.summary.hook_strength,
                structure=[
                    StructureStageOut(**s) for s in video.summary.structure
                ],
                success_patterns=video.summary.success_patterns,
                creator_tips=video.summary.creator_tips,
                analysis_summary=video.summary.analysis_summary,
                engagement_factors=video.summary.engagement_factors,
                structure_detail=(
                    StructureDetailOut(**video.summary.structure_detail)
                    if video.summary.structure_detail
                    else None
                ),
                analysis_provider=video.summary.analysis_provider,
                stage_samples=[
                    StageSampleOut(**s) for s in video.summary.stage_samples
                ],
            )
        segments = [
            SegmentOut(
                id=s.id.split(f"{video.id}_")[-1],  # 응답에는 segment_001 형태로
                start=s.start_time,
                end=s.end_time,
                title=s.title,
                description=s.description,
                thumbnail_url=s.thumbnail_url,
                ocr_text=s.ocr_text or "",
                speech_text=s.speech_text or "",
                learn_point=s.learn_point or "",
                features=s.features,
            )
            for s in video.segments
        ]

    youtube_info = None
    if video.source_type == "youtube":
        youtube_info = YoutubeInfo(
            video_id=video.youtube_video_id,
            title=video.youtube_title,
            thumbnail_url=video.youtube_thumbnail_url,
            source_url=video.source_url,
        )

    return VideoDetailResponse(
        id=video.id,
        status=video.status,
        current_step=video.current_step,
        filename=video.original_filename,
        source_type=video.source_type,
        youtube=youtube_info,
        duration=video.duration,
        width=video.width,
        height=video.height,
        fps=video.fps,
        aspect_ratio=video.aspect_ratio,
        error_message=video.error_message,
        summary=summary,
        segments=segments,
    )


@router.get("/{video_id}/status", response_model=StatusResponse)
def get_video_status(video_id: str, db: Session = Depends(get_db)):
    import os
    logger.info("status 조회 요청: video_id=%s (worker pid=%s)", video_id, os.getpid())
    video = _get_video_or_404(db, video_id)
    return StatusResponse(
        id=video.id,
        status=video.status,
        current_step=video.current_step,
        error_message=video.error_message,
    )


@router.get("/{video_id}/frames/{name}")
def get_frame(video_id: str, name: str):
    """4구간 샘플링 스크린샷 서빙 (안전한 파일명만 허용)."""
    from fastapi.responses import FileResponse

    # 경로 조작 방지: 단순 파일명만 허용
    if "/" in name or "\\" in name or ".." in name:
        raise HTTPException(status_code=404, detail="이미지를 찾을 수 없어요.")
    frame_path = get_settings().media_root_path / "frames" / video_id / name
    if not frame_path.exists():
        raise HTTPException(status_code=404, detail="이미지를 찾을 수 없어요.")
    return FileResponse(str(frame_path), media_type="image/jpeg")


@router.delete("/{video_id}", response_model=DeleteResponse)
def delete_video(video_id: str, db: Session = Depends(get_db)):
    video = _get_video_or_404(db, video_id)
    storage = get_storage()

    # 파일 + 캡쳐 삭제
    storage.delete_video_data(video.stored_filename, video.id)
    # DB 삭제 (segments/summary는 cascade)
    db.delete(video)
    db.commit()

    return DeleteResponse(id=video_id, deleted=True, message="영상과 분석 결과를 모두 지웠어요.")
