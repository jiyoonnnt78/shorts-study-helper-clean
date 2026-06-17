# 쇼츠 공부 도우미

짧은 세로 영상(유튜브 쇼츠 형식)을 올리면 화면 글자(OCR)와 말소리(STT)를 분석해
초등학생도 이해할 수 있는 쉬운 말로 주제·장면을 정리해 주는 웹 서비스입니다.

```
shorts-study-helper/
├── backend/    FastAPI + SQLite. 영상 분석 파이프라인.
└── frontend/   Next.js 14 + TypeScript + Tailwind. 사용자 화면.
```

## 빠르게 실행하기

두 개의 터미널이 필요합니다.

### 1) 백엔드 (먼저 실행)

```bash
cd backend
python -m venv .venv && source .venv/bin/activate   # 선택
pip install -r requirements.txt
cp .env.example .env                                # 필요 시 값 수정
python -m uvicorn app.main:app --reload --port 8000
```

- FFmpeg가 설치되어 있어야 합니다 (`ffmpeg`, `ffprobe`).
- 처음 실행 시 OCR(EasyOCR)·STT(faster-whisper)·Kiwi 모델을 내려받습니다.
  무겁다면 `.env`에서 `ENABLE_OCR=false`, `ENABLE_STT=false`로 끌 수 있습니다.
- SQLite는 자동 생성·자동 마이그레이션됩니다.

### 2) 프론트엔드

```bash
cd frontend
npm install
cp .env.example .env.local        # NEXT_PUBLIC_API_BASE=http://localhost:8000
npm run dev                       # http://localhost:3000
```

브라우저에서 http://localhost:3000 을 열고 영상을 올리면 됩니다.

## 페이지

- `/` 업로드 (드래그앤드롭, mp4/mov/webm, 100MB까지)
- `/videos/[id]/analyzing` 분석 진행 표시 (상태 폴링)
- `/videos/[id]` 결과 (주제·카테고리·확신도·키워드·출처비중·장면 카드)

## 주요 기능

- 화면 글자(OCR) + 말소리(STT) + (예정) 유튜브 메타데이터를 함께 분석
- 영상 내부 정보를 우선하고, 부족할 때만 메타데이터 가중치 상승
- 한국어 형태소 분석기(Kiwi)로 핵심 명사 추출 (실패 시 규칙 기반 fallback)
- 주제 사전 없이 동작 → 어떤 장르의 쇼츠든 키워드 추출
- 흥미(취미) 기준으로만 시청자 추천 (성별·외모 등 민감 정보 배제)

## 참고 문서

- `backend/KIWI.md` — 키워드 추출과 Kiwi 형태소 분석 동작 설명
- `backend/.env.example` — 백엔드 환경변수
- `frontend/.env.example` — 프론트엔드 환경변수

## 아직 안 된 것 / 다음 단계

- 유튜브 링크에서 영상·메타데이터 자동 수집 (현재는 파일 업로드만, 메타데이터 필드·분석 로직은 준비됨)
- Part 5: docker-compose, 배포 설정, 테스트 가이드
