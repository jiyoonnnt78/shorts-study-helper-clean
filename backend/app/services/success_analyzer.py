"""
숏폼 성공 구조 분석 (교육용).

목적
====
"이 영상이 무슨 내용인가"(요약)를 넘어
"왜 이 영상이 관심을 끄는가"(성공 구조)를 학생에게 설명한다.

이미 추출된 정보(segment별 OCR/STT, 타이밍 feature, 의도 카테고리,
감정/행동 신호, 핵심 키워드)만으로 아래를 만든다:
- Hook 분석     : hook_type / hook_reason / hook_strength
- 영상 구조     : 오프닝 -> 전개 -> 핵심 -> 마무리 단계
- 성공 법칙     : success_patterns
- 제작 팁       : creator_tips

확장성
======
유튜브 연동 후 title/description/tags가 들어오면 _hook_signals 등의
입력에 메타데이터 신호를 더하기만 하면 된다 (구조는 그대로).
"""
from __future__ import annotations

from dataclasses import dataclass, field


# ---------------------------------------------------------------------------
# 입력 신호 (explainer가 모아서 넘겨줌)
# ---------------------------------------------------------------------------
@dataclass
class StructureInput:
    duration: float
    segment_count: int
    # segment별 정보 (순서대로)
    seg_starts: list[float] = field(default_factory=list)
    seg_ends: list[float] = field(default_factory=list)
    seg_features: list[list[str]] = field(default_factory=list)
    seg_has_text: list[bool] = field(default_factory=list)   # OCR 글자 있는지
    seg_has_speech: list[bool] = field(default_factory=list)  # 말 있는지
    # 전체 분석 결과
    category: str = "기타"
    keywords: list[str] = field(default_factory=list)
    intent_expressions: list[str] = field(default_factory=list)
    emotions: list[str] = field(default_factory=list)
    has_large_text: bool = False
    first_question: bool = False   # 도입부에 질문/궁금증 신호
    confidence: float = 0.0


# ---------------------------------------------------------------------------
# 1) Hook 분석
# ---------------------------------------------------------------------------
# 도입부에서 궁금증을 유발하는 표현 (질문/예고/반전)
_HOOK_CURIOSITY = ["?", "왜", "어떻게", "과연", "진짜", "이거 아세요", "비밀", "충격", "방법"]
_HOOK_RESULT_FIRST = ["완성", "결과", "후기", "전후", "before", "after", "변화"]
_HOOK_NUMBER = ["1위", "top", "베스트", "순위", "가지", "개"]


def analyze_hook(inp: StructureInput) -> tuple[str, str, int]:
    """
    도입부 신호로 훅 유형/이유/강도를 추정.
    반환: (hook_type, hook_reason, hook_strength 0~100)
    """
    first_feats = inp.seg_features[0] if inp.seg_features else []
    first_text = inp.seg_has_text[0] if inp.seg_has_text else False
    first_speech = inp.seg_has_speech[0] if inp.seg_has_speech else False
    kw_blob = " ".join(inp.keywords)

    strength = 35  # 기본값
    hook_type = "정보 제시형"
    reason = "처음에 주제를 바로 보여주며 영상을 시작해요."

    # 빠른 시작 (도입부가 짧음) -> 강한 훅
    if "fast_start" in first_feats:
        strength += 20

    # 큰 자막으로 시작 -> 시선 집중
    if inp.has_large_text and first_text:
        strength += 12

    # 도입부에 글자+말이 함께 -> 메시지가 분명
    if first_text and first_speech:
        strength += 8

    # 유형 판별 (우선순위: 궁금증 > 결과먼저 > 숫자/리스트 > 감정 > 정보)
    if inp.first_question or any(w in kw_blob for w in _HOOK_CURIOSITY):
        hook_type = "궁금증 유발형"
        reason = "처음 몇 초 안에 궁금증을 자극해서 끝까지 보고 싶게 만들어요."
        strength += 18
    elif any(w in kw_blob.lower() for w in _HOOK_RESULT_FIRST):
        hook_type = "결과 먼저 보여주기형"
        reason = "결과나 완성된 모습을 먼저 보여줘서 '어떻게 했지?'를 궁금하게 해요."
        strength += 16
    elif any(w in kw_blob.lower() for w in _HOOK_NUMBER):
        hook_type = "리스트·순위형"
        reason = "숫자나 순위를 앞세워서 '몇 개나 될까?'를 기대하게 만들어요."
        strength += 12
    elif "재미" in inp.emotions or inp.category == "재미/오락":
        hook_type = "재미·반전형"
        reason = "웃기거나 의외인 장면으로 시작해서 시선을 확 끌어요."
        strength += 14
    elif inp.category in ("축하/응원", "감정 표현"):
        hook_type = "공감·감정형"
        reason = "감정을 자극하는 장면으로 시작해서 마음을 움직여요."
        strength += 10

    # 도입부에 아무 단서도 없으면 약한 훅
    if not first_text and not first_speech:
        hook_type = "잔잔한 시작형"
        reason = "처음에 글자나 말이 적어서 무슨 내용인지 천천히 드러나요."
        strength = min(strength, 40)

    strength = max(10, min(95, strength))
    return hook_type, reason, strength


