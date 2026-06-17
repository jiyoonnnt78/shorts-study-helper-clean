"use client";

import { useState } from "react";

/** 기본 접힘, 버튼 클릭 시 펼쳐지는 영역 */
export default function Collapsible({
  buttonLabel,
  openLabel,
  children,
  tone = "neutral",
}: {
  buttonLabel: string;
  openLabel?: string;
  children: React.ReactNode;
  tone?: "neutral" | "dev";
}) {
  const [open, setOpen] = useState(false);
  const toneCls =
    tone === "dev"
      ? "bg-black/5 text-ink/55 hover:bg-black/10"
      : "bg-blueberry-soft text-blueberry hover:bg-blueberry/15";

  return (
    <div>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className={`flex w-full items-center justify-between rounded-2xl px-4 py-2.5 text-sm font-bold transition-colors ${toneCls}`}
      >
        <span>{open ? openLabel ?? buttonLabel : buttonLabel}</span>
        <span
          className={`transition-transform ${open ? "rotate-180" : ""}`}
          aria-hidden
        >
          ▾
        </span>
      </button>
      {open && <div className="mt-3 animate-pop-in">{children}</div>}
    </div>
  );
}
