"""
쉬운 말 변환 (Explainer) — 전체 맥락 기반으로 재설계.

핵심 변화
=========
- topic을 "키워드 한 개 + 조사"로 만들지 않는다.
  대신 [영상의 의도(카테고리)] + [영상 전체에서 본 핵심 개념]을
  자연스러운 한 문장으로 합성한다.
    나쁨: "선생님이에요에 대한 영상"
    좋음: "졸업을 축하하고 응원하는 영상인 것 같아요."
- 분석은 첫 segment가 아니라 모든 segment의 글자/말/제목/설명을 합친
  '전체 문서'에서 한다. (text_analysis.build_document)
- OCR/STT를 동일 취급하지 않고 신뢰도(source_weights)를 계산하고,
  STT가 배경 노래 가사로 의심되면 STT 비중을 낮춘다.
- 확신이 낮으면 단정하지 않는다.

모든 문장은 초등 4~6학년 기준 쉬운 말. 추천은 관심사 기준만.
ExplainerAdapter 인터페이스는 유지 -> 나중에 LLM 구현으로 교체 가능.
"""
from __future__ import annotations

import logging
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import Segment, Video, VideoSummary
from . import text_analysis as ta

logger = logging.getLogger("explainer")

CATEGORY_OTHER = "기타"

# 카테고리 = 영상의 넓은 의도. 주제가 아니라 의도라서 장르에 무관하다.
CATEGORIES = [
    "정보 전달", "방법 설명", "재미/오락", "감정 표현",
    "후기/경험", "소개/홍보", "이야기/브이로그", "의견/주장", "축하/응원",
]

CONF_HIGH = 0.65
CONF_MID = 0.35

# 각 카테고리를 가리키는 행동 신호 (text_analysis의 행동 라벨 재사용)
_ACTION_TO_CATEGORY = {
    "설명": "방법 설명",
    "소개": "소개/홍보",
    "비교": "정보 전달",
    "응원": "축하/응원",
    "후기": "후기/경험",
    "주장": "의견/주장",
}

# 행동 테이블에 없는 카테고리 보강 (최소한의 의도 신호)
# 강한 신호(단독으로도 브이로그/정보로 인정)와 약한 신호(다른 단서와 함께일 때만)를 나눈다.
_EXTRA_SIGNALS = {
    "이야기/브이로그": ["브이로그", "vlog", "일상", "데일리"],
    "정보 전달": ["알려드", "사실은", "뉴스", "이유는", "뜻은"],
}
# 약한 신호: 단독으로는 카테고리를 못 정하고, 위 강한 신호가 이미 있을 때만 가산
_WEAK_EXTRA_SIGNALS = {
    "이야기/브이로그": ["하루", "루틴", "다녀온", "다녀왔", "오늘"],
}


# ===========================================================================
# 1) 영상 의도(카테고리) 판단
# ===========================================================================
@dataclass
class IntentResult:
    category: str
    scores: dict[str, float]
    best: float
    second: float


