"""
YouTube 링크 분석 API.

POST /api/youtube/analyze
  body: {"url": "https://youtube.com/shorts/..."}
  resp: {"id": "...", "status": "uploaded"}

설계:
- URL에서 video_id 추출 (shorts/watch/youtu.be).
- 메타데이터(title/description/hashtags/thumbnail)를 adapter로 가져온다 (무료 oEmbed 기본).
- 영상 파일 다운로드는 기본 비활성(ENABLE_YOUTUBE_DOWNLOAD=false).
  꺼져 있으면 file_path 없이 DB에 저장 -> analyzer가 메타데이터 전용 분석을 수행.
- 잘못된 URL은 친절한 400 오류.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from ..config import get_settings
from ..database import get_db
from ..models import Video, VideoStatus
from ..schemas import UploadResponse, YoutubeAnalyzeRequest
from ..services.analyzer import run_analysis
from ..services import youtube_url as yu
from ..services.youtube_metadata import fetch_metadata

logger = logging.getLogger("youtube_api")

router = APIRouter(prefix="/api/youtube", tags=["youtube"])


@router.post("/analyze", response_model=UploadResponse, status_code=201)
def analyze_youtube(
    payload: YoutubeAnalyzeRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    settings = get_settings()

    if not settings.ENABLE_YOUTUBE:
        raise HTTPException(
            status_code=503,
            detail="지금은 유튜브 링크 분석을 사용할 수 없어요. 영상 파일을 올려주세요.",
        )

    # 1) URL -> video_id
    video_id = yu.extract_video_id(payload.url or "")
    if not video_id:
        raise HTTPException(
            status_code=400,
            detail="유튜브 쇼츠 링크가 아닌 것 같아요. 링크를 다시 확인해 주세요.",
        )

    # 2) 메타데이터 가져오기 (adapter; 실패해도 썸네일은 확보)
    try:
        meta = fetch_metadata(
            video_id, enable_download=settings.ENABLE_YOUTUBE_DOWNLOAD
        )
    except Exception:
        logger.exception("메타데이터 수집 실패 (썸네일만으로 진행)")
        from ..services.youtube_metadata import YoutubeMetadata

        meta = YoutubeMetadata(
            video_id=video_id, thumbnail_url=yu.thumbnail_url(video_id), provider="none"
        )

    # 3) DB 레코드 생성 (영상 파일은 없음 -> 메타데이터 전용 분석)
    #    id를 여기서 명시적으로 만들어, 저장/응답/분석에 동일 값을 쓴다.
    #    (SQLAlchemy default 생성에 의존하지 않아 id 흐름이 100% 투명)
    import uuid as _uuid_mod

    new_id = _uuid_mod.uuid4().hex  # 32자리 hex
    video = Video(
        id=new_id,
        original_filename=f"youtube:{video_id}"[:255],
        stored_filename=None,
        file_path=None,
        source_type="youtube",
        source_url=yu.canonical_shorts_url(video_id),
        youtube_video_id=video_id,
        youtube_title=meta.title or None,
        youtube_description=meta.description or None,
        youtube_hashtags=meta.hashtags_str() or None,
        youtube_thumbnail_url=meta.thumbnail_url or yu.thumbnail_url(video_id),
        status=VideoStatus.UPLOADED,
    )
    db.add(video)
    db.commit()
    db.refresh(video)

    # 저장된 id가 우리가 만든 id와 같은지 확인 (다르면 심각한 버그)
    persisted = db.get(Video, new_id)
    persisted_id = persisted.id if persisted else None
    import os
    from ..config import get_settings as _gs
    logger.info(
        "YouTube 분석: 생성 id=%s | DB 저장 id=%s | 일치=%s | worker pid=%s | db=%s",
        new_id, persisted_id, persisted_id == new_id, os.getpid(), _gs().DATABASE_URL,
    )

    # 4) 분석 시작 (배경) — 반드시 방금 만든 id를 넘긴다.
    background_tasks.add_task(run_analysis, new_id)

    # 5) 응답 id == videos.id (요구사항 3)
    return UploadResponse(id=new_id, status=VideoStatus.UPLOADED)
