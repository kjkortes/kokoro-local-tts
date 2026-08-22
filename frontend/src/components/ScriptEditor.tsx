export function ScriptEditor({text, onChange}: {text: string; onChange: (text: string) => void}) {
  const words = text.trim() ? text.trim().split(/\s+/).length : 0;
  const estimatedSeconds = Math.round(words / 2.5);
  const estimate = estimatedSeconds < 60
    ? `~${Math.max(1, estimatedSeconds)} sec`
    : `~${Math.floor(estimatedSeconds / 60)}:${String(estimatedSeconds % 60).padStart(2, "0")}`;
  return (
    <section className="script-panel" aria-labelledby="script-heading">
      <div className="section-heading">
        <div>
          <span className="eyebrow">Your script</span>
          <h1 id="script-heading">Give the words a voice.</h1>
        </div>
        <span className="privacy-note">Stays on this machine</span>
      </div>
      <label className="sr-only" htmlFor="script">Script</label>
      <textarea
        id="script"
        value={text}
        onChange={(event) => onChange(event.target.value)}
        placeholder="Paste a script, narration, or a single line…"
        spellCheck="true"
        maxLength={100_000}
      />
      <div className="script-meta" aria-live="polite">
        <span>{words} {words === 1 ? "word" : "words"}</span>
        <span>{text.length.toLocaleString()} characters</span>
        <span>{estimate}</span>
      </div>
    </section>
  );
}

