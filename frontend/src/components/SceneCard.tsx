import type { Segment } from "@/lib/types";
import { mediaUrl } from "@/lib/api";
import { formatTime } from "@/lib/ui";
import Collapsible from "./Collapsible";

/**
 * 장면 카드 — 기본은 학생용 정보만:
 *   thumbnail / 시간 / title / description / learn_point
 * OCR(화면 글자) · STT(말소리) 원문은 기본 숨김.
 *   "원문 보기"를 눌러야 펼쳐진다 (참고용).
 */
export default function SceneCard({
  segment,
  index,
}: {
  segment: Segment;
  index: number;
}) {
  const thumb = mediaUrl(segment.thumbnail_url);
  const hasOcr = segment.ocr_text.trim().length > 0;
  const hasSpeech = segment.speech_text.trim().length > 0;
  const hasRaw = hasOcr || hasSpeech;

  return (
    <article className="overflow-hidden rounded-blob bg-white shadow-soft">
      <div className="flex flex-col sm:flex-row">
        {/* 썸네일 */}
        <div className="relative shrink-0 bg-blueberry-soft sm:w-40">
          {thumb ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={thumb}
              alt={`${index + 1}번째 장면`}
              className="h-48 w-full object-cover sm:h-full"
              loading="lazy"
            />
          ) : (
            <div className="flex h-48 w-full items-center justify-center text-3xl sm:h-full">
              🎞️
            </div>
          )}
          <span className="absolute left-2 top-2 rounded-full bg-ink/70 px-2 py-0.5 text-xs font-bold text-white">
            {formatTime(segment.start)} – {formatTime(segment.end)}
          </span>
        </div>

        {/* 내용 */}
        <div className="flex-1 p-4">
          <div className="flex items-center gap-2">
            <span className="inline-flex h-6 w-6 items-center justify-center rounded-full bg-blueberry text-xs font-bold text-white">
              {index + 1}
            </span>
            <h3 className="font-display text-lg text-ink">{segment.title}</h3>
          </div>
          {segment.description && (
            <p className="mt-1.5 text-sm text-ink/70">{segment.description}</p>
          )}

          {/* 배운 점 (학생용 핵심) */}
          {segment.learn_point && (
            <p className="mt-3 rounded-2xl bg-sunshine-soft px-3 py-2 text-sm text-[#9A6B00]">
              <span aria-hidden>🧠</span> {segment.learn_point}
            </p>
          )}

          {/* OCR/STT 원문 — 기본 숨김, 참고용 */}
          {hasRaw && (
            <div className="mt-3">
              <Collapsible
                tone="dev"
                buttonLabel="🔍 원문 보기 (참고용)"
                openLabel="🔍 원문 접기"
              >
                <div className="grid gap-2">
                  <p className="text-xs text-ink/40">
                    AI가 영상에서 읽은 글자와 말이에요. 정확하지 않을 수 있어요.
                  </p>
                  {hasOcr && (
                    <div className="rounded-2xl bg-blueberry-soft px-3 py-2">
                      <p className="text-xs font-bold text-blueberry">
                        화면 글자 (OCR)
                      </p>
                      <p className="mt-0.5 text-sm text-ink/75">
                        {segment.ocr_text}
                      </p>
                    </div>
                  )}
                  {hasSpeech && (
                    <div className="rounded-2xl bg-mint-soft px-3 py-2">
                      <p className="text-xs font-bold text-mint">말소리 (STT)</p>
                      <p className="mt-0.5 text-sm text-ink/75">
                        {segment.speech_text}
                      </p>
                    </div>
                  )}
                </div>
              </Collapsible>
            </div>
          )}
        </div>
      </div>
    </article>
  );
}
