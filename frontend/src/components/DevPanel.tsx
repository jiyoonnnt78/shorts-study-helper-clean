import type { Summary } from "@/lib/types";
import SourceWeightsBar from "./SourceWeightsBar";
import Collapsible from "./Collapsible";

/** 개발자/심사용 상세 분석 — 기본 숨김. source_weights 등 내부 지표. */
export default function DevPanel({ summary }: { summary: Summary }) {
  return (
    <section className="rounded-blob bg-white/60 p-4">
      <Collapsible
        tone="dev"
        buttonLabel="🛠️ 개발자용 분석 보기"
        openLabel="🛠️ 개발자용 분석 접기"
      >
        <div className="grid gap-3">
          <SourceWeightsBar
            weights={summary.source_weights}
            primary={summary.primary_source}
            metadataUsed={summary.metadata_used}
          />
          <div className="rounded-blob bg-white/70 p-4 text-sm text-ink/70">
            <div className="flex justify-between py-1">
              <span className="text-ink/45">카테고리</span>
              <span className="font-medium">{summary.category}</span>
            </div>
            <div className="flex justify-between py-1">
              <span className="text-ink/45">확신도</span>
              <span className="font-medium">
                {Math.round(summary.confidence * 100)}%
              </span>
            </div>
            <div className="flex justify-between py-1">
              <span className="text-ink/45">훅 강도</span>
              <span className="font-medium">{summary.hook_strength}%</span>
            </div>
            <div className="flex justify-between py-1">
              <span className="text-ink/45">주요 출처</span>
              <span className="font-medium">{summary.primary_source}</span>
            </div>
            {summary.metadata_keywords.length > 0 && (
              <div className="flex justify-between py-1">
                <span className="text-ink/45">메타 키워드</span>
                <span className="font-medium">
                  {summary.metadata_keywords.join(", ")}
                </span>
              </div>
            )}
          </div>
        </div>
      </Collapsible>
    </section>
  );
}
