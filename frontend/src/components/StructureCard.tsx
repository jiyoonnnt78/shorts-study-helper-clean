import type { StructureStage } from "@/lib/types";
import { formatTime } from "@/lib/ui";

const ROLE_COLOR: Record<string, string> = {
  opening: "bg-blueberry-soft text-blueberry",
  build: "bg-mint-soft text-mint",
  killing: "bg-sunshine-soft text-[#C98A00]",
  ending: "bg-coral-soft text-coral",
};

/** 🎬 영상 구조 — 오프닝 → 전개 → 핵심 장면 → 마무리 흐름 */
export default function StructureCard({
  structure,
}: {
  structure: StructureStage[];
}) {
  if (!structure.length) return null;

  return (
    <section className="rounded-blob bg-white p-5 shadow-soft sm:p-6">
      <div className="mb-4 flex items-center gap-2">
        <span className="text-2xl" aria-hidden>
          🎬
        </span>
        <h2 className="font-display text-xl text-ink">영상 구조</h2>
        <span className="ml-auto text-xs text-ink/40">
          어떻게 흘러가나요?
        </span>
      </div>

      <ol className="relative flex flex-col gap-2">
        {structure.map((s, i) => {
          const color = ROLE_COLOR[s.role] ?? "bg-black/5 text-ink/60";
          return (
            <li key={i} className="flex items-stretch gap-3">
              {/* 시간 */}
              <div className="flex w-16 shrink-0 flex-col items-end justify-center">
                <span className="font-display text-sm text-ink">
                  {formatTime(s.start)}
                </span>
                <span className="text-[10px] text-ink/35">
                  ~{formatTime(s.end)}
                </span>
              </div>

              {/* 단계 박스 */}
              <div
                className={`flex flex-1 items-center gap-3 rounded-2xl px-4 py-3 ${color}`}
              >
                <span className="text-xl" aria-hidden>
                  {s.emoji}
                </span>
                <div>
                  <p className="font-display text-base leading-none">{s.label}</p>
                  <p className="mt-0.5 text-xs opacity-70">{s.note}</p>
                </div>
              </div>
            </li>
          );
        })}
      </ol>
    </section>
  );
}
