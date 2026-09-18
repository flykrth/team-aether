import React, { useState } from 'react';
import { UserPlus, Loader2, Plus, Trash2, CheckCircle2, ClipboardPlus, FileUp, ChevronDown } from 'lucide-react';
import { api } from '../../services/api';
import {
  Field, InlineError, EntryRowsEditor, WriteResult, invalidRing, newRow, rowsToEntries,
  validateBirthDate, isCdtCode, normalizeCdt, errorText, todayIso,
} from './shared';

const COMMON_PROCEDURES = [
  { code: 'D7210', description: 'Surgical extraction' },
  { code: 'D7140', description: 'Simple extraction' },
  { code: 'D6010', description: 'Implant placement' },
  { code: 'D4341', description: 'Scaling and root planing' },
  { code: 'D3330', description: 'Molar root canal' },
];

let procSeq = 0;
const newProcedure = (seed = {}) => ({ key: `proc-${++procSeq}`, code: '', description: '', tooth_number: '', ...seed });
const EMPTY_FORM = { first_name: '', last_name: '', birth_date: '', gender: 'unknown', phone: '', email: '' };

export function NewPatientSection({ onCreated, onAddHistory, onImportRecords }) {
  const [form, setForm] = useState(EMPTY_FORM);
  const [procedures, setProcedures] = useState([]);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [rows, setRows] = useState([]);
  const [errors, setErrors] = useState({});
  const [rowErrors, setRowErrors] = useState({});
  const [submitError, setSubmitError] = useState(null);
  const [saving, setSaving] = useState(false);
  const [created, setCreated] = useState(null);

  const set = (key) => (e) => setForm((f) => ({ ...f, [key]: e.target.value }));
  const patchProcedure = (key, changes) => setProcedures((list) => list.map((p) => (p.key === key ? { ...p, ...changes } : p)));

  const validate = () => {
    const next = {};
    if (!form.first_name.trim()) next.first_name = 'First name is required.';
    if (!form.last_name.trim()) next.last_name = 'Last name is required.';
    const dob = validateBirthDate(form.birth_date);
    if (dob) next.birth_date = dob;
    if (form.email.trim() && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.email.trim())) next.email = 'Enter a valid email address.';
    if (form.phone.trim() && form.phone.replace(/\D/g, '').length < 7) next.phone = 'Enter a valid phone number.';
    procedures.forEach((p) => {
      const touched = p.code.trim() || p.description.trim() || p.tooth_number.trim();
      if (touched && !isCdtCode(p.code)) next[p.key] = 'CDT codes look like D7210 (D plus four digits).';
    });
    return next;
  };

  const submit = async (e) => {
    e.preventDefault();
    if (saving) return;
    const fieldErrors = validate();
    const { entries, errors: historyErrors } = rowsToEntries(historyOpen ? rows : []);
    setErrors(fieldErrors);
    setRowErrors(historyErrors);
    setSubmitError(null);
    if (Object.keys(fieldErrors).length || Object.keys(historyErrors).length) return;

    const payload = {
      first_name: form.first_name.trim(),
      last_name: form.last_name.trim(),
      birth_date: form.birth_date,
      gender: form.gender,
    };
    if (form.phone.trim()) payload.phone = form.phone.trim();
    if (form.email.trim()) payload.email = form.email.trim();
    const planned = procedures.filter((p) => p.code.trim()).map((p) => {
      const item = { code: normalizeCdt(p.code) };
      if (p.description.trim()) item.description = p.description.trim();
      if (p.tooth_number.trim()) item.tooth_number = p.tooth_number.trim();
      return item;
    });
    if (planned.length) payload.planned_procedures = planned;
    if (entries.length) payload.history = entries;

    setSaving(true);
    try {
      const res = await api.createRecordPatient(payload);
      setCreated(res);
      onCreated?.(res);
    } catch (err) {
      setSubmitError(errorText(err, 'The patient could not be created.'));
    } finally {
      setSaving(false);
    }
  };

  const reset = () => {
    setForm(EMPTY_FORM); setProcedures([]); setRows([]); setHistoryOpen(false);
    setErrors({}); setRowErrors({}); setSubmitError(null); setCreated(null);
  };

  if (created) {
    const history = created.history || created.history_result || (created.added ? created : null);
    const planned = created.planned_procedures || [];
    return (
      <div className="space-y-4 animate-fade-in">
        <div className="card-dark">
          <div className="flex items-center gap-2 text-white/60 text-sm">
            <CheckCircle2 className="w-4 h-4 text-success" strokeWidth={1.5} />
            {created.already_existed ? 'This patient was already registered' : 'Patient created'}
          </div>
          <div className="display-lg mt-3 break-words">{created.name}</div>
          <div className="flex flex-wrap gap-2 mt-4">
            <span className="inline-flex items-center h-8 px-3 rounded-full bg-white text-ink font-mono text-sm font-medium">{created.patient_id}</span>
            {created.mrn && <span className="inline-flex items-center h-8 px-3 rounded-full bg-white/10 font-mono text-sm">{created.mrn}</span>}
            {created.birth_date && <span className="inline-flex items-center h-8 px-3 rounded-full bg-white/10 text-sm">Born {created.birth_date}</span>}
          </div>
          {planned.length > 0 && (
            <p className="text-sm text-white/60 mt-4">
              Planned: {planned.map((p) => (typeof p === 'string' ? p : [p.code, p.description].filter(Boolean).join(' '))).join(', ')}
            </p>
          )}
          {created.already_existed && (
            <p className="text-sm text-white/60 mt-4">Same name and date of birth as an existing chart, so no duplicate was made. You can keep adding to that chart.</p>
          )}
        </div>

        {history && <WriteResult result={history} title="Initial history saved" />}

        <div className="grid sm:grid-cols-2 gap-2">
          <button type="button" className="btn-primary" onClick={() => onAddHistory?.(created.patient_id)}>
            <ClipboardPlus className="w-4 h-4" strokeWidth={1.5} /> Add medical history
          </button>
          <button type="button" className="btn-ghost" onClick={() => onImportRecords?.(created.patient_id)}>
            <FileUp className="w-4 h-4" strokeWidth={1.5} /> Import previous records
          </button>
        </div>
        <button type="button" className="btn-ghost w-full" onClick={reset}>
          <UserPlus className="w-4 h-4" strokeWidth={1.5} /> Register another patient
        </button>
      </div>
    );
  }

  return (
    <form onSubmit={submit} noValidate className="space-y-6">
      <section className="space-y-3">
        <h3 className="font-display font-medium text-lg">Demographics</h3>
        <div className="grid sm:grid-cols-2 gap-3">
          <Field label="First name" htmlFor="np-first" error={errors.first_name}>
            <input id="np-first" className={`field${invalidRing(errors.first_name)}`} value={form.first_name} onChange={set('first_name')} autoComplete="off" disabled={saving} />
          </Field>
          <Field label="Last name" htmlFor="np-last" error={errors.last_name}>
            <input id="np-last" className={`field${invalidRing(errors.last_name)}`} value={form.last_name} onChange={set('last_name')} autoComplete="off" disabled={saving} />
          </Field>
          <Field label="Date of birth" htmlFor="np-dob" error={errors.birth_date}>
            <input id="np-dob" type="date" max={todayIso()} className={`field${invalidRing(errors.birth_date)}`} value={form.birth_date} onChange={set('birth_date')} disabled={saving} />
          </Field>
          <Field label="Gender" htmlFor="np-gender">
            <select id="np-gender" className="field appearance-none cursor-pointer" value={form.gender} onChange={set('gender')} disabled={saving}>
              <option value="unknown">Not specified</option>
              <option value="female">Female</option>
              <option value="male">Male</option>
              <option value="other">Other</option>
            </select>
          </Field>
          <Field label="Phone (optional)" htmlFor="np-phone" error={errors.phone}>
            <input id="np-phone" type="tel" className={`field${invalidRing(errors.phone)}`} value={form.phone} onChange={set('phone')} autoComplete="off" disabled={saving} />
          </Field>
          <Field label="Email (optional)" htmlFor="np-email" error={errors.email}>
            <input id="np-email" type="email" className={`field${invalidRing(errors.email)}`} value={form.email} onChange={set('email')} autoComplete="off" disabled={saving} />
          </Field>
        </div>
      </section>

      <section className="space-y-3">
        <div>
          <h3 className="font-display font-medium text-lg">Planned procedures</h3>
          <p className="text-sm text-text-secondary">CDT codes the agents will check against the medical record. Optional.</p>
        </div>
        {procedures.map((p) => (
          <div key={p.key} className="well !p-3 space-y-2">
            <div className="flex items-center gap-2">
              <input aria-label="CDT code" placeholder="D7210" maxLength={5} value={p.code} disabled={saving}
                onChange={(e) => patchProcedure(p.key, { code: e.target.value.toUpperCase() })}
                className={`field !h-10 !bg-app-surface !w-24 font-mono shrink-0${invalidRing(errors[p.key])}`} />
              <input aria-label="Procedure description" placeholder="Description" value={p.description} disabled={saving}
                onChange={(e) => patchProcedure(p.key, { description: e.target.value })}
                className="field !h-10 !bg-app-surface min-w-0" />
              <input aria-label="Tooth number" placeholder="Tooth" maxLength={3} value={p.tooth_number} disabled={saving}
                onChange={(e) => patchProcedure(p.key, { tooth_number: e.target.value })}
                className="field !h-10 !bg-app-surface !w-20 shrink-0" />
              <button type="button" disabled={saving} onClick={() => setProcedures((list) => list.filter((x) => x.key !== p.key))}
                className="inline-flex items-center justify-center w-10 h-10 rounded-full bg-app-surface text-text-secondary hover:text-danger-dark shrink-0" aria-label="Remove procedure">
                <Trash2 className="w-4 h-4" strokeWidth={1.5} />
              </button>
            </div>
            {errors[p.key] && <p className="text-xs text-danger-dark px-2" role="alert">{errors[p.key]}</p>}
          </div>
        ))}
        <div className="flex flex-wrap gap-2">
          {COMMON_PROCEDURES.filter((c) => !procedures.some((p) => normalizeCdt(p.code) === c.code)).map((c) => (
            <button key={c.code} type="button" disabled={saving} className="chip hover:bg-app-bg hover:text-text-main"
              onClick={() => setProcedures((list) => [...list, newProcedure(c)])}>
              <Plus className="w-3 h-3" strokeWidth={2} /> <span className="font-mono">{c.code}</span> {c.description}
            </button>
          ))}
          <button type="button" disabled={saving} className="chip chip-accent" onClick={() => setProcedures((list) => [...list, newProcedure()])}>
            <Plus className="w-3 h-3" strokeWidth={2} /> Other code
          </button>
        </div>
      </section>

      <section className="space-y-3">
        <button type="button" onClick={() => { setHistoryOpen((o) => !o); if (!historyOpen && rows.length === 0) setRows([newRow('condition')]); }}
          className="w-full flex items-center gap-3 text-left" aria-expanded={historyOpen}>
          <div className="min-w-0 flex-1">
            <h3 className="font-display font-medium text-lg">Initial medical history</h3>
            <p className="text-sm text-text-secondary">Optional. Plain language is fine, it is coded to ICD-10 and RxNorm on save.</p>
          </div>
          <span className="icon-btn !w-9 !h-9"><ChevronDown className={`w-4 h-4 transition-transform ${historyOpen ? 'rotate-180' : ''}`} strokeWidth={1.5} /></span>
        </button>
        {historyOpen && <EntryRowsEditor rows={rows} onChange={setRows} errors={rowErrors} disabled={saving} idPrefix="np-entry" />}
      </section>

      <InlineError>{submitError}</InlineError>

      <button type="submit" className="btn-primary w-full" disabled={saving}>
        {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <UserPlus className="w-4 h-4" strokeWidth={1.5} />}
        {saving ? 'Creating patient…' : 'Create patient'}
      </button>
    </form>
  );
}
