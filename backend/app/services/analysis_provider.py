"""
분석 provider adapter.

두 가지 분석 방식을 같은 인터페이스로 제공한다:
- RuleBasedProvider : 무료/로컬. 기존 success_analyzer + explainer 신호 사용 (기본값).
- LLMProvider       : 선택. 외부 LLM API로 더 풍부한 분석. 키/네트워크 필요.

설계 원칙
=========
- 기본은 규칙 기반(무료). LLM은 ENABLE_LLM_ANALYSIS=true + API 키가 있을 때만.
- LLM 실패(키 없음/타임아웃/파싱 오류)는 자동으로 규칙 기반으로 fallback.
- 두 provider 모두 AnalysisResult(동일 형태)를 반환 -> explainer는 그대로 동작.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field

from ..config import get_settings

logger = logging.getLogger("analysis_provider")


# ---------------------------------------------------------------------------
# 입력 / 출력 공통 형태
# ---------------------------------------------------------------------------
@dataclass
class AnalysisInput:
    """LLM/규칙 분석에 공통으로 넘기는 입력."""
    title: str = ""
    description: str = ""
    hashtags: str = ""
    ocr_text: str = ""
    stt_text: str = ""
    duration: float = 0.0
    category: str = "기타"
    keywords: list[str] = field(default_factory=list)


@dataclass
class StructureStageDetail:
    content: str = ""
    purpose: str = ""

    def to_dict(self) -> dict:
        return {"content": self.content, "purpose": self.purpose}


@dataclass
class AnalysisResult:
    """두 provider가 공통으로 반환하는 분석 결과."""
    summary: str = ""                                    # 3~5문장 요약
    topic: str = ""                                      # 핵심 주제
    hook_type: str = ""
    hook_strength: int = 0
    hook_reason: str = ""
    # opening/development/climax/ending 각 {content, purpose}
    structure_detail: dict = field(default_factory=dict)
    engagement_factors: list[str] = field(default_factory=list)
    success_patterns: list[str] = field(default_factory=list)
    creator_tips: list[str] = field(default_factory=list)
    provider: str = "rule"


# ---------------------------------------------------------------------------
# 인터페이스
# ---------------------------------------------------------------------------
class AnalysisProvider:
    name = "base"

    def analyze(self, inp: AnalysisInput, rule_result: AnalysisResult) -> AnalysisResult:
        """
        rule_result: 규칙 기반으로 이미 만든 결과 (LLM 실패 시 fallback 기반).
        """
        raise NotImplementedError


# ---------------------------------------------------------------------------
# 규칙 기반 provider (기존 결과를 그대로 사용)
# ---------------------------------------------------------------------------
class RuleBasedProvider(AnalysisProvider):
    name = "rule"

    def analyze(self, inp: AnalysisInput, rule_result: AnalysisResult) -> AnalysisResult:
        rule_result.provider = "rule"
        return rule_result


# ---------------------------------------------------------------------------
# LLM provider
# ---------------------------------------------------------------------------
SYSTEM_PROMPT = (
    "당신은 초등학생도 이해할 수 있게 숏폼 영상을 분석하는 콘텐츠 전문가입니다. "
    "영상의 제목, 설명, OCR 텍스트, STT 텍스트를 바탕으로 단순 요약이 아니라 "
    "영상의 구성 방식과 시청자 몰입 요소를 분석합니다. "
    "반드시 지정된 JSON 형식으로만 응답하고, 다른 말은 덧붙이지 않습니다."
)

# 출력 JSON 스키마를 명시하는 사용자 프롬프트 템플릿
JSON_SPEC = """반드시 아래 형식의 JSON으로만 응답하세요.
{
  "summary": "영상 전체를 쉬운 말로 3~5문장 요약",
  "topic": "영상의 핵심 주제",
  "structure": {
    "opening": {"content": "시작 부분에서 무엇을 보여주는지", "purpose": "관심을 끄는 전략"},
    "development": {"content": "중간 전개 내용", "purpose": "계속 보게 만드는 요소"},
    "climax": {"content": "가장 중요한 장면 또는 정보", "purpose": "핵심 메시지 또는 반전"},
    "ending": {"content": "마무리 부분", "purpose": "시청자에게 남기는 인상"}
  },
  "hook_analysis": {
    "hook_type": "질문형, 충격형, 공감형, 정보형, 스토리형 중 하나",
    "hook_strength": 0,
    "reason": "왜 관심을 끄는지 설명"
  },
  "engagement_factors": ["몰입 요소 1", "몰입 요소 2", "몰입 요소 3"],
  "success_pattern": ["성공 공식 1", "성공 공식 2", "성공 공식 3"],
  "creator_tips": ["구체적 제작 팁 1", "...2", "...3", "...4", "...5"]
}
중요:
- creator_tips는 일반론 금지("말로 설명하면 좋아요", "자막을 크게" 같은 조언 금지).
- 영상 내용과 주제에 맞는 구체적인 제작 전략을 제안한다.
- creator_tips는 최소 5개, 각 팁은 서로 다른 전략이어야 한다.
- structure는 반드시 opening -> development -> climax -> ending 으로 구분한다.
- hook_strength는 0~100 사이 정수.
"""


def _build_user_prompt(inp: AnalysisInput) -> str:
    parts = ["다음 숏폼 영상을 분석하세요.\n"]
    if inp.title:
        parts.append(f"[제목] {inp.title}")
    if inp.description:
        parts.append(f"[설명] {inp.description}")
    if inp.hashtags:
        parts.append(f"[해시태그] {inp.hashtags}")
    if inp.ocr_text:
        parts.append(f"[화면 글자(OCR)] {inp.ocr_text}")
    if inp.stt_text:
        parts.append(f"[말소리(STT)] {inp.stt_text}")
    if inp.duration:
        parts.append(f"[길이] 약 {int(inp.duration)}초")
    if inp.category and inp.category != "기타":
        parts.append(f"[추정 분류] {inp.category}")
    parts.append("\n" + JSON_SPEC)
    return "\n".join(parts)


class LLMProvider(AnalysisProvider):
    name = "llm"

    # 우리 hook_type 명칭 <- LLM이 쓰는 명칭 매핑 (UI 일관성용; 실패해도 원문 유지)
    _HOOK_MAP = {
        "질문형": "궁금증 유발형",
        "충격형": "재미·반전형",
        "공감형": "공감·감정형",
        "정보형": "정보 제시형",
        "스토리형": "잔잔한 시작형",
    }

    def analyze(self, inp: AnalysisInput, rule_result: AnalysisResult) -> AnalysisResult:
        settings = get_settings()
        if not settings.LLM_API_KEY:
            logger.info("LLM_API_KEY 없음 -> 규칙 기반으로 fallback")
            return rule_result

        try:
            raw = self._call_llm(inp, settings)
            data = self._parse_json(raw)
            return self._to_result(data, rule_result)
        except Exception:
            logger.warning("LLM 분석 실패 -> 규칙 기반으로 fallback", exc_info=True)
            return rule_result

    # --- 실제 호출 (provider별 분기) ---
    def _call_llm(self, inp: AnalysisInput, settings) -> str:
        user = _build_user_prompt(inp)
        provider = (settings.LLM_PROVIDER or "openai").lower()
        if provider == "anthropic":
            return self._call_anthropic(user, settings)
        return self._call_openai(user, settings)

    def _call_openai(self, user_prompt: str, settings) -> str:
        import urllib.request

        base = (settings.LLM_BASE_URL or "https://api.openai.com/v1").rstrip("/")
        body = json.dumps({
            "model": settings.LLM_MODEL or "gpt-4o-mini",
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.7,
            "response_format": {"type": "json_object"},
        }).encode("utf-8")
        req = urllib.request.Request(
            f"{base}/chat/completions",
            data=body,
            headers={
                "Authorization": f"Bearer {settings.LLM_API_KEY}",
                "Content-Type": "application/json",
            },
        )
        with urllib.request.urlopen(req, timeout=settings.LLM_TIMEOUT_SECONDS) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        return payload["choices"][0]["message"]["content"]

    def _call_anthropic(self, user_prompt: str, settings) -> str:
        import urllib.request

        base = (settings.LLM_BASE_URL or "https://api.anthropic.com/v1").rstrip("/")
        body = json.dumps({
            "model": settings.LLM_MODEL or "claude-3-5-haiku-latest",
            "max_tokens": 1500,
            "system": SYSTEM_PROMPT,
            "messages": [{"role": "user", "content": user_prompt}],
        }).encode("utf-8")
        req = urllib.request.Request(
            f"{base}/messages",
            data=body,
            headers={
                "x-api-key": settings.LLM_API_KEY,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json",
            },
        )
        with urllib.request.urlopen(req, timeout=settings.LLM_TIMEOUT_SECONDS) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        return payload["content"][0]["text"]

    # --- 파싱 ---
    @staticmethod
    def _parse_json(raw: str) -> dict:
        s = raw.strip()
        # 코드펜스 제거
        if s.startswith("```"):
            s = s.split("```", 2)[1] if "```" in s[3:] else s.strip("`")
            s = s.removeprefix("json").strip()
        # 중괄호 구간만 추출
        start, end = s.find("{"), s.rfind("}")
        if start != -1 and end != -1:
            s = s[start : end + 1]
        return json.loads(s)

    def _to_result(self, data: dict, fallback: AnalysisResult) -> AnalysisResult:
        def slist(v) -> list[str]:
            if isinstance(v, list):
                return [str(x).strip() for x in v if str(x).strip()]
            return []

        hook = data.get("hook_analysis") or {}
        raw_hook_type = str(hook.get("hook_type", "")).strip()
        hook_type = self._HOOK_MAP.get(raw_hook_type, raw_hook_type) or fallback.hook_type

        try:
            strength = int(hook.get("hook_strength", fallback.hook_strength))
        except (TypeError, ValueError):
            strength = fallback.hook_strength
        strength = max(0, min(100, strength))

        struct = data.get("structure") or {}
        structure_detail = {}
        for key in ("opening", "development", "climax", "ending"):
            stage = struct.get(key) or {}
            structure_detail[key] = {
                "content": str(stage.get("content", "")).strip(),
                "purpose": str(stage.get("purpose", "")).strip(),
            }

        tips = slist(data.get("creator_tips"))
        patterns = slist(data.get("success_pattern")) or slist(data.get("success_patterns"))
        engagement = slist(data.get("engagement_factors"))

        return AnalysisResult(
            summary=str(data.get("summary", "")).strip() or fallback.summary,
            topic=str(data.get("topic", "")).strip() or fallback.topic,
            hook_type=hook_type,
            hook_strength=strength,
            hook_reason=str(hook.get("reason", "")).strip() or fallback.hook_reason,
            structure_detail=structure_detail if any(
                v.get("content") for v in structure_detail.values()
            ) else fallback.structure_detail,
            engagement_factors=engagement or fallback.engagement_factors,
            success_patterns=patterns or fallback.success_patterns,
            creator_tips=tips if len(tips) >= 3 else fallback.creator_tips,
            provider="llm",
        )


# ---------------------------------------------------------------------------
# provider 선택
# ---------------------------------------------------------------------------
def get_analysis_provider() -> AnalysisProvider:
    settings = get_settings()
    if settings.ENABLE_LLM_ANALYSIS and settings.LLM_API_KEY:
        return LLMProvider()
    return RuleBasedProvider()
