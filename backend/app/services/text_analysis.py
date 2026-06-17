"""
텍스트 분석 유틸 (Explainer가 사용).

여기 있는 함수들은 DB나 모델을 모르고, 순수하게 텍스트만 다룬다.
그래서 단위 테스트가 쉽고, 나중에 LLM 기반 구현으로 바꿔도 그대로 재사용할 수 있다.

담당:
- 모든 segment의 글자/말/제목/설명을 하나의 문서로 합치기 (중복/반복/짧은 단어 제거)
- 한국어 단어 정규화 (조사·어미 제거, 일부는 풀어쓰기)
- OCR / STT 신뢰도 평가 -> source_weights
- STT가 노래 가사/배경음악일 가능성 감지
- 핵심 개념(명사) / 행동 / 감정 신호 추출
"""
from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field

# ===========================================================================
# 불용어 / 일반어
# ===========================================================================
STOPWORDS = {
    "이거", "그거", "저거", "여기", "거기", "저기", "오늘", "지금", "진짜", "정말",
    "너무", "아주", "조금", "많이", "그냥", "근데", "그런데", "그래서", "하지만",
    "그리고", "이제", "다시", "같이", "함께", "우리", "여러분", "안녕", "안녕하세요",
    "있어요", "없어요", "있는", "없는", "합니다", "입니다", "거예요", "건데",
    "이렇게", "저렇게", "그렇게", "어떻게", "무엇", "뭐가", "뭔가", "하나", "정도",
    "사람", "사람들", "때문", "통해", "위해", "대해", "보면", "보고", "하고",
    "되는", "되요", "된다", "이런", "저런", "그런", "어떤", "무슨", "여러",
    "영상", "부분", "내용", "화면", "글자", "정리", "장면",
    # 시간 표현
    "작년", "올해", "내년", "어제", "내일", "방금", "아까", "이때", "그때", "요즘",
    "예전", "나중", "먼저", "이번", "저번", "다음", "처음", "마지막",
    # 감탄사 / 리액션 부스러기
    "진짜", "헐", "와", "우와", "아이고", "어머", "에이", "음", "아무튼", "역시",
    # 부탁 / 정도 / 약한 부사
    "제발", "부디", "약간", "살짝", "거의", "엄청", "되게", "완전", "막", "좀",
    "혹시", "그냥", "맨날", "자꾸", "계속", "또", "더",
    "the", "and", "this", "that", "with", "for", "you", "are", "was", "very",
    "shorts", "short", "video", "youtube", "mp4", "mov", "webm", "final", "edit",
    "copy", "new", "test", "img", "vid", "are", "have", "from",
}

# 조사/어미 (긴 것부터)
_SUFFIXES = [
    "이에요", "예요", "이었던", "이었어", "였어요", "였던", "이라는", "라는",
    "해보세요", "했어요", "하세요", "입니다", "합니다", "인데요", "하던",
    "에서", "에게", "으로", "한테", "처럼", "보다", "까지", "부터", "마저",
    "해요", "하는", "하기", "했다", "해서", "하면", "하고", "되는", "되어",
    "이라고", "라고", "이고", "이며", "이나", "라도",
    "들이", "들을", "들은", "들과", "들의", "들아",
    "은", "는", "이", "가", "을", "를", "에", "와", "과", "도", "만", "로",
    "요", "해", "야", "아", "의",
]

# 정규화 보정 사전 (자주 어색해지는 것만 최소로 — 주제 사전이 아니라 표현 교정용)
_NORMALIZE_FIX = {
    "담임": "담임 선생님",
    "쌤": "선생님",
    "샘": "선생님",
}

_TOKEN_RE = re.compile(r"[가-힣a-zA-Z0-9]{2,}")
_SENT_SPLIT_RE = re.compile(r"[.!?\n]+|\s{2,}")


def normalize_word(token: str) -> str:
    """조사·어미를 떼고, 보정 사전이 있으면 풀어쓴다."""
    word = token
    # 어미/조사 한 번만 제거 (남는 글자가 2자 이상일 때만)
    for suf in _SUFFIXES:
        if word.endswith(suf) and len(word) - len(suf) >= 2:
            word = word[: -len(suf)]
            break
    return _NORMALIZE_FIX.get(word, word)


