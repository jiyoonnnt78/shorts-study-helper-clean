# 수정: YouTube 링크 분석에서도 영상 구조 분석이 풍부하게 나오도록

## 문제
metadata-only 분석(YouTube 링크, segment 0개)에서 structure_detail이 빈약해
화면에 훅 분석 정도만 보이고 오프닝/전개/클라이맥스/마무리가 거의 안 나왔음.

## 수정 (백엔드)
### app/services/success_analyzer.py
- StructureInput에 title/description/hashtags 추가.
- analyze_hook: 키워드뿐 아니라 **제목·설명·해시태그도 신호로 사용**.
  metadata-only일 때 '잔잔한 시작형'으로 강제하지 않고 제목 기반으로 훅 유형 판정.
  (예: "...TOP5" -> 리스트·순위형, "...완성/후기" -> 결과 먼저 보여주기형)
- build_structure_detail: 제목을 활용해 오프닝/전개/클라이맥스/마무리를
  **구체적 문장으로 추정**. 각 단계에 content(무엇을) + purpose(왜).
- _topic_word: 해시태그 > 키워드 > 제목 순으로 주제어 선택,
  의도표현(설명/방법)·숫자토큰(TOP5)·약한 단어(남자/여자/사람) 제외.
  => "여자패션 TOP5" 영상에서 주제어 '패션'을 정확히 추출.

### app/services/explainer.py
- StructureInput에 youtube_title/description/hashtags 전달.

## 수정 (프론트)
### src/components/StructureDetailCard.tsx
- 제목을 "영상 구조 분석"으로, 부제 "오프닝 → 전개 → 클라이맥스 → 마무리".
- 각 단계에 번호(1~4) 표시.
- 하단에 "제작 가이드" 안내: 이 순서대로 만들면 된다는 문장 추가 (요구사항 5).
- 결과 페이지에서 훅 분석 카드 바로 아래에 위치 (기존 연결 유지).

## 검증
- "여자패션 TOP5" -> 훅: 리스트·순위형 / 주제어: 패션 / 4단계 구체 문장 / 팁 5개
- "김치볶음밥 완성" -> 결과 먼저 보여주기형 / 주제어: 요리
- "아이폰 후기" -> 결과 먼저 보여주기형 / 주제어: 아이폰
- API 응답에 structure_detail + creator_tips 5개 정상 전달
- 프론트 빌드 통과

## 적용
backend 2개 + frontend 1개 파일 덮어쓰고 재배포.
segment 없는 YouTube 분석도 구조 분석이 풍부하게 표시됨.
