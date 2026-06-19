"""
Shorts Study Helper - Backend 진입점.

실행:
    uvicorn app.main:app --reload --port 8000
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from .api.videos import router as videos_router
from .api.youtube import router as youtube_router
from .config import get_settings
from .database import create_all_tables

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger("app")

settings = get_settings()

# StaticFiles mount는 import 시점에 폴더가 있어야 하므로 여기서 먼저 생성
settings.videos_dir.mkdir(parents=True, exist_ok=True)
settings.frames_dir.mkdir(parents=True, exist_ok=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    create_all_tables()
    logger.info("media root: %s", settings.media_root_path)
    yield


app = FastAPI(title="Shorts Study Helper API", version="0.1.0", lifespan=lifespan)

# ---------------------------------------------------------------------------
# CORS (라우터 등록보다 먼저 적용)
# ---------------------------------------------------------------------------
# CORS_ORIGINS 환경변수를 comma split해서 읽고, 비어 있으면 ["*"]를 기본값으로 사용.
origins = settings.CORS_ORIGINS
if isinstance(origins, str):
    origins = [o.strip() for o in origins.split(",") if o.strip()]
if not origins:
    origins = ["*"]

# allow_origins=["*"] 와 allow_credentials=True 는 브라우저가 거부한다(충돌).
# 쿠키/인증을 쓰지 않으므로 credentials=False 로 두고 와일드카드를 허용한다.
allow_credentials = origins != ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)

logger.info("CORS allow_origins=%s credentials=%s", origins, allow_credentials)

app.include_router(videos_router)
app.include_router(youtube_router)

# 캡쳐 이미지 서빙: /media/frames/{video_id}/segment_001.jpg
# 업로드 원본 영상(videos/)은 공개하지 않고 frames만 공개한다.
app.mount("/media/frames", StaticFiles(directory=str(settings.frames_dir)), name="frames")


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    # 내부 경로/스택은 로그에만 남기고, 사용자에게는 친절한 문장만.
    logger.exception("unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "문제가 생겼어요. 잠시 후 다시 시도해 주세요."})


@app.get("/api/health")
def health():
    return {"ok": True}
