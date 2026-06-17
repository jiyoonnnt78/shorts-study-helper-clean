"""
Kiwi 형태소 분석기 기반 명사 추출 (선택적).

설계
====
- ENABLE_KIWI=true 일 때만 사용한다.
- kiwipiepy 미설치 / 모델 로드 실패 / 분석 실패 시 None을 돌려준다.
  -> 호출자(text_analysis.extract_concepts)는 None이면 기존 규칙 방식으로 fallback.
- 품사 태깅으로 '명사(NNG/NNP)'만 고른다.
  그래서 조사(JK*), 어미(E*), 부사(MAG), 대명사(NP), 감탄사(IC) 등은
  불용어 사전 없이도 자동으로 제외된다. ("나를", "벌써", "정말" 등)
- '선생'+'님'(XSN) 같은 접미 파생은 한 단어("선생님")로 복원한다.
- '작년/오늘' 같은 시간 명사만 작은 목록으로 별도 제외한다.

이 모듈은 무거운 모델을 프로세스당 1번만 로드한다 (lazy singleton).
"""
from __future__ import annotations

import logging

logger = logging.getLogger("kiwi_extractor")

# Kiwi가 명사로 주더라도 핵심 주제어로 부적절한 시간/일반 명사 (최소한만)
_TIME_OR_GENERIC_NOUNS = {
    "작년", "올해", "내년", "어제", "오늘", "내일", "요즘", "예전", "지금",
    "방금", "아까", "나중", "이번", "저번", "다음", "동안", "그동안", "때",
    "거", "것", "수", "줄", "데", "점", "분", "초", "년", "월", "일",
    "영상", "부분", "내용", "화면", "장면", "사람", "사람들",
}

# 복수/높임 접미사: 앞 명사에 붙여 복원하거나 떼어낸다.
_SUFFIX_TAGS = {"XSN"}              # 명사 파생 접미사 (님, 들, 식 등)
_DROP_SUFFIXES = {"들"}            # 복수 접미사는 떼어서 단수 명사로
_KEEP_SUFFIXES = {"님"}            # 높임 접미사는 붙여서 의미 보존 (선생->선생님)

_NOUN_TAGS = {"NNG", "NNP"}        # 일반명사 / 고유명사
_FOREIGN_TAGS = {"SL"}             # 영문 등 (lash, BTS 같은 주제어가 될 수 있음)
_PROPER_TAGS = {"NNP", "SL"}       # 고유명사로 취급해 핵심 선별에서 우대

_kiwi = None
_kiwi_failed = False


def _get_kiwi():
    """Kiwi lazy singleton. 실패 시 None (한 번 실패하면 다시 시도하지 않음)."""
    global _kiwi, _kiwi_failed
    if _kiwi_failed:
        return None
    if _kiwi is None:
        try:
            from kiwipiepy import Kiwi

            _kiwi = Kiwi()
            logger.info("Kiwi 형태소 분석기 준비 완료")
        except Exception:
            _kiwi_failed = True
            logger.warning("Kiwi 로드 실패 -> 규칙 기반 추출로 fallback", exc_info=True)
            return None
    return _kiwi


