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
def _topic_word(inp: StructureInput) -> str:
    """대표 주제어 1개 (없으면 빈 문자열). 팁 문장에 끼워 구체화한다."""
    for k in inp.keywords:
        # 의도 표현(설명/후기 등)이 아닌 진짜 주제 명사 우선
        if k and len(k) >= 2:
            return k
    return ""


def _subject_phrase(inp: StructureInput) -> str:
    """'이 [주제]' 형태의 자연스러운 지칭. 주제어 없으면 '이 영상'."""
    w = _topic_word(inp)
    return f"'{w}'" if w else "이 영상"


# 훅 유형별 구체 전략 — 영상의 시작 방식에 맞춘 실행 가능한 팁
def _hook_strategy_tips(hook_type: str, subj: str) -> list[str]:
    table = {
        "궁금증 유발형": [
            f"{subj}에서 가장 궁금한 질문을 첫 문장 자막으로 띄우고, 답은 영상 끝에 공개해보세요.",
            "정답을 바로 말하지 말고 '과연 될까?' 같은 한마디로 긴장을 만든 뒤 결과를 보여주세요.",
        ],
        "결과 먼저 보여주기형": [
            f"완성된 결과를 0~2초에 먼저 보여주고, 그다음 '어떻게 했는지'를 거꾸로 풀어보세요.",
            "결과 장면을 가장 화려한 컷으로 맨 앞에 배치하고, 과정은 빠르게 이어붙여보세요.",
        ],
        "리스트·순위형": [
            "1위를 맨 마지막에 공개한다고 예고해서 끝까지 보게 만들어보세요.",
            "각 순위를 짧게 끊어 보여주고, 숫자 자막(①②③)으로 다음이 궁금하게 만들어보세요.",
        ],
        "재미·반전형": [
            "평범하게 시작했다가 예상 밖 장면으로 뒤집는 반전 포인트를 한 번 넣어보세요.",
            "웃음 포인트를 3초 안에 한 번 먼저 터뜨려서 이탈을 막아보세요.",
        ],
        "공감·감정형": [
            "보는 사람이 '내 얘기 같다'고 느낄 상황을 첫 장면에 보여주세요.",
            "감정이 가장 강한 순간을 클로즈업하고, 그 위에 짧은 속마음 자막을 얹어보세요.",
        ],
        "정보 제시형": [
            "가장 놀라운 정보 하나를 첫 문장에 먼저 던지고 설명을 이어보세요.",
            "'사실 ~였대요' 같은 반전 정보로 시작해서 끝까지 보게 만들어보세요.",
        ],
        "잔잔한 시작형": [
            "지금은 시작이 잔잔해요. 가장 흥미로운 장면을 맨 앞 3초로 끌어와보세요.",
            "첫 화면에 오늘 영상에서 볼 결과를 살짝 미리 보여주는 컷을 넣어보세요.",
        ],
    }
    return table.get(hook_type, table["정보 제시형"])


# 카테고리별 구체 전략 — 주제어를 끼워 그 영상에 맞춘 팁
def _category_strategy_tips(category: str, subj: str, topic: str) -> list[str]:
    t = topic or "핵심 소재"
    table = {
        "방법 설명": [
            f"{t}을(를) 만드는 과정을 ①준비 ②실행 ③완성 세 컷으로 끊어 자막을 달아보세요.",
            f"가장 자주 틀리는 부분을 '여기서 주의!' 자막과 함께 느리게 보여주세요.",
        ],
        "후기/경험": [
            f"{t}을(를) 써보기 전과 후를 나란히 비교하는 장면을 넣어보세요.",
            "가장 솔직한 반응(놀람·실망)이 나온 순간을 자르지 말고 그대로 보여주세요.",
        ],
        "재미/오락": [
            "가장 웃긴 장면을 썸네일이자 첫 컷으로 써서 '이거 보려고' 들어오게 만드세요.",
            f"{t} 상황에서 예상과 다른 결말을 마지막에 배치해 한 번 더 웃게 하세요.",
        ],
        "축하/응원": [
            f"{t}에게 전하고 싶은 한마디를 큰 손글씨 자막으로 마지막에 띄워보세요.",
            "받는 사람의 표정이나 반응 장면을 넣어 진심이 전해지게 해보세요.",
        ],
        "정보 전달": [
            f"{t}에 대해 사람들이 잘못 알고 있는 점을 '사실은?'으로 바로잡아보세요.",
            "숫자나 비교(2배, 절반)를 자막으로 보여주면 정보가 더 와닿아요.",
        ],
        "소개/홍보": [
            f"{t}의 가장 좋은 점 하나만 골라 첫 3초에 보여주세요.",
            "직접 써보는 장면을 넣어 '말'이 아니라 '증거'로 보여주세요.",
        ],
        "이야기/브이로그": [
            f"오늘 이야기의 결론(가장 인상적인 순간)을 맨 앞에 미리 보여주세요.",
            "장면이 바뀔 때 시간·장소 자막을 넣어 흐름을 따라가기 쉽게 해보세요.",
        ],
        "의견/주장": [
            "주장을 첫 문장에 분명히 밝히고, 그 뒤에 이유를 하나씩 보여주세요.",
            "반대 의견을 먼저 짧게 보여준 뒤 내 생각으로 반박하는 구성을 써보세요.",
        ],
    }
    return table.get(category, [])


