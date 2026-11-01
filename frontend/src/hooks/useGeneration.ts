import {useCallback, useEffect, useRef, useState} from "react";

import {cancelJob, createJob, getJob, transcribeJob} from "../api";
import type {GenerationRequest, JobResponse, TimestampEngine} from "../types";


const ACTIVE_STATES = new Set(["queued", "loading_model", "synthesizing", "processing"]);
const TRANSCRIBING_STATES = new Set(["queued", "transcribing"]);
const needsPolling = (job: JobResponse) => ACTIVE_STATES.has(job.state) || TRANSCRIBING_STATES.has(job.transcription_state ?? "idle");

export function useGeneration({pollInterval = 350}: {pollInterval?: number} = {}) {
  const [job, setJob] = useState<JobResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const timer = useRef<number | null>(null);
  const controller = useRef<AbortController | null>(null);
  const version = useRef(0);

  const stopPolling = useCallback(() => {
    version.current += 1;
    if (timer.current !== null) window.clearTimeout(timer.current);
    timer.current = null;
    controller.current?.abort();
    controller.current = null;
  }, []);

  const poll = useCallback((identifier: string) => {
    const requestVersion = version.current;
    const tick = async () => {
      if (requestVersion !== version.current) return;
      const nextController = new AbortController();
      controller.current = nextController;
      try {
        const next = await getJob(identifier, nextController.signal);
        if (requestVersion !== version.current || nextController.signal.aborted) return;
        setJob(next);
        setError(null);
        if (needsPolling(next)) {
          timer.current = window.setTimeout(tick, pollInterval);
        } else if (next.state === "failed") {
          setError(next.error?.action ?? next.error?.message ?? "Speech generation failed.");
        }
      } catch (problem) {
        if (requestVersion === version.current && (problem as Error).name !== "AbortError") {
          setError((problem as Error).message);
          timer.current = window.setTimeout(tick, Math.max(pollInterval, 2000));
        }
      }
    };
    timer.current = window.setTimeout(tick, pollInterval);
  }, [pollInterval]);

  const generate = useCallback(async (payload: GenerationRequest) => {
    stopPolling();
    setError(null);
    const nextController = new AbortController();
    const requestVersion = version.current;
    controller.current = nextController;
    try {
      const created = await createJob(payload, nextController.signal);
      if (requestVersion !== version.current || nextController.signal.aborted) return;
      setJob(created);
      if (needsPolling(created)) poll(created.id);
    } catch (problem) {
      if (requestVersion === version.current && (problem as Error).name !== "AbortError") setError((problem as Error).message);
    }
  }, [poll, stopPolling]);

  const transcribe = useCallback(async (timestampEngine: TimestampEngine) => {
    if (!job || job.state !== "complete" || TRANSCRIBING_STATES.has(job.transcription_state ?? "idle")) return;
    stopPolling();
    setError(null);
    const nextController = new AbortController();
    controller.current = nextController;
    const requestVersion = version.current;
    try {
      const next = await transcribeJob(job.id, timestampEngine, nextController.signal);
      if (requestVersion !== version.current || nextController.signal.aborted) return;
      setJob(next);
      if (needsPolling(next)) poll(next.id);
    } catch (problem) {
      if (requestVersion === version.current && (problem as Error).name !== "AbortError") setError((problem as Error).message);
    }
  }, [job, poll, stopPolling]);

  const cancel = useCallback(async () => {
    if (!job || !ACTIVE_STATES.has(job.state)) return;
    stopPolling();
    const requestVersion = version.current;
    try {
      const next = await cancelJob(job.id);
      if (requestVersion === version.current) setJob(next);
    } catch (problem) {
      if (requestVersion === version.current) setError((problem as Error).message);
    }
  }, [job, stopPolling]);

  useEffect(() => stopPolling, [stopPolling]);

  return {
    job,
    isRunning: job !== null && ACTIVE_STATES.has(job.state),
    error,
    generate,
    transcribe,
    cancel,
    clearError: () => setError(null),
  };
}
