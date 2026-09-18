import React from 'react';
import { Plus, Trash2, CheckCircle2, AlertTriangle, CopyCheck, CircleAlert } from 'lucide-react';

/* Shared pieces for the patient records slide-over: validators, the history row editor,
   the patient picker and the "what did the backend code?" result summary. */

export const ENTRY_TYPES = [
  { id: 'condition', label: 'Condition', plural: 'Conditions', placeholder: 'e.g. atrial fibrillation, type 2 diabetes' },
  { id: 'medication', label: 'Medication', plural: 'Medications', placeholder: 'e.g. warfarin 5 mg daily' },
  { id: 'allergy', label: 'Allergy', plural: 'Allergies', placeholder: 'e.g. penicillin' },
  { id: 'observation', label: 'Lab value', plural: 'Lab values', placeholder: 'e.g. INR, HbA1c' },
];
const TYPE_LABEL = Object.fromEntries(ENTRY_TYPES.map((t) => [t.id, t.label]));
export const typeLabel = (type) => TYPE_LABEL[type] || type || 'Entry';

// ── Validation ─────────────────────────────────────────────────────────────
const ISO_DATE = /^\d{4}-\d{2}-\d{2}$/;

/** A real calendar date (rejects 2024-02-31) or null. */
export const parseIsoDate = (value) => {
  if (!ISO_DATE.test(value || '')) return null;
  const [y, m, d] = value.split('-').map(Number);
  const date = new Date(y, m - 1, d);
  return date.getFullYear() === y && date.getMonth() === m - 1 && date.getDate() === d ? date : null;
};

export const todayIso = () => {
  const now = new Date();
  const pad = (n) => String(n).padStart(2, '0');
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
};

export const validateBirthDate = (value) => {
  if (!value) return 'Date of birth is required.';
  const date = parseIsoDate(value);
  if (!date) return 'Enter a real date (YYYY-MM-DD).';
  if (value >= todayIso()) return 'Date of birth must be in the past.';
  if (date.getFullYear() < 1900) return 'Date of birth must be after 1900.';
  return null;
};

/** Optional date that may not be in the future (onset, record date). */
export const validatePastOrToday = (value, label = 'Date') => {
  if (!value) return null;
  if (!parseIsoDate(value)) return `${label} is not a real date.`;
  if (value > todayIso()) return `${label} cannot be in the future.`;
  return null;
};

const CDT_CODE = /^D\d{4}$/;
export const normalizeCdt = (value) => (value || '').trim().toUpperCase();
export const isCdtCode = (value) => CDT_CODE.test(normalizeCdt(value));

export const errorText = (err, fallback = 'Something went wrong. Please try again.') =>
  err?.detail || (err?.message === 'Failed to fetch' ? 'The backend is not reachable.' : err?.message) || fallback;

// ── Patients ───────────────────────────────────────────────────────────────
/** Accepts both the App shape {id, first_name, last_name} and the records API shape {patient_id, name}. */
export const normalizePatient = (p) => {
  if (!p) return null;
  const id = p.id || p.patient_id;
  if (!id) return null;
  const name = p.name || [p.first_name, p.last_name].filter(Boolean).join(' ') || id;
  return { id, name, mrn: p.mrn || null, birth_date: p.birth_date || null };
};

export function PatientSelect({ id, patients, value, onChange, disabled }) {
  return (
    <select
      id={id}
      value={value || ''}
      onChange={(e) => onChange(e.target.value)}
      disabled={disabled}
      className="field appearance-none cursor-pointer disabled:opacity-50"
    >
      <option value="">Select a patient…</option>
      {patients.map((p) => (
        <option key={p.id} value={p.id}>
          {p.name} · {p.id}{p.birth_date ? ` · born ${p.birth_date}` : ''}
        </option>
      ))}
    </select>
  );
}

// ── Form atoms ─────────────────────────────────────────────────────────────
export function Field({ label, htmlFor, error, hint, children, className = '' }) {
  return (
    <div className={className}>
      <label htmlFor={htmlFor} className="eyebrow block mb-1.5 px-1">{label}</label>
      {children}
      {error
        ? <p className="text-xs text-danger-dark mt-1.5 px-1" role="alert">{error}</p>
        : hint ? <p className="text-xs text-text-muted mt-1.5 px-1">{hint}</p> : null}
    </div>
  );
}

export function InlineError({ children }) {
  if (!children) return null;
  return (
    <div role="alert" className="rounded-3xl bg-danger-light text-danger-dark p-4 text-sm flex gap-3 animate-fade-in">
      <CircleAlert className="w-4 h-4 mt-0.5 shrink-0" strokeWidth={1.5} />
      <span className="min-w-0 break-words">{children}</span>
    </div>
  );
}

