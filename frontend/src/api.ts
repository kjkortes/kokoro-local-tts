import type {AppConfig, FishVoiceInput, FishVoicePage, FishVoiceReference, GenerationRequest, JobResponse, StatusResponse} from "./types";


export class LocalApiError extends Error {
  constructor(message: string, public readonly action?: string) {
    super(message);
    this.name = "LocalApiError";
  }
}

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(url, init);
  } catch {
    throw new LocalApiError("The local Kokoro service is not reachable. Start the app and try again.");
  }
  if (!response.ok) {
    const body = await response.json().catch(() => null) as
      | {error?: {message?: string; action?: string}}
      | null;
    throw new LocalApiError(
      body?.error?.message ?? `The local service returned ${response.status}.`,
      body?.error?.action,
    );
  }
  return response.json() as Promise<T>;
}

export const getStatus = (signal?: AbortSignal) =>
  request<StatusResponse>("/api/status", {signal});

export const getConfig = (signal?: AbortSignal) =>
  request<AppConfig>("/api/config", {signal});

export const getFishVoices = (signal?: AbortSignal) =>
  request<FishVoiceReference[]>("/api/fish-voices", {signal});

export const getFishVoicePage = (page: number, signal?: AbortSignal) =>
  request<FishVoicePage>(`/api/fish-voices/page?page=${page}&page_size=10`, {signal});

export const saveFishVoice = (voice: FishVoiceInput, identifier?: string) =>
  request<FishVoiceReference>(identifier ? `/api/fish-voices/${encodeURIComponent(identifier)}` : "/api/fish-voices", {
    method: identifier ? "PUT" : "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify(voice),
  });

export const deleteFishVoice = (identifier: string) =>
  request<FishVoiceReference>(`/api/fish-voices/${encodeURIComponent(identifier)}`, {method: "DELETE"});

export const createJob = (payload: GenerationRequest, signal?: AbortSignal) =>
  request<JobResponse>("/api/jobs", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify(payload),
    signal,
  });

export const getJob = (identifier: string, signal?: AbortSignal) =>
  request<JobResponse>(`/api/jobs/${identifier}`, {signal});

export const cancelJob = (identifier: string, signal?: AbortSignal) =>
  request<JobResponse>(`/api/jobs/${identifier}`, {method: "DELETE", signal});

