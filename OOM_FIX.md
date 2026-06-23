# 수정: 다운로드 이후 분석 단계 OOM(프로세스 재시작) 방지

## 원인
다운로드(3.73MB) 성공 후, easyocr 모델 로드(~300-400MB)가 메모리를 폭발시켜
Render Free(512MB) 초과 -> 프로세스 강제 재시작(OOM). 예외가 아니라 kill.

## 핵심 방향 (요청대로)
timeout으로 중단하지 않음. 시간이 걸려도 **끝까지 completed**.
대신 메모리를 줄여서 OOM을 막고, 단계별 status를 저장해 진행을 보여줌.

## 수정 내용

### app/services/analyzer.py (_run_youtube_sampling 재작성)
- **timeout/deadline 제거**: 끝까지 진행 (요구사항: 포기하지 말 것).
- **단계별 status 저장** (status API가 그대로 반환):
  downloading -> download_completed -> probing_video ->
  extracting_frames -> running_ocr -> generating_summary -> completed
- 각 단계 로그 추가 (ffprobe 시작/완료, frame 추출, OCR 시작, explainer 시작/완료).
- 영상 길이 제한: SAMPLING_MAX_DURATION 초과 시 프레임 수 축소(2장).
- 예외 발생 시 메타데이터 폴백 -> 그래도 실패면 failed 저장 (서버 안 죽음).

### app/services/sampling_analyzer.py (sample_segments 메모리 안전)
- 프레임을 **먼저 전부 추출**(가벼움) -> 그 다음 OCR.
- OCR reader **1회만 로드**, 실패하면 즉시 중단(재시도 안 함) -> 메모리 절약.
- 각 프레임 OCR 후 **gc.collect()** 로 메모리 즉시 회수.
- 끝나면 reader 명시적 해제.
- enable_ocr=False면 프레임만(가장 가벼움). max_frames로 장수 제어.
- on_step 콜백으로 단계별 DB status 저장.

### app/config.py
- ENABLE_STT 기본 false (whisper 무거움. 필요시 true).
- SAMPLING_MAX_FRAMES=4 (OCR 프레임 수, 4~6).
- SAMPLING_MAX_DURATION=0 (긴 영상 프레임 축소 기준, 0=제한없음).

## 시연용 권장 환경변수 (Render)
USE_RAPIDAPI_DOWNLOAD=true
ENABLE_YOUTUBE_DOWNLOAD=true
RAPIDAPI_KEY=<키>
RAPIDAPI_HOST=youtube-video-fast-downloader-24-7.p.rapidapi.com
ENABLE_OCR=true
ENABLE_STT=false           # STT 끔 (메모리 절약)
SAMPLING_MAX_FRAMES=4      # 프레임 4장
SAMPLING_MAX_DURATION=120  # 2분 초과 영상은 프레임 2장으로

## 시연 흐름 (요구사항 8)
RapidAPI 다운로드 -> 프레임 4장 -> OCR -> Explainer -> completed
STT 없음. timeout 없음. 끝까지 진행.

## status API (요구사항 4)
GET /api/videos/{id}/status -> current_step에 위 단계명이 실시간 반영.
프론트는 "downloading", "running_ocr" 등을 보고 진행 표시 가능.

## 재시작 복구 (요구사항 5)
각 단계가 current_step을 DB에 저장하므로, 서버가 중간에 죽어도
마지막 단계가 DB에 남음. (status=analyzing + step=running_ocr 등)
예외 시 failed 저장.

## 검증 (로컬, mock)
- 전체 흐름: downloading->...->completed 단계별 status 저장 확인.
- OCR reader 로드 실패해도 1회만 시도 후 프레임 유지하고 completed.
- 어떤 단계 실패해도 서버 안 죽고 폴백/failed.
- (실제 easyocr 메모리는 Render 배포 후 확인 필요)

## 주의 (솔직하게)
- 이 수정은 메모리 피크를 낮추지만, easyocr 자체가 무거워서
  Render Free(512MB)에서도 빠듯할 수 있음. 여전히 OOM이면:
  - SAMPLING_MAX_FRAMES=2 로 더 줄이기
  - 또는 대회 기간만 Render 플랜 상향(Standard 2GB)
- gc로 메모리 회수하지만 easyocr 모델 자체는 로드 시 큰 메모리를 씀.