export const invalidRing = (error) => (error ? ' ring-2 ring-danger/40' : '');

// ── History row editor ─────────────────────────────────────────────────────
let rowSeq = 0;
export const newRow = (type = 'condition') => ({ key: `row-${++rowSeq}`, type, text: '', onset: '', value: '', unit: '' });

/** rows -> {entries, errors:{[row.key]: message}}. Blank rows are ignored, not errors. */
export const rowsToEntries = (rows) => {
  const entries = [];
  const errors = {};
  rows.forEach((row) => {
    const text = row.text.trim();
    const value = String(row.value ?? '').trim();
    if (!text && !value && !row.onset) return;
    if (!text) { errors[row.key] = `Describe the ${typeLabel(row.type).toLowerCase()}.`; return; }
    const entry = { type: row.type, text };
    if (row.type === 'observation') {
      if (!value) { errors[row.key] = 'A lab value needs a result.'; return; }
      // Numeric results go out as numbers so they land in valueQuantity.value.
      entry.value = /^-?\d+(\.\d+)?$/.test(value) ? Number(value) : value;
      if (row.unit.trim()) entry.unit = row.unit.trim();
    }
    if (row.onset) {
      const dateError = validatePastOrToday(row.onset, row.type === 'observation' ? 'Test date' : 'Onset');
      if (dateError) { errors[row.key] = dateError; return; }
      entry.onset = row.onset;
    }
    entries.push(entry);
  });
  return { entries, errors };
};

export function EntryRowsEditor({ rows, onChange, errors = {}, disabled, idPrefix = 'entry' }) {
  const patch = (key, changes) => onChange(rows.map((r) => (r.key === key ? { ...r, ...changes } : r)));
  const remove = (key) => onChange(rows.filter((r) => r.key !== key));

  return (
    <div className="space-y-2">
      {rows.map((row) => {
        const meta = ENTRY_TYPES.find((t) => t.id === row.type) || ENTRY_TYPES[0];
        const error = errors[row.key];
        return (
          <div key={row.key} className="well !p-3 space-y-2">
            <div className="flex items-center gap-2">
              <select
                aria-label="Entry type"
                value={row.type}
                onChange={(e) => patch(row.key, { type: e.target.value })}
                disabled={disabled}
                className="h-10 rounded-full bg-app-surface px-4 text-sm font-medium text-text-main outline-none focus:ring-2 focus:ring-accent/30 appearance-none cursor-pointer shrink-0"
              >
                {ENTRY_TYPES.map((t) => <option key={t.id} value={t.id}>{t.label}</option>)}
              </select>
              <input
                id={`${idPrefix}-${row.key}`}
                aria-label={`${meta.label} description`}
                value={row.text}
                onChange={(e) => patch(row.key, { text: e.target.value })}
                placeholder={meta.placeholder}
                disabled={disabled}
                className={`field !h-10 !bg-app-surface min-w-0${invalidRing(error)}`}
              />
              <button
                type="button"
                onClick={() => remove(row.key)}
                disabled={disabled}
                className="inline-flex items-center justify-center w-10 h-10 rounded-full bg-app-surface text-text-secondary hover:text-danger-dark shrink-0"
                aria-label={`Remove ${meta.label.toLowerCase()} row`}
              >
                <Trash2 className="w-4 h-4" strokeWidth={1.5} />
              </button>
            </div>
            {row.type === 'observation' && (
              <div className="grid grid-cols-3 gap-2">
                <input aria-label="Result value" value={row.value} onChange={(e) => patch(row.key, { value: e.target.value })}
                  placeholder="Result, e.g. 2.8" disabled={disabled} inputMode="decimal" className="field !h-10 !bg-app-surface" />
                <input aria-label="Unit" value={row.unit} onChange={(e) => patch(row.key, { unit: e.target.value })}
                  placeholder="Unit, e.g. %" disabled={disabled} className="field !h-10 !bg-app-surface" />
                <input aria-label="Test date" type="date" max={todayIso()} value={row.onset} onChange={(e) => patch(row.key, { onset: e.target.value })}
                  disabled={disabled} className="field !h-10 !bg-app-surface" />
              </div>
            )}
            {row.type === 'condition' && (
              <div className="flex items-center gap-2">
                <span className="text-xs text-text-muted pl-2 shrink-0">Onset (optional)</span>
                <input aria-label="Onset date" type="date" max={todayIso()} value={row.onset} onChange={(e) => patch(row.key, { onset: e.target.value })}
                  disabled={disabled} className="field !h-10 !bg-app-surface" />
              </div>
            )}
            {error && <p className="text-xs text-danger-dark px-2" role="alert">{error}</p>}
          </div>
        );
      })}

      <div className="flex flex-wrap gap-2 pt-1">
        {ENTRY_TYPES.map((t) => (
          <button key={t.id} type="button" disabled={disabled} onClick={() => onChange([...rows, newRow(t.id)])}
            className="chip hover:bg-app-bg hover:text-text-main disabled:opacity-40">
            <Plus className="w-3 h-3" strokeWidth={2} /> {t.label}
          </button>
        ))}
      </div>
    </div>
  );
}

