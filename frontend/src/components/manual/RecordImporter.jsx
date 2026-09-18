import React, { useRef, useState } from 'react';
import { FileUp, Loader2, FileText, X, Sparkles, AlertTriangle } from 'lucide-react';
import { api } from '../../services/api';

const GROUPS = [
  ['condition', 'Conditions'], ['procedure', 'Procedures and implants'], ['medication', 'Medications'],
  ['allergy', 'Allergies'], ['observation', 'Labs and vitals'],
];
const CONTEXT_LABEL = { family_history: 'Family history', social_history: 'Social history', immunization: 'Immunization' };
const REASON_LABEL = { negated: 'ruled out', discontinued: 'stopped', resolved: 'resolved', uncertain: 'uncertain', family: 'family', 'family history': 'family' };
const sameName = (a, b) => {
  const words = (v) => new Set(String(v || '').toLowerCase().match(/[a-z]{2,}/g) || []);
  const [x, y] = [words(a), words(b)];
  return [...x].filter((w) => y.has(w)).length >= Math.min(2, x.size, y.size);
};
const METHOD_LABEL = {
  'pdf-text-layer': 'Read from the PDF on this machine',
  'nvidia-nemotron-parse': 'Scanned PDF, read by AI',
  'gemini-transcription': 'Scanned PDF, read by AI',
  'text-file': 'Text file',
};

/**
 * Paste text or drop a PDF / text file -> preview of the coded findings -> caller decides what to do.
 * onChange({ text, title, entries, document }) fires with the ticked entries whenever the selection changes.
 * patientName (optional): warns when the document is about someone else.
 */
