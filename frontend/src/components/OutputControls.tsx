import type {OutputFormat} from "../types";


export function OutputControls({formats, format, normalize, onFormat, onNormalize}: {
  formats: OutputFormat[];
  format: OutputFormat;
  normalize: boolean;
  onFormat: (value: OutputFormat) => void;
  onNormalize: (value: boolean) => void;
}) {
  return (
    <section className="control-section output-section" aria-labelledby="output-heading">
      <div className="control-title"><h2 id="output-heading">Output</h2><span>24 kHz</span></div>
      <div className="format-grid" role="group" aria-label="Audio format">
        {formats.map((item) => (
          <button type="button" key={item} className={item === format ? "active" : ""} onClick={() => onFormat(item)} aria-pressed={item === format}>
            {item.toUpperCase()}
          </button>
        ))}
      </div>
      <label className="switch-row compact">
        <input type="checkbox" checked={normalize} onChange={(event) => onNormalize(event.target.checked)} />
        <span><b>Normalize loudness</b><small>Balance the final level for listening.</small></span>
      </label>
    </section>
  );
}

