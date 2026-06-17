import type {
  UploadResponse,
  StatusResponse,
  VideoDetail,
} from "./types";

// 백엔드 주소. 배포 시 NEXT_PUBLIC_API_BASE 로 교체.
export const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE?.replace(/\/$/, "") ||
  "http://localhost:8000";

/** thumbnail_url 등 백엔드가 준 상대 경로(/media/...)를 절대 URL로 바꾼다. */
export function mediaUrl(path: string | null | undefined): string | null {
  if (!path) return null;
  if (path.startsWith("http://") || path.startsWith("https://")) return path;
  return `${API_BASE}${path.startsWith("/") ? "" : "/"}${path}`;
}

async function readError(res: Response): Promise<string> {
  try {
    const data = await res.json();
    if (typeof data?.detail === "string") return data.detail;
    if (typeof data?.message === "string") return data.message;
  } catch {
    /* ignore */
  }
  return "문제가 생겼어요. 잠시 후 다시 해볼까요?";
}

export async function uploadVideo(file: File): Promise<UploadResponse> {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${API_BASE}/api/videos`, {
    method: "POST",
    body: form,
  });
  if (!res.ok) throw new Error(await readError(res));
  return res.json();
}

export async function analyzeYoutube(url: string): Promise<UploadResponse> {
  const res = await fetch(`${API_BASE}/api/youtube/analyze`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ url }),
  });
  if (!res.ok) throw new Error(await readError(res));
  return res.json();
}

export async function getStatus(id: string): Promise<StatusResponse> {
  const res = await fetch(`${API_BASE}/api/videos/${id}/status`, {
    cache: "no-store",
  });
  if (!res.ok) throw new Error(await readError(res));
  return res.json();
}

export async function getVideo(id: string): Promise<VideoDetail> {
  const res = await fetch(`${API_BASE}/api/videos/${id}`, {
    cache: "no-store",
  });
  if (!res.ok) throw new Error(await readError(res));
  return res.json();
}

export async function deleteVideo(id: string): Promise<void> {
  const res = await fetch(`${API_BASE}/api/videos/${id}`, {
    method: "DELETE",
  });
  if (!res.ok) throw new Error(await readError(res));
}