# ===========================================================================
# 1) 문서 합치기 (중복/반복/짧은 단어 제거)
# ===========================================================================
@dataclass
class CombinedDoc:
    ocr_text: str          # 정리된 OCR 전체
    stt_text: str          # 정리된 STT 전체
    extra_text: str        # 제목+설명 (보조)
    full_text: str         # 위 셋을 합친 분석용 문서
    content_text: str      # OCR+STT만 (우리가 만든 제목/설명 제외 — 의도/신호 분석용)


def _dedupe_sentences(text: str) -> str:
    """문장 단위로 쪼개 중복/거의 같은 문장을 제거."""
    parts = [p.strip() for p in _SENT_SPLIT_RE.split(text) if p and p.strip()]
    seen: set[str] = set()
    out: list[str] = []
    for p in parts:
        key = re.sub(r"\s+", "", p.lower())
        if len(key) < 2:
            continue
        if key in seen:
            continue
        seen.add(key)
        out.append(p)
    return " ".join(out)


def build_document(
    ocr_parts: list[str],
    stt_parts: list[str],
    titles: list[str],
    descriptions: list[str],
) -> CombinedDoc:
    ocr = _dedupe_sentences(" ".join(t for t in ocr_parts if t))
    stt = _dedupe_sentences(" ".join(t for t in stt_parts if t))
    extra = _dedupe_sentences(" ".join(t for t in (titles + descriptions) if t))
    full = " ".join([ocr, stt, extra]).strip()
    content = " ".join([ocr, stt]).strip()
    return CombinedDoc(
        ocr_text=ocr, stt_text=stt, extra_text=extra, full_text=full, content_text=content
    )


# ===========================================================================
# 2) 반복도 / 겹침도 (신뢰도 계산 재료)
# ===========================================================================
def char_len(text: str) -> int:
    return len(re.sub(r"\s+", "", text or ""))


def repetition_ratio(text: str) -> float:
    """
    같은 단어가 얼마나 반복되는지 (0~1). 1에 가까울수록 반복 심함.
    노래 가사/후렴구 감지에 쓴다.
    """
    tokens = _TOKEN_RE.findall(text or "")
    if len(tokens) < 4:
        return 0.0
    counts = Counter(tokens)
    repeated = sum(c for c in counts.values() if c >= 2) - len([c for c in counts.values() if c >= 2])
    return round(repeated / len(tokens), 3)


def sentence_repetition_ratio(text: str) -> float:
    """짧은 문장(후렴구)이 통째로 반복되는 비율 (0~1)."""
    parts = [re.sub(r"\s+", "", p.lower()) for p in _SENT_SPLIT_RE.split(text or "") if p.strip()]
    parts = [p for p in parts if len(p) >= 2]
    if len(parts) < 3:
        return 0.0
    counts = Counter(parts)
    repeated = sum(c - 1 for c in counts.values() if c >= 2)
    return round(repeated / len(parts), 3)


def keyword_overlap(a: str, b: str) -> float:
    """두 텍스트의 핵심 단어 겹침 정도 (0~1, Jaccard)."""
    sa = {normalize_word(t) for t in _TOKEN_RE.findall(a or "") if t.lower() not in STOPWORDS}
    sb = {normalize_word(t) for t in _TOKEN_RE.findall(b or "") if t.lower() not in STOPWORDS}
    sa = {w for w in sa if len(w) >= 2}
    sb = {w for w in sb if len(w) >= 2}
    if not sa or not sb:
        return 0.0
    inter = len(sa & sb)
    union = len(sa | sb)
    return round(inter / union, 3) if union else 0.0


# ===========================================================================
# 3) 노래 가사 / 배경음악 감지
# ===========================================================================
@dataclass
class LyricSignal:
    is_likely_lyrics: bool
    reason: str


