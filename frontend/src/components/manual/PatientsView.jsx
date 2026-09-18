import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Search, UserPlus, Pencil, Trash2, Check, X, Plus, Loader2, ShieldAlert, FileText, HeartPulse, Pill, AlertTriangle,
  FlaskConical, CalendarClock, FileUp,
} from 'lucide-react';
import { api } from '../../services/api';
import { RecordImporter, toApiEntries } from './RecordImporter';

const SECTIONS = [
  { type: 'condition', title: 'Conditions', Icon: HeartPulse, placeholder: 'e.g. atrial fibrillation' },
  { type: 'medication', title: 'Medications', Icon: Pill, placeholder: 'e.g. warfarin 5 mg' },
  { type: 'allergy', title: 'Allergies', Icon: AlertTriangle, placeholder: 'e.g. penicillin' },
  { type: 'observation', title: 'Labs', Icon: FlaskConical, placeholder: 'e.g. HbA1c 8.2' },
];

const initials = (name = '') => name.split(/\s+/).filter(Boolean).slice(0, 2).map((w) => w[0]).join('').toUpperCase();
const errText = (err) => err?.detail || err?.message || 'Something went wrong';

function EntryRow({ entry, onSave, onDelete }) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const isLab = entry.type === 'observation';

  const start = () => { setDraft({ text: entry.text, onset: entry.onset || '', value: entry.value ?? '', unit: entry.unit || '' }); setError(null); setEditing(true); };
  const run = async (action) => {
    setBusy(true); setError(null);
    try { await action(); setEditing(false); } catch (err) { setError(errText(err)); } finally { setBusy(false); }
  };
  const save = () => run(() => onSave(entry, {
    text: draft.text.trim(), ...(draft.onset ? { onset: draft.onset } : {}),
    ...(isLab && draft.value !== '' ? { value: draft.value, unit: draft.unit } : {}),
  }));

  if (editing) {
    return (
      <div className="rounded-2xl bg-white p-3 space-y-2">
        <div className="flex flex-wrap gap-2">
          <input autoFocus value={draft.text} onChange={(e) => setDraft({ ...draft, text: e.target.value })}
            onKeyDown={(e) => { if (e.key === 'Enter') save(); if (e.key === 'Escape') setEditing(false); }}
            className="field !h-9 flex-1 min-w-[160px]" aria-label="Description" />
          {isLab && <input value={draft.value} onChange={(e) => setDraft({ ...draft, value: e.target.value })} placeholder="Value" className="field !h-9 !w-24" aria-label="Value" />}
          {isLab && <input value={draft.unit} onChange={(e) => setDraft({ ...draft, unit: e.target.value })} placeholder="Unit" className="field !h-9 !w-20" aria-label="Unit" />}
          <input type="date" value={draft.onset} onChange={(e) => setDraft({ ...draft, onset: e.target.value })} className="field !h-9 !w-40" aria-label="Date" />
        </div>
        <div className="flex items-center gap-2">
          <button onClick={save} disabled={busy || !draft.text.trim()} className="btn-primary !h-8 !px-3 !text-sm">
            {busy ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Check className="w-3.5 h-3.5" />} Save
          </button>
          <button onClick={() => setEditing(false)} className="btn-ghost !h-8 !px-3 !text-sm">Cancel</button>
          {error && <span className="text-xs text-danger-dark">{error}</span>}
        </div>
      </div>
    );
  }

  return (
    <div className="group flex items-center gap-3 rounded-2xl bg-white px-3 py-2">
      <div className="min-w-0 flex-1">
        <div className="text-sm text-text-main truncate">
          {entry.text}
          {isLab && entry.value !== null && entry.value !== undefined && entry.value !== '' && <span className="font-medium"> · {entry.value} {entry.unit}</span>}
        </div>
        <div className="text-[11px] text-text-muted">
          {entry.onset || 'No date'}{entry.unconfirmed ? ' · unconfirmed' : ''}{!entry.code ? ' · not coded' : ''}
        </div>
      </div>
      {entry.code && <span className="chip h-6 font-mono text-[11px] shrink-0">{entry.code}</span>}
      <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 focus-within:opacity-100 transition-opacity shrink-0">
        <button onClick={start} className="p-1.5 rounded-full hover:bg-app-secondary text-text-secondary" aria-label={`Edit ${entry.text}`}><Pencil className="w-3.5 h-3.5" /></button>
        <button onClick={() => run(() => onDelete(entry))} disabled={busy} className="p-1.5 rounded-full hover:bg-danger-light text-danger" aria-label={`Remove ${entry.text}`}>
          {busy ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Trash2 className="w-3.5 h-3.5" />}
        </button>
      </div>
      {error && <span className="text-xs text-danger-dark">{error}</span>}
    </div>
  );
}

