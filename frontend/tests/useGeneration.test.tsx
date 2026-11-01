import {act, renderHook, waitFor} from "@testing-library/react";

import {useGeneration} from "../src/hooks/useGeneration";
import type {GenerationRequest, JobResponse} from "../src/types";


const request: GenerationRequest = {
  text: "Hello from Kokoro.",
  language: "a",
  primary_voice: "af_heart",
  secondary_voice: null,
  blend_ratio: 0.35,
  preset: "neutral",
  expression: null,
  output_format: "wav",
  normalize: true,
};

function response(state: JobResponse["state"]): JobResponse {
  return {
    id: "job-1",
    state,
    phase: state === "complete" ? "Audio ready" : "Speaking",
    progress: state === "complete" ? 1 : 0.4,
    error: null,
    audio_url: state === "complete" ? "/api/jobs/job-1/audio" : null,
    download_url: state === "complete" ? "/api/jobs/job-1/download" : null,
    filename: state === "complete" ? "hello.wav" : null,
    duration: state === "complete" ? 1.2 : null,
    segments: [],
    transcript: state === "complete" ? "Hello from Kokoro." : null,
  };
}

it("polls a submitted job until its audio is ready", async () => {
  const values = [response("queued"), response("synthesizing"), response("complete")];
  vi.stubGlobal("fetch", vi.fn(async (_url: string, init?: RequestInit) => {
    const value = init?.method === "POST" ? values[0] : values.shift() ?? response("complete");
    return new Response(JSON.stringify(value), {status: init?.method === "POST" ? 202 : 200});
  }));

  const {result} = renderHook(() => useGeneration({pollInterval: 5}));
  await act(async () => result.current.generate(request));
  await waitFor(() => expect(result.current.job?.state).toBe("complete"));
  expect(result.current.job?.audio_url).toBe("/api/jobs/job-1/audio");
  expect(result.current.isRunning).toBe(false);
});

it("normalizes an unreachable local service error", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => { throw new TypeError("network"); }));
  const {result} = renderHook(() => useGeneration({pollInterval: 5}));
  await act(async () => result.current.generate(request));
  expect(result.current.error).toBe("The local Kokoro service is not reachable. Start the app and try again.");
});

it("polls manual transcription without submitting a second speech generation", async () => {
  const calls: string[] = [];
  const audioOnly = {...response("complete"), transcription_state: "idle"};
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    if (init?.method === "POST") calls.push(url);
    if (url.endsWith("/transcript")) {
      expect(JSON.parse(String(init?.body))).toEqual({timestamp_engine: "whisper"});
      return Response.json({...audioOnly, transcription_state: "queued"}, {status: 202});
    }
    if (init?.method === "POST") return Response.json(audioOnly, {status: 202});
    return Response.json({...audioOnly, transcription_state: "complete", segments: [{text: "Hello.", start: 0, end: 1}], timing_source: "whisper"});
  }));
  const {result} = renderHook(() => useGeneration({pollInterval: 5}));
  await act(async () => result.current.generate(request));
  await act(async () => result.current.transcribe("whisper"));
  await waitFor(() => expect(result.current.job?.transcription_state).toBe("complete"));
  expect(result.current.job?.audio_url).toBe("/api/jobs/job-1/audio");
  expect(result.current.isRunning).toBe(false);
  expect(calls).toEqual(["/api/jobs", "/api/jobs/job-1/transcript"]);
});

it("ignores a late transcript response after newer audio has been generated", async () => {
  let resolveTranscript!: (value: Response) => void;
  let generations = 0;
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    if (url.endsWith("/transcript")) return new Promise<Response>((resolve) => {resolveTranscript = resolve;});
    if (init?.method === "POST") generations += 1;
    return Response.json({...response("complete"), id: `job-${generations}`, transcription_state: "idle"});
  }));
  const {result} = renderHook(() => useGeneration({pollInterval: 5}));
  await act(async () => result.current.generate(request));
  let pending!: Promise<void>;
  act(() => {pending = result.current.transcribe("whisperx");});
  await act(async () => result.current.generate(request));
  await act(async () => {
    resolveTranscript(Response.json({...response("complete"), transcription_state: "queued"}));
    await pending;
  });
  expect(result.current.job?.id).toBe("job-2");
});

it("recovers from a failed transcript status request and clears the temporary error", async () => {
  let polls = 0;
  const audioOnly = {...response("complete"), transcription_state: "idle"};
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    if (url.endsWith("/transcript")) return Response.json({...audioOnly, transcription_state: "queued"}, {status: 202});
    if (init?.method === "POST") return Response.json(audioOnly, {status: 202});
    if (++polls === 1) throw new TypeError("Temporary network failure");
    return Response.json({...audioOnly, transcription_state: "complete", segments: [{text: "Hello.", start: 0, end: 1}]});
  }));
  const {result} = renderHook(() => useGeneration({pollInterval: 5}));
  await act(async () => result.current.generate(request));
  await act(async () => result.current.transcribe("whisperx"));
  await waitFor(() => expect(result.current.error).toContain("not reachable"));
  await waitFor(() => expect(result.current.job?.transcription_state).toBe("complete"), {timeout: 3500});
  expect(result.current.error).toBeNull();
  expect(result.current.job?.segments).toHaveLength(1);
  expect(polls).toBe(2);
});
