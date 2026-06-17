"""
파일 업로드 보안 유틸.

- 확장자 + MIME type 화이트리스트 검증
- 서버가 만든 UUID 파일명만 사용 (원본 파일명은 DB에만 저장)
- 경로 탐색 공격 차단 (저장 경로가 MEDIA_ROOT 안인지 확인)
- 최대 용량 제한 (스트리밍 저장 중 초과 시 즉시 중단)
"""
import uuid
from pathlib import Path

from fastapi import UploadFile

ALLOWED_EXTENSIONS = {".mp4", ".mov", ".webm"}
ALLOWED_MIME_PREFIXES = ("video/",)

CHUNK_SIZE = 1024 * 1024  # 1MB


class UploadValidationError(Exception):
    """사용자에게 그대로 보여줘도 안전한 메시지만 담는다."""

    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


def validate_upload_meta(upload: UploadFile) -> str:
    """확장자/MIME 검증 후 안전한 확장자를 반환."""
    original_name = upload.filename or "video"
    ext = Path(original_name).suffix.lower()

    if ext not in ALLOWED_EXTENSIONS:
        raise UploadValidationError("mp4, mov, webm 영상만 올릴 수 있어요.")

    content_type = (upload.content_type or "").lower()
    if not content_type.startswith(ALLOWED_MIME_PREFIXES):
        raise UploadValidationError("영상 파일이 아닌 것 같아요. 영상 파일을 올려주세요.")

    return ext


def make_stored_filename(ext: str) -> str:
    """서버에서 만든 안전한 파일명 (사용자 입력을 전혀 쓰지 않음)."""
    return f"{uuid.uuid4().hex}{ext}"


def ensure_inside(base_dir: Path, target: Path) -> Path:
    """target이 base_dir 안에 있는지 확인 (경로 탐색 공격 방지)."""
    base = base_dir.resolve()
    resolved = target.resolve()
    if base != resolved and base not in resolved.parents:
        raise UploadValidationError("파일을 저장할 수 없어요. 다시 시도해 주세요.")
    return resolved


async def save_upload_streaming(upload: UploadFile, dest: Path, max_bytes: int) -> int:
    """
    업로드 파일을 스트리밍으로 저장.
    max_bytes를 넘으면 파일을 지우고 예외를 던진다.
    반환: 저장된 바이트 수
    """
    dest.parent.mkdir(parents=True, exist_ok=True)
    total = 0
    try:
        with dest.open("wb") as f:
            while True:
                chunk = await upload.read(CHUNK_SIZE)
                if not chunk:
                    break
                total += len(chunk)
                if total > max_bytes:
                    raise UploadValidationError(
                        f"파일이 너무 커요. {max_bytes // (1024 * 1024)}MB 이하 영상을 올려주세요."
                    )
                f.write(chunk)
    except UploadValidationError:
        dest.unlink(missing_ok=True)
        raise
    except Exception:
        dest.unlink(missing_ok=True)
        raise UploadValidationError("파일을 저장하는 중 문제가 생겼어요. 다시 시도해 주세요.")
    finally:
        await upload.close()

    if total == 0:
        dest.unlink(missing_ok=True)
        raise UploadValidationError("빈 파일이에요. 영상 파일을 다시 올려주세요.")

    return total