export function RecordImporter({ onChange, patientName }) {
  const [text, setText] = useState('');
  const [fileInfo, setFileInfo] = useState(null);
  const [preview, setPreview] = useState(null); // {entries, excluded}
  const [ticked, setTicked] = useState({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [dragging, setDragging] = useState(false);
  const fileRef = useRef(null);

  const publish = (nextText, nextPreview, nextTicked, title) => {
    const entries = (nextPreview?.entries || []).filter((_, i) => nextTicked[i]);
    const doc = nextPreview?.document;
    const docTitle = doc?.type && doc.type !== 'other' ? `${doc.type[0].toUpperCase()}${doc.type.slice(1)}${doc.date ? ` ${doc.date}` : ''}` : null;
    onChange?.({ text: nextText, title: docTitle || title || 'Previous medical record', entries, document: doc || null });
  };

  const applyPreview = (nextText, result, title) => {
    const all = Object.fromEntries((result.entries || []).map((_, i) => [i, true]));
    setPreview(result); setTicked(all); publish(nextText, result, all, title);
  };

  const readFile = async (file) => {
    if (!file) return;
    setBusy(true); setError(null);
    try {
      const result = await api.extractRecordFile(file);
      setText(result.text); setFileInfo({ name: file.name, method: result.method, pages: result.pages, truncated: result.truncated });
      applyPreview(result.text, result, file.name.replace(/\.[^.]+$/, ''));
    } catch (err) {
      setError(err.detail || err.message);
    } finally {
      setBusy(false);
    }
  };

  const analyseText = async () => {
    if (!text.trim()) return;
    setBusy(true); setError(null);
    try {
      applyPreview(text, await api.extractRecordText(text), fileInfo?.name);
    } catch (err) {
      setError(err.detail || err.message);
    } finally {
      setBusy(false);
    }
  };

  const toggle = (i) => {
    const next = { ...ticked, [i]: !ticked[i] };
    setTicked(next); publish(text, preview, next, fileInfo?.name);
  };

  const clear = () => { setText(''); setFileInfo(null); setPreview(null); setTicked({}); setError(null); onChange?.(null); };

  return (
    <div className="space-y-3">
      <div
        onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => { e.preventDefault(); setDragging(false); readFile(e.dataTransfer.files?.[0]); }}
        className={`rounded-3xl p-1 transition-colors ${dragging ? 'bg-accent-soft' : 'bg-app-secondary'}`}
      >
        <textarea
          value={text}
          onChange={(e) => { setText(e.target.value); setPreview(null); onChange?.(null); }}
          rows={5}
          placeholder="Paste a referral letter, discharge summary or history here, or drop a PDF."
          className="w-full bg-transparent resize-y outline-none text-sm text-text-main placeholder:text-text-muted px-4 py-3"
        />
        <div className="flex flex-wrap items-center gap-2 px-2 pb-2">
          <input ref={fileRef} type="file" accept=".pdf,.txt,.md,.json,.csv,application/pdf,text/plain" className="hidden"
            onChange={(e) => { readFile(e.target.files?.[0]); e.target.value = ''; }} />
          <button type="button" onClick={() => fileRef.current?.click()} disabled={busy} className="btn-ghost !h-9 !px-4 !text-sm !bg-white">
            <FileUp className="w-4 h-4" strokeWidth={1.5} /> Upload PDF or text
          </button>
          <button type="button" onClick={analyseText} disabled={busy || !text.trim()} className="btn-dark !h-9 !px-4 !text-sm">
            {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : <FileText className="w-4 h-4" strokeWidth={1.5} />} {busy ? 'Reading…' : 'Find history in text'}
          </button>
          {(text || fileInfo) && (
            <button type="button" onClick={clear} className="ml-auto text-xs text-text-muted hover:text-text-main inline-flex items-center gap-1">
              <X className="w-3.5 h-3.5" /> Clear
            </button>
          )}
        </div>
      </div>

      {fileInfo && (
        <p className="text-xs text-text-muted px-1">
          {fileInfo.name} · {METHOD_LABEL[fileInfo.method] || fileInfo.method}{fileInfo.pages ? ` · ${fileInfo.pages} page${fileInfo.pages > 1 ? 's' : ''}` : ''}
          {fileInfo.truncated ? ' · long document, first part only' : ''}
        </p>
      )}
      {error && <p className="text-sm text-danger-dark bg-danger-light rounded-2xl px-4 py-3">{error}</p>}

      {preview && (() => {
        const doc = preview.document;
        const indexed = preview.entries.map((e, i) => ({ ...e, i }));
        const wrongPatient = patientName && doc?.patient_name && !sameName(patientName, doc.patient_name);
        return (
          <div className="space-y-3 animate-fade-in">
            {doc && (
              <div className="well">
                <div className="flex flex-wrap items-center gap-1.5">
                  <span className="chip chip-accent capitalize">{doc.type}</span>
                  {doc.date && <span className="chip bg-white">{doc.date}</span>}
                  {doc.facility && <span className="chip bg-white truncate max-w-[240px]">{doc.facility}</span>}
                  {doc.patient_name && <span className="chip bg-white">About {doc.patient_name}{doc.patient_dob ? ` · ${doc.patient_dob}` : ''}</span>}
                </div>
                {doc.summary && <p className="text-sm text-text-secondary mt-2">{doc.summary}</p>}
              </div>
            )}
            {wrongPatient && (
              <p className="flex gap-2 text-sm text-danger-dark bg-danger-light rounded-2xl px-4 py-3">
                <AlertTriangle className="w-4 h-4 mt-0.5 shrink-0" strokeWidth={1.5} />
                This document is about {doc.patient_name}, but the open chart is {patientName}. Check before saving.
              </p>
            )}

            <div className="well">
              {preview.entries.length === 0 && <p className="text-sm text-text-muted">No history found. You can still save the document and add items by hand.</p>}
              {GROUPS.map(([category, label]) => {
                const rows = indexed.filter((e) => (e.category || e.type) === category);
                if (!rows.length) return null;
                return (
                  <div key={category} className="mb-3 last:mb-0">
                    <div className="eyebrow mb-1.5">{label}</div>
                    <div className="space-y-1">
                      {rows.map((e) => (
                        <label key={e.i} className="flex items-start gap-3 rounded-2xl bg-white px-3 py-2 cursor-pointer">
                          <input type="checkbox" checked={!!ticked[e.i]} onChange={() => toggle(e.i)} className="accent-[#1F5EFF] w-4 h-4 mt-0.5" />
                          <span className="min-w-0 flex-1">
                            <span className="block text-sm text-text-main">
                              {e.display || e.text}
                              {e.value !== undefined && e.value !== null && e.value !== '' && <span className="font-medium"> · {e.value} {e.unit}</span>}
                              {e.onset && <span className="text-text-muted"> · {e.onset}</span>}
                            </span>
                            {e.evidence && <span className="block text-[11px] text-text-muted truncate" title={e.evidence}>“{e.evidence}”</span>}
                          </span>
                          {e.status === 'historical' && <span className="chip h-6 shrink-0">past</span>}
                          {e.code ? <span className="chip h-6 font-mono text-[11px] shrink-0">{e.code}</span> : <span className="chip h-6 shrink-0 text-text-muted">no code</span>}
                        </label>
                      ))}
                    </div>
                  </div>
                );
              })}
            </div>

            {(preview.excluded?.length > 0 || preview.context?.length > 0) && (
              <div className="well text-xs text-text-secondary space-y-1.5">
                {preview.excluded?.length > 0 && (
                  <p><span className="font-medium text-text-main">Not charted: </span>
                    {preview.excluded.map((e) => `${e.display || e.text} (${REASON_LABEL[e.reason] || e.reason})`).join(', ')}.</p>
                )}
                {(preview.context || []).map((c, i) => (
                  <p key={i}><span className="font-medium text-text-main">{CONTEXT_LABEL[c.category] || c.category}: </span>{c.text}. Kept in the document, not on the problem list.</p>
                ))}
              </div>
            )}

            <p className="flex items-center gap-1.5 text-[11px] text-text-muted px-1">
              <Sparkles className="w-3 h-3" strokeWidth={1.5} />
              {preview.analysis_method === 'model+rules'
                ? `Read by AI, every item checked against the text${preview.dropped_ungrounded ? ` (${preview.dropped_ungrounded} unsupported item${preview.dropped_ungrounded > 1 ? 's' : ''} discarded)` : ''}. Codes come from the rule-based lexicon.`
                : 'Read by the rule-based extractor only. Add an AI key for fuller classification.'}
            </p>
          </div>
        );
      })()}
    </div>
  );
}

// The API accepts only these keys per entry; the backend re-codes the text itself.
export const toApiEntries = (entries) =>
  (entries || []).map(({ type, text, display, onset, value, unit }) => ({
    type, text: text || display, ...(onset ? { onset } : {}), ...(value !== undefined && value !== null && value !== '' ? { value } : {}), ...(unit ? { unit } : {}),
  }));
