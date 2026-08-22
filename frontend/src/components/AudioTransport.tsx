import {useEffect, useRef, useState} from "react";

import {useAudioTransport} from "../hooks/useAudioTransport";
import type {JobResponse} from "../types";


function formatTime(seconds: number) {
  const safe = Number.isFinite(seconds) ? Math.max(0, Math.floor(seconds)) : 0;
  return `${Math.floor(safe / 60)}:${String(safe % 60).padStart(2, "0")}`;
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
  const transport = useAudioTransport(audioRef, result.duration ?? 0);
  const envelope = useWaveform(result.audio_url);
  const progress = transport.duration ? transport.currentTime / transport.duration : 0;

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
  return (
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
  );
}

