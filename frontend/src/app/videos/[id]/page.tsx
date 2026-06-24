"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import BrandHeader from "@/components/BrandHeader";
import HookCard from "@/components/HookCard";
import StructureCard from "@/components/StructureCard";
import StructureDetailCard from "@/components/StructureDetailCard";
import StageSamplesCard from "@/components/StageSamplesCard";
import { InsightListCard } from "@/components/InsightListCard";
import SummaryCard from "@/components/SummaryCard";
import SceneCard from "@/components/SceneCard";
import LowConfidenceBanner from "@/components/LowConfidenceBanner";
import YoutubeInfoCard from "@/components/YoutubeInfoCard";
import { getVideo, deleteVideo } from "@/lib/api";
import type { VideoDetail } from "@/lib/types";

export default function ResultPage() {
  const router = useRouter();
  const params = useParams<{ id: string }>();
  const id = params.id;

  const [data, setData] = useState<VideoDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [deleting, setDeleting] = useState(false);

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const detail = await getVideo(id);
        if (!alive) return;
        if (detail.status === "analyzing" || detail.status === "uploaded") {
          router.replace(`/videos/${id}/analyzing`);
          return;
        }
        setData(detail);
      } catch (e) {
        if (!alive) return;
        setError(e instanceof Error ? e.message : "결과를 불러오지 못했어요.");
      }
    })();
    return () => {
      alive = false;
    };
  }, [id, router]);

  async function handleDelete() {
    if (deleting) return;
    const ok = window.confirm("이 분석 결과를 지울까요? 되돌릴 수 없어요.");
    if (!ok) return;
    setDeleting(true);
    try {
      await deleteVideo(id);
      router.push("/");
    } catch {
      setDeleting(false);
      window.alert("지우지 못했어요. 잠시 후 다시 해주세요.");
    }
  }

  if (error) {
    return (
      <>
        <BrandHeader compact />
        <main className="flex flex-1 flex-col items-center justify-center text-center">
          <div className="text-6xl" aria-hidden>
            🤕
          </div>
          <h1 className="mt-4 font-display text-2xl text-ink">
            결과를 불러오지 못했어요
          </h1>
          <p className="mt-2 text-ink/60">{error}</p>
          <button
            onClick={() => router.push("/")}
            className="mt-6 rounded-full bg-blueberry px-6 py-3 font-display text-lg text-white shadow-soft transition-transform hover:scale-105"
          >
            처음으로
          </button>
        </main>
      </>
    );
  }

  if (!data) {
    return (
      <>
        <BrandHeader compact />
        <main className="flex flex-1 flex-col items-center justify-center">
          <div className="text-5xl animate-bounce-soft" aria-hidden>
            📒
          </div>
          <p className="mt-4 font-display text-lg text-ink/60">
            결과를 펼치는 중…
          </p>
        </main>
      </>
    );
  }

  if (data.status === "failed" || !data.summary) {
    return (
      <>
        <BrandHeader compact />
        <main className="flex flex-1 flex-col items-center justify-center text-center">
          <div className="text-6xl" aria-hidden>
            😢
          </div>
          <h1 className="mt-4 font-display text-2xl text-ink">
            분석을 마치지 못했어요
          </h1>
          <p className="mt-2 max-w-sm text-ink/60">
            {data.error_message ?? "다른 영상으로 다시 시도해 보면 좋겠어요."}
          </p>
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

  const s = data.summary;

  return (
    <>
      <BrandHeader compact />
      <main className="flex flex-1 flex-col gap-5">
        {/* YouTube 링크 분석이면 영상 정보 먼저 */}
        {data.source_type === "youtube" && data.youtube && (
          <YoutubeInfoCard youtube={data.youtube} summary={s} />
        )}

        {/* 페이지 제목: 성공 구조 분석기 */}
        <div className="text-center">
          <h1 className="font-display text-2xl text-ink sm:text-3xl">
            이 쇼츠는 왜 관심을 끌까요?
          </h1>
          <p className="mt-1 text-sm text-ink/50">
            인기 숏폼의 성공 구조를 함께 살펴봐요
          </p>
        </div>

        <LowConfidenceBanner confidence={s.confidence} />

        {/* 1. 훅 분석 (최상단) */}
        <HookCard summary={s} />

        {/* 2. 영상 구조 (타임라인) */}
        <StructureCard structure={s.structure} />

        {/* 2-2. 구성 분석 (오프닝/전개/클라이맥스/마무리 content+purpose) */}
        {s.structure_detail && (
          <StructureDetailCard detail={s.structure_detail} />
        )}

        {/* 2-3. 핵심 장면 분석 (스크린샷+OCR+팁) */}
        {s.stage_samples && s.stage_samples.length > 0 && (
          <StageSamplesCard samples={s.stage_samples} />
        )}

        {/* 배포 확인용 표식 (이 줄이 보이면 최신 프론트가 배포된 것) */}
        <p className="text-center text-[10px] text-ink/20">structure-v3</p>

        {/* 3. 몰입 요소 */}
        {s.engagement_factors && s.engagement_factors.length > 0 && (
          <InsightListCard
            emoji="🧲"
            title="몰입 요소"
            subtitle="끝까지 보게 만드는 힘"
            items={s.engagement_factors}
            accent="mint"
          />
        )}

        {/* 4. 성공 법칙 */}
        <InsightListCard
          emoji="⭐"
          title="성공 법칙"
          subtitle="잘한 점이에요"
          items={s.success_patterns}
          accent="sunshine"
        />

        {/* 5. 제작 팁 */}
        <InsightListCard
          emoji="📝"
          title="제작 팁"
          subtitle="내 영상에 써먹어요"
          items={s.creator_tips}
          accent="mint"
        />

        {/* 5. 영상 요약 (보조) */}
        <SummaryCard summary={s} />

        {/* 6. 장면별 보기 */}
        {data.segments.length > 0 && (
          <section>
            <div className="mb-3 flex items-center gap-2">
              <span className="text-2xl" aria-hidden>
                🎞️
              </span>
              <h2 className="font-display text-xl text-ink">장면별로 보기</h2>
              <span className="ml-auto text-sm text-ink/40">
                {data.segments.length}개 장면
              </span>
            </div>
            <div className="flex flex-col gap-3">
              {data.segments.map((seg, i) => (
                <SceneCard key={seg.id} segment={seg} index={i} />
              ))}
            </div>
          </section>
        )}

        {/* 개발자용 분석 패널은 숨김 (OCR/STT 미사용으로 불필요) */}

        {/* 액션 */}
        <div className="no-print mt-2 flex flex-wrap items-center justify-center gap-3">
          <button
            onClick={() => window.print()}
            className="rounded-full bg-mint px-6 py-3 font-display text-lg text-white shadow-soft transition-transform hover:scale-105"
          >
            🖨️ PDF로 저장 / 공유
          </button>
          <button
            onClick={() => router.push("/")}
            className="rounded-full bg-blueberry px-6 py-3 font-display text-lg text-white shadow-soft transition-transform hover:scale-105"
          >
            새 영상 올리기
          </button>
          <button
            onClick={handleDelete}
            disabled={deleting}
            className="rounded-full bg-white px-6 py-3 font-display text-lg text-ink/60 ring-1 ring-black/10 transition-colors hover:bg-coral-soft hover:text-coral disabled:opacity-60"
          >
            {deleting ? "지우는 중…" : "이 결과 지우기"}
          </button>
        </div>
      </main>
    </>
  );
}
