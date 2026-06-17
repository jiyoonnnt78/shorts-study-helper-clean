"""
API 스키마 (Pydantic).

요청서의 응답 예시 JSON 형태와 동일하게 맞춘다.
서버 내부 경로(file_path, thumbnail_path)는 절대 포함하지 않는다.
"""
from pydantic import BaseModel, ConfigDict


class UploadResponse(BaseModel):
    id: str
    status: str


class YoutubeAnalyzeRequest(BaseModel):
    url: str


class YoutubeInfo(BaseModel):
    """결과 페이지 상단에 보여줄 YouTube 영상 정보."""
    video_id: str | None = None
    title: str | None = None
    thumbnail_url: str | None = None
    source_url: str | None = None


class StatusResponse(BaseModel):
    id: str
    status: str
    current_step: str | None = None
    error_message: str | None = None


class SegmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    start: float
    end: float
    title: str
    description: str
    thumbnail_url: str | None = None
    ocr_text: str
    speech_text: str
    learn_point: str
    features: list[str] = []


class SourceWeightsOut(BaseModel):
    ocr: float = 0.0
    stt: float = 0.0
    metadata: float = 0.0


class StructureStageOut(BaseModel):
    role: str = ""
    label: str = ""
    emoji: str = ""
    note: str = ""
    start: float = 0.0
    end: float = 0.0


class SummaryOut(BaseModel):
    topic: str
    purpose: str
    difficulty: str
    category: str = "기타"
    confidence: float = 0.0
    confidence_reason: str = ""
    detected_keywords: list[str] = []
    primary_source: str = "none"
    source_weights: SourceWeightsOut = SourceWeightsOut()
    metadata_used: bool = False
    metadata_keywords: list[str] = []
    recommended_audience: list[str] = []
    try_points: list[str] = []
    caution_points: list[str] = []
    # 숏폼 성공 구조 분석 (교육용)
    hook_type: str = ""
    hook_reason: str = ""
    hook_strength: int = 0
    structure: list[StructureStageOut] = []
    success_patterns: list[str] = []
    creator_tips: list[str] = []


class VideoDetailResponse(BaseModel):
    id: str
    status: str
    current_step: str | None = None
    filename: str
    source_type: str = "upload"
    youtube: YoutubeInfo | None = None
    duration: float | None = None
    width: int | None = None
    height: int | None = None
    fps: float | None = None
    aspect_ratio: str | None = None
    error_message: str | None = None
    summary: SummaryOut | None = None
    segments: list[SegmentOut] = []


class DeleteResponse(BaseModel):
    id: str
    deleted: bool
    message: str