def extract_nouns_tagged(text: str, min_len: int = 2) -> list[tuple[str, bool]] | None:
    """
    텍스트에서 (명사, 고유명사여부)를 등장 순서대로 추출한다 (중복 제거).
    - 명사(NNG/NNP) + 영문(SL)을 받는다.
    - 고유명사여부=True이면 NNP/SL (게임명·제품명·영문 등 -> 핵심 선별에서 우대)
    - 반환 None: Kiwi 사용 불가/실패 -> 호출자가 규칙 방식으로 fallback
    """
    if not text or not text.strip():
        return []

    kiwi = _get_kiwi()
    if kiwi is None:
        return None
    try:
        tokens = kiwi.tokenize(text)
    except Exception:
        logger.warning("Kiwi 분석 실패 -> 규칙 기반 추출로 fallback", exc_info=True)
        return None

    nouns: list[str] = []
    is_proper: list[bool] = []
    seen: dict[str, int] = {}
    prev_idx: int | None = None

    for tok in tokens:
        form, tag = tok.form, tok.tag

        if tag in _NOUN_TAGS or tag in _FOREIGN_TAGS:
            word = form
            ok_len = len(word) >= min_len
            if ok_len and word not in _TIME_OR_GENERIC_NOUNS:
                if word not in seen:
                    seen[word] = len(nouns)
                    nouns.append(word)
                    is_proper.append(tag in _PROPER_TAGS)
                prev_idx = seen[word]
            else:
                prev_idx = None
            continue

        if tag in _SUFFIX_TAGS and prev_idx is not None:
            base = nouns[prev_idx]
            if form in _KEEP_SUFFIXES:
                combined = base + form
                if combined not in seen:
                    proper = is_proper[prev_idx]
                    # 목록 갱신
                    del seen[base]
                    nouns[prev_idx] = combined
                    seen[combined] = prev_idx
                    is_proper[prev_idx] = proper
            elif form in _DROP_SUFFIXES:
                pass
            prev_idx = None
            continue

        prev_idx = None

    out = [
        (n, p)
        for n, p in zip(nouns, is_proper)
        if n not in _TIME_OR_GENERIC_NOUNS and len(n) >= min_len
    ]
    return out


def extract_nouns(text: str, min_len: int = 2) -> list[str] | None:
    """
    텍스트에서 명사를 등장 순서대로 추출한다 (중복 제거).
    - 반환 list: 성공
    - 반환 None: Kiwi 사용 불가/실패 -> 호출자가 규칙 방식으로 fallback

    품사가 명사인 토큰만 남기므로 조사/어미/부사/대명사/감탄사는 자동 제외.
    '선생'+'님'은 '선생님'으로 복원하고, '들' 복수 접미는 떼어 단수화한다.
    """
    if not text or not text.strip():
        return []

    kiwi = _get_kiwi()
    if kiwi is None:
        return None

    try:
        tokens = kiwi.tokenize(text)
    except Exception:
        logger.warning("Kiwi 분석 실패 -> 규칙 기반 추출로 fallback", exc_info=True)
        return None

    nouns: list[str] = []
    seen: set[str] = set()
    prev_noun_idx: int | None = None  # 직전에 추가한 명사의 nouns 내 인덱스

    for tok in tokens:
        form, tag = tok.form, tok.tag

        # 1) 명사: 후보로 추가
        if tag in _NOUN_TAGS:
            word = form
            if len(word) >= min_len and word not in _TIME_OR_GENERIC_NOUNS:
                key = word
                if key not in seen:
                    seen.add(key)
                    nouns.append(word)
                    prev_noun_idx = len(nouns) - 1
                else:
                    prev_noun_idx = nouns.index(word)
            else:
                prev_noun_idx = None
            continue

        # 2) 명사 파생 접미사: 직전 명사에 결합/처리
        if tag in _SUFFIX_TAGS and prev_noun_idx is not None:
            base = nouns[prev_noun_idx]
            if form in _KEEP_SUFFIXES:
                # 선생 -> 선생님 (의미 보존). seen/목록 갱신
                combined = base + form
                if combined not in seen:
                    seen.discard(base)
                    seen.add(combined)
                    nouns[prev_noun_idx] = combined
            elif form in _DROP_SUFFIXES:
                pass  # '들'은 떼고 단수 명사 유지
            prev_noun_idx = None
            continue

        # 3) 그 외(조사/어미/부사/동사 등)는 무시하되, 명사 연결 끊기
        prev_noun_idx = None

    # 시간/일반 명사 제거가 접미 결합 뒤에도 적용되도록 한 번 더 필터
    return [n for n in nouns if n not in _TIME_OR_GENERIC_NOUNS and len(n) >= min_len]


def is_available() -> bool:
    """Kiwi를 실제로 쓸 수 있는지 (설치 + 로드 성공)."""
    return _get_kiwi() is not None
