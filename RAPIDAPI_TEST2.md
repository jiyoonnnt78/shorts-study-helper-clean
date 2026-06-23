# RapidAPI 테스트 수정 (실제 Playground 명세 적용)

## 변경 핵심
추측 endpoint 7개 전부 제거. RapidAPI Code Snippet 그대로 1개만 호출.

Code Snippet 기준:
  GET /download_video/{video_id}?quality={quality}
  headers: x-rapidapi-key, x-rapidapi-host, Content-Type: application/json

## 요청하신 작업 반영
1. 추측 endpoint 목록 제거 ✓
2. 실제 path 사용: /download_video/{video_id} ✓
3. 실제 query parameter: ?quality=247 (기본값, 조정 가능) ✓
4. 응답 JSON 그대로 반환 (raw_response) ✓
5. timeout 60초로 넉넉히 ✓
6. 로그에 호출 URL / status code / response text 출력 ✓

## 사용법 (배포 후)
GET https://<백엔드>/api/test/downloader?url=https://www.youtube.com/watch?v=jNQXAC9IVRw

quality 바꾸려면:
GET https://<백엔드>/api/test/downloader?url=...&quality=247

## 로그 (Render)
- "RapidAPI 호출 시작: GET https://.../download_video/{id}?quality=247"
- "RapidAPI 응답: status=200"
- "RapidAPI 응답 본문(앞 1000자): {...}"

## 응답 형태
성공: {"success": true, "request_url": "...", "status": 200, "is_json": true, "raw_response": {...}}
실패: {"success": false, "request_url": "...", "status": 4xx/5xx, "raw_response": "..."}

## 주의: quality=247이 뭔지
snippet의 247은 특정 포맷 코드로 보입니다(유튜브 itag와 유사).
이 API가 "사용 가능한 quality 목록 조회" 엔드포인트를 따로 제공할 수 있으니,
download_video 응답을 보고 quality 값을 맞춰야 할 수도 있습니다.
우선 247 그대로 호출해 raw_response를 확인하세요.
- 200 + 다운로드 URL이 오면 -> 성공, 그 구조로 다음 단계(스크린샷) 진행
- quality 관련 에러가 오면 -> 응답에 적힌 사용가능 quality로 재시도

## ⚠️ 보안
스크린샷에 API 키가 노출됐습니다(4ac8e2ca...로 시작).
RapidAPI에서 키 Regenerate(재발급) 후, Render 환경변수만 갱신하세요.
코드에는 키가 들어가지 않습니다(환경변수로만 사용).

## 변경 파일
- app/services/rapidapi_test.py (추측 제거, 실제 명세 1개 호출)
- app/api/test_downloader.py (quality 파라미터 추가)
