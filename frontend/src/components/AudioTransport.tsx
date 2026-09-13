import {useEffect, useRef, useState} from "react";

import {useAudioTransport} from "../hooks/useAudioTransport";
import type {JobResponse} from "../types";


function formatTime(seconds: number) {
  const safe = Number.isFinite(seconds) ? Math.max(0, Math.floor(seconds)) : 0;
  return `${Math.floor(safe / 60)}:${String(safe % 60).padStart(2, "0")}`;
}

function formatTimestamp(seconds: number) {
  const safe = Number.isFinite(seconds) ? Math.max(0, seconds) : 0;
  const wholeSeconds = Math.floor(safe);
  const tenth = Math.floor(safe * 10) % 10;
  return `${Math.floor(wholeSeconds / 60)}:${String(wholeSeconds % 60).padStart(2, "0")}.${tenth}`;
}

function formatTimestampedTranscript(segments: NonNullable<JobResponse["segments"]>) {
  return segments.map((segment, index) => {
    const line = `[${formatTimestamp(segment.start)} — ${formatTimestamp(segment.end)}] ${segment.text}`;
    if (index === segments.length - 1) return line;
    return `${line}${segment.paragraph_end ? "\n\n" : "\n"}`;
  }).join("");
}

async function writeClipboard(text: string) {
  if (navigator.clipboard?.writeText) {
    try {
      await navigator.clipboard.writeText(text);
      return true;
    } catch {
      // Fall through for browsers that restrict Clipboard API access on local-network HTTP.
    }
  }
  let field: HTMLTextAreaElement | null = null;
  try {
    field = document.createElement("textarea");
    field.value = text;
    field.readOnly = true;
    field.style.position = "fixed";
    field.style.opacity = "0";
    document.body.append(field);
    field.select();
    return typeof document.execCommand === "function" && document.execCommand("copy");
  } catch {
    return false;
  } finally {
    field?.remove();
  }
}

function useWaveform(url: string | null) {
  const [envelope, setEnvelope] = useState<number[]>([]);
  useEffect(() => {
    if (!url) return;
    const controller = new AbortController();
    let context: AudioContext | null = null;
    (async () => {
      try {
        const response = await fetch(url, {signal: controller.signal});
        const buffer = await response.arrayBuffer();
        const AudioContextClass = window.AudioContext;
        if (!AudioContextClass) return;
        context = new AudioContextClass();
        const decoded = await context.decodeAudioData(buffer.slice(0));
        const samples = decoded.getChannelData(0);
        const bars = 96;
        const stride = Math.max(1, Math.floor(samples.length / bars));
        setEnvelope(Array.from({length: bars}, (_, index) => {
          let peak = 0;
          const end = Math.min(samples.length, (index + 1) * stride);
          for (let cursor = index * stride; cursor < end; cursor += 1) peak = Math.max(peak, Math.abs(samples[cursor]));
          return peak;
        }));
      } catch (error) {
        if ((error as Error).name !== "AbortError") setEnvelope([]);
      }
    })();
    return () => {
      controller.abort();
      void context?.close();
    };
  }, [url]);
  return envelope;
}

