import Link from "next/link";

/**
 * 홈 화면 맨 아래에 조용히 들어가는 footer.
 * - 개인정보처리방침 링크
 * - 학습지원 소프트웨어 심의용 체크리스트(hwp) 다운로드
 *
 * 사용법: 기존 홈 page.tsx의 </main> 바로 위(또는 main 안 맨 아래)에
 *   <HomeFooter /> 한 줄만 추가하면 됨.
 */
export default function HomeFooter() {
  return (
    <footer className="mt-10 flex flex-col items-center gap-2 border-t border-black/5 pt-6 text-xs text-ink/40">
      <div className="flex flex-wrap items-center justify-center gap-x-4 gap-y-1">
        <Link
          href="/privacy-policy"
          className="underline-offset-2 hover:text-ink/60 hover:underline"
        >
          개인정보처리방침
        </Link>
        <span aria-hidden className="text-ink/20">
          ·
        </span>
        <a
          href="/docs/학습지원소프트웨어_체크리스트_쇼츠공부도우미.hwp"
          download
          className="underline-offset-2 hover:text-ink/60 hover:underline"
        >
          학교 심의용 체크리스트 다운로드 (.hwp)
        </a>
      </div>
      <p className="text-ink/30">
        쇼츠 공부 도우미 · 인천동암초등학교
      </p>
    </footer>
  );
}