def classify_intent(doc: ta.CombinedDoc, concepts: ta.Concepts) -> IntentResult:
    """전체 문서의 행동/감정 신호를 종합해 '무엇을 하려는 영상인가'를 정한다."""
    # 우리가 만든 제목/설명("내용을 설명하는 부분"의 '설명' 등)이 신호를 오염시키지
    # 않도록, 추가 단어 신호도 실제 콘텐츠(content_text)에서만 찾는다.
    text = doc.content_text.lower()
    scores: dict[str, float] = {c: 0.0 for c in CATEGORIES}

    # 행동 신호 = 영상이 '무엇을 하려는가'의 주된 단서 -> 가장 강하게 본다
    for action in concepts.actions:
        cat = _ACTION_TO_CATEGORY.get(action)
        if cat in scores:
            scores[cat] += 2.0
    has_action = any(_ACTION_TO_CATEGORY.get(a) in scores for a in concepts.actions)

    for cat, words in _EXTRA_SIGNALS.items():
        for w in words:
            if w in text:
                scores[cat] += 1.0

    # 약한 신호(하루/오늘 등)는 같은 카테고리의 강한 신호가 이미 잡혔을 때만 보강
    for cat, words in _WEAK_EXTRA_SIGNALS.items():
        if scores.get(cat, 0.0) > 0:
            for w in words:
                if w in text:
                    scores[cat] += 0.5

    # 감정 신호: 행동이 분명하면 부차적(작게), 행동이 없으면 주된 의도로(크게).
    # 단, 같은 감정 신호가 여러 개 겹치면(예: 개그+웃긴+ㅋㅋ) 그 감정을 더 신뢰한다.
    if concepts.emotions:
        fun_hits = ta._count_emotion_hits(text, "재미")
        fun_w = (0.6 if has_action else 1.6) + max(0, fun_hits - 1) * 0.7
        emo_w = 0.5 if has_action else 1.2
        if "재미" in concepts.emotions:
            scores["재미/오락"] += fun_w
        non_fun = [e for e in concepts.emotions if e != "재미"]
        if non_fun:
            scores["감정 표현"] += emo_w * len(non_fun)
        if "감동" in concepts.emotions or "기쁨" in concepts.emotions:
            scores["축하/응원"] += 0.5

    nonzero = {k: v for k, v in scores.items() if v > 0}
    if not nonzero:
        return IntentResult(CATEGORY_OTHER, scores, 0.0, 0.0)

    ranked = sorted(nonzero.items(), key=lambda kv: -kv[1])
    best_cat, best = ranked[0]
    second = ranked[1][1] if len(ranked) > 1 else 0.0
    return IntentResult(best_cat, scores, best, second)


# ===========================================================================
# 2) 확신도
# ===========================================================================
def compute_confidence(
    intent: IntentResult,
    doc: ta.CombinedDoc,
    overlap: float,
    top_concept_count: int,
    key_noun_count: int = 0,
    metadata_used: bool = False,
    metadata_weight: float = 0.0,
) -> tuple[float, str]:
    """
    OCR/STT/metadata 각각의 단서 수와 일치도로 확신을 계산한다.
    - 영상 내부 글자/말이 많고 일치할수록 확신↑
    - 핵심 명사가 또렷할수록 확신↑
    - 메타데이터로 보강되면 약간↑ (단, 메타데이터에만 의존하면 상한)
    """
    text_chars = ta.char_len(doc.full_text)
    internal_empty = text_chars < 6 and intent.best <= 0 and key_noun_count == 0

    # 내부 정보가 전혀 없고 메타데이터도 없으면 가장 낮은 확신
    if internal_empty and not metadata_used:
        return 0.08, "글자나 말이 거의 없어서 영상 내용을 더 확인해 봐야 할 것 같아요."

    conf = 0.15
    if text_chars >= 80:
        conf += 0.25
    elif text_chars >= 30:
        conf += 0.15
    elif text_chars >= 10:
        conf += 0.07
    conf += min(0.25, intent.best * 0.08)
    if intent.best - intent.second >= 2:
        conf += 0.1
    if overlap >= 0.2:          # OCR과 STT가 일치 -> 신뢰
        conf += 0.12
    if top_concept_count >= 2:
        conf += 0.08
    if key_noun_count >= 2:
        conf += 0.12
    elif key_noun_count == 1:
        conf += 0.05

    # 메타데이터 보강: 내부 정보가 있을 때 메타가 더해주면 소폭 가산.
    # 내부가 거의 없고 메타에만 의존하면 확신에 상한을 둬 단정하지 않게 한다.
    meta_capped = False
    if metadata_used:
        if internal_empty or metadata_weight >= 0.7:
            conf = min(conf + 0.1, 0.55)   # 메타 의존 -> 상한 0.55
            meta_capped = True
        else:
            conf += 0.05

    conf = round(min(0.95, conf), 2)
    if conf >= CONF_HIGH:
        reason = "글자와 말에서 핵심 단서를 찾았어요."
    elif conf >= CONF_MID:
        if meta_capped:
            reason = "영상 정보가 적어서 제목·설명도 함께 참고했어요."
        else:
            reason = "단서를 조금 찾았지만 확실하지는 않아요."
    else:
        reason = "글자나 말이 적어서 확실하지 않아요."
    return conf, reason