def detect_lyrics(stt_text: str, ocr_text: str) -> LyricSignal:
    """
    STT가 영상 설명이 아니라 배경음악 가사일 가능성을 판단.
    근거: 단어 반복 많음 + 문장 반복 많음 + OCR과 거의 무관 + 문장이 짧고 많음.
    """
    if char_len(stt_text) < 10:
        return LyricSignal(False, "")

    word_rep = repetition_ratio(stt_text)
    sent_rep = sentence_repetition_ratio(stt_text)
    overlap = keyword_overlap(stt_text, ocr_text) if char_len(ocr_text) >= 4 else 1.0

    signals = 0
    if word_rep >= 0.35:
        signals += 1
    if sent_rep >= 0.3:
        signals += 1
    if char_len(ocr_text) >= 8 and overlap <= 0.1:
        signals += 1

    if signals >= 2:
        return LyricSignal(True, "같은 말이 자주 반복돼서 배경 노래일 수 있어요.")
    return LyricSignal(False, "")


# ===========================================================================
# 4) 출처 신뢰도 (source_weights)
# ===========================================================================
@dataclass
class SourceWeights:
    ocr: float
    stt: float
    metadata: float          # title + description + hashtags + filename 통합 (보조)
    primary: str             # ocr / stt / metadata / none
    lyrics: LyricSignal
    metadata_used: bool      # 메타데이터가 실제로 가중치를 받았는지


def compute_source_weights(
    ocr_text: str,
    stt_text: str,
    metadata_text: str = "",
) -> SourceWeights:
    """
    영상 내부(OCR/STT) 우선, 메타데이터는 보조.

    원칙:
    - 영상 내부 정보(OCR/STT)가 충분하면 메타데이터 비중은 작게 유지(상한).
    - 내부 정보가 부족할수록 메타데이터 비중을 키운다.
    - 제목 등 메타데이터만으로 주제를 단정하지 않도록, 메타데이터 단독 상한을 둔다.
    합은 1.0으로 정규화.
    """
    ocr_len = char_len(ocr_text)
    stt_len = char_len(stt_text)
    meta_len = char_len(metadata_text)

    def vol_score(n: int) -> float:
        if n <= 0:
            return 0.0
        if n < 10:
            return 0.3
        if n < 40:
            return 0.7
        return 1.0

    ocr_raw = vol_score(ocr_len)
    stt_raw = vol_score(stt_len)

    lyric = detect_lyrics(stt_text, ocr_text)
    if lyric.is_likely_lyrics:
        stt_raw *= 0.3
        ocr_raw = max(ocr_raw, 0.7)

    internal = ocr_raw + stt_raw  # 영상 내부 정보의 총량

    # 메타데이터 가중치: 내부 정보가 적을수록 커진다.
    if meta_len < 2:
        meta_raw = 0.0
    elif internal <= 0.3:
        meta_raw = 0.9    # 내부 정보 거의 없음 -> 메타데이터에 크게 의존
    elif internal <= 0.8:
        meta_raw = 0.5    # 내부 정보 부족 -> 메타데이터 보강 비중 상승
    else:
        meta_raw = 0.2    # 내부 정보 충분 -> 메타데이터는 보조(상한)

    total = ocr_raw + stt_raw + meta_raw
    if total <= 0:
        return SourceWeights(0.0, 0.0, 0.0, "none", lyric, False)

    ocr_w = round(ocr_raw / total, 2)
    stt_w = round(stt_raw / total, 2)
    meta_w = round(max(0.0, 1.0 - ocr_w - stt_w), 2)

    if ocr_w >= stt_w and ocr_w >= meta_w and ocr_w > 0:
        primary = "ocr"
    elif stt_w >= meta_w and stt_w > 0:
        primary = "stt"
    elif meta_w > 0:
        primary = "metadata"
    else:
        primary = "none"

    return SourceWeights(
        ocr=ocr_w, stt=stt_w, metadata=meta_w,
        primary=primary, lyrics=lyric, metadata_used=meta_raw > 0,
    )