# ---------------------------------------------------------------------------
# 2) 영상 구조 (오프닝 -> 전개 -> 핵심 -> 마무리)
# ---------------------------------------------------------------------------
# 구조 단계 라벨 (역할 기반, 길이에 따라 자동 배분)
_STAGE_LABELS = {
    "opening": ("오프닝", "🎣", "시선을 끌어요"),
    "build": ("전개", "📖", "내용을 풀어가요"),
    "killing": ("핵심 장면", "⭐", "가장 중요한 부분이에요"),
    "ending": ("마무리", "🏁", "정리하거나 마무리해요"),
}


def analyze_structure(inp: StructureInput) -> list[dict]:
    """
    segment 타이밍을 4단계 역할(오프닝/전개/핵심/마무리)에 매핑.
    각 단계: {role, label, emoji, note, start, end}
    """
    n = inp.segment_count
    if n == 0 or not inp.seg_starts:
        return []

    starts, ends = inp.seg_starts, inp.seg_ends

    # segment 수에 따라 역할 배분
    if n == 1:
        roles = ["opening"]
    elif n == 2:
        roles = ["opening", "ending"]
    elif n == 3:
        roles = ["opening", "killing", "ending"]
    else:
        # 4개 이상: 첫=오프닝, 마지막=마무리, 가운데를 전개/핵심으로
        roles = ["opening"]
        middle = n - 2
        # 가운데에서 뒤쪽 절반을 핵심으로 (킬링파트는 보통 중후반)
        for i in range(middle):
            roles.append("killing" if i >= middle / 2 else "build")
        roles.append("ending")

    # 같은 역할 연속이면 하나로 합쳐 보여준다
    stages: list[dict] = []
    for i, role in enumerate(roles):
        label, emoji, note = _STAGE_LABELS[role]
        seg_start = starts[i] if i < len(starts) else 0.0
        seg_end = ends[i] if i < len(ends) else seg_start
        if stages and stages[-1]["role"] == role:
            stages[-1]["end"] = seg_end  # 연속 구간 병합
        else:
            stages.append({
                "role": role, "label": label, "emoji": emoji,
                "note": note, "start": round(seg_start, 1), "end": round(seg_end, 1),
            })
    return stages


