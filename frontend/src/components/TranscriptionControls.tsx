import type {TimestampEngine, TtsEngine} from "../types";


export function TranscriptionControls({engine, automatic, timestampEngine, onAutomatic, onTimestampEngine}: {
  engine: TtsEngine;
  automatic: boolean;
  timestampEngine: TimestampEngine;
  onAutomatic: (value: boolean) => void;
  onTimestampEngine: (value: TimestampEngine) => void;
}) {
  return (
    <section className="control-section" aria-labelledby="transcription-heading">
      <div className="control-title"><h2 id="transcription-heading">Transcript</h2><span>Optional</span></div>
      <label className="switch-row transcription-switch">
        <input type="checkbox" aria-label="Automatically transcribe generated audio" checked={automatic} onChange={(event) => onAutomatic(event.target.checked)} />
        <span><b>Automatically transcribe generated audio</b><small>Leave unchecked to listen first. Use Transcribe audio afterward when you want timestamps.</small></span>
      </label>
      {engine === "fish_audio" ? <>
        <label className="field">Timestamp engine
          <select value={timestampEngine} onChange={(event) => onTimestampEngine(event.target.value as TimestampEngine)}>
            <option value="whisperx">WhisperX — word alignment (default)</option>
            <option value="whisper">Whisper — faster-whisper</option>
          </select>
        </label>
        <p className="control-help">{timestampEngine === "whisperx"
          ? "Aligns recognized words locally. The first transcription downloads a language-specific alignment model."
          : "Uses local Whisper word timestamps without an additional alignment model."}</p>
      </> : <p className="control-help">Kokoro uses its built-in speech timing, so transcription does not need another model.</p>}
    </section>
  );
}
