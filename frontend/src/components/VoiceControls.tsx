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
  const available = props.voices.filter((voice) =>
    voice.language === props.language && (props.gender === "all" || voice.gender === props.gender)
  );
  const secondary = props.voices.filter((voice) => voice.language === props.language && voice.id !== props.primary);
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
      <label className="field">Primary voice
        <select value={props.primary} onChange={(event) => props.onPrimary(event.target.value)}>
          {available.map((voice) => <option key={voice.id} value={voice.id}>{voice.name}</option>)}
        </select>
      </label>
      <label className="switch-row">
        <input type="checkbox" checked={props.blendEnabled} onChange={(event) => props.onBlendEnabled(event.target.checked)} />
        <span><b>Blend a second voice</b><small>Mix two voices from the same language.</small></span>
      </label>
      {props.blendEnabled && (
        <div className="blend-panel">
          <label className="field">Second voice
            <select value={props.secondary} onChange={(event) => props.onSecondary(event.target.value)}>
              {secondary.map((voice) => <option key={voice.id} value={voice.id}>{voice.name}</option>)}
            </select>
          </label>
          <label className="range-field">
            <span>Voice A <output>{Math.round((1 - props.blendRatio) * 100)} / {Math.round(props.blendRatio * 100)}</output> Voice B</span>
            <input aria-label="Voice blend" type="range" min="0.05" max="0.95" step="0.05" value={props.blendRatio} onChange={(event) => props.onBlendRatio(Number(event.target.value))} />
          </label>
        </div>
      )}
    </section>
  );
}

