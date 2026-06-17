"use client";

import { useRouter } from "next/navigation";
import { useRef, useState } from "react";
import BrandHeader from "@/components/BrandHeader";
import { uploadVideo, analyzeYoutube } from "@/lib/api";

const ALLOWED = ["video/mp4", "video/quicktime", "video/webm"];
const ALLOWED_EXT = [".mp4", ".mov", ".webm"];
const MAX_MB = 100;

export default function HomePage() {
  const router = useRouter();
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [ytUrl, setYtUrl] = useState("");

  async function handleYoutube() {
    const url = ytUrl.trim();
    if (!url || busy) return;
    setError(null);
    setBusy(true);
    try {
      const { id } = await analyzeYoutube(url);
      router.push(`/videos/${id}/analyzing`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "링크 분석에 실패했어요.");
      setBusy(false);
    }
  }

  function validate(file: File): string | null {
    const lower = file.name.toLowerCase();
    const okExt = ALLOWED_EXT.some((e) => lower.endsWith(e));
    if (!ALLOWED.includes(file.type) && !okExt) {
      return "mp4, mov, webm 영상만 올릴 수 있어요.";
    }
    if (file.size > MAX_MB * 1024 * 1024) {
      return `영상이 너무 커요. ${MAX_MB}MB보다 작은 영상을 올려주세요.`;
    }
    return null;
  }

  async function handleFile(file: File) {
    setError(null);
    const problem = validate(file);
    if (problem) {
      setError(problem);
      return;
    }
    setBusy(true);
    try {
      const { id } = await uploadVideo(file);
      router.push(`/videos/${id}/analyzing`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "업로드에 실패했어요.");
      setBusy(false);
    }
  }

  return (
    <>
      <BrandHeader />

      <main className="flex flex-1 flex-col">
        {/* 히어로 */}
        <div className="mb-6 text-center">
          <div className="mb-3 inline-block animate-bounce-soft text-5xl" aria-hidden>
            🎬
          </div>
          <h1 className="font-display text-3xl leading-tight text-ink sm:text-4xl">
            내 짧은 영상,
            <br />
            무슨 내용인지 알려줄게요
          </h1>
          <p className="mt-3 text-base text-ink/60">
            영상을 올리면 화면 글자와 말소리를 살펴보고
            <br className="hidden sm:block" /> 쉬운 말로 풀어드려요.
          </p>
        </div>

        {/* YouTube 링크 입력 */}
        <div className="mb-4 rounded-blob bg-white/70 p-4">
          <div className="mb-2 flex items-center gap-2">
            <span className="text-xl" aria-hidden>
              🔗
            </span>
            <h2 className="font-display text-lg text-ink">유튜브 링크로 분석</h2>
          </div>
          <div className="flex flex-col gap-2 sm:flex-row">
            <input
              type="url"
              inputMode="url"
              value={ytUrl}
              onChange={(e) => setYtUrl(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") handleYoutube();
              }}
              disabled={busy}
              placeholder="유튜브 쇼츠 링크를 붙여넣어 보세요"
              className="flex-1 rounded-2xl border-2 border-blueberry/20 bg-white px-4 py-3 text-base text-ink outline-none transition-colors placeholder:text-ink/35 focus:border-blueberry/60 disabled:opacity-60"
            />
            <button
              type="button"
              onClick={handleYoutube}
              disabled={busy || !ytUrl.trim()}
              className="shrink-0 rounded-2xl bg-blueberry px-5 py-3 font-display text-base text-white shadow-soft transition-transform hover:scale-[1.03] disabled:opacity-50 disabled:hover:scale-100"
            >
              링크로 분석하기
            </button>
          </div>
          <p className="mt-2 text-xs leading-relaxed text-ink/45">
            유튜브 링크 분석은 영상 제목과 설명, 가능한 분석 정보를 바탕으로
            도와줘요. 결과는 틀릴 수 있어요.
          </p>
        </div>

        {/* 구분선 */}
        <div className="mb-4 flex items-center gap-3">
          <span className="h-px flex-1 bg-black/10" />
          <span className="text-sm text-ink/40">또는 영상 파일 올리기</span>
          <span className="h-px flex-1 bg-black/10" />
        </div>

        {/* 업로드 박스 */}
        <button
          type="button"
          onClick={() => !busy && inputRef.current?.click()}
          onDragOver={(e) => {
            e.preventDefault();
            setDragging(true);
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={(e) => {
            e.preventDefault();
            setDragging(false);
            const f = e.dataTransfer.files?.[0];
            if (f) handleFile(f);
          }}
          disabled={busy}
          className={`group relative flex min-h-[15rem] w-full flex-col items-center justify-center rounded-blob border-4 border-dashed bg-white/70 p-8 text-center transition-all ${
            dragging
              ? "border-blueberry bg-blueberry-soft scale-[1.01]"
              : "border-blueberry/30 hover:border-blueberry/60 hover:bg-white"
          } ${busy ? "cursor-wait opacity-70" : "cursor-pointer"}`}
        >
          {busy ? (
            <>
              <span className="text-5xl animate-bounce-soft" aria-hidden>
                ⏳
              </span>
              <p className="mt-4 font-display text-xl text-ink">
                영상을 올리고 있어요…
              </p>
            </>
          ) : (
            <>
              <span
                className="text-5xl transition-transform group-hover:scale-110"
                aria-hidden
              >
                ⬆️
              </span>
              <p className="mt-4 font-display text-xl text-ink">
                여기를 눌러 영상 고르기
              </p>
              <p className="mt-1 text-sm text-ink/50">
                또는 영상을 끌어다 놓아요
              </p>
              <p className="mt-4 rounded-full bg-black/5 px-3 py-1 text-xs text-ink/45">
                mp4 · mov · webm · {MAX_MB}MB까지
              </p>
            </>
          )}
        </button>

        <input
          ref={inputRef}
          type="file"
          accept=".mp4,.mov,.webm,video/mp4,video/quicktime,video/webm"
          className="hidden"
          onChange={(e) => {
            const f = e.target.files?.[0];
            if (f) handleFile(f);
            e.target.value = "";
          }}
        />

        {error && (
          <div
            role="alert"
            className="mt-4 rounded-blob bg-coral-soft px-4 py-3 text-center text-sm text-coral"
          >
            {error}
          </div>
        )}

        {/* 안내 3단계 */}
        <div className="mt-8 grid gap-3 sm:grid-cols-3">
          {[
            { e: "📤", t: "영상 올리기", d: "짧은 세로 영상이 좋아요" },
            { e: "🔎", t: "함께 살펴보기", d: "글자와 말소리를 읽어요" },
            { e: "📒", t: "쉽게 알려주기", d: "주제와 장면을 정리해요" },
          ].map((s, i) => (
            <div
              key={i}
              className="rounded-blob bg-white/60 p-4 text-center"
            >
              <div className="text-3xl" aria-hidden>
                {s.e}
              </div>
              <p className="mt-2 font-display text-base text-ink">{s.t}</p>
              <p className="text-xs text-ink/50">{s.d}</p>
            </div>
          ))}
        </div>
      </main>
    </>
  );
}
