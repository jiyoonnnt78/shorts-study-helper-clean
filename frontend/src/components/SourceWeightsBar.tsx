import type { SourceWeights } from "@/lib/types";
import { SOURCE_LABEL, SOURCE_COLOR } from "@/lib/ui";

/** source_weights를 색깔 막대 한 줄로 보여준다. */
export default function SourceWeightsBar({
  weights,
  primary,
  metadataUsed,
}: {
  weights: SourceWeights;
  primary: string;
  metadataUsed: boolean;
}) {
  const items: { key: keyof SourceWeights; value: number }[] = [
    { key: "ocr", value: weights.ocr ?? 0 },
    { key: "stt", value: weights.stt ?? 0 },
    { key: "metadata", value: weights.metadata ?? 0 },
  ];
  const total = items.reduce((s, i) => s + i.value, 0) || 1;

  return (
    <div className="rounded-blob bg-white/70 p-4">
      <div className="mb-2 flex items-center justify-between">
        <h3 className="font-display text-base text-ink">무엇을 보고 알아냈나요?</h3>
        <span className="text-xs text-ink/40">
          가장 많이 본 건 {SOURCE_LABEL[primary] ?? "정보 없음"}
        </span>
      </div>

      {/* 한 줄 막대 */}
      <div className="flex h-4 w-full overflow-hidden rounded-full bg-black/5">
        {items.map((it) =>
          it.value > 0 ? (
            <div
              key={it.key}
              className={`${SOURCE_COLOR[it.key]} h-full transition-all`}
              style={{ width: `${(it.value / total) * 100}%` }}
              title={`${SOURCE_LABEL[it.key]} ${Math.round(it.value * 100)}%`}
            />
          ) : null
        )}
      </div>

      {/* 범례 */}
      <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1">
        {items.map((it) => (
          <div key={it.key} className="flex items-center gap-1.5 text-sm">
            <span className={`h-3 w-3 rounded-full ${SOURCE_COLOR[it.key]}`} />
            <span className="text-ink/70">{SOURCE_LABEL[it.key]}</span>
            <span className="text-ink/40">{Math.round(it.value * 100)}%</span>
          </div>
        ))}
      </div>

      {metadataUsed && (
        <p className="mt-3 rounded-2xl bg-sunshine-soft px-3 py-2 text-xs text-[#9A6B00]">
          🧩 영상 속 글자와 말이 적어서, 제목·설명도 함께 살펴봤어요.
        </p>
      )}
    </div>
  );
}