# ---------------------------------------------------------------------------
# 3) 성공 법칙
# ---------------------------------------------------------------------------
def analyze_success_patterns(inp: StructureInput, hook_strength: int) -> list[str]:
    """이 영상이 가진 '잘 만든 점'을 골라낸다 (해당하는 것만)."""
    patterns: list[str] = []

    if hook_strength >= 60:
        patterns.append("처음 몇 초 안에 시선을 확실히 잡아요")
    if inp.has_large_text:
        patterns.append("큰 자막으로 핵심을 또렷하게 보여줘요")

    # 빠른 템포: 짧은 장면이 많음
    short_count = sum(1 for f in inp.seg_features if "short_scene" in f)
    if short_count >= max(2, inp.segment_count // 2):
        patterns.append("장면을 빠르게 바꿔서 지루할 틈을 안 줘요")

    # 글자+말 동시 전달
    both = sum(1 for t, s in zip(inp.seg_has_text, inp.seg_has_speech) if t and s)
    if both >= 2:
        patterns.append("글자와 말을 함께 써서 내용을 쉽게 전달해요")

    # 감정 활용
    if inp.emotions:
        patterns.append("감정을 담아서 보는 사람의 마음을 움직여요")

    # 명확한 의도
    if inp.intent_expressions:
        kinds = "·".join(inp.intent_expressions[:2])
        patterns.append(f"무엇을 하려는지({kinds}) 분명하게 드러나요")

    # 마무리가 따로 있음 (구조가 완결적)
    if inp.segment_count >= 3:
        patterns.append("끝에 정리·마무리가 있어서 깔끔하게 닫혀요")

    # 적정 길이 (쇼츠 호흡)
    if 0 < inp.duration <= 35:
        patterns.append("짧고 간결해서 끝까지 보기 좋아요")

    if not patterns:
        patterns.append("아직 두드러진 성공 요소는 적지만, 기본 구조는 갖췄어요")
    return patterns[:6]


# ---------------------------------------------------------------------------
# 4) 제작 팁 (학생이 자기 영상 만들 때)
# ---------------------------------------------------------------------------
def make_creator_tips(inp: StructureInput, hook_strength: int) -> list[str]:
    """이 영상에서 배워 자기 쇼츠에 적용할 실전 팁."""
    tips: list[str] = []

    # 훅이 약하면 보강 팁, 강하면 따라하기 팁
    if hook_strength < 55:
        tips.append("첫 3초 안에 가장 궁금한 것이나 결과를 먼저 보여줘요")
    else:
        tips.append("이 영상처럼 처음 3초에 시선을 끄는 장면을 넣어요")

    if not inp.has_large_text:
        tips.append("중요한 말은 큰 자막으로도 보여주면 더 잘 전달돼요")
    else:
        tips.append("핵심 단어는 큰 자막으로 강조해요")

    # 마무리
    if inp.segment_count < 3:
        tips.append("끝에 핵심을 한 번 더 정리하면 기억에 남아요")
    else:
        tips.append("마지막에 핵심을 정리해서 깔끔하게 마무리해요")

    # 템포
    long_count = sum(1 for f in inp.seg_features if "long_scene" in f)
    if long_count >= 1:
        tips.append("한 장면이 너무 길면 지루해요. 장면을 짧게 끊어줘요")
    else:
        tips.append("빠른 템포를 유지해서 끝까지 보게 만들어요")

    # 카테고리 맞춤 팁
    cat_tip = {
        "방법 설명": "순서를 1, 2, 3처럼 번호로 나눠 보여주면 따라하기 쉬워요",
        "후기/경험": "솔직한 느낌과 결과를 같이 보여주면 더 믿음이 가요",
        "재미/오락": "웃음 포인트를 앞쪽에 배치하면 더 많이 봐요",
        "축하/응원": "진심이 담긴 한마디를 자막으로 남기면 감동이 커져요",
        "정보 전달": "어려운 말은 쉬운 말로 바꿔서 설명해요",
        "소개/홍보": "가장 좋은 점을 먼저 보여주고 이유를 설명해요",
    }.get(inp.category)
    if cat_tip:
        tips.append(cat_tip)

    return tips[:6]


# ---------------------------------------------------------------------------
# 통합 진입점
# ---------------------------------------------------------------------------
@dataclass
class SuccessAnalysis:
    hook_type: str
    hook_reason: str
    hook_strength: int
    structure: list[dict]
    success_patterns: list[str]
    creator_tips: list[str]


def analyze_success_structure(inp: StructureInput) -> SuccessAnalysis:
    hook_type, hook_reason, hook_strength = analyze_hook(inp)
    structure = analyze_structure(inp)
    patterns = analyze_success_patterns(inp, hook_strength)
    tips = make_creator_tips(inp, hook_strength)
    return SuccessAnalysis(
        hook_type=hook_type,
        hook_reason=hook_reason,
        hook_strength=hook_strength,
        structure=structure,
        success_patterns=patterns,
        creator_tips=tips,
    )