# ===========================================================================
# 5) 핵심 개념 / 행동 / 감정 추출
# ===========================================================================
# 행동(영상이 무엇을 하는지)과 감정 신호.
# 이건 "주제" 사전이 아니라 어느 장르에나 공통으로 나오는 의도 신호다.
ACTION_SIGNALS: dict[str, list[str]] = {
    # '설명/방법'을 나타내는 행동 동사 — 어떤 주제든 통하는 신호
    "설명": [
        "설명", "알려", "이렇게", "방법", "하는 법", "하는법", "순서", "단계", "정리",
        "만들", "만드는", "만들기", "만들어", "그리", "그려", "그리기",
        "외워", "외우", "암기", "따라", "따라하", "배워", "배우",
        "키우", "기르", "꾸미", "정리하", "준비하", "고치", "조립",
        "레시피", "tip", "팁", "꿀팁", "how", "해보세요", "해볼게", "해봐요",
    ],
    "소개": ["소개", "보여드릴", "보여줄", "공개", "신상", "추천", "오픈"],
    "비교": ["비교", "차이", "더 좋", "보다", "대신", "vs"],
    "응원": ["응원", "축하", "파이팅", "화이팅", "수고", "잘했", "고마워", "감사", "힘내"],
    "후기": ["후기", "리뷰", "써봤", "먹어봤", "가봤", "해봤", "사봤", "직접", "솔직",
            "먹어볼", "먹방", "먹어보", "다녀왔", "다녀온"],
    "주장": ["생각해", "제 생각", "내 생각", "중요하다", "해야", "동의", "반대"],
}

EMOTION_SIGNALS: dict[str, list[str]] = {
    "기쁨": ["행복", "기뻐", "기뻤", "신나", "즐거", "뿌듯", "최고"],
    "슬픔": ["슬프", "슬펐", "눈물", "그리워", "보고싶", "속상", "아쉬"],
    "재미": ["웃긴", "웃음", "ㅋㅋ", "대박", "신기", "귀엽", "재밌", "재미",
            "개그", "꿀잼", "레전드", "병맛", "몰카", "장난", "웃프"],
    "감동": ["감동", "뭉클", "고맙", "벅차", "잊지"],
    "놀람": ["깜짝", "헐", "충격", "반전", "설마"],
}

# 의도 표현: 영상이 '무엇을 하는지'를 나타내는 대표 단어.
# 화면/말에서 이 신호가 발견되면 detected_keywords에 명사와 함께 넣는다.
# (라벨이 아니라 사람이 읽는 단어 그대로: "축하", "응원", "설명"...)
INTENT_EXPRESSIONS: dict[str, list[str]] = {
    "축하": ["축하", "축하해", "축하합니다"],
    "응원": ["응원", "파이팅", "화이팅", "힘내", "잘했", "수고"],
    "설명": ["설명", "알려", "방법", "하는 법", "순서", "단계"],
    "소개": ["소개", "보여드릴", "공개", "신상"],
    "추천": ["추천", "강추", "꿀팁"],
    "비교": ["비교", "차이", "대신"],
    "후기": ["후기", "리뷰", "써봤", "먹어봤", "가봤", "해봤", "솔직"],
    "감사": ["고마워", "고마웠", "감사", "고맙"],
}


def _count_emotion_hits(text: str, emotion_label: str) -> int:
    """특정 감정 라벨의 신호 단어가 텍스트에 몇 종류 등장했는지 센다."""
    words = EMOTION_SIGNALS.get(emotion_label, [])
    low = text.lower()
    return sum(1 for w in words if w.lower() in low)


def extract_intent_expressions(text: str) -> list[str]:
    """말/글에서 발견된 의도 표현을 대표 단어로 추출 (중복 없이, 등장 순서 유지)."""
    low = text.lower()
    found: list[str] = []
    for label, variants in INTENT_EXPRESSIONS.items():
        if any(v.lower() in low for v in variants):
            found.append(label)
    return found


@dataclass
class Concepts:
    nouns: list[str] = field(default_factory=list)              # 핵심 주제 명사 (중요도순)
    actions: list[str] = field(default_factory=list)            # 행동 라벨 (의도 분류용)
    emotions: list[str] = field(default_factory=list)           # 감정 라벨
    intent_expressions: list[str] = field(default_factory=list) # 의도 표현 단어 (축하/응원/설명...)
    metadata_keywords: list[str] = field(default_factory=list)  # 메타데이터에서만 나온 키워드

    @property
    def keywords(self) -> list[str]:
        """detected_keywords = 의도 표현 + 핵심 주제 명사 (의도 표현을 앞쪽에)."""
        out: list[str] = []
        for w in self.intent_expressions + self.nouns:
            if w and w not in out:
                out.append(w)
        return out


