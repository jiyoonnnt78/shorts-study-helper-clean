# OpenAI Vision 분석 전환 (OCR/STT 제거)

OCR/STT/easyocr/whisper/Kiwi를 쓰지 않고, 대표 프레임 + 메타데이터를
OpenAI Vision에 보내 분석한다. easyocr 모델 로드가 사라져 Render OOM이 근본 해결됨.

## 흐름
YouTube URL -> RapidAPI 다운로드 -> 대표 프레임 6장 추출(ffmpeg)
  -> 메타데이터 수집 -> OpenAI Vision -> 결과를 기존 summary 구조에 매핑 -> completed

## 1. 수정/추가 파일
[추가] app/services/frame_extractor.py  : ffmpeg 시간대별 프레임 추출(+리사이즈)
[추가] app/services/vision_analyzer.py  : OpenAI Vision 호출(httpx, JSON 응답)
[수정] app/services/analyzer.py         : _run_vision_analysis + _map_vision_to_summary,
                                          ANALYSIS_MODE=vision 분기
[수정] app/config.py                    : Vision 관련 설정 추가
(requirements.txt: httpx 이미 있음 -> 변경 없음)

## 2. 제거 가능한 OCR/STT 의존성
Vision 모드에서는 호출 안 함:
- easyocr (ocr_service.py)
- whisper/faster-whisper (stt_service.py)
- kiwi (사용 안 함)
파일은 남겨둬도 됨(ANALYSIS_MODE=ocr로 되돌릴 때 사용). requirements에서
easyocr/torch/whisper를 빼면 빌드 용량/시간이 크게 줄어듦(원하면 제거).
* 단, ANALYSIS_MODE=ocr 폴백을 완전히 포기할 때만 제거 권장.

## 3. OpenAI Vision 서비스 (vision_analyzer.py)
- httpx로 https://api.openai.com/v1/chat/completions 직접 호출 (SDK 불필요)
- 프레임을 base64 data URL로, detail:low (비용/속도 절감)
- system 프롬프트로 JSON 형식 강제(response_format=json_object)
- 반환 필드: topic, purpose, category, core_message, analysis_summary,
  audience[], hook_type, hook_reason, persuasion[],
  structure{opening/development/climax/ending}, key_scenes[], creator_tips[], success_patterns[]
- 실패 시 None -> analyzer가 메타데이터 전용 폴백

## 4. 프레임 추출 서비스 (frame_extractor.py)
- ffmpeg만 사용(easyocr 의존 없음)
- 비율 [0,0.2,0.4,0.6,0.8,0.95...] 시간순, FRAME_COUNT장
- 가로 FRAME_MAX_WIDTH(512px)로 축소

## 5. analyzer 연결 (analyzer.py)
- run_analysis: source_type=youtube + ENABLE_YOUTUBE_DOWNLOAD + ANALYSIS_MODE=vision
  -> _run_vision_analysis 호출
- _run_vision_analysis: 다운로드 -> 프레임 -> Vision -> _map_vision_to_summary -> completed
- 단계별 status 저장: downloading, download_completed, probing_video,
  extracting_frames, running_vision, generating_summary, completed
- 실패 시 _run_metadata_only 폴백 (서버 안 죽음)
- _map_vision_to_summary: Vision JSON을 VideoSummary 필드 + stage_samples(프레임+장면)로 매핑
  -> 프론트 스키마(summary/topic/category/structure_detail/stage_samples) 유지

## 6. 환경변수 (Render)
ANALYSIS_MODE=vision
OPENAI_API_KEY=<OpenAI 키>
OPENAI_VISION_MODEL=gpt-4o-mini       # 저렴/빠름 (정밀하게는 gpt-4o)
FRAME_COUNT=6                          # 6~8
FRAME_MAX_WIDTH=512
USE_RAPIDAPI_DOWNLOAD=true
ENABLE_YOUTUBE_DOWNLOAD=true
RAPIDAPI_KEY=<재발급 키>
RAPIDAPI_HOST=youtube-video-fast-downloader-24-7.p.rapidapi.com
ENABLE_OCR=false                       # 안전하게 꺼둠
ENABLE_STT=false

## 7. requirements 변경
- httpx: 이미 있음 (추가 불필요)
- openai SDK: 불필요 (httpx로 직접 호출)
- (선택) easyocr/torch/whisper 제거 시 빌드 가벼워짐 - ocr 폴백 포기할 때만

## 8. 검증 (로컬, Vision mock)
- 전체 흐름: downloading->...->running_vision->generating_summary->completed
- OCR/STT 전혀 호출 안 됨
- 매핑: topic/category/hook_type/structure(4단계)/stage_samples(6장)/creator_tips 정상
- 프레임 추출: 0/20/40/60/80/95% 6장, 512px 리사이즈 확인
- Vision 실패 시 메타데이터 폴백 확인
* 실제 OpenAI 호출은 배포 후 OPENAI_API_KEY로 확인 필요

## 비용 (참고)
gpt-4o-mini + 프레임 6장(detail:low) ≈ 호출당 수원~수십원 수준.
시연/대회용으로 충분히 저렴. 정밀도가 더 필요하면 gpt-4o(비쌈)로 모델만 교체.

## 주의
- OPENAI_API_KEY가 없으면 Vision은 None 반환 -> 메타데이터 전용으로 폴백(앱 안 죽음).
- 첫 배포 후 /api/youtube/analyze로 실제 링크 분석해서 로그 확인:
  "OpenAI Vision 호출 시작" -> "OpenAI Vision 분석 성공" -> completed