function AddEntry({ section, onAdd }) {
  const [text, setText] = useState('');
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState(null);
  const submit = async () => {
    if (!text.trim() || busy) return;
    setBusy(true); setNote(null);
    try {
      const res = await onAdd({ type: section.type, text: text.trim() });
      if (res?.skipped_duplicates?.length) setNote('Already on the chart');
      else if (res?.unrecognized?.length) setNote('Saved without a code');
      setText('');
    } catch (err) { setNote(errText(err)); } finally { setBusy(false); }
  };
  return (
    <div className="flex items-center gap-2">
      <input value={text} onChange={(e) => setText(e.target.value)} onKeyDown={(e) => e.key === 'Enter' && submit()}
        placeholder={`Add · ${section.placeholder}`} className="field !h-9 !bg-white flex-1" aria-label={`Add to ${section.title}`} />
      <button onClick={submit} disabled={busy || !text.trim()} className="icon-btn !w-9 !h-9 !bg-ink !text-white disabled:opacity-30" aria-label="Add">
        {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : <Plus className="w-4 h-4" />}
      </button>
      {note && <span className="text-xs text-text-muted shrink-0">{note}</span>}
    </div>
  );
}

function DetailsForm({ chart, onSave, onCancel }) {
  const [form, setForm] = useState({
    first_name: chart.first_name, last_name: chart.last_name, birth_date: chart.birth_date, gender: chart.gender,
    phone: chart.phone, email: chart.email, next_appointment: chart.next_appointment, primary_dentist: chart.primary_dentist,
  });
  const [plan, setPlan] = useState(chart.planned_procedures.map((p) => ({ ...p })));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });

  const save = async () => {
    setBusy(true); setError(null);
    try {
      await onSave({ ...form, planned_procedures: plan.filter((p) => p.code.trim()).map((p) => ({ code: p.code.trim().toUpperCase(), description: p.description || undefined, tooth_number: p.tooth_number || undefined })) });
    } catch (err) { setError(errText(err)); setBusy(false); }
  };

  const Field = ({ label, k, type = 'text' }) => (
    <label className="block">
      <span className="eyebrow block mb-1">{label}</span>
      <input type={type} value={form[k] || ''} onChange={set(k)} className="field" />
    </label>
  );

  return (
    <div className="card space-y-4 animate-fade-in">
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        {Field({ label: 'First name', k: 'first_name' })}
        {Field({ label: 'Last name', k: 'last_name' })}
        {Field({ label: 'Date of birth', k: 'birth_date', type: 'date' })}
        <label className="block">
          <span className="eyebrow block mb-1">Gender</span>
          <select value={form.gender} onChange={set('gender')} className="field">
            {['female', 'male', 'other', 'unknown'].map((g) => <option key={g} value={g}>{g}</option>)}
          </select>
        </label>
        {Field({ label: 'Phone', k: 'phone' })}
        {Field({ label: 'Email', k: 'email', type: 'email' })}
        {Field({ label: 'Next appointment', k: 'next_appointment' })}
        {Field({ label: 'Dentist', k: 'primary_dentist' })}
      </div>
      <div>
        <span className="eyebrow block mb-2">Planned procedures</span>
        <div className="space-y-2">
          {plan.map((p, i) => (
            <div key={i} className="flex gap-2">
              <input value={p.code} onChange={(e) => setPlan(plan.map((x, j) => (j === i ? { ...x, code: e.target.value } : x)))} placeholder="D7210" className="field !w-28 font-mono" aria-label="CDT code" />
              <input value={p.description || ''} onChange={(e) => setPlan(plan.map((x, j) => (j === i ? { ...x, description: e.target.value } : x)))} placeholder="Description" className="field flex-1" aria-label="Description" />
              <input value={p.tooth_number || ''} onChange={(e) => setPlan(plan.map((x, j) => (j === i ? { ...x, tooth_number: e.target.value } : x)))} placeholder="Tooth" className="field !w-24" aria-label="Tooth" />
              <button onClick={() => setPlan(plan.filter((_, j) => j !== i))} className="icon-btn" aria-label="Remove procedure"><Trash2 className="w-4 h-4" strokeWidth={1.5} /></button>
            </div>
          ))}
          <button onClick={() => setPlan([...plan, { code: '', description: '', tooth_number: '' }])} className="btn-ghost !h-9 !text-sm"><Plus className="w-4 h-4" /> Add procedure</button>
        </div>
      </div>
      <div className="flex items-center gap-2">
        <button onClick={save} disabled={busy} className="btn-primary">{busy && <Loader2 className="w-4 h-4 animate-spin" />} Save details</button>
        <button onClick={onCancel} className="btn-ghost">Cancel</button>
        {error && <span className="text-sm text-danger-dark">{error}</span>}
      </div>
    </div>
  );
}

