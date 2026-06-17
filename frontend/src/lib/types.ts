// 백엔드 app/schemas.py 와 1:1로 맞춘 타입

export type VideoStatus = "uploaded" | "analyzing" | "completed" | "failed";

export interface UploadResponse {
  id: string;
  status: VideoStatus;
}

export interface StatusResponse {
  id: string;
  status: VideoStatus;
  current_step: string | null;
  error_message: string | null;
}

export interface SourceWeights {
  ocr: number;
  stt: number;
  metadata: number;
}

export interface StructureStage {
  role: string;
  label: string;
  emoji: string;
  note: string;
  start: number;
  end: number;
}

export interface Summary {
  topic: string;
  purpose: string;
  difficulty: string; // 쉬움 / 보통 / 어려움
  category: string;
  confidence: number; // 0~1
  confidence_reason: string;
  detected_keywords: string[];
  primary_source: string; // ocr / stt / metadata / none
  source_weights: SourceWeights;
  metadata_used: boolean;
  metadata_keywords: string[];
  recommended_audience: string[];
  try_points: string[];
  caution_points: string[];
  // 숏폼 성공 구조 분석 (교육용)
  hook_type: string;
  hook_reason: string;
  hook_strength: number; // 0~100
  structure: StructureStage[];
  success_patterns: string[];
  creator_tips: string[];
}

export interface Segment {
  id: string;
  start: number;
  end: number;
  title: string;
  description: string;
  thumbnail_url: string | null;
  ocr_text: string;
  speech_text: string;
  learn_point: string;
  features: string[];
}

export interface YoutubeInfo {
  video_id: string | null;
  title: string | null;
  thumbnail_url: string | null;
  source_url: string | null;
}

export interface VideoDetail {
  id: string;
  status: VideoStatus;
  current_step: string | null;
  filename: string;
  source_type: string; // "upload" | "youtube"
  youtube: YoutubeInfo | null;
  duration: number | null;
  width: number | null;
  height: number | null;
  fps: number | null;
  aspect_ratio: string | null;
  error_message: string | null;
  summary: Summary | null;
  segments: Segment[];
}
