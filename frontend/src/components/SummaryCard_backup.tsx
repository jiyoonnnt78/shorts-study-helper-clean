import type { Summary } from "@/lib/types";
import { categoryStyle, difficultyStyle } from "@/lib/ui";
import ConfidenceGauge from "./ConfidenceGauge";
import KeywordChips from "./KeywordChips";
import Collapsible from "./Collapsible";

/**
 * 영상 요약 카드 — "무슨 영상인가"는 핵심만 간결하게.
 * (성공 구조 분석이 메인이므로 이 카드는 보조 역할)
 * - topic / purpose / category / 난이도 / confidence 노출
 * - 핵심 단어는 기본 접힘 ("핵심 단어 보기"로 펼침)
 * - source_weights는 여기서 빼고 개발자 모드(원문 보기)로 이동
 */
export default function SummaryCard({ summary }: { summary: Summary }) {
  const cat = categoryStyle(summary.category);
  const diff = difficultyStyle(summary.difficulty);

  return (
    <section className="rounded-blob bg-white p-5 shadow-soft sm:p-6">
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <span
          className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-sm font-bold ring-1 ${cat.bg} ${cat.text} ${cat.ring}`}
        >
          <span aria-hidden>{cat.emoji}</span>
          {summary.category}
        </span>
        <span className="inline-flex items-center gap-1.5 rounded-full bg-black/5 px-3 py-1.5 text-sm text-ink/70">
          <span aria-hidden>{diff.emoji}</span>
          난이도 {summary.difficulty}
        </span>
      </div>

      <p className="text-xs font-bold uppercase tracking-wide text-ink/35">
        이 영상은요
      </p>
      <h2 className="mt-1 font-display text-2xl leading-snug text-ink sm:text-[1.75rem]">
        {summary.topic}
      </h2>
      <p className="mt-2 text-base text-ink/70">{summary.purpose}</p>

      <div className="mt-4">
        <ConfidenceGauge
          confidence={summary.confidence}
          reason={summary.confidence_reason}
        />
      </div>

      {/* 핵심 단어 — 기본 접힘 */}
      <div className="mt-4">
        <Collapsible buttonLabel="🔑 핵심 단어 보기" openLabel="🔑 핵심 단어 접기">
          <KeywordChips
            keywords={summary.detected_keywords}
            metadataKeywords={summary.metadata_keywords}
          />
        </Collapsible>
      </div>
    </section>
  );
}
