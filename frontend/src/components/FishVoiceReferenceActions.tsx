import {useState} from "react";

import {writeClipboard} from "../clipboard";
import {fishVoicePageUrl} from "../fishReference";


export function FishVoiceReferenceActions({name, reference}: {name: string; reference: string}) {
  const [copyState, setCopyState] = useState<"idle" | "copying" | "copied" | "failed">("idle");
  const url = fishVoicePageUrl(reference);

  async function copy() {
    setCopyState("copying");
    setCopyState(await writeClipboard(reference) ? "copied" : "failed");
  }

  return (
    <div className="voice-reference-tools">
      <div className="voice-library-actions">
        <button type="button" aria-label={`Copy reference ID for ${name}`} disabled={copyState === "copying"} onClick={() => void copy()}>Copy ID</button>
        {url && <a href={url} target="_blank" rel="noopener noreferrer" aria-label={`Open ${name} in Fish Audio`}>Open in Fish Audio</a>}
      </div>
      {copyState === "copied" && <span className="reference-copy-status" role="status">ID copied</span>}
      {copyState === "failed" && <label className="reference-manual-copy">Select and copy this ID:
        <input readOnly autoFocus aria-label={`Reference ID to copy for ${name}`} value={reference} onFocus={(event) => event.currentTarget.select()} />
      </label>}
    </div>
  );
}
