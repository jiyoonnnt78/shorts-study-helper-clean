/** ⭐ 성공 법칙 / 📝 제작 팁 — 공통 리스트 카드 */
export function InsightListCard({
  emoji,
  title,
  subtitle,
  items,
  accent,
}: {
  emoji: string;
  title: string;
  subtitle: string;
  items: string[];
  accent: "sunshine" | "mint";
}) {
  if (!items.length) return null;
  const bullet = accent === "sunshine" ? "⭐" : "✅";
  const bg = accent === "sunshine" ? "bg-sunshine-soft" : "bg-mint-soft";

  return (
    <section className={`rounded-blob ${bg} p-5 sm:p-6`}>
      <div className="mb-3 flex items-center gap-2">
        <span className="text-2xl" aria-hidden>
          {emoji}
        </span>
        <h2 className="font-display text-xl text-ink">{title}</h2>
        <span className="ml-auto text-xs text-ink/40">{subtitle}</span>
      </div>
      <ul className="flex flex-col gap-2">
        {items.map((it, i) => (
          <li
            key={i}
            className="flex items-start gap-2.5 rounded-2xl bg-white/70 px-3.5 py-2.5 text-sm text-ink/80"
          >
            <span aria-hidden>{bullet}</span>
            <span>{it}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}
