"""
DB 모델: Video / Segment / VideoSummary
"""
import json
import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def _uuid() -> str:
    return uuid.uuid4().hex


def _now() -> datetime:
    return datetime.now(timezone.utc)


class VideoStatus:
    UPLOADED = "uploaded"
    ANALYZING = "analyzing"
    COMPLETED = "completed"
    FAILED = "failed"


class Video(Base):
    __tablename__ = "videos"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    original_filename: Mapped[str] = mapped_column(String(255))          # 원본 파일명은 DB에만 저장
    stored_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)  # 업로드 영상만. YouTube 링크면 없음
    file_path: Mapped[str | None] = mapped_column(Text, nullable=True)   # 업로드 영상의 내부 경로 (YouTube 링크면 없을 수 있음)

    # 입력 출처: 파일 업로드 vs YouTube 링크
    source_type: Mapped[str] = mapped_column(String(20), default="upload")  # "upload" | "youtube"
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)     # 원본 링크 (youtube면 채워짐)

    status: Mapped[str] = mapped_column(String(20), default=VideoStatus.UPLOADED, index=True)
    current_step: Mapped[str | None] = mapped_column(String(100), nullable=True)

    duration: Mapped[float | None] = mapped_column(Float, nullable=True)
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    fps: Mapped[float | None] = mapped_column(Float, nullable=True)
    aspect_ratio: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # YouTube 메타데이터 (보조 정보). 영상 내부(OCR/STT)를 우선하고 이 값들은 보조로만 쓴다.
    youtube_video_id: Mapped[str | None] = mapped_column(String(20), nullable=True)
    youtube_title: Mapped[str | None] = mapped_column(Text, nullable=True)
    youtube_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    youtube_hashtags: Mapped[str | None] = mapped_column(Text, nullable=True)  # "#태그1 #태그2" 또는 JSON
    youtube_thumbnail_url: Mapped[str | None] = mapped_column(Text, nullable=True)

    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)  # 사용자용 친절한 문장만 저장

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)

    segments: Mapped[list["Segment"]] = relationship(
        back_populates="video", cascade="all, delete-orphan", order_by="Segment.start_time"
    )
    summary: Mapped["VideoSummary | None"] = relationship(
        back_populates="video", cascade="all, delete-orphan", uselist=False
    )


