export type Gender = "female" | "male";
export type OutputFormat = "wav" | "mp3" | "flac" | "ogg";
export type TtsEngine = "kokoro" | "fish_audio";
export type TimestampEngine = "whisperx" | "whisper";
export type FishDeliveryStyle =
  | "natural"
  | "documentary"
  | "conversational"
  | "educational"
  | "energetic"
  | "mysterious"
  | "dramatic"
  | "calm"
  | "custom";
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

export interface FishVoiceInput {
  name: string;
  description: string;
  reference_id: string;
}

export interface FishVoiceReference extends FishVoiceInput {
  id: string;
}

export interface FishVoicePage {
  items: FishVoiceReference[];
  total: number;
  page: number;
  page_size: number;
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
  defaults: {
    engine: TtsEngine;
    fish_voice: string;
    timestamp_engine?: TimestampEngine;
    language: string;
    voice: string;
    preset: string;
    format: OutputFormat;
  };
  limits: Record<string, {min: number; max: number}>;
  openrouter_configured?: boolean;
}

export interface StatusResponse {
  state: "unloaded" | "loading" | "ready" | "error";
  device: string;
  version: string;
  detail: string | null;
}

interface GenerationRequestBase {
  text: string;
  segments?: string[];
}

export interface KokoroGenerationRequest extends GenerationRequestBase {
  engine?: "kokoro";
  language: string;
  primary_voice: string;
  secondary_voice: string | null;
  blend_ratio: number;
  preset: "neutral" | "warm" | "calm" | "bright" | "serious" | "dramatic";
  expression: ExpressionValues | null;
  pause_ms?: number | null;
  output_format: OutputFormat;
  normalize: boolean;
}

export interface FishGenerationRequest extends GenerationRequestBase {
  engine: "fish_audio";
  fish_voice?: string;
  fish_style: FishDeliveryStyle;
  timestamp_engine?: TimestampEngine;
  fish_custom_style?: string;
  openrouter_api_key?: string;
  output_format: "mp3";
}

export type GenerationRequest = KokoroGenerationRequest | FishGenerationRequest;

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
  timing_source?: "kokoro" | "whisper" | "whisperx" | null;
}
