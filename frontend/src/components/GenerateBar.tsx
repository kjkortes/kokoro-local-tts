export function GenerateBar({disabled, running, phase, progress, description = "Generation runs locally on this CPU.", onGenerate, onCancel}: {
  disabled: boolean;
  running: boolean;
  phase?: string;
  progress?: number;
  description?: string;
  onGenerate: () => void;
  onCancel: () => void;
}) {
  return (
    <div className="generate-bar">
      {running ? (
        <>
          <div className="progress-copy"><b>{phase}</b><span>{Math.round((progress ?? 0) * 100)}%</span></div>
          <div className="progress-track"><i style={{width: `${(progress ?? 0) * 100}%`}} /></div>
          <button className="button secondary" type="button" onClick={onCancel}>Cancel</button>
        </>
      ) : (
        <>
          <div><span className="eyebrow">Ready when you are</span><p>{description}</p></div>
          <button className="button primary" type="button" disabled={disabled} onClick={onGenerate}>
            Generate speech <span aria-hidden="true">↗</span>
          </button>
        </>
      )}
    </div>
  );
}
