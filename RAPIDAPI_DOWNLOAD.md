# RapidAPI 실제 mp4 다운로드 파이프라인

YouTube URL -> RapidAPI -> file URL polling -> mp4 다운로드 -> media 저장 -> 경로 반환

## 흐름
1. call_downloader()로 RapidAPI 호출 -> raw_response.file (없으면 reserved_file)
2. file URL을 polling: 404면 10초 간격, 최대 5분 대기
3. 200 + 바디 -> media/videos/{video_id}.mp4 저장
4. file 실패하면 reserved_file로 폴백
5. 저장 경로 반환

## 추가/수정 파일
- [추가] app/services/rapidapi_download.py : 다운로드 파이프라인 (polling+저장+폴백)
- [수정] app/api/test_downloader.py        : POST/GET /api/test/download (검증용)
- [수정] app/services/analyzer.py          : USE_RAPIDAPI_DOWNLOAD=true면 RapidAPI로 다운로드
- [수정] app/config.py                     : USE_RAPIDAPI_DOWNLOAD, RAPIDAPI_QUALITY

## 다운로드 검증 (배포 후)
브라우저:
  GET https://<백엔드>/api/test/download?url=https://www.youtube.com/watch?v=jNQXAC9IVRw

응답:
  {"success": true, "saved_path": ".../media/videos/{id}.mp4",
   "file_exists": true, "size_mb": 3.2}

※ 파일 준비에 최대 5분 걸릴 수 있어 응답이 오래 걸릴 수 있음 (정상).

## analyzer 연결 (실제 분석에 적용)
Render 환경변수:
  USE_RAPIDAPI_DOWNLOAD=true
  RAPIDAPI_KEY=<재발급한 키>
  RAPIDAPI_HOST=youtube-video-fast-downloader-24-7.p.rapidapi.com
  RAPIDAPI_QUALITY=247       (선택, 기본 247)
  ENABLE_YOUTUBE_DOWNLOAD=true   (샘플링 경로 진입에 필요)

이러면 YouTube 링크 분석 시 yt-dlp 대신 RapidAPI로 영상을 받아
기존 4구간 샘플링(스크린샷+OCR)이 그대로 동작.
RapidAPI 실패 시 자동으로 메타데이터 전용 분석으로 폴백(무한로딩 없음).

## 로그
- "RapidAPI 다운로드 요청 시작: video_id=..."
- "file URL 수신: file=... reserved=..."
- "[file] 파일 준비 확인 #N: GET ..."
- "[file] 아직 준비 안 됨(404). 10초 후 재시도 (남은 N초)"
- "[file] 다운로드 시작 -> ..." / "[file] 다운로드 완료: ... (N MB)"
- "저장 경로: ..."

## 검증 완료 (로컬)
- polling: 404 2번 -> 200 다운로드 -> 저장 정상
- 폴백: file URL 실패 -> reserved_file로 성공
- (실제 RapidAPI 호출은 Render 배포 후 /api/test/download로 확인)

## 주의
- 5분 polling 때문에 분석이 오래 걸릴 수 있음. 시연용은 미리 분석/캐시 권장.
- 영상 받은 뒤 OCR(easyocr) 메모리까지 겹치면 Render Free에선 OOM 위험.
  실제 분석 적용 시 메모리 모니터링 필요.
