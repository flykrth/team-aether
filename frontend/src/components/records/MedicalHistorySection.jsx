import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Loader2, Save, RefreshCw, HeartPulse, Pill, ShieldAlert, FlaskConical, Link2, Link2Off } from 'lucide-react';
import { api } from '../../services/api';
import { Field, InlineError, EntryRowsEditor, WriteResult, PatientSelect, newRow, rowsToEntries, errorText } from './shared';

const GROUPS = [
  { key: 'conditions', label: 'Conditions', icon: HeartPulse },
  { key: 'medications', label: 'Medications', icon: Pill },
  { key: 'allergies', label: 'Allergies', icon: ShieldAlert },
];

/** Loads the coded history on file for a patient. Stale responses (patient switched mid-flight) are dropped. */
export function usePatientRecord(patientId) {
  const [state, setState] = useState({ record: null, loading: false, error: null });
  const latest = useRef(0);

  const load = useCallback(async () => {
    const ticket = ++latest.current;
    if (!patientId) { setState({ record: null, loading: false, error: null }); return; }
    setState((s) => ({ ...s, loading: true, error: null }));
    try {
      const record = await api.getPatientRecord(patientId);
      if (ticket !== latest.current) return;
      if (record?.found === false) setState({ record: null, loading: false, error: record.message || 'No record found for this patient.' });
      else setState({ record, loading: false, error: null });
    } catch (err) {
      if (ticket !== latest.current) return;
      setState({ record: null, loading: false, error: errorText(err, 'The record could not be loaded.') });
    }
  }, [patientId]);

  useEffect(() => { load(); }, [load]);
  return { ...state, reload: load };
}

export function CurrentRecord({ record, loading, error, onReload }) {
  if (error) return <InlineError>{error}</InlineError>;
  if (!record) {
    return loading
      ? <div className="well flex items-center gap-2 text-sm text-text-muted"><Loader2 className="w-4 h-4 animate-spin" /> Loading the record on file…</div>
      : null;
  }
  const observations = record.observations || [];
  const total = GROUPS.reduce((n, g) => n + (record[g.key]?.length || 0), 0) + observations.length;

  return (
    <div className="well space-y-3">
      <div className="flex items-center gap-2">
        <div className="min-w-0 flex-1">
          <div className="eyebrow">On file</div>
          <div className="font-display font-medium truncate">{record.name || record.patient_id}</div>
        </div>
        <span className={`chip !bg-app-surface ${record.medical_record_linked ? '!text-success-dark' : ''}`}>
          {record.medical_record_linked ? <Link2 className="w-3 h-3" strokeWidth={1.5} /> : <Link2Off className="w-3 h-3" strokeWidth={1.5} />}
          {record.medical_record_linked ? 'Medical record linked' : 'No medical record yet'}
        </span>
        <button type="button" onClick={onReload} disabled={loading} className="inline-flex items-center justify-center w-8 h-8 rounded-full bg-app-surface text-text-secondary hover:text-text-main shrink-0" aria-label="Refresh record">
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} strokeWidth={1.5} />
        </button>
      </div>

      {total === 0 && <p className="text-sm text-text-secondary">Nothing coded on file yet. Entries you add below appear here.</p>}

      {GROUPS.map(({ key, label, icon: Icon }) => {
        const items = record[key] || [];
        if (!items.length) return null;
        return (
          <div key={key}>
            <div className="flex items-center gap-1.5 text-xs font-medium text-text-secondary mb-1.5">
              <Icon className="w-3.5 h-3.5" strokeWidth={1.5} /> {label} <span className="text-text-muted">{items.length}</span>
            </div>
            <ul className="flex flex-wrap gap-1.5">
              {items.map((item, i) => (
                <li key={`${item.code || item.display}-${i}`} className="inline-flex items-center gap-1.5 min-h-7 px-3 py-1 rounded-full bg-app-surface text-xs text-text-main max-w-full"
                  title={[item.drug_class, item.onset ? `since ${item.onset}` : null].filter(Boolean).join(' · ') || undefined}>
                  <span className="truncate">{item.display || item.code}</span>
                  {item.code && item.display && <span className="font-mono text-[10px] text-text-muted shrink-0">{item.code}</span>}
                </li>
              ))}
            </ul>
          </div>
        );
      })}

      {observations.length > 0 && (
        <div>
          <div className="flex items-center gap-1.5 text-xs font-medium text-text-secondary mb-1.5">
            <FlaskConical className="w-3.5 h-3.5" strokeWidth={1.5} /> Lab values <span className="text-text-muted">{observations.length}</span>
          </div>
          <ul className="flex flex-wrap gap-1.5">
            {observations.map((o, i) => (
              <li key={`${o.test}-${o.date}-${i}`} className="inline-flex items-center gap-1.5 min-h-7 px-3 py-1 rounded-full bg-app-surface text-xs text-text-main max-w-full" title={o.date || undefined}>
                <span className="truncate">{o.test || 'Observation'}</span>
                {o.value != null && <span className="font-mono text-[11px] text-accent-deep shrink-0">{o.value}{o.unit ? ` ${o.unit}` : ''}</span>}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

export function MedicalHistorySection({ patients, patientId, onPatientChange, onChanged, recordState }) {
  const { record, loading, error, reload } = recordState;
  const [rows, setRows] = useState(() => [newRow('condition')]);
  const [rowErrors, setRowErrors] = useState({});
  const [formError, setFormError] = useState(null);
  const [saving, setSaving] = useState(false);
  const [result, setResult] = useState(null);

  // A result belongs to the patient it was saved for.
  useEffect(() => { setResult(null); setFormError(null); }, [patientId]);

  const submit = async (e) => {
    e.preventDefault();
    if (saving) return;
    const { entries, errors } = rowsToEntries(rows);
    setRowErrors(errors);
    setFormError(null);
    if (!patientId) { setFormError('Pick a patient first.'); return; }
    if (Object.keys(errors).length) return;
    if (!entries.length) { setFormError('Add at least one condition, medication, allergy or lab value.'); return; }

    setSaving(true);
    try {
      const res = await api.addHistoryEntries(patientId, entries, 'manual');
      setResult(res);
      setRows([newRow('condition')]);
      onChanged?.(res?.patient_id || patientId);
      reload();
    } catch (err) {
      setFormError(errorText(err, 'The history could not be saved.'));
    } finally {
      setSaving(false);
    }
  };

  return (
    <form onSubmit={submit} noValidate className="space-y-5">
      <Field label="Patient" htmlFor="mh-patient">
        <PatientSelect id="mh-patient" patients={patients} value={patientId} onChange={onPatientChange} disabled={saving} />
      </Field>

      {patientId && <CurrentRecord record={record} loading={loading} error={error} onReload={reload} />}

      <section className="space-y-3">
        <div>
          <h3 className="font-display font-medium text-lg">Add to the history</h3>
          <p className="text-sm text-text-secondary">Write it the way you would say it. The backend codes each entry to ICD-10 or RxNorm, and tells you what it could not code.</p>
        </div>
        <EntryRowsEditor rows={rows} onChange={setRows} errors={rowErrors} disabled={saving} idPrefix="mh-entry" />
      </section>

      <InlineError>{formError}</InlineError>
      <WriteResult result={result} />

      <button type="submit" className="btn-primary w-full" disabled={saving || !patientId}>
        {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" strokeWidth={1.5} />}
        {saving ? 'Saving…' : 'Save to medical history'}
      </button>
    </form>
  );
}
