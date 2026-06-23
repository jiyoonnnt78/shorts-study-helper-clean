"""
OpenAI Vision으로 영상 프레임 + 메타데이터를 분석한다.

OCR/STT/Kiwi 없이, 추출한 대표 프레임(시간순)과 메타데이터를 LLM에 보내
영상 전체 흐름을 추론하고 교육용 분석 결과(JSON)를 받는다.

httpx로 OpenAI Chat Completions API(vision)를 직접 호출 (SDK 의존 없음).
키/모델 실패 시 None을 반환 -> 호출자가 메타데이터 전용으로 폴백.
"""
from __future__ import annotations

import base64
import json
import logging

import httpx

from ..config import get_settings

logger = logging.getLogger("vision_analyzer")

OPENAI_URL = "https://api.openai.com/v1/chat/completions"

# LLM이 반드시 이 JSON 형태로만 응답하도록 지시.
_SYSTEM_PROMPT = """\
너는 초등학생(4~6학년)에게 인기 유튜브 쇼츠가 "왜 인기 있는지"를 가르치는 분석가야.
시간순으로 제공된 영상 프레임들과 메타데이터를 보고 영상 전체 흐름을 추론해.
어려운 편집 용어는 쓰지 말고, 초등학생도 이해할 친절한 한국어로 설명해.

반드시 아래 JSON 형식으로만 응답해. 다른 말/마크다운/코드블록 금지.

{
  "topic": "영상 주제 (한 줄)",
  "purpose": "영상 목적 (한 줄)",
  "category": "소개/홍보 | 정보/교육 | 재미/오락 | 감정/공감 | 후기/리뷰 | 기타 중 하나",
  "core_message": "핵심 메시지 (한 줄)",
  "analysis_summary": "영상 전체를 3~4문장으로 쉽게 요약",
  "audience": ["시청 대상 2~3개"],
  "hook_type": "궁금증 유발형 | 결과 먼저 보여주기형 | 리스트·순위형 | 재미·반전형 | 공감·감정형 | 정보 제시형 중 하나",
  "hook_reason": "왜 사람들이 처음에 관심을 갖는지 한 줄",
  "persuasion": ["영상이 쓴 설득/몰입 방식 2~4개"],
  "structure": {
    "opening":     {"content": "처음 장면에서 무엇을 보여주는지", "purpose": "왜 그렇게 시작하는지"},
    "development": {"content": "중간 전개", "purpose": "그 역할"},
    "climax":      {"content": "가장 인상적인 부분", "purpose": "그 역할"},
    "ending":      {"content": "마무리", "purpose": "그 역할"}
  },
  "key_scenes": ["중요한 장면 3~5개를 시간 흐름대로 한 줄씩"],
  "creator_tips": ["이 영상처럼 만들려면 어떻게 할지 따라하기 팁 5개"],
  "success_patterns": ["이 영상이 잘한 점 3~5개"]
}
"""


def _img_data_url(path: str) -> str | None:
    try:
        with open(path, "rb") as f:
            b = base64.b64encode(f.read()).decode("ascii")
        return f"data:image/jpeg;base64,{b}"
    except Exception:
        logger.warning("이미지 인코딩 실패: %s", path, exc_info=True)
        return None


def analyze_with_vision(frames: list[dict], meta: dict) -> dict | None:
    """
    frames: [{"at_sec","name","path"}, ...] (시간순)
    meta:   {"title","description","channel","duration","hashtags"}
    반환: 분석 결과 dict 또는 None(실패).
    """
    s = get_settings()
    if not s.OPENAI_API_KEY:
        logger.error("OPENAI_API_KEY 미설정 -> Vision 분석 불가")
        return None

    # 메타데이터 텍스트 블록
    meta_lines = [
        f"제목: {meta.get('title') or '(없음)'}",
        f"설명: {(meta.get('description') or '(없음)')[:500]}",
        f"채널: {meta.get('channel') or '(없음)'}",
        f"영상 길이: {meta.get('duration') or '?'}초",
        f"해시태그: {meta.get('hashtags') or '(없음)'}",
        f"제공된 프레임: {len(frames)}장 (시간순)",
    ]
    meta_text = "\n".join(meta_lines)

    # user content: 텍스트 + 프레임 이미지들(시간순, 각 프레임 앞에 시각 표시)
    content: list[dict] = [{
        "type": "text",
        "text": "다음은 인기 유튜브 쇼츠의 정보와 시간순 프레임이야. "
                "프레임 흐름으로 영상 전체를 추론해서 분석해줘.\n\n" + meta_text,
    }]
    for fr in frames:
        url = _img_data_url(fr["path"])
        if not url:
            continue
        content.append({"type": "text", "text": f"[{fr.get('at_sec','?')}초 지점]"})
        content.append({
            "type": "image_url",
            "image_url": {"url": url, "detail": "low"},  # low = 비용/속도 절감
        })

    if len(content) <= 1:
        logger.error("유효한 프레임 이미지가 없음 -> Vision 분석 불가")
        return None

    payload = {
        "model": s.OPENAI_VISION_MODEL,
        "messages": [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": content},
        ],
        "max_tokens": 1500,
        "temperature": 0.5,
        "response_format": {"type": "json_object"},
    }
    headers = {
        "Authorization": f"Bearer {s.OPENAI_API_KEY}",
        "Content-Type": "application/json",
    }

    logger.info("OpenAI Vision 호출 시작: model=%s 프레임=%d장",
                s.OPENAI_VISION_MODEL, len(frames))
    try:
        with httpx.Client(timeout=120.0) as client:
            r = client.post(OPENAI_URL, headers=headers, json=payload)
        logger.info("OpenAI Vision 응답: status=%s", r.status_code)
        if r.status_code != 200:
            logger.error("OpenAI Vision 실패: %s | %s",
                         r.status_code, r.text[:500])
            return None
        data = r.json()
        text = data["choices"][0]["message"]["content"]
        result = json.loads(text)
        logger.info("OpenAI Vision 분석 성공: topic=%s",
                    str(result.get("topic"))[:40])
        return result
    except Exception:
        logger.error("OpenAI Vision 호출/파싱 오류", exc_info=True)
        return None
