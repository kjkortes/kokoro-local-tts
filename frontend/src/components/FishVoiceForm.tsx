import {useId, useState} from "react";

import {normalizeFishReference} from "../fishReference";
import type {FishVoiceInput} from "../types";


interface Props {
  initial: FishVoiceInput;
  editing: boolean;
  saving: boolean;
  onSave: (voice: FishVoiceInput) => Promise<void>;
  onCancel: () => void;
}

export function FishVoiceForm({initial, editing, saving, onSave, onCancel}: Props) {
  const [draft, setDraft] = useState(initial);
  const [error, setError] = useState<string | null>(null);
  const hint = useId();

  function normalize(): FishVoiceInput | null {
    try {
      const next = {...draft, name: draft.name.trim(), description: draft.description.trim(), reference_id: normalizeFishReference(draft.reference_id)};
      setDraft(next);
      setError(null);
      return next;
    } catch (reason) {
      setError((reason as Error).message);
      return null;
    }
  }

  return (
    <form className="voice-library-editor" aria-label={editing ? "Edit saved voice" : "Add saved voice"}
      onSubmit={(event) => {event.preventDefault(); const next = normalize(); if (next) void onSave(next);}}>
      <fieldset disabled={saving}>
        <legend>{editing ? "Edit saved voice" : "Add saved voice"}</legend>
        <label className="field text-field">Name
          <input autoFocus value={draft.name} required maxLength={100} placeholder="e.g. Documentary narrator"
            onChange={(event) => setDraft({...draft, name: event.target.value})} />
        </label>
        <label className="field">Description
          <textarea className="voice-description" value={draft.description} maxLength={2000} rows={4}
            placeholder="Accent, tone, and what this voice works well for"
            onChange={(event) => setDraft({...draft, description: event.target.value})} />
        </label>
        <label className="field text-field">Reference ID
          <input value={draft.reference_id} required maxLength={2048} autoComplete="off" spellCheck={false} aria-describedby={hint}
            placeholder="Reference ID or https://fish.audio/app/m/…"
            onChange={(event) => {setDraft({...draft, reference_id: event.target.value}); setError(null);}}
            onBlur={() => {normalize();}}
            onPaste={(event) => {
              try {
                const reference = normalizeFishReference(event.clipboardData.getData("text"));
                if (!reference) return;
                event.preventDefault();
                setDraft({...draft, reference_id: reference});
                setError(null);
              } catch { /* Let the pasted value remain editable; validate on blur/save. */ }
            }} />
        </label>
        <p className="control-help" id={hint}>Paste a Fish Audio voice link to extract its reference ID automatically.</p>
        {error && <p className="voice-library-error" role="alert">{error}</p>}
        <div className="voice-library-actions">
          <button type="submit" className="primary" disabled={!draft.name.trim() || !draft.reference_id.trim()}>{saving ? "Saving…" : "Save voice"}</button>
          <button type="button" onClick={onCancel}>Cancel</button>
        </div>
      </fieldset>
    </form>
  );
}
