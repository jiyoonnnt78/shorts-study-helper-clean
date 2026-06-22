# 수정: Kiwi 이후 분석이 멈춤 (completed/failed 미기록)

## 로그 해석
```
00:33:25 kiwi_extractor INFO Kiwi 형태소 분석기 준비 완료
00:35:32 ==> Running 'python -m uvicorn ...'   <- 서버 재시작
```
Kiwi 로드 직후 ~2분 만에 프로세스가 통째로 재시작됨. completed/failed가 안 찍힌 이유는
**파이썬 예외가 아니라 프로세스 강제 종료(OOM kill)**이기 때문. 예외였다면 _mark_failed가
failed를 기록했을 것. Kiwi 모델 로드가 메모리(수백 MB)를 써서 512MB 환경에서 죽은 것으로 추정.

## 수정 내용

### 1) 단계별 로그 (요구사항)
explain() 전 구간에 진행 로그 추가:
- explain[1] 구간 문장 / [2] 문서 빌드 / [4] 출처 가중치 / [5] 핵심명사(use_kiwi 표시)
  / [6] 의도·확신도 / [9] 성공구조 / [10] 분석 provider
analyzer._run_metadata_only: 시작 / explain 호출 직전 / explain 반환 / completed 저장 로그.
=> 다음에 멈추면 **정확히 어느 단계인지** 로그로 보입니다.

### 2) 백그라운드 단계마다 status + commit + 로그
- _set_step()이 step 저장 + commit + 로그 (기존 업로드 경로).
- 메타데이터 경로도 동일하게 단계 로그 + 완료 시 status=completed commit.

### 3) OOM 회피 (핵심)
메타데이터 전용 분석(YouTube 링크, 영상 파일 없음)에서는 기본적으로 **Kiwi를 건너뜀**.
- 새 설정 KIWI_FOR_METADATA_ONLY (기본 false).
- 메타데이터는 텍스트가 짧아 규칙 기반 추출로 충분 -> Kiwi 모델 로드 자체를 안 해서
  메모리 급증/OOM을 피함.
- 업로드 영상(OCR/STT 있음)은 기존대로 ENABLE_KIWI를 따름.

## 설정
```
ENABLE_KIWI=true                 # 업로드 영상 분석에 Kiwi 사용
KIWI_FOR_METADATA_ONLY=false     # 메타데이터(YouTube) 분석은 Kiwi 생략 (메모리 절약)
```
메모리 여유가 있고 메타데이터 토픽 정확도를 높이고 싶으면 true로.

## 변경 파일
- app/services/explainer.py : 단계 로그, 메타데이터 전용 시 Kiwi 생략 분기
- app/services/analyzer.py  : _run_metadata_only 단계 로그
- app/config.py             : KIWI_FOR_METADATA_ONLY 추가
- .env.example              : 설정 문서화

## 만약 그래도 멈춘다면
새 로그에서 마지막으로 찍힌 explain[N]을 확인하세요.
- explain[5]에서 멈춤 + use_kiwi=True -> 여전히 Kiwi OOM. KIWI_FOR_METADATA_ONLY=false 확인.
- explain[10] 부근 멈춤 + LLM 켬 -> LLM 호출 타임아웃/메모리. ENABLE_LLM_ANALYSIS=false로.
- 어느 단계도 안 찍히고 재시작 -> Render 인스턴스 메모리 부족. 플랜 상향 또는 Kiwi/STT/OCR 축소.

## 적용
4개 파일 덮어쓰고 재배포. 기본값(KIWI_FOR_METADATA_ONLY=false)만으로 OOM은 해결될 것.