export function AudioTransport({result}: {result: JobResponse}) {
  const audioRef = useRef<HTMLAudioElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const copyAttemptRef = useRef(0);
  const copyQueueRef = useRef(Promise.resolve());
  const [copyState, setCopyState] = useState<"idle" | "copied" | "failed">("idle");
  const [copyCount, setCopyCount] = useState(0);
  const [transcriptView, setTranscriptView] = useState<"transcript" | "json">("transcript");
  const [timestampLevel, setTimestampLevel] = useState<"segments" | "words">("segments");
  const transport = useAudioTransport(audioRef, result.duration ?? 0);
  const envelope = useWaveform(result.audio_url);
  const segments = result.segments ?? [];
  const words = result.words ?? [];
  const activeTimestampLevel = timestampLevel === "words" && words.length > 0 ? "words" : "segments";
  const timestampItems = activeTimestampLevel === "words" ? words : segments;
  const timescriptJson = JSON.stringify(timestampItems.map(({start, end, text}) => ({start, end, text})), null, 2);
  const readableTranscript = formatTimestampedTranscript(timestampItems);
  const copyContent = transcriptView === "json" ? timescriptJson : readableTranscript;
  const transcriptIsJson = transcriptView === "json";
  const granularityPrefix = activeTimestampLevel === "words" ? "word-" : "";
  const transcriptDownloadName = `${(result.filename ?? "kokoro-audio").replace(/\.[^.]+$/, "") || "kokoro-audio"}-${granularityPrefix}${transcriptIsJson ? "timescript.json" : "transcript.txt"}`;
  const transcriptDownloadUrl = `data:${transcriptIsJson ? "application/json" : "text/plain"};charset=utf-8,${encodeURIComponent(copyContent)}`;
  const progress = transport.duration ? transport.currentTime / transport.duration : 0;
  const activeTimestamp = timestampItems.findIndex((item) => (
    transport.currentTime >= item.start
    && transport.currentTime < item.end
  ));

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const draw = () => {
      const bounds = canvas.getBoundingClientRect();
      const ratio = window.devicePixelRatio || 1;
      canvas.width = Math.max(1, Math.floor(bounds.width * ratio));
      canvas.height = Math.max(1, Math.floor(bounds.height * ratio));
      const context = canvas.getContext("2d");
      if (!context) return;
      context.scale(ratio, ratio);
      context.clearRect(0, 0, bounds.width, bounds.height);
      const values = envelope.length ? envelope : Array.from({length: 72}, (_, index) => .18 + Math.abs(Math.sin(index * .63)) * .45);
      const max = Math.max(...values, .01);
      const gap = 2;
      const width = Math.max(1, bounds.width / values.length - gap);
      values.forEach((value, index) => {
        const height = Math.max(3, value / max * (bounds.height - 8));
        const x = index * bounds.width / values.length;
        context.fillStyle = index / values.length <= progress ? "#3157e5" : "#c8ceca";
        context.fillRect(x, (bounds.height - height) / 2, width, height);
      });
    };
    draw();
    const observer = typeof ResizeObserver === "undefined" ? null : new ResizeObserver(draw);
    observer?.observe(canvas);
    return () => observer?.disconnect();
  }, [envelope, progress]);

  const format = result.filename?.split(".").pop()?.toUpperCase() ?? "AUDIO";
  const changeTranscriptView = (view: "transcript" | "json") => {
    if (view === transcriptView) return;
    copyAttemptRef.current += 1;
    setTranscriptView(view);
    setCopyState("idle");
    setCopyCount(0);
  };
  const changeTimestampLevel = (level: "segments" | "words") => {
    if (level === timestampLevel) return;
    copyAttemptRef.current += 1;
    setTimestampLevel(level);
    setCopyState("idle");
    setCopyCount(0);
  };
  const copyTranscript = async () => {
    if (segments.length === 0) return;
    const attempt = copyAttemptRef.current + 1;
    copyAttemptRef.current = attempt;
    const pendingCopy = copyQueueRef.current.then(() => writeClipboard(copyContent));
    copyQueueRef.current = pendingCopy.then(() => undefined, () => undefined);
    const copied = await pendingCopy;
    if (attempt !== copyAttemptRef.current) return;
    setCopyState(copied ? "copied" : "failed");
    if (copied) setCopyCount((count) => count + 1);
  };
  return (
    <>
      <section className="audio-transport" aria-label="Generated audio">
        <audio ref={audioRef} src={result.audio_url ?? undefined} preload="metadata" />
        <button className="play-button" type="button" onClick={transport.toggle} aria-label={transport.playing ? "Pause" : "Play"}>
          <span aria-hidden="true">{transport.playing ? "Ⅱ" : "▶"}</span>
        </button>
        <div className="transport-main">
          <div className="transport-copy"><b>{result.filename ?? "Generated speech"}</b><span>{formatTime(transport.currentTime)} / {formatTime(transport.duration)}</span></div>
          <div className="waveform-wrap">
            <canvas ref={canvasRef} aria-hidden="true" />
            <input
              aria-label="Seek audio"
              type="range"
              min="0"
              max={Math.max(transport.duration, .01)}
              step="0.01"
              value={Math.min(transport.currentTime, Math.max(transport.duration, .01))}
              onChange={(event) => transport.seek(Number(event.target.value))}
            />
          </div>
        </div>
        <a className="download-button" href={result.download_url ?? "#"} download={result.filename ?? true}>
          <span>Download {format}</span><span aria-hidden="true">↓</span>
        </a>
      </section>
      {segments.length > 0 && (
        <section className="transcript-panel" aria-label="Timestamped transcript">
          <div className="transcript-heading">
            <h2>Timestamped transcript</h2>
            {result.timing_source === "whisper" && (
              <span className="timing-source">Timed locally with Whisper</span>
            )}
            {words.length > 0 && (
              <div className="transcript-view-switch" aria-label="Timestamp granularity">
                <button
                  type="button"
                  aria-label="Segment timestamps"
                  aria-pressed={activeTimestampLevel === "segments"}
                  onClick={() => changeTimestampLevel("segments")}
                >
                  Segments
                </button>
                <button
                  type="button"
                  aria-label="Word timestamps"
                  aria-pressed={activeTimestampLevel === "words"}
                  onClick={() => changeTimestampLevel("words")}
                >
                  Words
                </button>
              </div>
            )}
            <div className="transcript-view-switch" aria-label="Timescript format">
              <button
                type="button"
                aria-label="Transcript view"
                aria-pressed={transcriptView === "transcript"}
                onClick={() => changeTranscriptView("transcript")}
              >
                Transcript
              </button>
              <button
                type="button"
                aria-label="JSON view"
                aria-pressed={transcriptView === "json"}
                onClick={() => changeTranscriptView("json")}
              >
                JSON
              </button>
            </div>
            <div className="transcript-actions">
              <button
                className="transcript-action copy-transcript"
                type="button"
                onClick={copyTranscript}
              >
                {transcriptIsJson ? "Copy JSON" : "Copy transcript"}
              </button>
              <a
                className="transcript-action transcript-download"
                href={transcriptDownloadUrl}
                download={transcriptDownloadName}
              >
                <span>{transcriptIsJson ? "Download JSON" : "Download transcript"}</span>
                <span aria-hidden="true">↓</span>
              </a>
            </div>
            {copyState !== "idle" && (
              <span className={`copy-status ${copyState}`} role="status">
                {copyState === "copied"
                  ? `${transcriptView === "json" ? "JSON" : "Transcript"} copied${copyCount > 1 ? ` · ${copyCount}` : ""}`
                  : `Copy failed. Select the ${transcriptView === "json" ? "JSON" : "full transcript"} below.`}
              </span>
            )}
          </div>
          {copyState === "failed" && (
            <textarea
              className="manual-transcript"
              aria-label={transcriptView === "json" ? "Full JSON timescript" : "Full transcript"}
              readOnly
              value={copyContent}
              onFocus={(event) => event.currentTarget.select()}
            />
          )}
          {transcriptView === "transcript" ? (
            <ol className="transcript-segments">
              {timestampItems.map((item, index) => (
                <li key={`${item.start}-${item.end}-${index}`}>
                  <button
                    type="button"
                    aria-label={`Seek to ${activeTimestampLevel === "words" ? "word" : "segment"} at ${formatTimestamp(item.start)}: ${item.text}`}
                    aria-current={activeTimestamp === index ? "true" : undefined}
                    onClick={() => transport.seek(item.start)}
                  >
                    <time>{formatTimestamp(item.start)} — {formatTimestamp(item.end)}</time>
                    <span>{item.text}</span>
                  </button>
                </li>
              ))}
            </ol>
          ) : (
            <pre className="timescript-json" aria-label="Timescript JSON"><code>{timescriptJson}</code></pre>
          )}
        </section>
      )}
    </>
  );
}
