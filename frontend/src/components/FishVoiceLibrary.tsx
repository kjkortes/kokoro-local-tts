import {useEffect, useState} from "react";

import {deleteFishVoice, getFishVoices, saveFishVoice} from "../api";
import type {FishVoiceInput, FishVoiceReference} from "../types";
import {FishVoiceForm} from "./FishVoiceForm";
import {FishVoiceReferenceActions} from "./FishVoiceReferenceActions";


interface Props {
  voice: string;
  onVoice: (value: string) => void;
  revision?: number;
}

interface VoiceDraft extends FishVoiceInput {
  id?: string;
}

export function FishVoiceLibrary({voice, onVoice, revision = 0}: Props) {
  const [voices, setVoices] = useState<FishVoiceReference[]>([]);
  const [loading, setLoading] = useState(true);
  const [reload, setReload] = useState(0);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState("");
  const [custom, setCustom] = useState(false);
  const [draft, setDraft] = useState<VoiceDraft | null>(null);
  const [deleting, setDeleting] = useState<FishVoiceReference | null>(null);
  const [saving, setSaving] = useState(false);
  const selected = voices.find((item) => item.reference_id === voice);
  const selection = custom ? "custom" : !voice ? "provider" : selected?.id ?? "custom";
  const editing = draft !== null || deleting !== null;

  useEffect(() => {setCustom(false);}, [revision]);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setLoadError(null);
    getFishVoices(controller.signal).then((items) => {
      if (!controller.signal.aborted) setVoices(items);
    }).catch((reason: Error) => {
      if (!controller.signal.aborted) setLoadError(reason.message);
    }).finally(() => {
      if (!controller.signal.aborted) setLoading(false);
    });
    return () => controller.abort();
  }, [reload, revision]);

  function choose(value: string) {
    setCustom(value === "custom");
    setError(null);
    setMessage("");
    if (value === "provider") onVoice("");
    else if (value !== "custom") onVoice(voices.find((item) => item.id === value)?.reference_id ?? "");
  }

  function edit(next: VoiceDraft) {
    setError(null);
    setMessage("");
    setDraft(next);
  }

  async function save(input: FishVoiceInput) {
    if (!draft) return;
    setSaving(true);
    setError(null);
    try {
      const saved = await saveFishVoice(input, draft.id);
      setVoices((current) => [...current.filter((item) => item.id !== saved.id), saved]
        .sort((a, b) => a.name.localeCompare(b.name)));
      onVoice(saved.reference_id);
      setCustom(false);
      setDraft(null);
      setMessage(`Saved ${saved.name}.`);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not save this voice.");
    } finally {
      setSaving(false);
    }
  }

  async function remove() {
    if (!deleting) return;
    setSaving(true);
    setError(null);
    try {
      await deleteFishVoice(deleting.id);
      setVoices((current) => current.filter((item) => item.id !== deleting.id));
      if (voice === deleting.reference_id) {
        onVoice("");
        setCustom(false);
      }
      setDeleting(null);
      setMessage(`Deleted ${deleting.name}.`);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not delete this voice.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="fish-voice-library">
      <label className="field">Fish voice
        <select value={selection} onChange={(event) => choose(event.target.value)} disabled={loading || editing}>
          <option value="provider">Provider default</option>
          {voices.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
          <option value="custom">Custom reference ID…</option>
        </select>
      </label>
      {selection === "custom" ? (
        <label className="field text-field">Custom Fish Voice / Reference ID
          <input type="text" aria-label="Custom Fish Voice / Reference ID" value={voice} onChange={(event) => onVoice(event.target.value)}
            placeholder="Paste a Fish Audio reference ID" maxLength={256} autoComplete="off" spellCheck={false} disabled={editing} />
          <small>Use once, or add it to your saved voices below.</small>
        </label>
      ) : selected && (
        <><p className="fish-reference-id"><span>Reference ID</span><code>{selected.reference_id}</code></p>
          <FishVoiceReferenceActions key={selected.reference_id} name={selected.name} reference={selected.reference_id} />
          {selected.description && <p className="control-help">{selected.description}</p>}</>
      )}
      <p className="control-help">Save speaker identities and accents here. Your library is shared by devices using this server.</p>
      <div className="voice-library-actions">
        <button type="button" disabled={loading || Boolean(loadError) || editing} onClick={() => edit({name: "", description: "", reference_id: selection === "custom" ? voice : ""})}>Add voice</button>
        <button type="button" disabled={!selected || selection === "custom" || loading || editing} onClick={() => selected && edit(selected)}>Edit voice</button>
        <button type="button" disabled={!selected || selection === "custom" || loading || editing} onClick={() => {setError(null); setMessage(""); setDeleting(selected ?? null);}}>Delete voice</button>
        <button type="button" disabled={loading || editing} onClick={() => {setError(null); setMessage(""); setReload((value) => value + 1);}}>Reload voices</button>
      </div>
      <a className="manage-voices-link" href="#voices">Manage all voices</a>
      {loading && <p className="control-help" role="status">Loading saved voices…</p>}
      {loadError && <p className="voice-library-error" role="alert">{loadError}</p>}
      {!loading && !loadError && voices.length === 0 && <p className="control-help">No saved voices yet. Add your first reference.</p>}
      {draft && <FishVoiceForm initial={draft} editing={Boolean(draft.id)} saving={saving} onSave={save} onCancel={() => {setDraft(null); setError(null);}} />}
      {deleting && (
        <div className="voice-library-editor">
          <p>Delete “{deleting.name}” from saved voices?</p>
          <div className="voice-library-actions">
            <button type="button" className="danger" disabled={saving} onClick={() => void remove()}>{saving ? "Deleting…" : "Confirm delete"}</button>
            <button type="button" disabled={saving} onClick={() => {setDeleting(null); setError(null);}}>Keep voice</button>
          </div>
        </div>
      )}
      {error && <p className="voice-library-error" role="alert">{error}</p>}
      {message && <p className="control-help" role="status">{message}</p>}
    </div>
  );
}