# ===========================================================================
# 3) topic 합성 (의도 + 핵심 개념 -> 자연스러운 문장)
# ===========================================================================
_TOPIC_FRAMES = {
    "정보 전달": "{what}에 대한 정보를 알려주는 영상인 것 같아요.",
    "방법 설명": "{what} 방법을 알려주는 영상인 것 같아요.",
    "재미/오락": "{what}을 보여주며 재미있게 만든 영상인 것 같아요.",
    "감정 표현": "{what}에 대한 마음을 표현하는 영상인 것 같아요.",
    "축하/응원": "{what}을 축하하고 응원하는 영상인 것 같아요.",
    "후기/경험": "{what}을 직접 해본 이야기를 들려주는 영상인 것 같아요.",
    "소개/홍보": "{what}을 소개하는 영상인 것 같아요.",
    "이야기/브이로그": "{what} 하루 이야기를 보여주는 영상인 것 같아요.",
    "의견/주장": "{what}에 대한 생각을 이야기하는 영상인 것 같아요.",
}

_TOPIC_GENERIC = {
    "정보 전달": "새로운 정보를 알려주는 영상인 것 같아요.",
    "방법 설명": "어떤 일을 하는 방법을 알려주는 영상인 것 같아요.",
    "재미/오락": "재미있는 장면을 보여주는 영상인 것 같아요.",
    "감정 표현": "느낀 마음을 표현하는 영상인 것 같아요.",
    "축하/응원": "누군가를 축하하고 응원하는 영상인 것 같아요.",
    "후기/경험": "직접 해본 이야기를 들려주는 영상인 것 같아요.",
    "소개/홍보": "무언가를 소개하는 영상인 것 같아요.",
    "이야기/브이로그": "하루 이야기를 보여주는 영상인 것 같아요.",
    "의견/주장": "자기 생각을 이야기하는 영상인 것 같아요.",
}


def _josa_eul(word: str) -> str:
    if not word:
        return "을"
    ch = word[-1]
    if "가" <= ch <= "힣":
        return "을" if (ord(ch) - 0xAC00) % 28 else "를"
    return "을"


def _what_phrase(concepts: ta.Concepts) -> str | None:
    """
    topic에 들어갈 주제구. 핵심 주제 명사 1~2개를 자연스러운 명사구로 만든다.
    명사가 없으면 None (그러면 카테고리 일반 문장 사용).
    """
    nouns = [n for n in concepts.nouns if len(n) >= 2 and n not in ta._WEAK_NOUNS]
    if not nouns:
        nouns = [n for n in concepts.nouns if len(n) >= 2]
    if not nouns:
        return None
    if len(nouns) == 1:
        return nouns[0]
    joiner = "과" if _josa_eul(nouns[0]) == "을" else "와"
    return f"{nouns[0]}{joiner} {nouns[1]}"


def make_topic(category: str, concepts: ta.Concepts, confidence: float) -> str:
    if confidence < CONF_MID or category == CATEGORY_OTHER:
        return "영상 내용을 더 확인해 봐야 할 것 같아요."

    what = _what_phrase(concepts)

    # 의도 표현이 여러 개면(예: 감사+응원) 문장에 그대로 녹여 더 자연스럽게.
    # 예: "졸업과 선생님에 대한 감사와 응원을 전하는 영상인 것 같아요."
    intents = _topic_intent_phrase(category, concepts)
    if what and intents:
        # 예: "졸업과 선생님에 대한 감사와 응원을 전하는 영상인 것 같아요."
        sentence = f"{what}에 대한 {intents}{_josa_eul(intents)} 전하는 영상인 것 같아요."
        return ("아마 " + sentence) if confidence < CONF_HIGH else sentence

    frame = _TOPIC_FRAMES.get(category)
    if what and frame:
        sentence = _fill_frame(frame, what)
        return ("아마 " + sentence) if confidence < CONF_HIGH else sentence

    generic = _TOPIC_GENERIC.get(category, "영상 내용을 더 확인해 봐야 할 것 같아요.")
    return ("아마 " + generic) if confidence < CONF_HIGH else generic


