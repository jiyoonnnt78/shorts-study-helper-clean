"""
[Part 2에서 완전 구현 예정]
ffprobe로 영상 기본 정보를 추출하는 모듈.

Part 1에서는 인터페이스와 최소 동작(ffprobe가 있으면 사용)을 제공한다.
"""
from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass


@dataclass
class VideoInfo:
    duration: float
    width: int
    height: int
    fps: float
    has_audio: bool

    @property
    def aspect_ratio_label(self) -> str:
        if self.width <= 0 or self.height <= 0:
            return "알 수 없음"
        if self.height > self.width:
            ratio = self.width / self.height
            # 9:16 = 0.5625
            if abs(ratio - 9 / 16) < 0.05:
                return "9:16 (쇼츠에 잘 맞는 세로 영상)"
            return "세로 영상"
        if self.width > self.height:
            return "가로 영상"
        return "정사각형 영상"


def probe_video(file_path: str) -> VideoInfo | None:
    """ffprobe로 기본 정보 추출. 실패 시 None."""
    if shutil.which("ffprobe") is None:
        return None
    try:
        cmd = [
            "ffprobe", "-v", "error",
            "-print_format", "json",
            "-show_format", "-show_streams",
            file_path,
        ]
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if out.returncode != 0:
            return None
        data = json.loads(out.stdout)

        duration = float(data.get("format", {}).get("duration", 0) or 0)
        width = height = 0
        fps = 0.0
        has_audio = False
        for s in data.get("streams", []):
            if s.get("codec_type") == "video" and width == 0:
                width = int(s.get("width", 0) or 0)
                height = int(s.get("height", 0) or 0)
                rate = s.get("avg_frame_rate") or s.get("r_frame_rate") or "0/1"
                try:
                    num, den = rate.split("/")
                    fps = round(float(num) / float(den), 2) if float(den) else 0.0
                except (ValueError, ZeroDivisionError):
                    fps = 0.0
                if duration <= 0:
                    duration = float(s.get("duration", 0) or 0)
            elif s.get("codec_type") == "audio":
                has_audio = True

        if duration <= 0 or width <= 0:
            return None
        return VideoInfo(duration=round(duration, 2), width=width, height=height, fps=fps, has_audio=has_audio)
    except Exception:
        return None
