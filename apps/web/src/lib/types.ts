export type Axis = "quality" | "safety" | "moderation";

export type ReviewLabel = "unreviewed" | "correct" | "false_positive" | "false_negative";

export interface Contribution {
  feature: string;
  weight: number;
  snippet: string;
  offset: number;
  length: number;
}

export interface AxisScore {
  axis: Axis;
  score: number;
  label: string;
  flagged: boolean;
  reasons: string[];
  contributions: Contribution[];
}

export interface CheckRecord {
  id: string;
  prompt_version: string;
  output_text: string;
  flagged: boolean;
  axes: AxisScore[];
  review_label: ReviewLabel;
  created_at: string;
  reviewed_at: string | null;
}

export interface ScoreResponse {
  check_id: string;
  flagged: boolean;
  axes: AxisScore[];
  latency_ms: number;
}

export interface PromptVersionStats {
  prompt_version: string;
  total: number;
  quality_pass_rate: number;
  safety_pass_rate: number;
  moderation_pass_rate: number;
}
