# 훅 분석 Vision화 + 진행 상태 UI + 핵심 장면/개발자 패널 정리

## 1. 훅 분석 카드 (Vision 기반)
### 백엔드
- vision_analyzer.py: 프롬프트에 훅 필드 추가
  hook_type, hook_strength(0~100), hook_summary, hook_reason, hook_improvement_tip
  "훅은 첫 1~2 프레임과 제목 중심으로 판단" 지시.
- models.py: hook_summary, hook_improvement_tip 컬럼 추가
  (hook_strength는 기존에 있었음)
- database.py: ensure_schema에 새 컬럼 등록 -> 배포 시 PostgreSQL 자동 추가
- schemas.py: SummaryOut에 hook_summary, hook_improvement_tip 추가
- analyzer.py(_map_vision_to_summary): 훅 필드 매핑 + strength 0~100 보정
### 프론트
- HookCard.tsx: hook_summary(초반에 어떻게 끄는지), hook_reason(왜 그렇게 판단),
  hook_improvement_tip(더 강하게 만들기) 표시. 강도 게이지는 hook_strength.

## 2. 진행 상태 UI
### 백엔드
- schemas.py StatusResponse에 progress(int), message(str) 추가
- videos.py: 단계->진행률/문구 매핑(_progress_for)
  metadata=10, downloading=30, download_completed=40, probing_video=45,
  extracting_frames=55, running_vision/vision_analyzing=75,
  generating_summary=90, completed=100, failed=100
### 프론트
- videos/[id]/analyzing/page.tsx 재작성:
  - status API의 progress/message로 진행바 + 단계 표시
  - 진행바가 멈춰 보이지 않게 부드럽게 차오르는 애니메이션(+점 애니메이션)
  - 1.5초 polling, completed면 결과로 이동, failed면 친절한 오류 문구
  - "1~2분 걸릴 수 있어요" 안내

## 3. "핵심 장면 4곳 분석" -> "핵심 장면 분석"
- StageSamplesCard.tsx, page.tsx 텍스트 변경 (6장까지 나오므로 "4곳" 제거)

## 4. 개발자용 분석 패널 숨김
- page.tsx에서 DevPanel 렌더/import 제거 (OCR/STT 미사용으로 불필요)

## 변경 파일
백엔드: vision_analyzer.py, analyzer.py, models.py, database.py, schemas.py, api/videos.py
프론트: HookCard.tsx, lib/types.ts, videos/[id]/analyzing/page.tsx,
        videos/[id]/page.tsx, components/StageSamplesCard.tsx

## 검증
- 훅 필드 매핑(type/strength=85/summary/improvement_tip) 정상
- progress 매핑 정상 (10~100)
- 새 컬럼 자동 마이그레이션 확인 (SQLite/PostgreSQL)
- 프론트 빌드 성공
- 진행바 화면 렌더 확인

## 환경변수/requirements
변경 없음 (이전 Vision 설정 그대로)
