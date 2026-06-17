"""
저장소 추상화.

지금은 LocalStorage만 구현하지만,
나중에 S3Storage / MinIOStorage를 같은 인터페이스로 추가하면
analyzer/api 코드를 바꾸지 않고 교체할 수 있다.
"""
from __future__ import annotations

import shutil
from abc import ABC, abstractmethod
from pathlib import Path

from ..config import get_settings


class Storage(ABC):
    """파일 저장소 인터페이스."""

    @abstractmethod
    def video_path(self, stored_filename: str) -> Path:
        """업로드된 영상이 저장될 서버 내부 경로."""

    @abstractmethod
    def frame_dir(self, video_id: str) -> Path:
        """캡쳐 이미지가 저장될 폴더."""

    @abstractmethod
    def frame_url(self, video_id: str, frame_filename: str) -> str:
        """브라우저가 캡쳐 이미지를 가져올 공개 URL."""

    @abstractmethod
    def delete_video_data(self, stored_filename: str, video_id: str) -> None:
        """영상 파일 + 캡쳐 폴더를 모두 삭제 (개인정보 보호)."""


class LocalStorage(Storage):
    def __init__(self):
        self.settings = get_settings()
        self.settings.videos_dir.mkdir(parents=True, exist_ok=True)
        self.settings.frames_dir.mkdir(parents=True, exist_ok=True)

    def video_path(self, stored_filename: str) -> Path:
        return self.settings.videos_dir / stored_filename

    def frame_dir(self, video_id: str) -> Path:
        d = self.settings.frames_dir / video_id
        d.mkdir(parents=True, exist_ok=True)
        return d

    def frame_url(self, video_id: str, frame_filename: str) -> str:
        base = self.settings.PUBLIC_MEDIA_URL.rstrip("/")
        return f"{base}/frames/{video_id}/{frame_filename}"

    def delete_video_data(self, stored_filename: str, video_id: str) -> None:
        if stored_filename:  # 업로드 영상만 파일 삭제 (YouTube 분석은 파일 없음)
            self.video_path(stored_filename).unlink(missing_ok=True)
        frame_dir = self.settings.frames_dir / video_id
        if frame_dir.exists():
            shutil.rmtree(frame_dir, ignore_errors=True)


_storage: Storage | None = None


def get_storage() -> Storage:
    global _storage
    if _storage is None:
        _storage = LocalStorage()
    return _storage