# 카테고리별로 '의도 명사구'를 만들 때 쓰는 의도 표현 (감사/응원/축하 등)
_INTENT_NOUN = {
    "축하": "축하", "응원": "응원", "감사": "감사",
    "설명": "설명", "소개": "소개", "추천": "추천", "비교": "비교", "후기": "후기",
}
# 이 의도들이 함께 나올 때 '~을 전하는' 류의 문장이 자연스러운 카테고리
_TRANSFER_CATEGORIES = {"축하/응원", "감정 표현"}


def _topic_intent_phrase(category: str, concepts: ta.Concepts) -> str | None:
    """
    '감사와 응원' 처럼 의도 표현을 이어붙인 명사구. 전달형 카테고리에서만 사용.
    """
    if category not in _TRANSFER_CATEGORIES:
        return None
    found = [_INTENT_NOUN[e] for e in concepts.intent_expressions if e in _INTENT_NOUN]
    # 중복 제거, 순서 유지
    uniq: list[str] = []
    for w in found:
        if w not in uniq:
            uniq.append(w)
    if not uniq:
        return None
    if len(uniq) == 1:
        return uniq[0]
    return f"{uniq[0]}와 {uniq[1]}" if _josa_eul(uniq[0]) == "를" else f"{uniq[0]}과 {uniq[1]}"


def _fill_frame(frame: str, what: str) -> str:
    """topic 골격에 주제구를 받침에 맞춰 끼운다."""
    if "{what}을" in frame:
        return frame.replace("{what}을", f"{what}{_josa_eul(what)}")
    return frame.replace("{what}", what)


# ===========================================================================
# 4) purpose
# ===========================================================================
_PURPOSE = {
    "정보 전달": "친구들에게 새로운 정보를 알려주려고 만든 것 같아요.",
    "방법 설명": "어떤 일을 하는 방법을 쉽게 알려주려고 만든 것 같아요.",
    "재미/오락": "보는 사람을 웃게 하려고 만든 것 같아요.",
    "감정 표현": "느낀 마음을 친구들과 나누려고 만든 것 같아요.",
    "축하/응원": "응원하는 마음을 전하려고 만든 것 같아요.",
    "후기/경험": "직접 해본 경험을 나누려고 만든 것 같아요.",
    "소개/홍보": "좋은 것을 소개해 주려고 만든 것 같아요.",
    "이야기/브이로그": "자기 하루 이야기를 보여주려고 만든 것 같아요.",
    "의견/주장": "자기 생각을 사람들에게 이야기하려고 만든 것 같아요.",
    CATEGORY_OTHER: "이 영상이 왜 만들어졌는지는 조금 더 살펴봐야 알 수 있어요.",
}


def make_purpose(category: str, concepts: ta.Concepts, confidence: float) -> str:
    if confidence < CONF_MID or category == CATEGORY_OTHER:
        return _PURPOSE[CATEGORY_OTHER]
    return _PURPOSE.get(category, _PURPOSE[CATEGORY_OTHER])


# ===========================================================================
# 5) 추천 대상 (관심사 기준만)
# ===========================================================================
CATEGORY_AUDIENCE: dict[str, list[str]] = {
    "정보 전달": ["새로운 정보를 알고 싶은 친구"],
    "방법 설명": ["따라 해보고 싶은 친구", "처음 배우는 친구"],
    "재미/오락": ["재미있는 영상을 좋아하는 친구"],
    "감정 표현": ["다른 사람의 마음이 궁금한 친구"],
    "축하/응원": ["친구를 응원하고 싶은 친구", "기분 좋은 영상을 보고 싶은 친구"],
    "후기/경험": ["직접 해보기 전에 미리 알아보고 싶은 친구"],
    "소개/홍보": ["새로운 것을 구경하고 싶은 친구"],
    "이야기/브이로그": ["다른 사람의 하루가 궁금한 친구"],
    "의견/주장": ["여러 가지 생각을 들어보고 싶은 친구"],
    CATEGORY_OTHER: ["짧은 영상을 좋아하는 친구"],
}

_SENSITIVE = {
    "남자", "여자", "남녀", "예쁜", "못생", "뚱뚱", "날씬", "외모", "몸매",
    "교회", "성당", "기도", "하나님", "부처", "종교",
    "대통령", "정당", "선거", "보수", "진보", "정치",
    "다이어트", "우울", "불안", "장애",
    "부자", "가난", "이혼",
}


