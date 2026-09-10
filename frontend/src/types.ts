export type Gender = "female" | "male";
export type OutputFormat = "wav" | "mp3" | "flac" | "ogg";
export type JobState =
  | "queued"
  | "loading_model"
  | "synthesizing"
  | "processing"
  | "complete"
  | "cancelled"
  | "failed";

export interface LanguageInfo {
  code: string;
  name: string;
  locale: string;
}

export interface VoiceInfo {
  id: string;
  name: string;
  language: string;
  gender: Gender;
}

export interface ExpressionValues {
  speed?: number;
  pitch?: number;
  tempo?: number;
  pause_scale?: number;
  volume?: number;
}

export interface ExpressionPreset {
  id: string;
  name: string;
  description: string;
  speed: number;
  pitch: number;
  tempo: number;
  pause_scale: number;
}

export interface AppConfig {
  languages: LanguageInfo[];
  voices: VoiceInfo[];
  presets: ExpressionPreset[];
  formats: OutputFormat[];
  defaults: {language: string; voice: string; preset: string; format: OutputFormat; comma_pause_ms: number};
  limits: Record<string, {min: number; max: number}>;
}

export interface StatusResponse {
  state: "unloaded" | "loading" | "ready" | "error";
  device: string;
  version: string;
  detail: string | null;
}

export interface GenerationRequest {
  text: string;
  segments?: string[];
  language: string;
  primary_voice: string;
  secondary_voice: string | null;
  blend_ratio: number;
  preset: "neutral" | "warm" | "calm" | "bright" | "serious" | "dramatic";
  expression: ExpressionValues | null;
  pause_ms?: number | null;
  comma_pause_ms: number;
  output_format: OutputFormat;
  normalize: boolean;
}

export interface TranscriptSegment {
  text: string;
  start: number;
  end: number;
  paragraph_end?: boolean;
}

export interface TranscriptWord {
  text: string;
  start: number;
  end: number;
}

export interface JobResponse {
  id: string;
  state: JobState;
  phase: string;
  progress: number;
  error: {code: string; message: string; action?: string} | null;
  audio_url: string | null;
  download_url: string | null;
  filename: string | null;
  duration: number | null;
  segments: TranscriptSegment[];
  words?: TranscriptWord[];
  transcript: string | null;
}
