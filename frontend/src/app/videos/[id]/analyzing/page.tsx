"use client";

import { useEffect, useRef, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import BrandHeader from "@/components/BrandHeader";
import { getStatus } from "@/lib/api";

// 백엔드 analyzer.py 의 STEP_* 순서. current_step 문자열과 매칭해 진행도를 보여준다.
const STEPS = [
  "영상 정보를 확인하는 중",
  "화면을 나누는 중",
  "캡쳐를 만드는 중",
  "글자를 읽는 중",
  "소리를 듣는 중",
  "쉬운 설명을 만드는 중",
];

const STEP_EMOJI = ["🎬", "✂️", "📸", "🔤", "👂", "📒"];

export default function AnalyzingPage() {
  const router = useRouter();
  const params = useParams<{ id: string }>();
  const id = params.id;

  const [step, setStep] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    let alive = true;

    async function poll() {
      try {
        const s = await getStatus(id);
        if (!alive) return;

        if (s.status === "completed") {
          router.replace(`/videos/${id}`);
          return;
        }
        if (s.status === "failed") {
          setError(
            s.error_message ??
              "영상을 분석하는 중에 문제가 생겼어요. 다른 영상으로 다시 해볼까요?"
          );
          return;
        }
        setStep(s.current_step);
        timer.current = setTimeout(poll, 1500);
      } catch {
        if (!alive) return;
        // 일시적 네트워크 문제면 계속 시도
        timer.current = setTimeout(poll, 2500);
      }
    }
    poll();

    return () => {
      alive = false;
      if (timer.current) clearTimeout(timer.current);
    };
  }, [id, router]);

  const activeIndex = step ? STEPS.indexOf(step) : -1;

  if (error) {
    return (
      <>
        <BrandHeader compact />
        <main className="flex flex-1 flex-col items-center justify-center text-center">
          <div className="text-6xl" aria-hidden>
            😢
          </div>
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
      <main className="flex flex-1 flex-col items-center justify-center">
        <div className="text-6xl animate-bounce-soft" aria-hidden>
          {activeIndex >= 0 ? STEP_EMOJI[activeIndex] : "🔎"}
        </div>
        <h1 className="mt-5 text-center font-display text-2xl text-ink">
          영상을 살펴보고 있어요
        </h1>
        <p className="mt-2 h-6 text-center text-ink/60">
          {step ?? "준비하는 중…"}
        </p>

        {/* 단계 진행 표시 */}
        <ol className="mt-8 w-full max-w-sm space-y-2">
          {STEPS.map((label, i) => {
            const done = activeIndex > i;
            const active = activeIndex === i;
            return (
              <li
                key={label}
                className={`flex items-center gap-3 rounded-blob px-4 py-3 transition-all ${
                  active
                    ? "bg-white shadow-soft"
                    : done
                    ? "bg-white/50"
                    : "bg-white/30"
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
                  {done ? "✓" : i + 1}
                </span>
                <span
                  className={`text-sm ${
                    active
                      ? "font-bold text-ink"
                      : done
                      ? "text-ink/50"
                      : "text-ink/40"
                  }`}
                >
                  {label}
                </span>
                {active && (
                  <span className="ml-auto text-lg animate-wiggle" aria-hidden>
                    {STEP_EMOJI[i]}
                  </span>
                )}
              </li>
            );
          })}
        </ol>

        <p className="mt-6 text-xs text-ink/40">
          조금만 기다려 주세요. 보통 몇 초에서 1분쯤 걸려요.
        </p>
      </main>
    </>
  );
}
