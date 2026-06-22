// 諛깆뿏??app/schemas.py ? 1:1濡?留욎텣 ???
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
  difficulty: string; // ?ъ? / 蹂댄넻 / ?대젮?
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
  // ?륂뤌 ?깃났 援ъ“ 遺꾩꽍 (援먯쑁??
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

export interface StructurePart {
  content?: string;
  purpose?: string;
  title?: string;
  description?: string;
}

export interface StructureDetail {
  opening?: StructurePart;
  development?: StructurePart;
  climax?: StructurePart;
  ending?: StructurePart;
}


export interface Summary {
  analysis_summary?: string;
}

export interface StructurePart {
  content?: string;
  purpose?: string;
  title?: string;
  description?: string;
}

export interface StructureDetail {
  opening?: StructurePart;
  development?: StructurePart;
  climax?: StructurePart;
  ending?: StructurePart;
}

declare module "@/lib/types" {
  interface Summary {
    structure_detail?: StructureDetail;
  }
}

declare module "@/lib/types" {
  interface Summary {
    engagement_factors?: string[];
  }
}
