import {useEffect, useMemo, useState} from "react";

import {getConfig, getStatus} from "./api";
import {AppHeader} from "./components/AppHeader";
import {AudioTransport} from "./components/AudioTransport";
import {ErrorNotice} from "./components/ErrorNotice";
import {EngineControls} from "./components/EngineControls";
import {ExpressionControls} from "./components/ExpressionControls";
import {FishAudioControls} from "./components/FishAudioControls";
import {FishVoiceManager} from "./components/FishVoiceManager";
import {GenerateBar} from "./components/GenerateBar";
import {OutputControls} from "./components/OutputControls";
import {ScriptEditor} from "./components/ScriptEditor";
import {VoiceControls} from "./components/VoiceControls";
import {useGeneration} from "./hooks/useGeneration";
import type {AppConfig, ExpressionPreset, ExpressionValues, FishDeliveryStyle, FishVoiceReference, Gender, OutputFormat, StatusResponse, TimestampEngine, TtsEngine} from "./types";


type PresetId = "neutral" | "warm" | "calm" | "bright" | "serious" | "dramatic";
const FALLBACK_VALUES = {speed: 1, pitch: 0, tempo: 1, pause_scale: 1, volume: 1};

export function App() {
  const [page, setPage] = useState<"studio" | "voices">(() => window.location.hash === "#voices" ? "voices" : "studio");
  const [libraryRevision, setLibraryRevision] = useState(0);
  const [config, setConfig] = useState<AppConfig | null>(null);
  const [status, setStatus] = useState<StatusResponse | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [text, setText] = useState("");
  const [engine, setEngine] = useState<TtsEngine>("fish_audio");
  const [storyboardSegments, setStoryboardSegments] = useState<string[] | null>(null);
  const [language, setLanguage] = useState("a");
  const [gender, setGender] = useState<Gender | "all">("all");
  const [primary, setPrimary] = useState("af_heart");
  const [blendEnabled, setBlendEnabled] = useState(false);
  const [secondary, setSecondary] = useState("af_bella");
  const [blendRatio, setBlendRatio] = useState(.35);
  const [preset, setPreset] = useState<PresetId>("neutral");
  const [expression, setExpression] = useState<Required<ExpressionValues>>(FALLBACK_VALUES);
  const [pauseMs, setPauseMs] = useState<number | null>(null);
  const [custom, setCustom] = useState(false);
  const [format, setFormat] = useState<OutputFormat>("wav");
  const [normalize, setNormalize] = useState(true);
  const [fishVoice, setFishVoice] = useState("b0204e37cbc94a16954c78697b844af2");
  const [fishStyle, setFishStyle] = useState<FishDeliveryStyle>("natural");
  const [timestampEngine, setTimestampEngine] = useState<TimestampEngine>("whisperx");
  const [fishCustomStyle, setFishCustomStyle] = useState("");
  const [openRouterApiKey, setOpenRouterApiKey] = useState("");
  const generation = useGeneration();
  const speechText = storyboardSegments === null ? text : storyboardSegments.join("\n\n");

  useEffect(() => {
    const navigate = () => setPage(window.location.hash === "#voices" ? "voices" : "studio");
    window.addEventListener("hashchange", navigate);
    return () => window.removeEventListener("hashchange", navigate);
  }, []);

  function libraryChanged(saved: FishVoiceReference | null, previous?: FishVoiceReference) {
    if (previous) setFishVoice((current) => current === previous.reference_id ? saved?.reference_id ?? "" : current);
    setLibraryRevision((value) => value + 1);
  }

  useEffect(() => {
    const controller = new AbortController();
    Promise.all([getConfig(controller.signal), getStatus(controller.signal)])
      .then(([nextConfig, nextStatus]) => {
        setConfig(nextConfig);
        setStatus(nextStatus);
        setEngine(nextConfig.defaults.engine);
        setFishVoice(nextConfig.defaults.fish_voice);
        setTimestampEngine(nextConfig.defaults.timestamp_engine ?? "whisperx");
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
    setPauseMs(null);
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

  function updatePauseMs(value: number | null) {
    setPauseMs(value);
    setCustom(true);
  }

  function generate() {
    if (engine === "fish_audio") {
      generation.generate({
        engine: "fish_audio",
        text: speechText,
        segments: storyboardSegments ?? undefined,
        fish_voice: fishVoice.trim() || undefined,
        fish_style: fishStyle,
        timestamp_engine: timestampEngine,
        fish_custom_style: fishStyle === "custom" ? fishCustomStyle.trim() : undefined,
        openrouter_api_key: openRouterApiKey.trim() || undefined,
        output_format: "mp3",
      });
      return;
    }
    generation.generate({
      engine: "kokoro",
      text: speechText,
      segments: storyboardSegments ?? undefined,
      language,
      primary_voice: primary,
      secondary_voice: blendEnabled ? secondary : null,
      blend_ratio: blendRatio,
      preset,
      expression,
      pause_ms: pauseMs,
      output_format: format,
      normalize,
    });
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
      <AppHeader status={status} page={page} />
      {page === "voices" && <FishVoiceManager onChanged={libraryChanged} onUse={(voice) => {
        setFishVoice(voice.reference_id);
        setLibraryRevision((value) => value + 1);
        setEngine("fish_audio");
        window.location.hash = "workspace";
      }} />}
      <main id="workspace" hidden={page === "voices"}>
        {(loadError || generation.error) && <ErrorNotice message={loadError ?? generation.error!} onClose={() => {setLoadError(null); generation.clearError();}} />}
        <div className="workspace-grid">
          <ScriptEditor
            text={text}
            onChange={setText}
            storyboardSegments={storyboardSegments}
            onStoryboardSegments={setStoryboardSegments}
            privacyLabel={engine === "kokoro" ? "Stays on this machine" : "Sent to Fish Audio via OpenRouter"}
          />
          <aside className="control-panel">
            <EngineControls engine={engine} onEngine={setEngine} />
            {engine === "kokoro" ? (
              <>
                <VoiceControls
                  languages={config.languages} voices={config.voices} language={language} gender={gender}
                  primary={primary} secondary={secondary} blendEnabled={blendEnabled} blendRatio={blendRatio}
                  onLanguage={chooseLanguage} onGender={chooseGender} onPrimary={choosePrimary} onSecondary={setSecondary}
                  onBlendEnabled={setBlendEnabled} onBlendRatio={setBlendRatio}
                />
                <ExpressionControls
                  presets={config.presets} selected={preset} values={expression} pauseMs={pauseMs}
                  custom={custom}
                  onPreset={applyPreset} onValue={updateExpression} onPauseMs={updatePauseMs}
                />
                <OutputControls formats={config.formats} format={format} normalize={normalize} onFormat={setFormat} onNormalize={setNormalize} />
              </>
            ) : (
              <FishAudioControls
                voice={fishVoice}
                style={fishStyle}
                timestampEngine={timestampEngine}
                onTimestampEngine={setTimestampEngine}
                customStyle={fishCustomStyle}
                apiKey={openRouterApiKey}
                environmentKeyConfigured={Boolean(config.openrouter_configured)}
                onVoice={setFishVoice}
                onStyle={setFishStyle}
                onCustomStyle={setFishCustomStyle}
                onApiKey={setOpenRouterApiKey}
                libraryRevision={libraryRevision}
              />
            )}
          </aside>
        </div>
        <GenerateBar
          disabled={!speechText.trim() || (engine === "kokoro" && !primary) || (engine === "fish_audio" && fishStyle === "custom" && !fishCustomStyle.trim())}
          running={generation.isRunning}
          phase={generation.job?.phase}
          progress={generation.job?.progress}
          onCancel={generation.cancel}
          description={engine === "kokoro" ? "Generation runs locally on this CPU." : "Your script is sent to Fish Audio through OpenRouter."}
          onGenerate={generate}
        />
        {generation.job?.state === "complete" ? (
          <AudioTransport result={generation.job} />
        ) : (
          <div className="transport-placeholder" aria-hidden="true"><span>Audio transport appears here after generation</span><i /></div>
        )}
      </main>
      <footer><span>{engine === "kokoro" ? "Kokoro 82M" : "Fish Audio S2.1 Pro Free"}</span><span>{engine === "kokoro" ? "Private by default · Apache 2.0" : "Cloud mode · free model only"}</span></footer>
    </div>
  );
}