function NewPatient({ onCreated, onCancel }) {
  const [form, setForm] = useState({ first_name: '', last_name: '', birth_date: '', gender: 'unknown', phone: '' });
  const [record, setRecord] = useState(null); // {text, title, entries} from the importer
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });
  const ready = form.first_name.trim() && form.last_name.trim() && form.birth_date;

  const create = async () => {
    setBusy(true); setError(null);
    try {
      const patient = await api.createRecordPatient({ ...form, phone: form.phone || undefined });
      if (record?.text?.trim()) {
        await api.importPreviousRecord(patient.patient_id, { title: record.title, text: record.text, entries: toApiEntries(record.entries) });
      }
      onCreated(patient.patient_id);
    } catch (err) { setError(errText(err)); setBusy(false); }
  };

  return (
    <div className="space-y-6 animate-fade-in">
      <div className="card">
        <h2 className="display-lg">New patient</h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mt-5">
          <label className="block"><span className="eyebrow block mb-1">First name</span><input autoFocus value={form.first_name} onChange={set('first_name')} className="field" /></label>
          <label className="block"><span className="eyebrow block mb-1">Last name</span><input value={form.last_name} onChange={set('last_name')} className="field" /></label>
          <label className="block"><span className="eyebrow block mb-1">Date of birth</span><input type="date" value={form.birth_date} onChange={set('birth_date')} className="field" /></label>
          <label className="block"><span className="eyebrow block mb-1">Gender</span>
            <select value={form.gender} onChange={set('gender')} className="field">{['female', 'male', 'other', 'unknown'].map((g) => <option key={g} value={g}>{g}</option>)}</select>
          </label>
          <label className="block sm:col-span-2"><span className="eyebrow block mb-1">Phone</span><input value={form.phone} onChange={set('phone')} className="field" /></label>
        </div>
      </div>
      <div className="card">
        <h3 className="font-display text-xl font-medium mb-1">Medical history</h3>
        <p className="text-sm text-text-muted mb-4">Optional. Paste it or upload the PDF; you choose what goes on the chart.</p>
        <RecordImporter onChange={setRecord} />
        {record?.document?.patient_name && !form.first_name && !form.last_name && (() => {
          const parts = record.document.patient_name.trim().split(/\s+/);
          const fill = () => setForm({ ...form, first_name: parts.slice(0, -1).join(' ') || parts[0], last_name: parts.length > 1 ? parts[parts.length - 1] : '', birth_date: record.document.patient_dob || form.birth_date });
          return (
            <button onClick={fill} className="btn-ghost !h-9 !text-sm mt-3">
              Use “{record.document.patient_name}”{record.document.patient_dob ? `, born ${record.document.patient_dob}` : ''} from the document
            </button>
          );
        })()}
      </div>
      <div className="flex items-center gap-2">
        <button onClick={create} disabled={!ready || busy} className="btn-primary">
          {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : <UserPlus className="w-4 h-4" strokeWidth={1.5} />}
          Create patient{record?.entries?.length ? ` with ${record.entries.length} history item${record.entries.length > 1 ? 's' : ''}` : ''}
        </button>
        <button onClick={onCancel} className="btn-ghost">Cancel</button>
        {error && <span className="text-sm text-danger-dark">{error}</span>}
      </div>
    </div>
  );
}

