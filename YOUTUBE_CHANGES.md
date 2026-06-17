# YouTube Shorts 링크 분석 — 변경 내역

mp4 업로드에 더해, 유튜브 쇼츠 링크를 넣으면 분석할 수 있게 했습니다.
핵심 설계: **메타데이터 수집은 adapter로 분리**, **영상 다운로드는 기본 꺼짐(선택형)**,
**영상 내부 정보(OCR/STT) 우선 + 메타데이터는 보조**.

## 동작 방식

- 링크 입력 → URL에서 video_id 추출 → 메타데이터(제목/설명/해시태그/썸네일) 수집 → 분석.
- `ENABLE_YOUTUBE_DOWNLOAD=false`(기본): 영상 파일을 받지 않고 **메타데이터 기반 사전 분석**만 수행.
- 메타데이터 수집은 무료 oEmbed(키 불필요)가 기본. 썸네일은 video_id로 항상 확보.
- 나중에 yt-dlp나 YouTube Data API를 붙이려면 `youtube_metadata.py`에 provider만 추가하면 됨.

## 변경 파일 (덮어쓸 파일)

### 백엔드 — 신규
| 파일 | 역할 |
|---|---|
| `app/services/youtube_url.py` | URL→video_id 추출 (shorts/watch/youtu.be) |
| `app/services/youtube_metadata.py` | 메타데이터 provider adapter (oEmbed/yt-dlp/noop + 폴백) |
| `app/api/youtube.py` | `POST /api/youtube/analyze` 라우터 |

### 백엔드 — 수정
| 파일 | 변경 |
|---|---|
| `app/models.py` | Video에 source_type/source_url/youtube_video_id/youtube_thumbnail_url 추가, file_path를 nullable로 |
| `app/database.py` | videos 테이블 신규 컬럼 자동 마이그레이션 |
| `app/config.py` | ENABLE_YOUTUBE, ENABLE_YOUTUBE_DOWNLOAD(기본 false) 추가 |
| `app/schemas.py` | YoutubeAnalyzeRequest, YoutubeInfo 추가 / VideoDetailResponse에 source_type·youtube 추가 |
| `app/api/videos.py` | 상세 응답에 source_type·youtube 정보 매핑 |
| `app/services/analyzer.py` | 파일 없을 때(YouTube) 메타데이터 전용 분석 분기 (_run_metadata_only) |
| `app/services/explainer.py` | _build_metadata_text가 YouTube면 파일명 제외(video_id 조각 방지) |
| `app/services/storage.py` | 빈 stored_filename(파일 없는 YouTube 분석) 삭제 시 안전 처리 |
| `app/main.py` | youtube 라우터 등록 |
| `app/config`의 `.env.example`, `requirements.txt` | 설정/선택 의존성(yt-dlp) 주석 |

### 프론트엔드 — 신규
| 파일 | 역할 |
|---|---|
| `src/components/YoutubeInfoCard.tsx` | 결과 상단 영상 정보(제목/썸네일/링크/metadata_used) |

### 프론트엔드 — 수정
| 파일 | 변경 |
|---|---|
| `src/lib/types.ts` | YoutubeInfo 타입, VideoDetail에 source_type·youtube 추가 |
| `src/lib/api.ts` | analyzeYoutube() 추가 |
| `src/app/page.tsx` | 업로드 영역 위에 유튜브 링크 입력칸 + 안내 문구 추가 |
| `src/app/videos/[id]/page.tsx` | 결과 상단에 YoutubeInfoCard 표시 |

## API

```
POST /api/youtube/analyze
  body: { "url": "https://youtube.com/shorts/VIDEOID" }
  resp: { "id": "...", "status": "uploaded" }   (201)
  잘못된 URL → 400 (친절한 안내 메시지)
```

분석 진행/결과 조회는 기존 엔드포인트 재사용:
`GET /api/videos/{id}/status`, `GET /api/videos/{id}`.

## 실행 방법

### 백엔드
```bash
cd backend
pip install -r requirements.txt
cp .env.example .env          # ENABLE_YOUTUBE=true (기본). 다운로드는 false 권장.
python -m uvicorn app.main:app --reload --port 8000
```
- 무료 oEmbed만 쓰면 추가 설치 없음.
- 풍부한 메타데이터(설명/태그)를 원하면: `pip install yt-dlp` 후 `.env`에서
  `ENABLE_YOUTUBE_DOWNLOAD=true` (영상 파일은 받지 않고 정보만 가져옴).

### 프론트엔드
```bash
cd frontend
npm install
cp .env.example .env.local    # NEXT_PUBLIC_API_BASE=http://localhost:8000
npm run dev                   # http://localhost:3000
```

## 마이그레이션

- **필요하지만 자동입니다.** SQLite는 서버 시작 시 videos 테이블에 신규 컬럼이 자동 추가됩니다
  (구버전 DB로 검증 완료). PostgreSQL은 Alembic 등 정식 마이그레이션 권장.

## 메타데이터 활용 원칙 (요구사항 5)

- 영상 내부 정보(OCR/STT)가 있으면 그것을 우선. 제목만으로 주제를 단정하지 않음.
- 내부 정보가 부족할수록 metadata 가중치 상승. source_weights 예: `{ocr:0.4, stt:0.4, metadata:0.2}`.
- 메타데이터 의존 시 confidence 상한(0.55)으로 과신 방지, "제목·설명도 함께 참고했어요" 안내.

## 주의

- 영상 파일 다운로드는 약관 이슈가 있어 **기본 비활성**. 켜더라도 이 구현은 메타데이터만 가져오고
  영상 파일은 저장하지 않습니다.
- 네트워크가 막힌 환경에서도 video_id 기반 썸네일과 폴백으로 분석은 진행됩니다(제목은 비어 있을 수 있음).