def _is_sensitive(word: str) -> bool:
    return any(s in word for s in _SENSITIVE)


def recommend_audience(
    category: str,
    concepts: ta.Concepts,
    confidence: float,
    view_ctx: "ViewContext",
) -> list[str]:
    out: list[str] = []

    def add(item: str):
        if item not in out:
            out.append(item)

    for a in CATEGORY_AUDIENCE.get(category, []):
        add(a)

    if confidence >= CONF_MID:
        for noun in concepts.nouns:
            if len(noun) >= 2 and not _is_sensitive(noun):
                add(f"{noun} 이야기가 궁금한 친구")
                break

    if view_ctx.has_large_text:
        add("소리 없이 보는 친구")
    if view_ctx.speech_chars < 20 and view_ctx.ocr_chars >= 20:
        add("글을 읽으면서 보는 친구")
    if 0 < view_ctx.avg_segment_len <= 2.5:
        add("빠른 영상을 좋아하는 친구")
    if view_ctx.duration <= 30:
        add("짧은 설명을 좋아하는 친구")

    if not out:
        out = ["짧은 영상을 좋아하는 친구", "새로운 것을 구경하고 싶은 친구"]
    return out[:4]


# ===========================================================================
# 6) 영상 형태 정보
# ===========================================================================
@dataclass
class ViewContext:
    duration: float
    ocr_chars: int
    speech_chars: int
    speech_seconds: float
    has_large_text: bool
    segment_count: int
    avg_segment_len: float
    features_by_segment: list[list[str]] = field(default_factory=list)

    @property
    def speech_rate(self) -> float:
        return self.speech_chars / self.speech_seconds if self.speech_seconds > 0 else 0.0


FAST_SPEECH_RATE = 5.0
HEAVY_TEXT_CHARS = 120


def estimate_difficulty(v: ViewContext, lyrics: bool) -> str:
    if (not lyrics and v.speech_rate >= FAST_SPEECH_RATE) or v.ocr_chars >= HEAVY_TEXT_CHARS:
        return "어려움"
    if v.duration <= 30 and v.has_large_text:
        return "쉬움"
    if v.duration <= 20 and v.ocr_chars + v.speech_chars <= 60:
        return "쉬움"
    return "보통"


def make_try_points(v: ViewContext) -> list[str]:
    points: list[str] = []
    first = v.features_by_segment[0] if v.features_by_segment else []
    if "fast_start" in first:
        points.append("처음 2초 안에 재미있는 질문이나 큰 글씨를 넣어봐요.")
    if v.has_large_text:
        points.append("중요한 말은 큰 글씨로 보여줘요.")
    if v.segment_count >= 4:
        points.append("화면을 여러 번 바꿔서 지루하지 않게 만들어봐요.")
    if v.speech_chars >= 30 and v.ocr_chars >= 20:
        points.append("말과 글자를 같이 쓰면 더 잘 전달돼요.")
    if not points:
        points.append("처음 2초 안에 재미있는 질문을 넣어봐요.")
        points.append("너무 오래 같은 화면만 보여주지 않아요.")
    return points[:3]


def make_caution_points(v: ViewContext, lyrics: bool) -> list[str]:
    points: list[str] = []
    if not lyrics and v.speech_rate >= FAST_SPEECH_RATE:
        points.append("말이 빠르면 자막을 같이 넣으면 좋아요.")
    if v.ocr_chars >= HEAVY_TEXT_CHARS or (v.ocr_chars >= 40 and v.avg_segment_len <= 2.5):
        points.append("글자가 너무 빨리 지나가면 읽기 어려워요.")
    if any("long_scene" in f for f in v.features_by_segment):
        points.append("같은 화면이 너무 오래 나오면 지루할 수 있어요.")
    if v.speech_chars == 0 and v.ocr_chars == 0:
        points.append("말이나 글자가 없으면 무슨 내용인지 알기 어려울 수 있어요.")
    if not points:
        points.append("중요한 내용은 천천히 보여주면 더 좋아요.")
    return points[:3]