def _signal_hits(text: str, table: dict[str, list[str]]) -> list[str]:
    low = text.lower()
    hits = []
    for label, words in table.items():
        if any(w.lower() in low for w in words):
            hits.append(label)
    return hits


# 의도/행동/감정을 나타내는 단어는 '핵심 개념(명사)'으로 쓰지 않는다.
# (topic이 "졸업과 축하를 축하하고..."처럼 중복되는 것을 막음)
def _intent_word_set() -> set[str]:
    words: set[str] = set()
    for table in (ACTION_SIGNALS, EMOTION_SIGNALS):
        for group in table.values():
            for w in group:
                words.add(normalize_word(w))
                words.add(w)
    # 자주 쓰이는 의도/리액션 표현 보강
    words.update({
        "축하", "응원", "파이팅", "화이팅", "고마워", "고마웠어", "감사", "수고",
        "설명", "소개", "추천", "후기", "리뷰", "방법", "정보", "생각",
        "대박", "레전드", "웃긴", "재밌", "신기",
        "먹어봤어", "먹어봤", "써봤", "가봤", "해봤", "사봤", "다녀왔", "강추",
    })
    return words


_INTENT_WORDS_CACHE: set[str] | None = None
# 의도어 어근: 활용형(감사했고/응원할게/축하해)을 한 단어로 묶기 위한 접두 검사용
_INTENT_STEMS = ("축하", "응원", "감사", "고마", "소개", "설명", "추천", "비교", "후기")


def _is_intent_word(word: str) -> bool:
    global _INTENT_WORDS_CACHE
    if _INTENT_WORDS_CACHE is None:
        _INTENT_WORDS_CACHE = _intent_word_set()
    if word in _INTENT_WORDS_CACHE or normalize_word(word) in _INTENT_WORDS_CACHE:
        return True
    # "감사했고", "응원할게", "축하해" 처럼 의도어 어근으로 시작하면 의도어로 본다
    return any(word.startswith(stem) for stem in _INTENT_STEMS)


# 동사/형용사 활용형이 남긴 흔적 (명사가 아닐 가능성이 큰 꼬리)
# 예: "게임하다", "났어", "풀어요", "같을", "올라요"
_VERBISH_TAILS = (
    "하다", "했어", "했고", "했지", "했는데", "났어", "봤어", "았어", "었어",
    "할게", "할래", "할까", "겠어", "는다", "ㄴ다",
    "어요", "아요", "여요", "에요", "워요", "려요", "해요", "해서", "해도",
    "어서", "아서", "으면", "라요", "대요", "냐고", "는데", "거든", "이야", "더라",
)


def _looks_like_noun(word: str) -> bool:
    """핵심 개념으로 쓰기에 적당한 '명사다움' 간단 판정."""
    if len(word) < 2:
        return False
    if word.endswith(_VERBISH_TAILS):
        return False
    # 'X해'/'X해도'/'X했'처럼 '하다' 동사 활용 흔적 (예: 졸업해, 감사했)
    if len(word) >= 3 and word[-1] in ("해", "했", "함") and not _is_intent_word(word):
        return False
    # 관형형 'ㄹ/을/를' 받침만 남은 토막("같을") 등 약한 토큰 제외
    if word.endswith(("을", "ㄹ")) and len(word) <= 2:
        return False
    # 조사 잔여물로 끝나는 토막 제외 (예: "분이에", "번만", "에는")
    if word.endswith(("이에", "이었", "에는", "에도", "만", "랑", "이랑")):
        return False
    # 숫자+단위 토막 (예: "1년", "번만") 중 의미 약한 것 제외
    if re.match(r"^\d+", word):
        return False
    return True


