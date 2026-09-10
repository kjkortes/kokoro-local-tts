import {useEffect, useRef, useState} from "react";

import type {Gender, LanguageInfo, VoiceInfo} from "../types";


interface VoiceControlsProps {
  languages: LanguageInfo[];
  voices: VoiceInfo[];
  language: string;
  gender: Gender | "all";
  primary: string;
  secondary: string;
  blendEnabled: boolean;
  blendRatio: number;
  onLanguage: (value: string) => void;
  onGender: (value: Gender | "all") => void;
  onPrimary: (value: string) => void;
  onSecondary: (value: string) => void;
  onBlendEnabled: (value: boolean) => void;
  onBlendRatio: (value: number) => void;
}

export function VoiceControls(props: VoiceControlsProps) {
  const audioRef = useRef<HTMLAudioElement>(null);
  const playbackAttempt = useRef(0);
  const [previewing, setPreviewing] = useState<string | null>(null);
  const [previewError, setPreviewError] = useState<string | null>(null);
  const available = props.voices.filter((voice) =>
    voice.language === props.language && (props.gender === "all" || voice.gender === props.gender)
  );
  const secondary = props.voices.filter((voice) => voice.language === props.language && voice.id !== props.primary);
  const primaryVoice = props.voices.find((voice) => voice.id === props.primary);
  const secondaryVoice = props.voices.find((voice) => voice.id === props.secondary);

  useEffect(() => {
    const previewIsVisible = previewing === props.primary
      || (props.blendEnabled && previewing === props.secondary);
    if (previewing && !previewIsVisible) {
      stopPreview();
    }
  }, [previewing, props.primary, props.secondary, props.blendEnabled]);

  useEffect(() => {
    setPreviewError(null);
  }, [props.language, props.primary, props.secondary, props.blendEnabled]);

  function togglePreview(voice: VoiceInfo) {
    const audio = audioRef.current;
    if (previewing === voice.id) {
      stopPreview(true);
      return;
    }
    audio?.pause();
    setPreviewError(null);
    if (audio) audio.src = `/voice-samples/${voice.id}.mp3`;
    const attempt = ++playbackAttempt.current;
    const started = audio?.play();
    setPreviewing(voice.id);
    void started?.catch(() => {
      if (attempt === playbackAttempt.current) failPreview(voice.id);
    });
  }

  function failPreview(identifier: string) {
    playbackAttempt.current += 1;
    audioRef.current?.pause();
    audioRef.current?.removeAttribute("src");
    const voice = props.voices.find((item) => item.id === identifier);
    setPreviewError(`${voice?.name ?? "Voice"} preview could not be played.`);
    setPreviewing(null);
  }

  function stopPreview(rewind = false) {
    playbackAttempt.current += 1;
    const audio = audioRef.current;
    audio?.pause();
    if (audio && rewind) audio.currentTime = 0;
    audio?.removeAttribute("src");
    setPreviewing(null);
  }

  function previewButton(voice: VoiceInfo | undefined) {
    if (!voice) return null;
    const active = previewing === voice.id;
    return (
      <button
        type="button"
        className={active ? "voice-preview active" : "voice-preview"}
        aria-label={active ? `Stop ${voice.name} preview` : `Preview ${voice.name} voice`}
        onClick={() => togglePreview(voice)}
      >
        <span aria-hidden="true">{active ? "■" : "▶"}</span>
        {active ? "Stop" : "Preview"}
      </button>
    );
  }

  return (
    <section className="control-section" aria-labelledby="voice-heading">
      <div className="control-title"><h2 id="voice-heading">Voice</h2><span>{available.length} available</span></div>
      <div className="field-row">
        <label className="field">Language
          <select value={props.language} onChange={(event) => props.onLanguage(event.target.value)}>
            {props.languages.map((item) => <option key={item.code} value={item.code}>{item.name}</option>)}
          </select>
        </label>
        <label className="field">Gender
          <select value={props.gender} onChange={(event) => props.onGender(event.target.value as Gender | "all")}>
            <option value="all">All voices</option>
            <option value="female">Female</option>
            <option value="male">Male</option>
          </select>
        </label>
      </div>
      <div className="field">
        <label htmlFor="primary-voice">Primary voice</label>
        <div className="voice-select-row">
          <select id="primary-voice" value={props.primary} onChange={(event) => props.onPrimary(event.target.value)}>
            {available.map((voice) => <option key={voice.id} value={voice.id}>{voice.name}</option>)}
          </select>
          {previewButton(primaryVoice)}
        </div>
      </div>
      <audio
        ref={audioRef}
        aria-label="Voice preview"
        preload="auto"
        onEnded={() => stopPreview(true)}
        onError={() => previewing && failPreview(previewing)}
      />
      {previewError && <p className="voice-preview-error" role="alert">{previewError}</p>}
      <label className="switch-row">
        <input type="checkbox" checked={props.blendEnabled} onChange={(event) => props.onBlendEnabled(event.target.checked)} />
        <span><b>Blend a second voice</b><small>Mix two voices from the same language.</small></span>
      </label>
      {props.blendEnabled && (
        <div className="blend-panel">
          <div className="field">
            <label htmlFor="secondary-voice">Second voice</label>
            <div className="voice-select-row">
              <select id="secondary-voice" value={props.secondary} onChange={(event) => props.onSecondary(event.target.value)}>
                {secondary.map((voice) => <option key={voice.id} value={voice.id}>{voice.name}</option>)}
              </select>
              {previewButton(secondaryVoice)}
            </div>
          </div>
          <label className="range-field">
            <span>Voice A <output>{Math.round((1 - props.blendRatio) * 100)} / {Math.round(props.blendRatio * 100)}</output> Voice B</span>
            <input aria-label="Voice blend" type="range" min="0.05" max="0.95" step="0.05" value={props.blendRatio} onChange={(event) => props.onBlendRatio(Number(event.target.value))} />
          </label>
        </div>
      )}
    </section>
  );
}
