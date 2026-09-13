import type {FishDeliveryStyle} from "../types";


const STYLE_OPTIONS: Array<{id: FishDeliveryStyle; name: string}> = [
  {id: "natural", name: "Natural"},
  {id: "documentary", name: "Documentary"},
  {id: "conversational", name: "Conversational"},
  {id: "educational", name: "Educational"},
  {id: "energetic", name: "Energetic"},
  {id: "mysterious", name: "Mysterious"},
  {id: "dramatic", name: "Dramatic"},
  {id: "calm", name: "Calm"},
  {id: "custom", name: "Custom"},
];

interface Props {
  voice: string;
  style: FishDeliveryStyle;
  customStyle: string;
  apiKey: string;
  environmentKeyConfigured: boolean;
  onVoice: (value: string) => void;
  onStyle: (value: FishDeliveryStyle) => void;
  onCustomStyle: (value: string) => void;
  onApiKey: (value: string) => void;
}

export function FishAudioControls(props: Props) {
  return (
    <>
      <section className="control-section fish-section" aria-labelledby="fish-voice-heading">
        <div className="control-title"><h2 id="fish-voice-heading">Voice / Accent</h2><span>Fish Audio</span></div>
        <label className="field">Voice
          <select value="default" disabled>
            <option value="default">Default / Provider Default</option>
          </select>
        </label>
        <label className="field text-field">
          Custom Fish Voice / Reference ID
          <input
            type="text"
            aria-label="Custom Fish Voice / Reference ID"
            value={props.voice}
            onChange={(event) => props.onVoice(event.target.value)}
            placeholder="e.g. 802e3bc2b27e49c2995d23ef70e6ac89"
            autoComplete="off"
            spellCheck={false}
          />
          <small>Use a Fish Audio voice ID to choose speaker identity and accent. Leave blank for the provider default.</small>
        </label>
      </section>
      <section className="control-section fish-section" aria-label="Fish delivery controls">
        <div className="control-title"><h2 id="fish-delivery-heading">Delivery Style</h2><span>Performance</span></div>
        <label className="field" htmlFor="fish-delivery-style">Delivery Style</label>
        <select
          id="fish-delivery-style"
          value={props.style}
          onChange={(event) => props.onStyle(event.target.value as FishDeliveryStyle)}
        >
          {STYLE_OPTIONS.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
        </select>
        {props.style === "custom" && (
          <label className="field text-field custom-style-field">
            Custom style instruction
            <input
              type="text"
              aria-label="Custom style instruction"
              value={props.customStyle}
              onChange={(event) => props.onCustomStyle(event.target.value)}
              placeholder="quiet, warm and thoughtful"
            />
          </label>
        )}
        <p className="control-help">Bracketed instructions already in your script are preserved.</p>
      </section>
      <section className="control-section fish-section" aria-labelledby="openrouter-heading">
        <div className="control-title"><h2 id="openrouter-heading">OpenRouter</h2><span>Secret</span></div>
        <label className="field text-field">
          OpenRouter API Key
          <input
            type="password"
            aria-label="OpenRouter API Key"
            value={props.apiKey}
            onChange={(event) => props.onApiKey(event.target.value)}
            placeholder={props.environmentKeyConfigured ? "Using OPENROUTER_API_KEY" : "sk-or-…"}
            disabled={props.environmentKeyConfigured}
            autoComplete="off"
            spellCheck={false}
          />
          <small>{props.environmentKeyConfigured
            ? "This server is using OPENROUTER_API_KEY. The environment value takes precedence."
            : "Required for Fish Audio. This value stays in memory and is sent only to your local backend and OpenRouter."}</small>
        </label>
        <div className="fish-output"><span>Output</span><strong>MP3</strong><small>Returned directly by OpenRouter</small></div>
        <p className="free-model-note">Free model only · no paid fallback</p>
      </section>
    </>
  );
}
