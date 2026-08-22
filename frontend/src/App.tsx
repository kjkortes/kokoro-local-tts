import {useEffect, useMemo, useState} from "react";

import {getConfig, getStatus} from "./api";
import {AppHeader} from "./components/AppHeader";
import {AudioTransport} from "./components/AudioTransport";
import {ErrorNotice} from "./components/ErrorNotice";
import {ExpressionControls} from "./components/ExpressionControls";
import {GenerateBar} from "./components/GenerateBar";
import {OutputControls} from "./components/OutputControls";
import {ScriptEditor} from "./components/ScriptEditor";
import {VoiceControls} from "./components/VoiceControls";
import {useGeneration} from "./hooks/useGeneration";
import type {AppConfig, ExpressionPreset, ExpressionValues, Gender, OutputFormat, StatusResponse} from "./types";


type PresetId = "neutral" | "warm" | "calm" | "bright" | "serious" | "dramatic";
const FALLBACK_VALUES = {speed: 1, pitch: 0, tempo: 1, pause_scale: 1, volume: 1};

export function App() {
  const [config, setConfig] = useState<AppConfig | null>(null);
  const [status, setStatus] = useState<StatusResponse | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [text, setText] = useState("");
  const [language, setLanguage] = useState("a");
  const [gender, setGender] = useState<Gender | "all">("all");
  const [primary, setPrimary] = useState("af_heart");
  const [blendEnabled, setBlendEnabled] = useState(false);
  const [secondary, setSecondary] = useState("af_bella");
  const [blendRatio, setBlendRatio] = useState(.35);
  const [preset, setPreset] = useState<PresetId>("neutral");
  const [expression, setExpression] = useState<Required<ExpressionValues>>(FALLBACK_VALUES);
  const [custom, setCustom] = useState(false);
  const [format, setFormat] = useState<OutputFormat>("wav");
  const [normalize, setNormalize] = useState(true);
  const generation = useGeneration();

  useEffect(() => {
    const controller = new AbortController();
    Promise.all([getConfig(controller.signal), getStatus(controller.signal)])
      .then(([nextConfig, nextStatus]) => {
        setConfig(nextConfig);
        setStatus(nextStatus);
        setLanguage(nextConfig.defaults.language);
        setPrimary(nextConfig.defaults.voice);
        setFormat(nextConfig.defaults.format);
        const initial = nextConfig.presets.find((item) => item.id === nextConfig.defaults.preset) ?? nextConfig.presets[0];
        if (initial) applyPreset(initial);
      })
      .catch((error: Error) => {
        if (error.name !== "AbortError") setLoadError(error.message);
      });
    return () => controller.abort();
  }, []);

  const languageVoices = useMemo(
    () => config?.voices.filter((voice) => voice.language === language) ?? [],
    [config, language],
  );
  const filteredVoices = useMemo(
    () => languageVoices.filter((voice) => gender === "all" || voice.gender === gender),
    [languageVoices, gender],
  );

  function applyPreset(item: ExpressionPreset) {
    setPreset(item.id as PresetId);
    setExpression({speed: item.speed, pitch: item.pitch, tempo: item.tempo, pause_scale: item.pause_scale, volume: 1});
    setCustom(false);
  }

  function chooseLanguage(value: string) {
    setLanguage(value);
    setGender("all");
    const voices = config?.voices.filter((voice) => voice.language === value) ?? [];
    setPrimary(voices[0]?.id ?? "");
    setSecondary(voices[1]?.id ?? "");
    if (voices.length < 2) setBlendEnabled(false);
  }

  function chooseGender(value: Gender | "all") {
    setGender(value);
    const voices = languageVoices.filter((voice) => value === "all" || voice.gender === value);
    if (!voices.some((voice) => voice.id === primary)) setPrimary(voices[0]?.id ?? "");
  }

  function choosePrimary(value: string) {
    setPrimary(value);
    if (secondary === value) setSecondary(languageVoices.find((voice) => voice.id !== value)?.id ?? "");
  }

  function updateExpression(name: keyof ExpressionValues, value: number) {
    setExpression((current) => ({...current, [name]: value}));
    setCustom(true);
  }

  if (!config) {
    return (
      <div className="app-shell loading-shell">
        <AppHeader status={status} />
        <main><div className="loading-mark" /><p>{loadError ?? "Preparing the local studio…"}</p></main>
      </div>
    );
  }

  return (
    <div className="app-shell">
      <AppHeader status={status} />
      <main id="workspace">
        {(loadError || generation.error) && <ErrorNotice message={loadError ?? generation.error!} onClose={() => {setLoadError(null); generation.clearError();}} />}
        <div className="workspace-grid">
          <ScriptEditor text={text} onChange={setText} />
          <aside className="control-panel">
            <VoiceControls
              languages={config.languages} voices={config.voices} language={language} gender={gender}
              primary={primary} secondary={secondary} blendEnabled={blendEnabled} blendRatio={blendRatio}
              onLanguage={chooseLanguage} onGender={chooseGender} onPrimary={choosePrimary} onSecondary={setSecondary}
              onBlendEnabled={setBlendEnabled} onBlendRatio={setBlendRatio}
            />
            <ExpressionControls presets={config.presets} selected={preset} values={expression} custom={custom} onPreset={applyPreset} onValue={updateExpression} />
            <OutputControls formats={config.formats} format={format} normalize={normalize} onFormat={setFormat} onNormalize={setNormalize} />
          </aside>
        </div>
        <GenerateBar
          disabled={!text.trim() || !primary}
          running={generation.isRunning}
          phase={generation.job?.phase}
          progress={generation.job?.progress}
          onCancel={generation.cancel}
          onGenerate={() => generation.generate({
            text, language, primary_voice: primary,
            secondary_voice: blendEnabled ? secondary : null,
            blend_ratio: blendRatio, preset, expression, output_format: format, normalize,
          })}
        />
        {generation.job?.state === "complete" ? (
          <AudioTransport result={generation.job} />
        ) : (
          <div className="transport-placeholder" aria-hidden="true"><span>Audio transport appears here after generation</span><i /></div>
        )}
      </main>
      <footer><span>Kokoro 82M</span><span>Private by default · Apache 2.0</span></footer>
    </div>
  );
}
