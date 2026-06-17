/** confidence가 낮을 때 결과 페이지 상단에 표시하는 안내 */
export default function LowConfidenceBanner({
  confidence,
}: {
  confidence: number;
}) {
  if (confidence >= 0.6) return null;
  return (
    <div
      role="note"
      className="flex items-start gap-2 rounded-blob bg-sunshine-soft px-4 py-3 text-sm text-[#9A6B00]"
    >
      <span aria-hidden>💡</span>
      <span>
        AI가 영상 내용을 추측한 결과라 정확하지 않을 수 있어요. 참고용으로
        봐주세요.
      </span>
    </div>
  );
}
