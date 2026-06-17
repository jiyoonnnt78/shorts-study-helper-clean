import Link from "next/link";

export default function BrandHeader({ compact = false }: { compact?: boolean }) {
  return (
    <header className="mb-6 flex items-center justify-between">
      <Link href="/" className="group flex items-center gap-2">
        <span
          className="inline-flex h-10 w-10 items-center justify-center rounded-blob bg-blueberry text-xl shadow-soft transition-transform group-hover:-rotate-6"
          aria-hidden
        >
          🎈
        </span>
        <span className="font-display text-xl leading-none text-ink">
          쇼츠 공부 도우미
        </span>
      </Link>
      {!compact && (
        <span className="hidden rounded-full bg-white/70 px-3 py-1 text-xs text-ink/50 sm:inline">
          짧은 영상을 쉽게 풀어줘요
        </span>
      )}
    </header>
  );
}