// ── Backend write result ───────────────────────────────────────────────────
const entryLabel = (e) => (typeof e === 'string' ? e : e?.display || e?.text || e?.code || 'Entry');

function EntryLine({ entry, tone }) {
  const isObject = entry && typeof entry === 'object';
  return (
    <li className="flex items-center gap-2 text-sm min-w-0">
      {isObject && entry.type && <span className="text-[11px] text-text-muted w-20 shrink-0">{typeLabel(entry.type)}</span>}
      <span className="min-w-0 truncate text-text-main">{entryLabel(entry)}</span>
      {isObject && entry.value != null && entry.value !== '' && (
        <span className="text-xs text-text-secondary shrink-0">{entry.value}{entry.unit ? ` ${entry.unit}` : ''}</span>
      )}
      {tone === 'coded' && isObject && entry.code && (
        <span className="ml-auto font-mono text-[11px] h-6 px-2 inline-flex items-center rounded-full bg-success-light text-success-dark shrink-0">{entry.code}</span>
      )}
    </li>
  );
}

/** Renders {added, skipped_duplicates, unrecognized} from add_history_entries / import_previous_record. */
export function WriteResult({ result, title = 'Saved to the medical record' }) {
  if (!result) return null;
  const added = result.added || [];
  const skipped = result.skipped_duplicates || [];
  const unrecognized = result.unrecognized || [];
  const unrecognizedTexts = new Set(unrecognized.map((u) => entryLabel(u).toLowerCase()));
  const coded = added.filter((e) => e?.code && !unrecognizedTexts.has(entryLabel(e).toLowerCase()));
  const nothingNew = added.length === 0;

  return (
    <div className="rounded-3xl bg-success-light p-4 space-y-3 animate-fade-in" role="status">
      <div className="flex items-center gap-2 text-success-dark font-display font-medium">
        <CheckCircle2 className="w-4 h-4 shrink-0" strokeWidth={1.5} />
        <span className="min-w-0">{nothingNew ? 'Nothing new to add' : title}</span>
        <span className="ml-auto text-xs font-sans font-normal shrink-0">
          {added.length} added{skipped.length ? ` · ${skipped.length} duplicate${skipped.length === 1 ? '' : 's'}` : ''}
        </span>
      </div>
      {result.document_id && (
        <p className="text-xs text-success-dark">Filed in the CareStack chart as document <span className="font-mono">{result.document_id}</span>.</p>
      )}

      {coded.length > 0 && (
        <div className="rounded-2xl bg-app-surface p-3">
          <div className="eyebrow mb-2">Coded automatically</div>
          <ul className="space-y-1.5">{coded.map((e, i) => <EntryLine key={i} entry={e} tone="coded" />)}</ul>
        </div>
      )}
      {unrecognized.length > 0 && (
        <div className="rounded-2xl bg-warning-light p-3">
          <div className="flex items-center gap-1.5 text-[11px] font-medium uppercase tracking-[0.14em] text-warning-dark mb-2">
            <AlertTriangle className="w-3 h-3" strokeWidth={1.5} /> Stored as free text, not coded
          </div>
          <ul className="space-y-1.5">{unrecognized.map((e, i) => <EntryLine key={i} entry={e} />)}</ul>
          <p className="text-xs text-warning-dark mt-2">Uncoded entries stay on the chart but are not used by the risk rules. Rephrase with a standard clinical term to have them coded.</p>
        </div>
      )}
      {skipped.length > 0 && (
        <div className="rounded-2xl bg-app-surface p-3">
          <div className="flex items-center gap-1.5 eyebrow mb-2"><CopyCheck className="w-3 h-3" strokeWidth={1.5} /> Already on file, skipped</div>
          <ul className="space-y-1.5">{skipped.map((e, i) => <EntryLine key={i} entry={e} />)}</ul>
        </div>
      )}
    </div>
  );
}
