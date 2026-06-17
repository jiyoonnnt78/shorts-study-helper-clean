import type { Summary } from "@/lib/types";

/** 🎣 훅 분석 — 결과 페이지 최상단. "왜 관심을 끄는가"를 가장 먼저 보여준다. */
export default function HookCard({ summary }: { summary: Summary }) {
  const strength = Math.max(0, Math.min(100, summary.hook_strength));
  const barColor =
    strength >= 70 ? "bg-mint" : strength >= 45 ? "bg-sunshine" : "bg-coral";

  return (
    <section className="animate-pop-in rounded-blob bg-gradient-to-br from-blueberry to-[#7C8AFF] p-6 text-white shadow-pop sm:p-7">
      <div className="flex items-center gap-2">
        <span className="text-2xl" aria-hidden>
          🎣
        </span>
        <h2 className="font-display text-xl">훅 분석</h2>
        <span className="ml-auto rounded-full bg-white/20 px-3 py-1 text-xs">
          왜 관심을 끌까요?
        </span>
      </div>

      {/* 훅 유형 */}
      <p className="mt-4 text-sm text-white/70">이 영상의 시작 방식은</p>
      <p className="font-display text-3xl leading-tight">{summary.hook_type}</p>

      {/* 이유 */}
      <p className="mt-3 text-base leading-relaxed text-white/90">
        {summary.hook_reason}
      </p>

      {/* 강도 게이지 */}
      <div className="mt-5 rounded-blob bg-white/15 p-4">
        <div className="flex items-center justify-between">
          <span className="text-sm font-bold text-white/90">훅 강도</span>
          <span className="font-display text-2xl">{strength}%</span>
        </div>
        <div className="mt-2 h-3 w-full overflow-hidden rounded-full bg-white/25">
          <div
            className={`h-full rounded-full ${barColor} transition-all`}
            style={{ width: `${strength}%` }}
          />
        </div>
        <p className="mt-2 text-xs text-white/70">
          {strength >= 70
            ? "처음부터 시선을 강하게 사로잡아요!"
            : strength >= 45
            ? "시작이 꽤 흥미로워요."
            : "시작을 조금 더 강하게 만들면 좋아요."}
        </p>
      </div>
    </section>
  );
}
