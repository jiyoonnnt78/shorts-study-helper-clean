import type { StageSample } from "@/lib/types";
import { mediaUrl } from "@/lib/api";

const STAGE_COLOR: Record<string, string> = {
  opening: "bg-blueberry-soft text-blueberry",
  development: "bg-mint-soft text-mint",
  climax: "bg-sunshine-soft text-[#C98A00]",
  ending: "bg-coral-soft text-coral",
};
const STAGE_EMOJI: Record<string, string> = {
  opening: "🎬",
  development: "📖",
  climax: "⭐",
  ending: "🏁",
};

/**
 * 🎞️ 핵심 장면 분석 — 오프닝/전개/클라이맥스/마무리 각 구간의
 * 대표 스크린샷 + 화면 관찰(OCR) + 역할 + 따라 만들기 팁 + 예시 문장.
 */
export default function StageSamplesCard({
  samples,
}: {
  samples: StageSample[];
}) {
  const valid = samples?.filter((s) => s?.label);
  if (!valid || valid.length === 0) return null;

  return (
    <section className="rounded-blob bg-white p-5 shadow-soft sm:p-6">
      <div className="mb-4 flex items-center gap-2">
        <span className="text-2xl" aria-hidden>
          🎞️
        </span>
        <h2 className="font-display text-xl text-ink">핵심 장면 분석</h2>
        <span className="ml-auto text-xs text-ink/40">
          대표 장면을 깊게 읽었어요
        </span>
      </div>

      <div className="flex flex-col gap-5">
        {valid.map((s, i) => {
          const src = mediaUrl(s.screenshot);
          return (
            <div key={s.key} className="flex flex-col gap-3 sm:flex-row">
              {/* 스크린샷 */}
              <div className="shrink-0 sm:w-40">
                {src ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img
                    src={src}
                    alt={`${s.label} 장면`}
                    className="h-52 w-full rounded-2xl object-cover sm:h-40"
                    loading="lazy"
                  />
                ) : (
                  <div className="flex h-52 w-full items-center justify-center rounded-2xl bg-black/5 text-sm text-ink/40 sm:h-40">
                    장면 없음
                  </div>
                )}
              </div>

              {/* 내용 */}
              <div className="flex-1">
                <div className="flex items-center gap-2">
                  <span
                    className={`inline-flex h-7 w-7 items-center justify-center rounded-full text-base ${
                      STAGE_COLOR[s.key] ?? "bg-black/5"
                    }`}
                    aria-hidden
                  >
                    {STAGE_EMOJI[s.key] ?? "🎬"}
                  </span>
                  <h3 className="font-display text-lg text-ink">
                    {i + 1}. {s.label}
                  </h3>
                  <span className="text-xs text-ink/35">
                    {s.at_sec.toFixed(1)}초쯤
                  </span>
                </div>

                <dl className="mt-2 space-y-1.5 text-sm">
                  <div className="flex gap-2">
                    <dt className="shrink-0 text-ink/45">관찰</dt>
                    <dd className="text-ink/80">{s.observation}</dd>
                  </div>
                  <div className="flex gap-2">
                    <dt className="shrink-0 text-ink/45">역할</dt>
                    <dd className="text-ink/80">{s.role}</dd>
                  </div>
                  {s.keep_watching && (
                    <div className="flex gap-2">
                      <dt className="shrink-0 text-ink/45">몰입</dt>
                      <dd className="text-ink/80">{s.keep_watching}</dd>
                    </div>
                  )}
                </dl>

                {/* 따라 만들기 팁 + 예시 */}
                <div className="mt-2 rounded-2xl bg-mint-soft/60 px-3 py-2 text-xs text-ink/70">
                  <p>
                    <span aria-hidden>📝</span> {s.tip}
                  </p>
                  {s.example && (
                    <p className="mt-1 text-ink/55">
                      <span aria-hidden>💬</span> 예시: {s.example}
                    </p>
                  )}
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}
