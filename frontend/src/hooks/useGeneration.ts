import {useCallback, useEffect, useRef, useState} from "react";

import {cancelJob, createJob, getJob} from "../api";
import type {GenerationRequest, JobResponse} from "../types";


const ACTIVE_STATES = new Set(["queued", "loading_model", "synthesizing", "processing"]);

export function useGeneration({pollInterval = 350}: {pollInterval?: number} = {}) {
  const [job, setJob] = useState<JobResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const timer = useRef<number | null>(null);
  const controller = useRef<AbortController | null>(null);

  const stopPolling = useCallback(() => {
    if (timer.current !== null) window.clearTimeout(timer.current);
    timer.current = null;
    controller.current?.abort();
    controller.current = null;
  }, []);

  const poll = useCallback((identifier: string) => {
    const tick = async () => {
      controller.current = new AbortController();
      try {
        const next = await getJob(identifier, controller.current.signal);
        setJob(next);
        if (ACTIVE_STATES.has(next.state)) {
          timer.current = window.setTimeout(tick, pollInterval);
        } else if (next.state === "failed") {
          setError(next.error?.action ?? next.error?.message ?? "Speech generation failed.");
        }
      } catch (problem) {
        if ((problem as Error).name !== "AbortError") setError((problem as Error).message);
      }
    };
    timer.current = window.setTimeout(tick, pollInterval);
  }, [pollInterval]);

  const generate = useCallback(async (payload: GenerationRequest) => {
    stopPolling();
    setError(null);
    const nextController = new AbortController();
    controller.current = nextController;
    try {
      const created = await createJob(payload, nextController.signal);
      setJob(created);
      poll(created.id);
    } catch (problem) {
      if ((problem as Error).name !== "AbortError") setError((problem as Error).message);
    }
  }, [poll, stopPolling]);

  const cancel = useCallback(async () => {
    if (!job || !ACTIVE_STATES.has(job.state)) return;
    stopPolling();
    try {
      setJob(await cancelJob(job.id));
    } catch (problem) {
      setError((problem as Error).message);
    }
  }, [job, stopPolling]);

  useEffect(() => stopPolling, [stopPolling]);

  return {
    job,
    isRunning: job !== null && ACTIVE_STATES.has(job.state),
    error,
    generate,
    cancel,
    clearError: () => setError(null),
  };
}