# 주제 명사로 약한(덜 중요한) 일반 단어 — 빈도가 높아도 점수를 깎는다.
_WEAK_NOUNS = {
    "친구", "친구들", "얘기", "이야기", "생각", "기분", "마음",
    "느낌", "모습", "시간", "동안", "그동안",
    "여기", "거기", "이거", "그거", "경우", "이유", "결과",
    # 동사/형용사 어간이 명사로 잘못 잡히기 쉬운 것들
    "완성", "자연", "시작", "정도", "준비", "사용", "이용", "확인",
    "정말", "진짜", "조금", "전부", "모두", "가지", "종류",
}


def _importance_score(
    word: str, freq: int, in_stt: bool, in_ocr: bool, near_intent: bool
) -> float:
    """
    핵심 주제 명사로서의 중요도 점수.
    - 빈도: 반복될수록 가산 (상한 -> 한 단어 독식 방지)
    - 길이: 2~4자 한국어 명사 선호
    - OCR(화면 글자): 제작자가 화면에 띄운 = 강조한 핵심일 확률↑ (가장 강함)
    - STT(말): 말로 나온 핵심 표현 우대
    - 의도 동사 근처: 목적과 연결된 핵심일 확률↑
    - 약한 일반 명사: 감점
    """
    score = 0.0
    score += min(freq, 3) * 1.0
    n = len(word)
    if 2 <= n <= 4:
        score += 0.6
    elif n >= 6:
        score -= 0.4
    if in_ocr:
        score += 0.7
    if in_stt:
        score += 0.4
    if near_intent:
        score += 0.8
    if word in _WEAK_NOUNS:
        score -= 1.0
    return score


def _has_intent_nearby(word: str, text: str, window: int = 12) -> bool:
    """word 등장 위치 주변(window 글자)에 의도 표현이 있는지."""
    low = text.lower()
    intent_variants = [v for variants in INTENT_EXPRESSIONS.values() for v in variants]
    idx = low.find(word.lower())
    while idx != -1:
        seg = low[max(0, idx - window): idx + len(word) + window]
        if any(v.lower() in seg for v in intent_variants):
            return True
        idx = low.find(word.lower(), idx + 1)
    return False


def _candidate_nouns_regex(weighted_text: str) -> Counter:
    """규칙 기반 후보 명사 빈도 (정규화 + 불용어/의도어/활용형 제거)."""
    freqs: Counter = Counter()
    for token in _TOKEN_RE.findall(weighted_text or ""):
        if token.lower() in STOPWORDS or token.isdigit():
            continue
        norm = normalize_word(token)
        if len(norm) < 2 or norm.lower() in STOPWORDS:
            continue
        if _is_intent_word(norm):
            continue
        if not _looks_like_noun(norm):
            continue
        freqs[norm] += 1
    return freqs


# ===========================================================================
# 핵심 선별 (key noun selection)
# ===========================================================================
# 빈도만으로 고르지 않는다. 쇼츠에서 진짜 주제어는 화면 자막으로 잠깐 뜨거나,
# 말·글자 양쪽에 나오거나, 여러 장면에 걸쳐 등장한다.
# 그래서 단어마다 아래 신호들을 segment 단위로 모아 가중 합산한다.
#
# 가중치(4번 방식: 여러 신호 균형 조합, OCR에 약간 더 무게):
W_OCR        = 2.0   # 화면 글자(자막/타이틀)에 등장  -> 제작자가 강조한 핵심
W_BOTH       = 2.0   # OCR과 STT 양쪽에 모두 등장      -> 확실한 핵심
W_SPREAD     = 1.5   # 여러 segment에 걸쳐 등장        -> 영상 전체를 관통
W_FIRST      = 1.0   # 첫 segment(도입부)에 등장        -> 주제 선언일 확률
W_PROPER     = 1.2   # 고유명사/영문(게임명·제품명 등)
W_STT        = 0.8   # 말에 등장
W_FREQ       = 0.4   # 빈도 (약한 신호, 상한 적용)
W_NEAR_INTENT = 0.6  # 의도 표현(설명/소개/축하 등) 근처
# 메타데이터(제목/설명/해시태그) 등장 시 기본 가중. 내부 정보가 부족할수록 커진다.
# (compute_source_weights의 metadata 비중에 비례해 곱해짐)
W_META_BASE  = 1.5


