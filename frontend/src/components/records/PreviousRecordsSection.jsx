import React, { useEffect, useRef, useState } from 'react';
import { Loader2, FileUp, ScanSearch, FileText, X, Check } from 'lucide-react';
import { api } from '../../services/api';
import { Field, InlineError, WriteResult, PatientSelect, invalidRing, typeLabel, validatePastOrToday, errorText, todayIso } from './shared';
import { CurrentRecord } from './MedicalHistorySection';

const MAX_FILE_BYTES = 1024 * 1024; // pasted-text sized records only; nothing is uploaded until "Import"
const ACCEPTED = /\.(txt|md|markdown|json)$/i;

const SAMPLE = `Discharge summary. 68-year-old with atrial fibrillation on warfarin 5 mg daily, type 2 diabetes managed with metformin, and hypertension on lisinopril. Allergic to penicillin. Prior myocardial infarction in 2019.`;

export function PreviousRecordsSection({ patients, patientId, onPatientChange, onChanged, recordState }) {
  const { record, loading, error: recordError, reload } = recordState;
  const [meta, setMeta] = useState({ title: '', record_date: '', source_facility: '' });
  const [text, setText] = useState('');
  const [fileName, setFileName] = useState(null);
  const [preview, setPreview] = useState(null); // [{entry, checked}] extracted from the current text
  const [errors, setErrors] = useState({});
  const [formError, setFormError] = useState(null);
  const [busy, setBusy] = useState(null); // 'extract' | 'import'
  const [result, setResult] = useState(null);
  const fileRef = useRef(null);

  useEffect(() => { setResult(null); setFormError(null); }, [patientId]);

  const setMetaField = (key) => (e) => setMeta((m) => ({ ...m, [key]: e.target.value }));
  // The preview describes one exact text; any edit makes it stale.
  const changeText = (value) => { setText(value); setPreview(null); setResult(null); };

  const loadFile = async (file) => {
    if (!file) return;
    setFormError(null);
    if (!ACCEPTED.test(file.name) && !file.type.startsWith('text/') && file.type !== 'application/json') {
      setFormError('Only .txt, .md and .json files can be loaded here. Paste the text instead.');
      return;
    }
    if (file.size > MAX_FILE_BYTES) { setFormError('That file is larger than 1 MB. Paste the relevant section instead.'); return; }
    try {
      let content = await file.text();
      if (/\.json$/i.test(file.name) || file.type === 'application/json') {
        try { content = JSON.stringify(JSON.parse(content), null, 2); } catch { /* keep the raw text */ }
      }
      if (!content.trim()) { setFormError('That file is empty.'); return; }
      changeText(content);
      setFileName(file.name);
      setMeta((m) => (m.title.trim() ? m : { ...m, title: file.name.replace(/\.[^.]+$/, '').replace(/[_-]+/g, ' ') }));
    } catch {
      setFormError('That file could not be read as text.');
    }
  };

  const extract = async () => {
    if (busy) return;
    setFormError(null);
    if (!text.trim()) { setErrors((e) => ({ ...e, text: 'Paste the record text or load a file first.' })); return; }
    setErrors((e) => ({ ...e, text: undefined }));
    setBusy('extract');
    try {
      const res = await api.extractRecordText(text);
      // Negated, family-history and discontinued statements come back under "excluded": listed unticked with the
      // reason, so nothing is hidden and a wrongly excluded item can still be ticked by the user.
      setPreview([
        ...(res?.entries || []).map((entry) => ({ entry, checked: true })),
        ...(res?.excluded || []).map(({ reason, ...entry }) => ({ entry, checked: false, reason })),
      ]);
    } catch (err) {
      setFormError(errorText(err, 'The text could not be analysed.'));
    } finally {
      setBusy(null);
    }
  };

  const toggle = (index) => setPreview((list) => list.map((item, i) => (i === index ? { ...item, checked: !item.checked } : item)));

  const submit = async (e) => {
    e.preventDefault();
    if (busy) return;
    const next = {};
    if (!meta.title.trim()) next.title = 'Give the record a title.';
    if (!text.trim()) next.text = 'Paste the record text or load a file first.';
    const dateError = validatePastOrToday(meta.record_date, 'Record date');
    if (dateError) next.record_date = dateError;
    setErrors(next);
    setFormError(null);
    if (!patientId) { setFormError('Pick a patient first.'); return; }
    if (Object.keys(next).length) return;
    if (!preview) { setFormError('Preview what will be added before importing.'); return; }

    const payload = {
      title: meta.title.trim(),
      text,
      // Only the entries the user left ticked are written; the document itself is always filed.
      entries: preview.filter((p) => p.checked).map((p) => p.entry),
    };
    if (meta.record_date) payload.record_date = meta.record_date;
    if (meta.source_facility.trim()) payload.source_facility = meta.source_facility.trim();

    setBusy('import');
    try {
      const res = await api.importPreviousRecord(patientId, payload);
      setResult(res);
      setText(''); setFileName(null); setPreview(null);
      setMeta({ title: '', record_date: '', source_facility: '' });
      onChanged?.(res?.patient_id || patientId);
      reload();
    } catch (err) {
      setFormError(errorText(err, 'The record could not be imported.'));
    } finally {
      setBusy(null);
    }
  };

  const checkedCount = preview ? preview.filter((p) => p.checked).length : 0;
  const disabled = Boolean(busy);

  return (
    <form onSubmit={submit} noValidate className="space-y-5">
      <Field label="Patient" htmlFor="pr-patient">
        <PatientSelect id="pr-patient" patients={patients} value={patientId} onChange={onPatientChange} disabled={disabled} />
      </Field>

      {patientId && <CurrentRecord record={record} loading={loading} error={recordError} onReload={reload} />}

      <section className="space-y-3">
        <div>
          <h3 className="font-display font-medium text-lg">Previous record</h3>
          <p className="text-sm text-text-secondary">A discharge summary, referral letter or old chart note. The text is filed in the CareStack chart and the clinical facts in it are added to the medical history.</p>
        </div>
        <div className="grid sm:grid-cols-2 gap-3">
          <Field label="Title" htmlFor="pr-title" error={errors.title} className="sm:col-span-2">
            <input id="pr-title" className={`field${invalidRing(errors.title)}`} value={meta.title} onChange={setMetaField('title')} placeholder="e.g. Cardiology discharge summary" disabled={disabled} />
          </Field>
          <Field label="Record date (optional)" htmlFor="pr-date" error={errors.record_date}>
            <input id="pr-date" type="date" max={todayIso()} className={`field${invalidRing(errors.record_date)}`} value={meta.record_date} onChange={setMetaField('record_date')} disabled={disabled} />
          </Field>
          <Field label="Source facility (optional)" htmlFor="pr-facility">
            <input id="pr-facility" className="field" value={meta.source_facility} onChange={setMetaField('source_facility')} placeholder="e.g. St. Mary's Hospital" disabled={disabled} />
          </Field>
        </div>

        <Field label="Record text" htmlFor="pr-text" error={errors.text}>
          <textarea
            id="pr-text"
            value={text}
            onChange={(e) => { changeText(e.target.value); setFileName(null); }}
            onDragOver={(e) => e.preventDefault()}
            onDrop={(e) => { e.preventDefault(); loadFile(e.dataTransfer.files?.[0]); }}
            rows={8}
            disabled={disabled}
            placeholder="Paste the record here, or drop a .txt, .md or .json file"
            className={`w-full rounded-3xl bg-app-secondary px-5 py-4 text-sm leading-relaxed text-text-main placeholder:text-text-muted outline-none focus:bg-white focus:ring-2 focus:ring-accent/30 resize-y min-h-[9rem]${invalidRing(errors.text)}`}
          />
        </Field>

        <div className="flex flex-wrap items-center gap-2">
          <input ref={fileRef} type="file" accept=".txt,.md,.markdown,.json,text/plain,text/markdown,application/json" className="hidden"
            onChange={(e) => { loadFile(e.target.files?.[0]); e.target.value = ''; }} />
          <button type="button" className="chip hover:bg-app-bg hover:text-text-main" onClick={() => fileRef.current?.click()} disabled={disabled}>
            <FileUp className="w-3 h-3" strokeWidth={1.5} /> Load a file
          </button>
          {!text && (
            <button type="button" className="chip hover:bg-app-bg hover:text-text-main" disabled={disabled}
              onClick={() => { changeText(SAMPLE); setMeta((m) => (m.title.trim() ? m : { ...m, title: 'Sample discharge summary' })); }}>
              <FileText className="w-3 h-3" strokeWidth={1.5} /> Use a sample
            </button>
          )}
          {fileName && (
            <span className="chip chip-accent max-w-full">
              <FileText className="w-3 h-3 shrink-0" strokeWidth={1.5} /> <span className="truncate">{fileName}</span>
              <button type="button" onClick={() => { changeText(''); setFileName(null); }} aria-label="Clear loaded file" disabled={disabled}><X className="w-3 h-3" /></button>
            </span>
          )}
          {text && <span className="text-xs text-text-muted ml-auto">{text.length.toLocaleString()} characters</span>}
        </div>

        {!preview && (
          <button type="button" className="btn-dark w-full" onClick={extract} disabled={disabled || !text.trim()}>
            {busy === 'extract' ? <Loader2 className="w-4 h-4 animate-spin" /> : <ScanSearch className="w-4 h-4" strokeWidth={1.5} />}
            {busy === 'extract' ? 'Reading the record…' : 'Preview what will be added'}
          </button>
        )}
      </section>

      {preview && (
        <section className="space-y-3 animate-fade-in">
          <div className="flex items-end gap-3">
            <div className="min-w-0 flex-1">
              <h3 className="font-display font-medium text-lg">Found in this record</h3>
              <p className="text-sm text-text-secondary">
                {preview.length
                  ? 'Matched by the rule-based clinical lexicon, not guessed by a language model. Untick anything that should not go on the chart.'
                  : 'No known conditions, medications or allergies were recognised. The text can still be filed as a document.'}
              </p>
            </div>
            {preview.length > 1 && (
              <button type="button" className="text-xs font-medium text-accent-deep shrink-0 pb-0.5" disabled={disabled}
                onClick={() => setPreview((list) => list.map((p) => ({ ...p, checked: checkedCount !== list.length })))}>
                {checkedCount === preview.length ? 'Untick all' : 'Tick all'}
              </button>
            )}
          </div>
          {preview.length > 0 && (
            <ul className="space-y-1.5">
              {preview.map(({ entry, checked, reason }, i) => (
                <li key={`${entry.type}-${entry.code || entry.text}-${i}`}>
                  <label className={`flex items-center gap-3 rounded-3xl px-4 py-3 cursor-pointer ${checked ? 'bg-accent-soft' : 'bg-app-secondary opacity-60'}`}>
                    <input type="checkbox" className="sr-only peer" checked={checked} onChange={() => toggle(i)} disabled={disabled} />
                    <span className={`inline-flex items-center justify-center w-5 h-5 rounded-md shrink-0 peer-focus-visible:ring-2 peer-focus-visible:ring-accent/50 ${checked ? 'bg-accent text-white' : 'bg-app-surface'}`}>
                      {checked && <Check className="w-3.5 h-3.5" strokeWidth={2.5} />}
                    </span>
                    <span className="text-[11px] text-text-secondary w-20 shrink-0">{typeLabel(entry.type)}</span>
                    <span className="min-w-0">
                      <span className={`block text-sm text-text-main truncate ${checked ? '' : 'line-through'}`}>
                        {entry.display || entry.text}
                        {entry.value != null && entry.value !== '' ? ` · ${entry.value}${entry.unit ? ` ${entry.unit}` : ''}` : ''}
                      </span>
                      {/* the clause of the record the rule matched, so the user can judge it */}
                      {entry.evidence && (
                        <span className="block text-[11px] text-text-muted truncate" title={entry.evidence}>
                          {reason && <span className="font-medium text-warning-dark">Left out: {reason}. </span>}“{entry.evidence}”
                        </span>
                      )}
                    </span>
                    {entry.code && <span className="ml-auto font-mono text-[11px] text-accent-deep shrink-0">{entry.code}</span>}
                  </label>
                </li>
              ))}
            </ul>
          )}
        </section>
      )}

      <InlineError>{formError}</InlineError>
      <WriteResult result={result} title="Record imported" />

      {preview && (
        <button type="submit" className="btn-primary w-full" disabled={disabled || !patientId}>
          {busy === 'import' ? <Loader2 className="w-4 h-4 animate-spin" /> : <FileUp className="w-4 h-4" strokeWidth={1.5} />}
          {busy === 'import'
            ? 'Importing…'
            : checkedCount ? `Import record and add ${checkedCount} entr${checkedCount === 1 ? 'y' : 'ies'}` : 'File the record only'}
        </button>
      )}
    </form>
  );
}
