import { confidenceLevel } from "@/lib/ui";

/** AI 친구가 얼마나 확신하는지 보여주는 게이지 (시그니처 요소) */
export default function ConfidenceGauge({
  confidence,
  reason,
}: {
  confidence: number;
  reason?: string;
}) {
  const lv = confidenceLevel(confidence);
  return (
    <div className="rounded-blob bg-white/70 p-4">
      <div className="flex items-center gap-3">
        <span className="text-3xl" aria-hidden>
          {lv.emoji}
        </span>
        <div className="flex-1">
          <div className="flex items-center justify-between">
            <span className="font-display text-lg text-ink">{lv.label}</span>
            <span className="text-sm text-ink/40">
              {Math.round(confidence * 100)}%
            </span>
          </div>
          <div
            className="mt-1.5 flex gap-1.5"
            role="img"
            aria-label={`확신 ${lv.filled} / 3`}
          >
            {[0, 1, 2].map((i) => (
              <span
                key={i}
                className={`h-2.5 flex-1 rounded-full ${
                  i < lv.filled ? lv.color : "bg-black/10"
                }`}
              />
            ))}
          </div>
        </div>
      </div>
      {reason && <p className="mt-3 text-sm text-ink/55">{reason}</p>}
    </div>
  );
}