# ===========================================================================
# 7) 구간별 제목/설명/배울 점
# ===========================================================================
def segment_title(index: int, total: int, seg: Segment) -> str:
    text = f"{seg.ocr_text or ''} {seg.speech_text or ''}"
    if index == 0:
        return "처음 관심 끄는 부분"
    if index == total - 1:
        return "마지막 정리"
    if any(w in text for w in ["예시", "예를 들", "이런 식", "예:"]):
        return "예시를 보여주는 부분"
    if len((seg.ocr_text or "").replace(" ", "")) >= 15 and not seg.speech_text:
        return "글자로 알려주는 부분"
    if "short_scene" in seg.features:
        return "다른 화면을 보여주는 부분"
    if seg.speech_text:
        return "내용을 설명하는 부분"
    return "내용을 보여주는 부분"


def segment_description(index: int, total: int, seg: Segment) -> str:
    sentences: list[str] = []
    if index == 0:
        sentences.append("처음부터 눈길을 끌려고 만든 부분이에요.")
    elif index == total - 1:
        sentences.append("영상을 짧게 정리하는 부분이에요.")
    if "large_text" in seg.features:
        sentences.append("중요한 말이 크게 나와서 보기 쉬워요.")
    if "speech" in seg.features and len(sentences) < 2:
        sentences.append("말로 내용을 설명해줘요.")
    if "short_scene" in seg.features and len(sentences) < 2:
        sentences.append("화면이 바뀌어서 지루하지 않게 느껴져요.")
    if not sentences:
        sentences.append("내용을 차근차근 보여주는 부분이에요.")
    return " ".join(sentences[:2])


def segment_learn_point(index: int, total: int, seg: Segment) -> str:
    if index == 0:
        return "처음에는 궁금하게 만드는 말이 좋아요."
    if index == total - 1:
        return "마지막에 한 번 더 정리하면 기억에 남아요."
    if "large_text" in seg.features:
        return "중요한 말은 큰 글씨로 보여주면 좋아요."
    if "speech" in seg.features:
        return "말로 설명하면 더 쉽게 이해돼요."
    if "short_scene" in seg.features:
        return "화면을 바꾸면 보는 사람이 집중하기 좋아요."
    return "중요한 내용은 천천히 보여주면 좋아요."


# ===========================================================================
# Adapter
# ===========================================================================
class ExplainerAdapter(ABC):
    """나중에 LLM 기반 구현을 서버 환경변수만으로 교체하기 위한 인터페이스."""

    @abstractmethod
    def explain(self, db: Session, video: Video, segments: list[Segment]) -> None: ...


def _build_metadata_text(video) -> str:
    """
    YouTube 메타데이터(제목/설명/해시태그) + (업로드의 경우) 파일명을
    하나의 보조 텍스트로 합친다.
    제목만으로 주제를 단정하지 않도록, 이 텍스트는 select_key_nouns에서
    meta_weight(내부 정보 부족 시 커짐)를 통해서만 반영된다.
    """
    parts: list[str] = []
    if getattr(video, "youtube_title", None):
        parts.append(video.youtube_title)
    if getattr(video, "youtube_description", None):
        parts.append(video.youtube_description)
    if getattr(video, "youtube_hashtags", None):
        # "#졸업 #축하" 또는 "졸업,축하" 등 어떤 형식이든 단어만 남도록 기호 제거
        tags = re.sub(r"[#,]", " ", str(video.youtube_hashtags))
        parts.append(tags)
    # 파일명은 업로드 영상일 때만 약한 메타데이터로 포함 (YouTube면 video_id 조각이 새므로 제외)
    source_type = getattr(video, "source_type", "upload")
    if source_type != "youtube" and getattr(video, "original_filename", None):
        fname = re.sub(r"\.(mp4|mov|webm)$", "", video.original_filename, flags=re.IGNORECASE)
        parts.append(fname)
    return " ".join(p for p in parts if p).strip()


