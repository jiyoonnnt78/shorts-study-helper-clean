import type { YoutubeInfo, Summary } from "@/lib/types";

/** YouTube 링크 분석 결과 상단에 영상 정보(제목/썸네일/링크) 표시 */
export default function YoutubeInfoCard({
  youtube,
  summary,
}: {
  youtube: YoutubeInfo;
  summary: Summary | null;
}) {
  const title = youtube.title?.trim();
  const thumb = youtube.thumbnail_url;
  const url = youtube.source_url ?? undefined;

  return (
    <section className="overflow-hidden rounded-blob bg-white shadow-soft">
      <div className="flex flex-col sm:flex-row">
        {thumb && (
          <div className="relative shrink-0 bg-black sm:w-48">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src={thumb}
              alt={title || "유튜브 썸네일"}
              className="h-44 w-full object-cover sm:h-full"
              loading="lazy"
            />
            <span className="absolute left-2 top-2 rounded-full bg-coral px-2 py-0.5 text-xs font-bold text-white">
              ▶ YouTube
            </span>
          </div>
        )}
        <div className="flex flex-1 flex-col justify-center p-4">
          <p className="text-xs font-bold uppercase tracking-wide text-ink/35">
            유튜브 영상
          </p>
          <h2 className="mt-1 font-display text-lg leading-snug text-ink">
            {title || "제목을 가져오지 못했어요"}
          </h2>

          {summary?.metadata_used && (
            <p className="mt-2 inline-flex w-fit items-center gap-1 rounded-full bg-sunshine-soft px-2.5 py-1 text-xs text-[#9A6B00]">
              🧩 제목·설명을 분석에 함께 사용했어요
            </p>
          )}

          {url && (
            <a
              href={url}
              target="_blank"
              rel="noopener noreferrer"
              className="mt-3 inline-flex w-fit items-center gap-1.5 rounded-full bg-blueberry px-4 py-2 text-sm font-bold text-white transition-transform hover:scale-105"
            >
              유튜브에서 열기 ↗
            </a>
          )}
        </div>
      </div>
    </section>
  );
}
