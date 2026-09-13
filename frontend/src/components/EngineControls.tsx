import type {TtsEngine} from "../types";


export function EngineControls({engine, onEngine}: {
  engine: TtsEngine;
  onEngine: (engine: TtsEngine) => void;
}) {
  return (
    <section className="control-section engine-section" aria-labelledby="engine-heading">
      <div className="control-title"><h2 id="engine-heading">TTS Engine</h2><span>Provider</span></div>
      <fieldset className="engine-options" aria-label="TTS engine">
        <label className={engine === "kokoro" ? "active" : ""}>
          <input
            type="radio"
            aria-label="Kokoro Local"
            name="tts-engine"
            value="kokoro"
            checked={engine === "kokoro"}
            onChange={() => onEngine("kokoro")}
          />
          <span><b>Kokoro Local</b><small>Private, offline synthesis on this CPU.</small></span>
        </label>
        <label className={engine === "fish_audio" ? "active" : ""}>
          <input
            type="radio"
            aria-label="Fish Audio S2.1 Pro Free — OpenRouter"
            name="tts-engine"
            value="fish_audio"
            checked={engine === "fish_audio"}
            onChange={() => onEngine("fish_audio")}
          />
          <span><b>Fish Audio S2.1 Pro Free — OpenRouter</b><small>Cloud synthesis using the free-only model.</small></span>
        </label>
      </fieldset>
    </section>
  );
}
