"use client";

import { useEffect, useRef, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import BrandHeader from "@/components/BrandHeader";
import { getStatus } from "@/lib/api";

// 분석 단계 순서 (백엔드 progress와 함께 표시).
const STEPS = [
  { label: "영상 정보 확인", emoji: "🎬", at: 10 },
  { label: "영상 다운로드", emoji: "⬇️", at: 30 },
  { label: "대표 장면 추출", emoji: "📸", at: 55 },
  { label: "AI가 장면 살펴보기", emoji: "🤖", at: 75 },
  { label: "분석 결과 정리", emoji: "📒", at: 90 },
  { label: "완료", emoji: "🎉", at: 100 },
];

export default function AnalyzingPage() {
  const router = useRouter();
  const params = useParams<{ id: string }>();
  const id = params.id;

  const [progress, setProgress] = useState(5);
  const [message, setMessage] = useState("분석을 준비하는 중…");
  const [error, setError] = useState<string | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  // 표시용 진행바: 실제 progress로 점프하되, 멈춰 보이지 않게 살짝 흐른다.
  const [shownProgress, setShownProgress] = useState(5);

  useEffect(() => {
    let alive = true;
    async function poll() {
      try {
        const s = await getStatus(id);
        if (!alive) return;
        if (s.status === "completed") {
          setProgress(100);
          setMessage("완료");
          setTimeout(() => router.replace(`/videos/${id}`), 500);
          return;
        }
        if (s.status === "failed") {
          setError(
            s.error_message ??
              "영상을 분석하는 중에 문제가 생겼어요. 다른 영상으로 다시 해볼까요?"
          );
          return;
        }
        if (typeof s.progress === "number") setProgress(s.progress);
        if (s.message) setMessage(s.message);
        timer.current = setTimeout(poll, 1500);
      } catch {
        if (!alive) return;
        timer.current = setTimeout(poll, 2500);
      }
    }
    poll();
    return () => {
      alive = false;
      if (timer.current) clearTimeout(timer.current);
    };
  }, [id, router]);

  // 진행바가 멈춘 것처럼 보이지 않도록: 목표까지 부드럽게 차오르고,
  // 같은 단계에 머무는 동안에도 아주 천천히 +1씩 기어간다(최대 목표-2까지).
  useEffect(() => {
    const iv = setInterval(() => {
      setShownProgress((cur) => {
        if (cur < progress) return Math.min(progress, cur + 2);
        if (cur < Math.min(progress + 6, 98) && progress < 100) return cur + 0.3;
        if (progress >= 100) return 100;
        return cur;
      });
    }, 120);
    return () => clearInterval(iv);
  }, [progress]);

  const activeIndex = STEPS.findIndex((st) => progress <= st.at);
  const curIndex = activeIndex === -1 ? STEPS.length - 1 : activeIndex;

  if (error) {
    return (
      <>
        <BrandHeader compact />
        <main className="flex flex-1 flex-col items-center justify-center text-center">
          <div className="text-6xl" aria-hidden>😢</div>
          <h1 className="mt-4 font-display text-2xl text-ink">
            앗, 분석을 마치지 못했어요
          </h1>
          <p className="mt-2 max-w-sm text-ink/60">{error}</p>
          <button
            onClick={() => router.push("/")}
            className="mt-6 rounded-full bg-blueberry px-6 py-3 font-display text-lg text-white shadow-soft transition-transform hover:scale-105"
          >
            다른 영상 올리기
          </button>
        </main>
      </>
    );
  }

  return (
    <>
      <BrandHeader compact />
      <main className="flex flex-1 flex-col items-center justify-center px-4">
        <div className="text-6xl animate-bounce-soft" aria-hidden>
          {STEPS[curIndex].emoji}
        </div>
        <h1 className="mt-5 text-center font-display text-2xl text-ink">
          영상을 살펴보고 있어요
        </h1>
        <p className="mt-2 h-6 text-center text-ink/60">{message}</p>

        {/* 진행바 */}
        <div className="mt-6 w-full max-w-sm">
          <div className="h-4 w-full overflow-hidden rounded-full bg-black/10">
            <div
              className="h-full rounded-full bg-gradient-to-r from-blueberry to-mint transition-[width] duration-300 ease-out"
              style={{ width: `${Math.round(shownProgress)}%` }}
            />
          </div>
          <div className="mt-1 text-right text-sm font-bold text-ink/50">
            {Math.round(shownProgress)}%
          </div>
        </div>

        {/* 단계 목록 */}
        <ol className="mt-6 w-full max-w-sm space-y-2">
          {STEPS.slice(0, 5).map((st, i) => {
            const done = curIndex > i;
            const active = curIndex === i;
            return (
              <li
                key={st.label}
                className={`flex items-center gap-3 rounded-blob px-4 py-3 transition-all ${
                  active ? "bg-white shadow-soft" : done ? "bg-white/50" : "bg-white/30"
                }`}
              >
                <span
                  className={`inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-sm ${
                    done
                      ? "bg-mint text-white"
                      : active
                      ? "bg-blueberry text-white animate-pop-in"
                      : "bg-black/10 text-ink/40"
                  }`}
                >
                  {done ? "✓" : st.emoji}
                </span>
                <span
                  className={`text-sm ${
                    active ? "font-bold text-ink" : done ? "text-ink/50" : "text-ink/40"
                  }`}
                >
                  {st.label}
                </span>
                {active && (
                  <span className="ml-auto flex gap-1" aria-hidden>
                    <span className="h-2 w-2 animate-bounce rounded-full bg-blueberry [animation-delay:-0.3s]" />
                    <span className="h-2 w-2 animate-bounce rounded-full bg-blueberry [animation-delay:-0.15s]" />
                    <span className="h-2 w-2 animate-bounce rounded-full bg-blueberry" />
                  </span>
                )}
              </li>
            );
          })}
        </ol>

        <p className="mt-6 max-w-sm text-center text-xs text-ink/40">
          영상에 따라 1~2분 정도 걸릴 수 있어요. 조금만 기다려 주세요!
        </p>
      </main>
    </>
  );
}