# 성공 법칙에서 못 살린 점을 보완하는 팁 (영상이 실제로 약한 부분만)
def _gap_tips(inp: StructureInput) -> list[str]:
    tips: list[str] = []
    long_count = sum(1 for f in inp.seg_features if "long_scene" in f)
    if long_count >= 1:
        tips.append("늘어지는 장면은 1~2초로 잘라 붙여서 속도감을 만들어보세요.")
    if inp.segment_count < 3:
        tips.append("장면이 적어요. 도입–본론–마무리 세 덩어리로 나눠 찍어보세요.")
    if not inp.has_large_text and inp.category in ("방법 설명", "정보 전달"):
        tips.append("핵심 단계마다 큰 자막을 얹으면 소리 없이 봐도 이해돼요.")
    return tips


def make_creator_tips(
    inp: StructureInput, hook_strength: int, hook_type: str = ""
) -> list[str]:
    """
    이 영상의 훅 유형 × 카테고리 × 주제를 조합한 '맞춤형' 제작 팁.
    일반론("자막 크게")이 아니라, 그 영상에서 실제로 써먹을 구체 전략을 만든다.
    서로 다른 전략으로 최소 5개를 보장한다.
    """
    subj = _subject_phrase(inp)
    topic = _topic_word(inp)

    ordered: list[str] = []
    # 1) 훅 전략 (영상의 시작 방식에 맞춤)
    ordered += _hook_strategy_tips(hook_type, subj)
    # 2) 카테고리 전략 (주제어를 끼운 구체 실행)
    ordered += _category_strategy_tips(inp.category, subj, topic)
    # 3) 약한 부분 보완
    ordered += _gap_tips(inp)

    # 중복 제거 (순서 유지)
    seen: set[str] = set()
    tips: list[str] = []
    for t in ordered:
        if t not in seen:
            seen.add(t)
            tips.append(t)

    # 최소 5개 보장: 부족하면 서로 다른 범용 전략(그래도 구체적)으로 채운다
    fillers = [
        "처음 1초에 가장 강한 장면을 배치해 스크롤을 멈추게 해보세요.",
        "영상 끝에 '다음엔 ○○ 보여줄게요'를 넣어 다음 영상도 보게 만들어보세요.",
        "같은 장면을 다른 각도로 한 번 더 보여줘 지루함을 줄여보세요.",
        "배경음악의 박자에 맞춰 장면을 전환하면 리듬감이 생겨요.",
    ]
    for f in fillers:
        if len(tips) >= 5:
            break
        if f not in seen:
            seen.add(f)
            tips.append(f)

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
    tips = make_creator_tips(inp, hook_strength, hook_type=hook_type)
    return SuccessAnalysis(
        hook_type=hook_type,
        hook_reason=hook_reason,
        hook_strength=hook_strength,
        structure=structure,
        success_patterns=patterns,
        creator_tips=tips,
    )


# ---------------------------------------------------------------------------
# 규칙 기반 structure_detail (opening/development/climax/ending + content/purpose)
# ---------------------------------------------------------------------------
def build_structure_detail(inp: "StructureInput", hook_type: str) -> dict:
    """
    규칙 신호로 opening/development/climax/ending 각 {content, purpose}를 만든다.
    LLM 없이도 LLM 출력과 같은 형태를 제공해 프론트가 일관되게 렌더링하도록.
    """
    subj = _subject_phrase(inp)
    topic = _topic_word(inp) or "핵심 소재"
    n = inp.segment_count

    opening_purpose = {
        "궁금증 유발형": "궁금증을 자극해 끝까지 보게 만들어요",
        "결과 먼저 보여주기형": "결과를 먼저 보여줘 '어떻게?'를 궁금하게 해요",
        "리스트·순위형": "순위를 예고해 다음이 기대되게 해요",
        "재미·반전형": "웃음·의외성으로 시선을 확 끌어요",
        "공감·감정형": "공감되는 장면으로 마음을 끌어요",
        "정보 제시형": "핵심 정보를 먼저 던져 관심을 끌어요",
        "잔잔한 시작형": "천천히 분위기를 잡으며 시작해요",
    }.get(hook_type, "첫 장면으로 시선을 끌어요")

    detail = {
        "opening": {
            "content": f"{subj}을(를) 소개하며 영상이 시작돼요.",
            "purpose": opening_purpose,
        },
        "development": {
            "content": f"{topic}에 대한 내용을 차례대로 보여줘요."
            if n >= 2 else "내용을 이어서 보여줘요.",
            "purpose": "필요한 정보를 단계적으로 풀어 계속 보게 해요",
        },
        "climax": {
            "content": f"{topic}에서 가장 중요한 장면이나 정보가 나와요.",
            "purpose": "이 영상에서 가장 전하고 싶은 부분이에요",
        },
        "ending": {
            "content": "내용을 정리하거나 마무리 장면으로 끝나요."
            if n >= 2 else "짧게 마무리돼요.",
            "purpose": "끝까지 본 보람과 인상을 남겨요",
        },
    }
    return detail


def to_analysis_result(inp: "StructureInput", sa: "SuccessAnalysis"):
    """규칙 기반 SuccessAnalysis -> 공통 AnalysisResult로 변환."""
    from .analysis_provider import AnalysisResult

    return AnalysisResult(
        summary="",   # 규칙 기반은 요약문을 따로 만들지 않음 (explainer의 topic/purpose 사용)
        topic=_topic_word(inp),
        hook_type=sa.hook_type,
        hook_strength=sa.hook_strength,
        hook_reason=sa.hook_reason,
        structure_detail=build_structure_detail(inp, sa.hook_type),
        engagement_factors=list(sa.success_patterns[:3]),  # 규칙: 성공법칙 일부를 몰입요소로
        success_patterns=sa.success_patterns,
        creator_tips=sa.creator_tips,
        provider="rule",
    )