export function PatientsView({ onCheckRisk, refreshKey }) {
  const [patients, setPatients] = useState([]);
  const [query, setQuery] = useState('');
  const [selectedId, setSelectedId] = useState(null);
  const [chart, setChart] = useState(null);
  const [mode, setMode] = useState('view'); // view | edit-details | new | import
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [importRecord, setImportRecord] = useState(null);
  const [importBusy, setImportBusy] = useState(false);

  const loadPatients = useCallback(async () => {
    try {
      const list = await api.listRecordPatients();
      setPatients(list);
      setSelectedId((current) => current || list[0]?.patient_id || null);
    } catch (err) { setError(errText(err)); }
  }, []);

  const loadChart = useCallback(async (id) => {
    if (!id) return;
    setLoading(true); setError(null);
    try { setChart(await api.getPatientChart(id)); } catch (err) { setError(errText(err)); setChart(null); } finally { setLoading(false); }
  }, []);

  useEffect(() => { loadPatients(); }, [loadPatients, refreshKey]);
  useEffect(() => { setMode('view'); setImportRecord(null); loadChart(selectedId); }, [selectedId, loadChart]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return q ? patients.filter((p) => `${p.name} ${p.patient_id} ${p.mrn}`.toLowerCase().includes(q)) : patients;
  }, [patients, query]);

  const counts = useMemo(() => Object.fromEntries(SECTIONS.map((s) => [s.type, (chart?.entries || []).filter((e) => e.type === s.type).length])), [chart]);

  const saveEntry = async (entry, changes) => { await api.updateHistoryEntry(chart.patient_id, entry.resource_id, changes); await loadChart(chart.patient_id); };
  const deleteEntry = async (entry) => { await api.deleteHistoryEntry(chart.patient_id, entry.resource_id); await loadChart(chart.patient_id); };
  const addEntry = async (entry) => { const res = await api.addHistoryEntries(chart.patient_id, [entry], 'manual'); await loadChart(chart.patient_id); return res; };
  const saveDetails = async (changes) => { await api.updatePatient(chart.patient_id, changes); await Promise.all([loadChart(chart.patient_id), loadPatients()]); setMode('view'); };
  const runImport = async () => {
    setImportBusy(true); setError(null);
    try {
      await api.importPreviousRecord(chart.patient_id, { title: importRecord.title, text: importRecord.text, entries: toApiEntries(importRecord.entries) });
      setMode('view'); setImportRecord(null); await loadChart(chart.patient_id);
    } catch (err) { setError(errText(err)); } finally { setImportBusy(false); }
  };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 items-start">
      {/* Patient list */}
      <aside className="lg:col-span-4 xl:col-span-3 card !p-4 lg:sticky lg:top-5">
        <div className="flex items-center gap-2">
          <div className="relative flex-1">
            <Search className="w-4 h-4 text-text-muted absolute left-4 top-1/2 -translate-y-1/2" strokeWidth={1.5} />
            <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search patients" className="field !pl-10" aria-label="Search patients" />
          </div>
          <button onClick={() => setMode('new')} className="icon-btn !bg-accent !text-white" aria-label="New patient" title="New patient">
            <UserPlus className="w-[18px] h-[18px]" strokeWidth={1.5} />
          </button>
        </div>
        <div className="mt-3 space-y-1 max-h-[max(16rem,calc(100vh-13rem))] overflow-y-auto">
          {filtered.map((p) => {
            const active = p.patient_id === selectedId && mode !== 'new';
            return (
              <button key={p.patient_id} onClick={() => setSelectedId(p.patient_id)}
                className={`w-full flex items-center gap-3 rounded-2xl px-3 py-2.5 text-left transition-colors ${active ? 'bg-ink text-white' : 'hover:bg-app-secondary'}`}>
                <span className={`inline-flex items-center justify-center w-9 h-9 rounded-full text-xs font-semibold shrink-0 ${active ? 'bg-white/15' : 'bg-accent-soft text-accent-deep'}`}>{initials(p.name)}</span>
                <span className="min-w-0 flex-1">
                  <span className="block text-sm font-medium truncate">{p.name}</span>
                  <span className={`block text-[11px] truncate ${active ? 'text-white/60' : 'text-text-muted'}`}>{p.patient_id}{p.planned_procedures?.[0] ? ` · ${String(p.planned_procedures[0]).split(' ')[0]}` : ''}</span>
                </span>
              </button>
            );
          })}
          {filtered.length === 0 && <p className="text-sm text-text-muted text-center py-6">No patients match.</p>}
        </div>
      </aside>

      {/* Chart */}
      <section className="lg:col-span-8 xl:col-span-9 space-y-5 min-w-0">
        {error && <p className="text-sm text-danger-dark bg-danger-light rounded-3xl px-5 py-4">{error}</p>}

        {mode === 'new' && <NewPatient onCancel={() => setMode('view')} onCreated={async (id) => { await loadPatients(); setSelectedId(id); setMode('view'); loadChart(id); }} />}

        {mode !== 'new' && loading && !chart && <div className="card flex items-center gap-2 text-text-muted text-sm"><Loader2 className="w-4 h-4 animate-spin" /> Loading chart</div>}

        {mode !== 'new' && chart && (
          <>
            {/* Hero */}
            <div className="rounded-4xl p-6 lg:p-8 bg-gradient-to-br from-accent-soft via-app-surface to-app-surface">
              <div className="flex flex-wrap items-start gap-4">
                <span className="inline-flex items-center justify-center w-14 h-14 rounded-full bg-accent text-white font-display text-lg font-medium shrink-0">{initials(chart.name)}</span>
                <div className="min-w-0 flex-1">
                  <h1 className="display-lg truncate">{chart.name}</h1>
                  <p className="text-sm text-text-secondary mt-1">
                    {chart.patient_id}{chart.mrn ? ` · ${chart.mrn}` : ''} · born {chart.birth_date || 'unknown'} · {chart.gender}
                    {chart.phone ? ` · ${chart.phone}` : ''}
                  </p>
                </div>
                <div className="flex flex-wrap gap-2">
                  {chart.editable_details && <button onClick={() => setMode(mode === 'edit-details' ? 'view' : 'edit-details')} className="btn-ghost !bg-white"><Pencil className="w-4 h-4" strokeWidth={1.5} /> Edit details</button>}
                  <button onClick={() => setMode(mode === 'import' ? 'view' : 'import')} className="btn-ghost !bg-white"><FileUp className="w-4 h-4" strokeWidth={1.5} /> Add record</button>
                  <button onClick={() => onCheckRisk?.(chart.patient_id)} className="btn-dark"><ShieldAlert className="w-4 h-4" strokeWidth={1.5} /> Check risk</button>
                </div>
              </div>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mt-6">
                {SECTIONS.slice(0, 3).map(({ type, title, Icon }) => (
                  <div key={type} className="rounded-3xl bg-white/80 p-4">
                    <Icon className="w-4 h-4 text-text-muted" strokeWidth={1.5} />
                    <div className="font-display text-3xl font-medium mt-2 leading-none">{counts[type]}</div>
                    <div className="text-xs text-text-muted mt-1">{title}</div>
                  </div>
                ))}
                <div className="rounded-3xl bg-white/80 p-4">
                  <CalendarClock className="w-4 h-4 text-text-muted" strokeWidth={1.5} />
                  <div className="font-display text-lg font-medium mt-2 leading-tight">{chart.next_appointment ? chart.next_appointment.slice(0, 10) : 'None'}</div>
                  <div className="text-xs text-text-muted mt-1">{chart.planned_procedures.map((p) => p.code).join(', ') || 'Next visit'}</div>
                </div>
              </div>
            </div>

            {mode === 'edit-details' && <DetailsForm chart={chart} onSave={saveDetails} onCancel={() => setMode('view')} />}

            {mode === 'import' && (
              <div className="card animate-fade-in">
                <h3 className="font-display text-xl font-medium mb-4">Add a previous record</h3>
                <RecordImporter onChange={setImportRecord} patientName={chart.name} />
                <div className="flex items-center gap-2 mt-4">
                  <button onClick={runImport} disabled={!importRecord?.text?.trim() || importBusy} className="btn-primary">
                    {importBusy && <Loader2 className="w-4 h-4 animate-spin" />} Save to chart{importRecord?.entries?.length ? ` · ${importRecord.entries.length} item${importRecord.entries.length > 1 ? 's' : ''}` : ''}
                  </button>
                  <button onClick={() => { setMode('view'); setImportRecord(null); }} className="btn-ghost">Cancel</button>
                </div>
              </div>
            )}

            {/* History */}
            <div className="grid grid-cols-1 xl:grid-cols-2 gap-5">
              {SECTIONS.map((section) => {
                const entries = chart.entries.filter((e) => e.type === section.type);
                return (
                  <div key={section.type} className="card !p-5">
                    <div className="flex items-center gap-2 mb-3">
                      <section.Icon className="w-4 h-4 text-text-muted" strokeWidth={1.5} />
                      <h3 className="font-display text-lg font-medium">{section.title}</h3>
                      <span className="chip h-6 ml-auto">{entries.length}</span>
                    </div>
                    <div className="well !p-2 space-y-1">
                      {entries.map((e) => <EntryRow key={e.resource_id} entry={e} onSave={saveEntry} onDelete={deleteEntry} />)}
                      {entries.length === 0 && <p className="text-sm text-text-muted px-2 py-2">Nothing recorded.</p>}
                      <AddEntry section={section} onAdd={addEntry} />
                    </div>
                  </div>
                );
              })}
            </div>

            {chart.documents.length > 0 && (
              <div className="card !p-5">
                <div className="flex items-center gap-2 mb-3"><FileText className="w-4 h-4 text-text-muted" strokeWidth={1.5} /><h3 className="font-display text-lg font-medium">Documents</h3></div>
                <div className="space-y-1">
                  {chart.documents.map((d) => (
                    <div key={d.document_id} className="flex items-center gap-3 rounded-2xl bg-app-secondary px-4 py-2.5 text-sm">
                      <span className="flex-1 min-w-0 truncate text-text-main">{d.title}</span>
                      <span className="text-xs text-text-muted shrink-0">{d.document_type} · {(d.upload_timestamp || '').slice(0, 10)}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </>
        )}
      </section>
    </div>
  );
}
