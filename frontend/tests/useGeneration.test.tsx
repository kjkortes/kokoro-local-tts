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
  comma_pause_ms: 100,
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
