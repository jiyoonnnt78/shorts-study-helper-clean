// 카테고리별 이모지 + 색 토큰. 백엔드 CATEGORIES와 맞춤.
export const CATEGORY_STYLE: Record<
  string,
  { emoji: string; bg: string; text: string; ring: string }
> = {
  "정보 전달": { emoji: "💡", bg: "bg-blueberry-soft", text: "text-blueberry", ring: "ring-blueberry/30" },
  "방법 설명": { emoji: "🛠️", bg: "bg-mint-soft", text: "text-mint", ring: "ring-mint/30" },
  "재미/오락": { emoji: "😆", bg: "bg-sunshine-soft", text: "text-[#C98A00]", ring: "ring-sunshine/40" },
  "감정 표현": { emoji: "💗", bg: "bg-coral-soft", text: "text-coral", ring: "ring-coral/30" },
  "축하/응원": { emoji: "🎉", bg: "bg-sunshine-soft", text: "text-[#C98A00]", ring: "ring-sunshine/40" },
  "후기/경험": { emoji: "✍️", bg: "bg-blueberry-soft", text: "text-blueberry", ring: "ring-blueberry/30" },
  "소개/홍보": { emoji: "📣", bg: "bg-mint-soft", text: "text-mint", ring: "ring-mint/30" },
  "이야기/브이로그": { emoji: "🎬", bg: "bg-coral-soft", text: "text-coral", ring: "ring-coral/30" },
  "의견/주장": { emoji: "🙋", bg: "bg-blueberry-soft", text: "text-blueberry", ring: "ring-blueberry/30" },
  "기타": { emoji: "🔍", bg: "bg-black/5", text: "text-ink/60", ring: "ring-black/10" },
};

export function categoryStyle(cat: string) {
  return CATEGORY_STYLE[cat] ?? CATEGORY_STYLE["기타"];
}

// 확신도 -> 사람이 읽는 단계 (이모지 게이지)
export function confidenceLevel(conf: number): {
  label: string;
  emoji: string;
  filled: number; // 0~3
  color: string;
} {
  if (conf >= 0.65)
    return { label: "꽤 확실해요", emoji: "😎", filled: 3, color: "bg-mint" };
  if (conf >= 0.35)
    return { label: "아마도요", emoji: "🙂", filled: 2, color: "bg-sunshine" };
  return { label: "잘 모르겠어요", emoji: "🤔", filled: 1, color: "bg-coral" };
}

// 출처 라벨
export const SOURCE_LABEL: Record<string, string> = {
  ocr: "화면 글자",
  stt: "말소리",
  metadata: "영상 정보",
  none: "정보 없음",
};

export const SOURCE_COLOR: Record<string, string> = {
  ocr: "bg-blueberry",
  stt: "bg-mint",
  metadata: "bg-sunshine",
};

export function formatTime(sec: number): string {
  const s = Math.max(0, Math.round(sec));
  const m = Math.floor(s / 60);
  const r = s % 60;
  return `${m}:${r.toString().padStart(2, "0")}`;
}

export function difficultyStyle(diff: string): { emoji: string; cls: string } {
  switch (diff) {
    case "쉬움":
      return { emoji: "🟢", cls: "text-mint" };
    case "어려움":
      return { emoji: "🔴", cls: "text-coral" };
    default:
      return { emoji: "🟡", cls: "text-[#C98A00]" };
  }
}