@dataclass
class _NounSignals:
    word: str
    in_ocr: bool = False
    in_stt: bool = False
    in_first: bool = False
    seg_count: int = 0          # 등장한 segment 수
    freq: int = 0               # 전체 등장 빈도
    is_proper: bool = False
    near_intent: bool = False
    in_meta: bool = False       # 메타데이터(제목/설명/해시태그)에 등장
    meta_weight: float = 0.0    # 메타데이터 동적 가중 (0~1, 내부 정보 부족 시 커짐)

    def score(self) -> float:
        # 약한 일반 명사는 주제어가 될 수 없다 (고유명사로 잡힌 경우만 예외).
        if self.word in _WEAK_NOUNS and not self.is_proper:
            return -1.0
        s = 0.0
        if self.in_ocr:
            s += W_OCR
        if self.in_stt:
            s += W_STT
        if self.in_ocr and self.in_stt:
            s += W_BOTH
        if self.seg_count >= 2:
            s += W_SPREAD
        if self.in_first:
            s += W_FIRST
        if self.is_proper:
            s += W_PROPER
        if self.near_intent:
            s += W_NEAR_INTENT
        if self.in_meta:
            # 메타데이터는 내부 정보가 부족할수록 더 크게 반영
            s += W_META_BASE * self.meta_weight
            # 내부(OCR/STT)와 메타데이터에 함께 나오면 확실한 핵심 -> 소폭 가산
            if self.in_ocr or self.in_stt:
                s += 0.5
        s += min(self.freq, 3) * W_FREQ
        if len(self.word) >= 7:
            s -= 0.5
        return s


def _nouns_from_text_kiwi(text: str) -> list[tuple[str, bool]] | None:
    """Kiwi로 (명사, 고유명사여부) 목록. 실패 시 None."""
    from . import kiwi_extractor

    return kiwi_extractor.extract_nouns_tagged(text)


def _nouns_from_text_regex(text: str) -> list[tuple[str, bool]]:
    """규칙 기반 (명사, 고유명사여부=False) 목록 (Kiwi fallback)."""
    out: list[tuple[str, bool]] = []
    seen: set[str] = set()
    for token in _TOKEN_RE.findall(text or ""):
        if token.lower() in STOPWORDS or token.isdigit():
            continue
        norm = normalize_word(token)
        if len(norm) < 2 or norm.lower() in STOPWORDS:
            continue
        if not _looks_like_noun(norm):
            continue
        if norm not in seen:
            seen.add(norm)
            out.append((norm, False))
    return out


