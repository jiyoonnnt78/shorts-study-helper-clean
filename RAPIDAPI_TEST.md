# RapidAPI 연동 테스트 (검증 전용)

기존 분석 로직(OCR/STT/Kiwi/explainer/yt-dlp)은 **전혀 수정하지 않음**.
독립된 테스트 코드만 추가했습니다.

## 추가/수정 파일
- [추가] app/services/rapidapi_test.py  : RapidAPI 호출 + 응답 로그
- [추가] app/api/test_downloader.py     : 테스트 엔드포인트 라우터
- [수정] app/config.py                  : RAPIDAPI_KEY / RAPIDAPI_HOST 설정 추가
- [수정] app/main.py                    : 테스트 라우터 등록 1줄
- [수정] requirements.txt               : httpx 명시

## Render 환경변수 (배포 후 설정)
```
RAPIDAPI_KEY=<발급받은 키>
RAPIDAPI_HOST=youtube-video-fast-downloader-24-7.p.rapidapi.com
```

## 사용법 (배포 후)
1) 키 설정 확인:
   GET https://<백엔드>/api/test/downloader/ping
   -> {"rapidapi_key_set": true, "rapidapi_host": "...", "sample_video_id": "jNQXAC9IVRw"}

2) 실제 호출 (브라우저 주소창에 바로):
   GET https://<백엔드>/api/test/downloader?url=https://www.youtube.com/watch?v=jNQXAC9IVRw

   또는 POST:
   POST https://<백엔드>/api/test/downloader
   {"url": "https://www.youtube.com/watch?v=jNQXAC9IVRw"}

## 동작 방식 (중요)
이 다운로더 API의 정확한 엔드포인트 경로를 문서에서 확정하지 못해,
**여러 후보 경로를 순서대로 시도**하고 처음 성공(2xx)한 응답을 그대로 반환합니다.
- 성공: {"success": true, "endpoint": "실제 동작한 경로", "status": 200, "raw_response": {...}}
- 실패: {"success": false, "attempts": [{endpoint, status, body}, ...]}

후보 경로:
  /get_video_info/{id}, /get_available_quality/{id}, /get_video_quality/{id},
  /download_video/{id}, /video/{id}, /get_video/{id}, /info/{id}

## 다음 단계 (이 테스트 결과로)
배포 후 위 GET을 호출해서 나온 응답을 확인하세요:
- success=true면 -> "endpoint"가 실제 경로, "raw_response"가 응답 구조.
  거기서 video download url / audio url / title / filesize 필드명을 확인.
- success=false면 -> attempts의 각 status를 봄:
  - 401/403 -> 키/구독 문제 (RapidAPI에서 이 API 구독했는지 확인)
  - 404 모두 -> 후보 경로가 다 틀림. RapidAPI Playground의 실제 경로를 알려주면 맞춰드림.

## 로그 (Render 로그에서 확인 가능)
- "RapidAPI 요청 시작: host=... video_id=..."
- "→ 시도: GET /경로"
- "← 응답: <상태코드>"
- "✅ 성공 엔드포인트: ..." 또는 "✗ 비성공(...)"
- 응답 JSON 일부

## 주의
- 컨테이너(개발 환경)에서는 외부 네트워크가 막혀 실제 RapidAPI 호출은 Render 배포 후에만 검증 가능.
- 로컬에서는 키 미설정/URL파싱/에러 흐름까지 검증 완료.