class Segment(Base):
    __tablename__ = "segments"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)  # 예: {video_id}_segment_001
    video_id: Mapped[str] = mapped_column(String(32), ForeignKey("videos.id", ondelete="CASCADE"), index=True)

    start_time: Mapped[float] = mapped_column(Float)
    end_time: Mapped[float] = mapped_column(Float)

    title: Mapped[str] = mapped_column(String(100), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    thumbnail_path: Mapped[str | None] = mapped_column(Text, nullable=True)   # 서버 내부 경로
    thumbnail_url: Mapped[str | None] = mapped_column(Text, nullable=True)    # 공개 URL
    ocr_text: Mapped[str] = mapped_column(Text, default="")
    speech_text: Mapped[str] = mapped_column(Text, default="")
    learn_point: Mapped[str] = mapped_column(Text, default="")
    features_json: Mapped[str] = mapped_column(Text, default="[]")

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    video: Mapped[Video] = relationship(back_populates="segments")

    @property
    def features(self) -> list[str]:
        try:
            return json.loads(self.features_json or "[]")
        except json.JSONDecodeError:
            return []

    @features.setter
    def features(self, value: list[str]) -> None:
        self.features_json = json.dumps(value, ensure_ascii=False)


class VideoSummary(Base):
    __tablename__ = "video_summaries"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    video_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("videos.id", ondelete="CASCADE"), unique=True, index=True
    )

    topic: Mapped[str] = mapped_column(Text, default="")
    purpose: Mapped[str] = mapped_column(Text, default="")
    difficulty: Mapped[str] = mapped_column(String(20), default="보통")  # 쉬움 / 보통 / 어려움
    category: Mapped[str] = mapped_column(String(30), default="기타/확인 필요")  # 넓은 목적 카테고리
    confidence: Mapped[float] = mapped_column(Float, default=0.0)               # 0.0 ~ 1.0
    confidence_reason: Mapped[str] = mapped_column(Text, default="")            # 쉬운 문장
    detected_keywords_json: Mapped[str] = mapped_column(Text, default="[]")     # 추출된 핵심 단어
    primary_source: Mapped[str] = mapped_column(String(20), default="none")     # ocr / stt / metadata / none
    source_weights_json: Mapped[str] = mapped_column(Text, default="{}")        # {"ocr":..,"stt":..,"metadata":..}
    metadata_used: Mapped[bool] = mapped_column(default=False)                  # 메타데이터가 분석에 쓰였는지
    metadata_keywords_json: Mapped[str] = mapped_column(Text, default="[]")     # 메타데이터에서만 나온 키워드
    recommended_audience_json: Mapped[str] = mapped_column(Text, default="[]")
    try_points_json: Mapped[str] = mapped_column(Text, default="[]")
    caution_points_json: Mapped[str] = mapped_column(Text, default="[]")

    # --- 숏폼 성공 구조 분석 (교육용) ---
    hook_type: Mapped[str] = mapped_column(String(40), default="")            # 훅 유형
    hook_reason: Mapped[str] = mapped_column(Text, default="")                # 왜 효과적인가
    hook_strength: Mapped[int] = mapped_column(default=0)                     # 0~100
    structure_json: Mapped[str] = mapped_column(Text, default="[]")           # 영상 구조 단계 배열(타임라인)
    success_patterns_json: Mapped[str] = mapped_column(Text, default="[]")    # 성공 법칙
    creator_tips_json: Mapped[str] = mapped_column(Text, default="[]")        # 제작 팁
    # 더 풍부한 분석 (LLM provider가 채움; 규칙 기반은 비어 있을 수 있음)
    analysis_summary: Mapped[str] = mapped_column(Text, default="")           # 3~5문장 요약
    engagement_factors_json: Mapped[str] = mapped_column(Text, default="[]")  # 몰입 요소
    structure_detail_json: Mapped[str] = mapped_column(Text, default="{}")    # opening/development/climax/ending {content,purpose}
    analysis_provider: Mapped[str] = mapped_column(String(20), default="rule")  # rule / llm
    stage_samples_json: Mapped[str] = mapped_column(Text, default="[]")  # 4구간 샘플(스크린샷+OCR+서술)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    video: Mapped[Video] = relationship(back_populates="summary")

    # --- JSON helpers ---
    def _get(self, raw: str) -> list[str]:
        try:
            return json.loads(raw or "[]")
        except json.JSONDecodeError:
            return []

    @property
    def detected_keywords(self) -> list[str]:
        return self._get(self.detected_keywords_json)

    @detected_keywords.setter
    def detected_keywords(self, v: list[str]) -> None:
        self.detected_keywords_json = json.dumps(v, ensure_ascii=False)

    @property
    def source_weights(self) -> dict:
        try:
            return json.loads(self.source_weights_json or "{}")
        except json.JSONDecodeError:
            return {}

    @source_weights.setter
    def source_weights(self, v: dict) -> None:
        self.source_weights_json = json.dumps(v, ensure_ascii=False)

    @property
    def metadata_keywords(self) -> list[str]:
        return self._get(self.metadata_keywords_json)

    @metadata_keywords.setter
    def metadata_keywords(self, v: list[str]) -> None:
        self.metadata_keywords_json = json.dumps(v, ensure_ascii=False)

    @property
    def recommended_audience(self) -> list[str]:
        return self._get(self.recommended_audience_json)

    @recommended_audience.setter
    def recommended_audience(self, v: list[str]) -> None:
        self.recommended_audience_json = json.dumps(v, ensure_ascii=False)

    @property
    def try_points(self) -> list[str]:
        return self._get(self.try_points_json)

    @try_points.setter
    def try_points(self, v: list[str]) -> None:
        self.try_points_json = json.dumps(v, ensure_ascii=False)

    @property
    def caution_points(self) -> list[str]:
        return self._get(self.caution_points_json)

    @caution_points.setter
    def caution_points(self, v: list[str]) -> None:
        self.caution_points_json = json.dumps(v, ensure_ascii=False)

    # --- 성공 구조 분석 helpers ---
    def _get_obj(self, raw: str):
        try:
            return json.loads(raw or "[]")
        except json.JSONDecodeError:
            return []

    @property
    def structure(self) -> list:
        return self._get_obj(self.structure_json)

    @structure.setter
    def structure(self, v: list) -> None:
        self.structure_json = json.dumps(v, ensure_ascii=False)

    @property
    def success_patterns(self) -> list[str]:
        return self._get(self.success_patterns_json)

    @success_patterns.setter
    def success_patterns(self, v: list[str]) -> None:
        self.success_patterns_json = json.dumps(v, ensure_ascii=False)

    @property
    def creator_tips(self) -> list[str]:
        return self._get(self.creator_tips_json)

    @creator_tips.setter
    def creator_tips(self, v: list[str]) -> None:
        self.creator_tips_json = json.dumps(v, ensure_ascii=False)

    @property
    def engagement_factors(self) -> list[str]:
        return self._get(self.engagement_factors_json)

    @engagement_factors.setter
    def engagement_factors(self, v: list[str]) -> None:
        self.engagement_factors_json = json.dumps(v, ensure_ascii=False)

    @property
    def structure_detail(self) -> dict:
        try:
            return json.loads(self.structure_detail_json or "{}")
        except json.JSONDecodeError:
            return {}

    @structure_detail.setter
    def structure_detail(self, v: dict) -> None:
        self.structure_detail_json = json.dumps(v, ensure_ascii=False)

    @property
    def stage_samples(self) -> list:
        return self._get(self.stage_samples_json)

    @stage_samples.setter
    def stage_samples(self, v: list) -> None:
        self.stage_samples_json = json.dumps(v, ensure_ascii=False)
