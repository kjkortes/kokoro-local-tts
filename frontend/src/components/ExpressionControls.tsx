import type {ExpressionPreset, ExpressionValues} from "../types";


interface Props {
  presets: ExpressionPreset[];
  selected: string;
  values: Required<ExpressionValues>;
  pauseMs: number | null;
  custom: boolean;
  onPreset: (preset: ExpressionPreset) => void;
  onValue: (name: keyof ExpressionValues, value: number) => void;
  onPauseMs: (value: number | null) => void;
}

const format = (value: number, suffix = "×") => `${value.toFixed(2).replace(/\.00$/, "")}${suffix}`;

export function ExpressionControls({presets, selected, values, pauseMs, custom, onPreset, onValue, onPauseMs}: Props) {
  const active = presets.find((item) => item.id === selected) ?? presets[0];
  return (
    <section className="control-section expression-section" aria-labelledby="expression-heading">
      <div className="control-title"><h2 id="expression-heading">Expression</h2>{custom && <span>Custom</span>}</div>
      <div className="preset-grid" role="group" aria-label="Expression preset">
        {presets.map((preset) => (
          <button key={preset.id} type="button" className={preset.id === selected && !custom ? "active" : ""} onClick={() => onPreset(preset)}>
            {preset.name}
          </button>
        ))}
      </div>
      <p className="preset-summary">{active?.description}</p>
      <details>
        <summary>Fine-tune delivery <span>Speed, pitch, timing</span></summary>
        <div className="fine-tune-grid">
          <Range label="Synthesis speed" value={values.speed} min={.5} max={2} step={.05} output={format(values.speed)} onChange={(v) => onValue("speed", v)} />
          <Range label="Pitch" value={values.pitch} min={-4} max={4} step={.1} output={`${values.pitch > 0 ? "+" : ""}${values.pitch.toFixed(1)} st`} onChange={(v) => onValue("pitch", v)} />
          <Range label="Tempo" value={values.tempo} min={.75} max={1.25} step={.01} output={format(values.tempo)} onChange={(v) => onValue("tempo", v)} />
          <Range label="Automatic pause scale" value={values.pause_scale} min={.5} max={2} step={.05} output={format(values.pause_scale)} disabled={pauseMs !== null} onChange={(v) => onValue("pause_scale", v)} />
          <div className="number-field">
            <div><label htmlFor="pause-duration">Pause duration (ms)</label><output>{pauseMs === null ? "Automatic" : `${pauseMs} ms`}</output></div>
            <input
              id="pause-duration"
              type="number"
              min={0}
              max={5000}
              step={10}
              value={pauseMs ?? ""}
              placeholder="Automatic"
              aria-describedby="pause-duration-help"
              onChange={(event) => onPauseMs(event.target.value === "" ? null : Number(event.target.value))}
            />
            <small id="pause-duration-help">Leave blank to use the expression preset’s timing.</small>
          </div>
          <Range label="Volume" value={values.volume} min={0} max={1.5} step={.05} output={format(values.volume)} onChange={(v) => onValue("volume", v)} />
        </div>
      </details>
    </section>
  );
}

function Range({label, value, min, max, step, output, disabled = false, onChange}: {label: string; value: number; min: number; max: number; step: number; output: string; disabled?: boolean; onChange: (value: number) => void}) {
  return (
    <label className="range-field">
      <span>{label}<output>{output}</output></span>
      <input type="range" min={min} max={max} step={step} value={value} disabled={disabled} onChange={(event) => onChange(Number(event.target.value))} />
    </label>
  );
}
