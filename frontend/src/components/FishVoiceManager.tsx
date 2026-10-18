import {useEffect, useState} from "react";

import {deleteFishVoice, getFishVoicePage, saveFishVoice} from "../api";
import type {FishVoiceInput, FishVoicePage, FishVoiceReference} from "../types";
import {FishVoiceForm} from "./FishVoiceForm";
import {FishVoiceReferenceActions} from "./FishVoiceReferenceActions";


interface Props {
  onUse: (voice: FishVoiceReference) => void;
  onChanged: (saved: FishVoiceReference | null, previous?: FishVoiceReference) => void;
}

export function FishVoiceManager({onUse, onChanged}: Props) {
  const [page, setPage] = useState(1);
  const [data, setData] = useState<FishVoicePage | null>(null);
  const [reload, setReload] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState("");
  const [draft, setDraft] = useState<FishVoiceReference | "new" | null>(null);
  const [deleting, setDeleting] = useState<FishVoiceReference | null>(null);
  const [saving, setSaving] = useState(false);
  const editing = draft !== null || deleting !== null;
  const pages = Math.max(1, Math.ceil((data?.total ?? 0) / 10));

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError(null);
    getFishVoicePage(page, controller.signal).then((next) => {
      if (controller.signal.aborted) return;
      const lastPage = Math.max(1, Math.ceil(next.total / next.page_size));
      if (page > lastPage) setPage(lastPage);
      else setData(next);
    }).catch((reason: Error) => {
      if (!controller.signal.aborted) setError(reason.message);
    }).finally(() => {
      if (!controller.signal.aborted) setLoading(false);
    });
    return () => controller.abort();
  }, [page, reload]);

  async function save(input: FishVoiceInput) {
    setSaving(true);
    setError(null);
    try {
      const previous = draft && draft !== "new" ? draft : undefined;
      const saved = await saveFishVoice(input, previous?.id);
      onChanged(saved, previous);
      setDraft(null);
      if (!previous) setPage(1);
      setReload((value) => value + 1);
      setMessage(`Saved ${saved.name}.`);
    } catch (reason) {
      setError((reason as Error).message);
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
      onChanged(null, deleting);
      setDeleting(null);
      setReload((value) => value + 1);
      setMessage(`Deleted ${deleting.name}.`);
    } catch (reason) {
      setError((reason as Error).message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <main id="voices" className="voice-manager">
      <div className="voice-manager-heading">
        <div><h1>Voice library</h1><p>Keep your Fish Audio voices ready for the next script.</p></div>
        <div className="voice-library-actions">
          <button type="button" className="primary" disabled={loading || editing} onClick={() => {setError(null); setMessage(""); setDraft("new");}}>Add voice</button>
          <button type="button" disabled={loading || editing} onClick={() => {setMessage(""); setReload((value) => value + 1);}}>Reload voices</button>
        </div>
      </div>
      {error && <p className="voice-library-error" role="alert">{error}</p>}
      {message && <p className="control-help" role="status">{message}</p>}
      <div className={`voice-manager-layout${draft ? " has-editor" : ""}`}>
        {draft && <FishVoiceForm initial={draft === "new" ? {name: "", description: "", reference_id: ""} : draft}
          editing={draft !== "new"} saving={saving} onSave={save} onCancel={() => {setDraft(null); setError(null);}} />}
        <section className="voice-manager-list" aria-label="Saved Fish voices" aria-busy={loading}>
          <table className="voice-table">
            <caption className="sr-only">Saved Fish Audio voices</caption>
            <thead><tr><th scope="col">Name</th><th scope="col">Description</th><th scope="col">Reference ID</th><th scope="col">Actions</th></tr></thead>
            <tbody>{data?.items.map((voice) => <tr key={voice.id}>
              <td data-label="Name"><strong>{voice.name}</strong></td>
              <td data-label="Description" className="voice-table-description">{voice.description || <span className="muted">No description</span>}</td>
              <td data-label="Reference ID"><code>{voice.reference_id}</code>
                <FishVoiceReferenceActions key={voice.reference_id} name={voice.name} reference={voice.reference_id} />
              </td>
              <td data-label="Actions"><div className="voice-library-actions">
                <button type="button" disabled={loading || editing} aria-label={`Use ${voice.name}`} onClick={() => onUse(voice)}>Use voice</button>
                <button type="button" disabled={loading || editing} aria-label={`Edit ${voice.name}`} onClick={() => {setError(null); setMessage(""); setDraft(voice);}}>Edit</button>
                <button type="button" disabled={loading || editing} aria-label={`Delete ${voice.name}`} onClick={() => {setError(null); setMessage(""); setDeleting(voice);}}>Delete</button>
              </div>{deleting?.id === voice.id && <div className="voice-library-editor">
                <p>Delete “{voice.name}” from saved voices?</p>
                <div className="voice-library-actions">
                  <button type="button" className="danger" disabled={saving} onClick={() => void remove()}>Confirm delete</button>
                  <button type="button" disabled={saving} onClick={() => {setDeleting(null); setError(null);}}>Keep voice</button>
                </div>
              </div>}</td>
            </tr>)}</tbody>
          </table>
          {loading && <p className="voice-manager-empty" role="status">Loading saved voices…</p>}
          {!loading && !error && data?.total === 0 && <p className="voice-manager-empty">No saved voices yet. Add a voice using its reference ID or Fish Audio link.</p>}
          <nav className="voice-pagination" aria-label="Voice list pagination">
            <span>{data?.total ? `${(page - 1) * 10 + 1}–${Math.min(page * 10, data.total)} of ${data.total} voices` : "0 voices"}</span>
            <div className="voice-library-actions">
              <button type="button" aria-label="Previous page" disabled={page <= 1 || loading || editing} onClick={() => setPage((value) => value - 1)}>Previous</button>
              <span>Page {page} of {pages}</span>
              <button type="button" aria-label="Next page" disabled={page >= pages || loading || editing} onClick={() => setPage((value) => value + 1)}>Next</button>
            </div>
          </nav>
        </section>
      </div>
    </main>
  );
}
