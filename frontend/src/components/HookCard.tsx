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

      {/* 초반에 어떻게 관심을 끄는지 (hook_summary 우선, 없으면 reason) */}
      <p className="mt-3 text-base leading-relaxed text-white/90">
        {summary.hook_summary || summary.hook_reason}
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

      {/* 왜 그렇게 판단했는지 (hook_summary가 있을 때만 reason을 따로 노출) */}
      {summary.hook_summary && summary.hook_reason && (
        <p className="mt-4 text-sm leading-relaxed text-white/80">
          <span className="font-bold">왜 그럴까요? </span>
          {summary.hook_reason}
        </p>
      )}

      {/* 더 강한 훅으로 만드는 팁 */}
      {summary.hook_improvement_tip && (
        <div className="mt-4 rounded-blob bg-white/15 p-4">
          <p className="text-sm font-bold text-white/90">💡 더 강하게 만들려면</p>
          <p className="mt-1 text-sm leading-relaxed text-white/85">
            {summary.hook_improvement_tip}
          </p>
        </div>
      )}
    </section>
  );
}
