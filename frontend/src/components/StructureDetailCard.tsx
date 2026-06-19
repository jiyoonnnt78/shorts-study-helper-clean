import type { StructureDetail } from "@/lib/types";

const STAGES: {
  key: keyof StructureDetail;
  label: string;
  emoji: string;
  color: string;
}[] = [
  { key: "opening", label: "오프닝", emoji: "🎬", color: "bg-blueberry-soft text-blueberry" },
  { key: "development", label: "전개", emoji: "📖", color: "bg-mint-soft text-mint" },
  { key: "climax", label: "킬링파트", emoji: "⭐", color: "bg-sunshine-soft text-[#C98A00]" },
  { key: "ending", label: "마무리", emoji: "🏁", color: "bg-coral-soft text-coral" },
];

/**
 * 🧩 구성 분석 — 오프닝→전개→킬링파트→마무리 각 단계의
 * "무엇을 보여주는지(content)"와 "왜 그렇게 했는지(purpose)"를 보여준다.
 * 단순 요약이 아니라 '구성 방식'을 학생이 이해하도록 한다.
 */
export default function StructureDetailCard({
  detail,
}: {
  detail: StructureDetail;
}) {
  // 내용이 하나도 없으면 렌더하지 않음
  const hasAny = STAGES.some((st) => detail[st.key]?.content?.trim());
  if (!hasAny) return null;

  return (
    <section className="rounded-blob bg-white p-5 shadow-soft sm:p-6">
      <div className="mb-4 flex items-center gap-2">
        <span className="text-2xl" aria-hidden>
          🧩
        </span>
        <h2 className="font-display text-xl text-ink">구성 분석</h2>
        <span className="ml-auto text-xs text-ink/40">
          단계별로 왜 이렇게 만들었을까요?
        </span>
      </div>

      <ol className="flex flex-col gap-3">
        {STAGES.map((st, i) => {
          const d = detail[st.key];
          if (!d?.content?.trim()) return null;
          return (
            <li key={st.key} className="flex gap-3">
              {/* 단계 뱃지 */}
              <div className="flex flex-col items-center">
                <span
                  className={`inline-flex h-9 w-9 items-center justify-center rounded-full text-lg ${st.color}`}
                  aria-hidden
                >
                  {st.emoji}
                </span>
                {i < STAGES.length - 1 && (
                  <span className="mt-1 w-px flex-1 bg-black/10" />
                )}
              </div>

              <div className="flex-1 pb-1">
                <p className="font-display text-base text-ink">{st.label}</p>
                <p className="mt-0.5 text-sm text-ink/75">{d.content}</p>
                {d.purpose?.trim() && (
                  <p className="mt-1.5 rounded-2xl bg-black/[0.03] px-3 py-1.5 text-xs text-ink/55">
                    <span aria-hidden>🎯</span> {d.purpose}
                  </p>
                )}
              </div>
            </li>
          );
        })}
      </ol>
    </section>
  );
}
