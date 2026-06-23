# 실제 분석 파이프라인에 RapidAPI 다운로드 연결

## 동작 (YouTube 링크 분석 시)
YouTube URL -> RapidAPI 다운로드 -> mp4 저장 -> mp4 검증(ffprobe)
  -> 기존 4구간 샘플링(프레임 추출 + OCR) -> 장면 분석 -> completed

## 요구사항 반영
1. test endpoint 아닌 실제 분석 파이프라인 연결 O
   (_run_youtube_sampling에서 RapidAPI 다운로드 사용)
2. yt-dlp 대신 RapidAPI 사용 O
   (USE_RAPIDAPI_DOWNLOAD=true면 RapidAPI, 아니면 기존 yt-dlp)
3. URL -> 다운로드 -> mp4 -> 기존 OCR/프레임/장면분석 실행 O
4. metadata fallback 유지 O (다운로드 실패 시 _run_metadata_only)
5. 다운로드 완료 로그 추가 O
   "video=... 다운로드 완료: ....mp4 (N MB)"
6. mp4 실제 영상 검증 로그 추가 O (ffprobe duration)
   "video=... mp4 검증 OK: duration=8.0s 540x960 (실제 영상 확인)"
   - 파일 < 1KB면 손상 의심 -> 폴백
   - duration=0이면 경고

## 기존 분석 로직
건드리지 않음. 다운로드 경로만 교체(yt-dlp -> RapidAPI).
OCR / 프레임 추출 / 4구간 샘플링 / explainer 모두 그대로.

## Render 환경변수 (실제 적용)
USE_RAPIDAPI_DOWNLOAD=true
ENABLE_YOUTUBE_DOWNLOAD=true
RAPIDAPI_KEY=<재발급한 키>
RAPIDAPI_HOST=youtube-video-fast-downloader-24-7.p.rapidapi.com
RAPIDAPI_QUALITY=247

## 로그 흐름 (정상 시)
- "YouTube 샘플링 분석 시작"
- "RapidAPI 다운로드 사용"
- "RapidAPI 다운로드 요청 시작: video_id=..."
- "file URL 수신: ..."
- "[file] 다운로드 완료: ... (N MB)"
- "다운로드 완료: ....mp4 (N MB)"
- "mp4 검증 OK: duration=...s WxH (실제 영상 확인)"   <- ffprobe 검증
- "핵심 장면을 살펴보는 중"
- "YouTube 샘플링 분석 완료(구간 4개)"

## 변경 파일
- app/services/analyzer.py  (다운로드 완료 + mp4 검증 로그 추가)
  ※ RapidAPI 연결 분기는 이전 단계에서 이미 추가됨.

## 검증 (로컬, mock)
- RapidAPI 다운로드(mock) -> mp4 검증(ffprobe duration=8.0) -> 4구간 -> completed 정상
- 실제 RapidAPI는 이미 /api/test/download로 검증됨(0.64MB 다운로드 성공)

## 주의
- 5분 polling + OCR 메모리가 겹치면 Render Free에서 OOM 위험. 모니터링 필요.
- 시연용은 미리 분석/캐시 권장.
