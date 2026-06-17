export default function KeywordChips({
  keywords,
  metadataKeywords = [],
}: {
  keywords: string[];
  metadataKeywords?: string[];
}) {
  if (keywords.length === 0) {
    return (
      <p className="text-sm text-ink/40">
        핵심 단어를 찾지 못했어요. 글자나 말이 더 있으면 좋아요.
      </p>
    );
  }
  const metaSet = new Set(metadataKeywords);
  return (
    <div className="flex flex-wrap gap-2">
      {keywords.map((kw, i) => {
        const fromMeta = metaSet.has(kw);
        return (
          <span
            key={`${kw}-${i}`}
            className={`rounded-full px-3 py-1.5 text-sm font-medium ${
              fromMeta
                ? "bg-sunshine-soft text-[#9A6B00]"
                : "bg-blueberry-soft text-blueberry"
            }`}
            title={fromMeta ? "영상 정보(제목·설명)에서 찾은 단어예요" : undefined}
          >
            #{kw}
            {fromMeta && <span className="ml-1 opacity-60">🧩</span>}
          </span>
        );
      })}
    </div>
  );
}