class RuleBasedExplainer(ExplainerAdapter):
    def explain(self, db: Session, video: Video, segments: list[Segment]) -> None:
        total = len(segments)
        vid = video.id
        logger.info("explain 시작: video=%s segment=%d", vid, total)

        # 1) 구간별 문장 먼저
        for i, seg in enumerate(segments):
            seg.title = segment_title(i, total, seg)
            seg.description = segment_description(i, total, seg)
            seg.learn_point = segment_learn_point(i, total, seg)
        logger.info("explain[1] 구간 문장 생성 완료: video=%s", vid)

        # 2) 전체 문서 (모든 segment의 글자/말/제목/설명)
        doc = ta.build_document(
            ocr_parts=[s.ocr_text or "" for s in segments],
            stt_parts=[s.speech_text or "" for s in segments],
            titles=[s.title or "" for s in segments],
            descriptions=[s.description or "" for s in segments],
        )
        logger.info("explain[2] 문서 빌드 완료: video=%s", vid)

        # 3) 메타데이터 텍스트 합치기 (제목+설명+해시태그+파일명)
        #    영상 내부 정보를 우선하므로 메타데이터는 보조로만 쓴다.
        metadata_text = _build_metadata_text(video)

        # 4) 출처 신뢰도 + 가사 감지 (OCR/STT/metadata 3계층)
        sw = ta.compute_source_weights(doc.ocr_text, doc.stt_text, metadata_text)
        logger.info("explain[4] 출처 가중치 계산 완료: video=%s", vid)

        # 5) 핵심 개념: segment 단위 신호 + 메타데이터(보조)로 핵심 명사 선별
        lyrics = sw.lyrics.is_likely_lyrics
        seg_pairs = [
            (s.ocr_text or "", "" if lyrics else (s.speech_text or ""))
            for s in segments
        ]
        signal_src = doc.ocr_text if lyrics else doc.content_text
        # 메타데이터 전용(segment 없음)이면 메모리 절약을 위해 Kiwi를 건너뛸 수 있다.
        _settings = get_settings()
        if total == 0:
            use_kiwi = _settings.ENABLE_KIWI and _settings.KIWI_FOR_METADATA_ONLY
        else:
            use_kiwi = _settings.ENABLE_KIWI
        logger.info("explain[5] 핵심 명사 추출 시작(use_kiwi=%s, segment=%d): video=%s",
                    use_kiwi, total, vid)
        concepts = ta.extract_concepts(
            seg_pairs, signal_src, use_kiwi=use_kiwi,
            metadata_text=metadata_text, meta_weight=sw.metadata,
        )
        logger.info("explain[5] 핵심 명사 추출 완료(%d개): video=%s",
                    len(concepts.nouns), vid)

        # 6) 의도 분류 + 확신도
        intent = classify_intent(doc, concepts)
        overlap = ta.keyword_overlap(doc.ocr_text, doc.stt_text)
        top_count = sum(1 for n in concepts.nouns[:3] if doc.full_text.count(n) >= 2)
        confidence, reason = compute_confidence(
            intent, doc, overlap, top_count,
            key_noun_count=len(concepts.nouns),
            metadata_used=sw.metadata_used, metadata_weight=sw.metadata,
        )
        logger.info("explain[6] 의도/확신도 완료(category=%s conf=%.2f): video=%s",
                    intent.category, confidence, vid)

        category_out = intent.category if confidence >= CONF_MID else CATEGORY_OTHER

        # 7) 형태 정보
        seg_lens = [(s.end_time - s.start_time) for s in segments] or [0.0]
        speech_seconds = sum(
            (s.end_time - s.start_time) for s in segments if (s.speech_text or "").strip()
        )
        view = ViewContext(
            duration=video.duration or 0.0,
            ocr_chars=ta.char_len(doc.ocr_text),
            speech_chars=ta.char_len(doc.stt_text),
            speech_seconds=speech_seconds,
            has_large_text=any("large_text" in s.features for s in segments),
            segment_count=total,
            avg_segment_len=sum(seg_lens) / len(seg_lens),
            features_by_segment=[s.features for s in segments],
        )

        # 8) summary
        summary = (
            db.query(VideoSummary).filter(VideoSummary.video_id == video.id).first()
            or VideoSummary(video_id=video.id)
        )
        summary.topic = make_topic(category_out, concepts, confidence)
        summary.purpose = make_purpose(category_out, concepts, confidence)
        summary.category = category_out
        summary.confidence = confidence
        summary.confidence_reason = reason
        summary.detected_keywords = concepts.keywords[:5]
        summary.primary_source = sw.primary
        summary.source_weights = {"ocr": sw.ocr, "stt": sw.stt, "metadata": sw.metadata}
        summary.metadata_used = sw.metadata_used
        summary.metadata_keywords = concepts.metadata_keywords
        summary.difficulty = estimate_difficulty(view, sw.lyrics.is_likely_lyrics)
        summary.recommended_audience = recommend_audience(category_out, concepts, confidence, view)
        summary.try_points = make_try_points(view)
        summary.caution_points = make_caution_points(view, sw.lyrics.is_likely_lyrics)

        # 9) 숏폼 성공 구조 분석 (교육용) — 이미 추출된 신호만으로 생성
        from .success_analyzer import StructureInput, analyze_success_structure

        first_speech = (segments[0].speech_text or "") if segments else ""
        first_ocr = (segments[0].ocr_text or "") if segments else ""
        first_question = "?" in first_speech or "?" in first_ocr or any(
            q in (first_speech + first_ocr) for q in ("왜", "어떻게", "과연")
        )
        s_inp = StructureInput(
            duration=video.duration or 0.0,
            segment_count=total,
            seg_starts=[s.start_time for s in segments],
            seg_ends=[s.end_time for s in segments],
            seg_features=[s.features for s in segments],
            seg_has_text=[bool((s.ocr_text or "").strip()) for s in segments],
            seg_has_speech=[bool((s.speech_text or "").strip()) for s in segments],
            category=category_out,
            keywords=concepts.keywords[:8],
            intent_expressions=concepts.intent_expressions,
            emotions=concepts.emotions,
            has_large_text=view.has_large_text,
            first_question=first_question,
            confidence=confidence,
        )
        sa = analyze_success_structure(s_inp)
        logger.info("explain[9] 성공구조 분석 완료: video=%s", vid)

        # provider adapter: 기본 규칙 기반, 옵션으로 LLM이 보강/대체.
        from .success_analyzer import to_analysis_result
        from .analysis_provider import (
            AnalysisInput, get_analysis_provider,
        )

        rule_result = to_analysis_result(s_inp, sa)
        a_inp = AnalysisInput(
            title=video.youtube_title or "",
            description=video.youtube_description or "",
            hashtags=video.youtube_hashtags or "",
            ocr_text=doc.ocr_text,
            stt_text=doc.stt_text,
            duration=video.duration or 0.0,
            category=category_out,
            keywords=concepts.keywords[:8],
        )
        try:
            result = get_analysis_provider().analyze(a_inp, rule_result)
        except Exception:
            logger.exception("분석 provider 실패 -> 규칙 결과 사용")
            result = rule_result
        logger.info("explain[10] 분석 provider 완료(provider=%s): video=%s",
                    result.provider, vid)

        summary.hook_type = result.hook_type or sa.hook_type
        summary.hook_reason = result.hook_reason or sa.hook_reason
        summary.hook_strength = result.hook_strength or sa.hook_strength
        summary.structure = sa.structure  # 타임라인(시간축)은 규칙 기반 유지
        summary.structure_detail = result.structure_detail
        summary.success_patterns = result.success_patterns
        summary.creator_tips = result.creator_tips
        summary.engagement_factors = result.engagement_factors
        summary.analysis_summary = result.summary
        summary.analysis_provider = result.provider
        # LLM이 더 나은 주제 문장을 줬으면 topic 보강 (규칙 topic이 약할 때만)
        if result.provider == "llm" and result.summary:
            if not summary.topic or summary.topic.startswith("영상 내용을 더"):
                if result.topic:
                    summary.topic = result.topic
        db.add(summary)
        db.commit()
        logger.info(
            "설명 생성: video=%s category=%s conf=%.2f primary=%s keywords=%s",
            video.id, category_out, confidence, sw.primary, concepts.nouns[:5],
        )


_explainer: ExplainerAdapter | None = None


def get_explainer() -> ExplainerAdapter:
    global _explainer
    if _explainer is None:
        _explainer = RuleBasedExplainer()
    return _explainer