def select_key_nouns(
    segments: list[tuple[str, str]],   # [(ocr_text, stt_text), ...] segment 순서대로
    signal_text: str,                  # 의도 표현 근접 판정용 (실제 콘텐츠)
    use_kiwi: bool,
    metadata_text: str = "",           # title + description + hashtags 통합
    meta_weight: float = 0.0,          # 메타데이터 동적 가중 (0~1)
    top_n: int = 5,
) -> tuple[list[str], list[str]]:
    """
    segment 단위 신호 + 메타데이터를 모아 핵심 주제 명사를 고른다 (빈도 아님).
    반환: (핵심 명사 목록, 메타데이터에서만 나온 명사 목록)

    원칙: 영상 내부(OCR/STT)를 우선하고, 메타데이터는 보조.
    메타데이터에만 있는 단어는 meta_weight가 충분할 때만 핵심에 들어간다.
    -> 제목만으로 주제를 단정하지 않게 한다.
    """
    extractor = None
    if use_kiwi:
        test = _nouns_from_text_kiwi("테스트")
        if test is not None:
            extractor = _nouns_from_text_kiwi
    if extractor is None:
        extractor = _nouns_from_text_regex

    signals: dict[str, _NounSignals] = {}

    def get(word: str) -> _NounSignals:
        if word not in signals:
            signals[word] = _NounSignals(word=word)
        return signals[word]

    for idx, (ocr, stt) in enumerate(segments):
        ocr_nouns = extractor(ocr) or []
        stt_nouns = extractor(stt) or []
        seg_words: set[str] = set()
        for word, proper in ocr_nouns:
            if _is_intent_word(word):
                continue
            sig = get(word)
            sig.in_ocr = True
            sig.is_proper = sig.is_proper or proper
            sig.freq += 1
            if idx == 0:
                sig.in_first = True
            seg_words.add(word)
        for word, proper in stt_nouns:
            if _is_intent_word(word):
                continue
            sig = get(word)
            sig.in_stt = True
            sig.is_proper = sig.is_proper or proper
            sig.freq += 1
            if idx == 0:
                sig.in_first = True
            seg_words.add(word)
        for word in seg_words:
            signals[word].seg_count += 1

    # 메타데이터 명사 (제목/설명/해시태그) — 보조 신호로 추가
    meta_words: set[str] = set()
    if metadata_text and meta_weight > 0:
        for word, proper in (extractor(metadata_text) or []):
            if _is_intent_word(word):
                continue
            sig = get(word)
            sig.in_meta = True
            sig.meta_weight = meta_weight
            sig.is_proper = sig.is_proper or proper
            meta_words.add(word)

    for word, sig in signals.items():
        sig.near_intent = _has_intent_nearby(word, signal_text)

    # 어근 중복 정리
    words_by_len = sorted(signals.keys(), key=len)
    for i, short in enumerate(words_by_len):
        if short not in signals:
            continue
        for longer in words_by_len[i + 1:]:
            if longer in signals and longer.startswith(short):
                a, b = signals[longer], signals[short]
                a.in_ocr = a.in_ocr or b.in_ocr
                a.in_stt = a.in_stt or b.in_stt
                a.in_first = a.in_first or b.in_first
                a.is_proper = a.is_proper or b.is_proper
                a.in_meta = a.in_meta or b.in_meta
                a.meta_weight = max(a.meta_weight, b.meta_weight)
                a.seg_count = max(a.seg_count, b.seg_count)
                a.freq += b.freq
                del signals[short]
                break

    scored = [(w, s.score()) for w, s in signals.items()]
    scored.sort(key=lambda kv: (-kv[1], kv[0]))
    nouns = [w for w, sc in scored if sc > 0][:top_n]

    # 메타데이터에만 등장한 키워드 (내부엔 없던 것)
    meta_only = [
        w for w in nouns
        if signals.get(w) and signals[w].in_meta
        and not signals[w].in_ocr and not signals[w].in_stt
    ]
    return nouns, meta_only


def extract_concepts(
    segments: list[tuple[str, str]],
    signal_text: str,
    use_kiwi: bool = True,
    metadata_text: str = "",
    meta_weight: float = 0.0,
    top_n: int = 5,
) -> Concepts:
    """
    핵심 개념 추출 (영상 내부 우선 + 메타데이터 보조).

    segments: [(ocr_text, stt_text), ...] — segment 순서대로
    signal_text: 행동/감정/의도 신호를 찾을 실제 콘텐츠 텍스트
    metadata_text: title + description + hashtags 통합 (보조)
    meta_weight: 메타데이터 가중 (내부 정보 부족 시 큼). 0이면 메타데이터 미사용.

    핵심 명사는 빈도가 아니라 '여러 신호의 가중 합'으로 고른다.
    의도/행동/감정은 내부 콘텐츠(signal_text) 우선으로 찾되,
    내부 정보가 빈약하면 메타데이터의 의도 신호도 참고한다.
    """
    nouns, meta_only = select_key_nouns(
        segments, signal_text, use_kiwi=use_kiwi,
        metadata_text=metadata_text, meta_weight=meta_weight, top_n=top_n,
    )
    # 의도/행동/감정: 내부 콘텐츠 우선. 내부가 빈약할 때만 메타데이터까지 포함.
    intent_src = signal_text
    if char_len(signal_text) < 10 and metadata_text:
        intent_src = f"{signal_text} {metadata_text}"

    actions = _signal_hits(intent_src, ACTION_SIGNALS)
    emotions = _signal_hits(intent_src, EMOTION_SIGNALS)
    intent_expr = extract_intent_expressions(intent_src)
    return Concepts(
        nouns=nouns,
        actions=actions,
        emotions=emotions,
        intent_expressions=intent_expr,
        metadata_keywords=meta_only,
    )
