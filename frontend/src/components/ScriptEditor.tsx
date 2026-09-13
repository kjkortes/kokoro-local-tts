import {useState} from "react";

import {parseMarkdownTable, type MarkdownTable} from "../markdownStoryboard";


interface ScriptEditorProps {
  text: string;
  onChange: (text: string) => void;
  storyboardSegments: string[] | null;
  onStoryboardSegments: (segments: string[] | null) => void;
  privacyLabel?: string;
}

function readFile(file: File) {
  return new Promise<string>((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result ?? ""));
    reader.onerror = () => reject(new Error("The storyboard file could not be read."));
    reader.readAsText(file);
  });
}

export function ScriptEditor({text, onChange, storyboardSegments, onStoryboardSegments, privacyLabel = "Stays on this machine"}: ScriptEditorProps) {
  const [table, setTable] = useState<MarkdownTable | null>(null);
  const [selectedColumn, setSelectedColumn] = useState(0);
  const [filename, setFilename] = useState("");
  const [pastedMarkdown, setPastedMarkdown] = useState("");
  const [importError, setImportError] = useState<string | null>(null);
  const storyboardMode = storyboardSegments !== null;
  const visibleText = storyboardMode ? storyboardSegments.join("\n\n") : text;
  const words = visibleText.trim() ? visibleText.trim().split(/\s+/).length : 0;
  const estimatedSeconds = Math.round(words / 2.5);
  const estimate = estimatedSeconds < 60
    ? `~${Math.max(1, estimatedSeconds)} sec`
    : `~${Math.floor(estimatedSeconds / 60)}:${String(estimatedSeconds % 60).padStart(2, "0")}`;
  function chooseColumn(column: number, nextTable = table) {
    setSelectedColumn(column);
    const segments = nextTable?.rows.map((row) => row[column] ?? "").filter(Boolean) ?? [];
    onStoryboardSegments(segments);
  }

  function useStoryboard(source: string, sourceName = "") {
    setImportError(null);
    setFilename(sourceName);
    try {
      const parsed = parseMarkdownTable(source);
      setTable(parsed);
      chooseColumn(0, parsed);
    } catch (error) {
      setTable(null);
      onStoryboardSegments([]);
      setImportError((error as Error).message);
    }
  }

  async function importStoryboard(file: File | undefined) {
    if (!file) return;
    try {
      useStoryboard(await readFile(file), file.name);
    } catch (error) {
      setTable(null);
      onStoryboardSegments([]);
      setImportError((error as Error).message);
    }
  }

  return (
    <section className="script-panel" aria-labelledby="script-heading">
      <div className="section-heading">
        <div>
          <span className="eyebrow">Your script</span>
          <h1 id="script-heading">Give the words a voice.</h1>
        </div>
        <span className="privacy-note">{privacyLabel}</span>
      </div>
      <div className="script-source-switch" aria-label="Input method">
        <button
          type="button"
          className={!storyboardMode ? "active" : ""}
          aria-pressed={!storyboardMode}
          onClick={() => onStoryboardSegments(null)}
        >
          Paste script
        </button>
        <button
          type="button"
          className={storyboardMode ? "active" : ""}
          aria-pressed={storyboardMode}
          onClick={() => onStoryboardSegments(storyboardSegments ?? [])}
        >
          Upload storyboard
        </button>
      </div>
      {!storyboardMode ? (
        <>
          <label className="sr-only" htmlFor="script">Script</label>
          <textarea
            id="script"
            value={text}
            onChange={(event) => onChange(event.target.value)}
            placeholder="Paste a script, narration, or a single line…"
            spellCheck="true"
            maxLength={100_000}
          />
        </>
      ) : (
        <div className="storyboard-import">
          <div className="storyboard-paste">
            <label htmlFor="storyboard-markdown">Paste Markdown table</label>
            <textarea
              id="storyboard-markdown"
              className="storyboard-source"
              aria-label="Paste Markdown storyboard"
              value={pastedMarkdown}
              onChange={(event) => setPastedMarkdown(event.target.value)}
              placeholder="| Beat | VO script | Visual cue |"
              spellCheck="false"
            />
            <button
              type="button"
              className="storyboard-parse"
              disabled={!pastedMarkdown.trim()}
              onClick={() => useStoryboard(pastedMarkdown)}
            >
              Use pasted table
            </button>
          </div>
          <div className="storyboard-divider"><span>or upload a file</span></div>
          <label className="storyboard-file">
            <span>{filename || "Choose a Markdown storyboard"}</span>
            <input
              type="file"
              aria-label="Markdown storyboard"
              accept=".md,.markdown,.txt,text/markdown,text/plain"
              onChange={(event) => void importStoryboard(event.target.files?.[0])}
            />
          </label>
          {importError && <p className="storyboard-error" role="alert">{importError}</p>}
          {table && (
            <>
              <label className="field storyboard-column">
                Speech column
                <select value={selectedColumn} onChange={(event) => chooseColumn(Number(event.target.value))}>
                  {table.headers.map((header, index) => (
                    <option value={index} key={`${header}-${index}`}>{header || `Column ${index + 1}`}</option>
                  ))}
                </select>
              </label>
              {storyboardSegments.length > 0 ? (
                <ol className="storyboard-segments" aria-label="Read-only speech segments">
                  {storyboardSegments.map((segment, index) => <li key={index}><span>{segment}</span></li>)}
                </ol>
              ) : (
                <p className="storyboard-empty">This column has no speech text.</p>
              )}
            </>
          )}
        </div>
      )}
      <div className="script-meta" aria-live="polite">
        {storyboardMode && <span>{storyboardSegments.length} {storyboardSegments.length === 1 ? "segment" : "segments"}</span>}
        <span>{words} {words === 1 ? "word" : "words"}</span>
        <span>{visibleText.length.toLocaleString()} characters</span>
        <span>{estimate}</span>
      </div>
    </section>
  );
}
