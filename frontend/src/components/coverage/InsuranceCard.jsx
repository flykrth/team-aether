import React, { useEffect, useRef, useState } from 'react';
import { ShieldCheck, Pencil, Check, Loader2, FileUp, FileText, Trash2 } from 'lucide-react';
import { api } from '../../services/api';

export const DENTAL_STATUSES = [
  ['unknown', 'Not known yet'], ['active', 'Active'], ['expired', 'Expired'], ['exhausted', 'Annual maximum used up'],
  ['denied', 'Claim denied'], ['none', 'No dental cover'],
];
export const PLAN_TYPES = ['', 'HMO', 'PPO', 'POS', 'EPO', 'Traditional'];
const errText = (err) => err?.detail || err?.message || 'Something went wrong';
const label = (value) => DENTAL_STATUSES.find(([v]) => v === value)?.[1] || value;

/** The fields themselves, shared by the patient chart and the new-patient form. Everything is optional. */
export function InsuranceFields({ value, onChange, insurers = [] }) {
  const set = (group, key) => (e) => onChange({ ...value, [group]: { ...value[group], [key]: e.target.value } });
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
      <label className="block"><span className="eyebrow block mb-1">Dental benefit</span>
        <select value={value.dental.status} onChange={set('dental', 'status')} className="field">{DENTAL_STATUSES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select>
      </label>
      <label className="block"><span className="eyebrow block mb-1">Dental carrier</span><input value={value.dental.carrier} onChange={set('dental', 'carrier')} className="field" placeholder="e.g. Delta Dental" /></label>
      <label className="block"><span className="eyebrow block mb-1">Medical insurer</span>
        <input value={value.medical.insurer} onChange={set('medical', 'insurer')} list="insurer-options" className="field" placeholder="e.g. Aetna" />
        <datalist id="insurer-options">{insurers.map((i) => <option key={i} value={i} />)}</datalist>
      </label>
      <label className="block"><span className="eyebrow block mb-1">Plan type</span>
        <select value={value.medical.plan_type} onChange={set('medical', 'plan_type')} className="field">{PLAN_TYPES.map((t) => <option key={t} value={t}>{t || 'Not known'}</option>)}</select>
      </label>
      <label className="block"><span className="eyebrow block mb-1">Plan name</span><input value={value.medical.plan_name} onChange={set('medical', 'plan_name')} className="field" placeholder="e.g. Open Access PPO" /></label>
      <label className="block"><span className="eyebrow block mb-1">Member ID</span><input value={value.medical.member_id} onChange={set('medical', 'member_id')} className="field" /></label>
    </div>
  );
}

export const emptyInsurance = () => ({ dental: { status: 'unknown', carrier: '', note: '' }, medical: { insurer: '', plan_name: '', plan_type: '', member_id: '' } });
export const hasInsurance = (v) => v.dental.status !== 'unknown' || v.dental.carrier || Object.values(v.medical).some(Boolean);

/** Insurance on the patient chart: shown compactly, edited in place, plan document attached here too. */
export function InsuranceCard({ patientId }) {
  const [data, setData] = useState(null);
  const [draft, setDraft] = useState(null);
  const [insurers, setInsurers] = useState([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const fileRef = useRef(null);

  useEffect(() => { api.getCoverageSources('US').then((s) => setInsurers(s.insurers || [])).catch(() => {}); }, []);
  useEffect(() => {
    if (!patientId) return;
    setData(null); setDraft(null); setError(null);
    api.getInsurance(patientId).then(setData).catch((e) => setError(errText(e)));
  }, [patientId]);

  const run = async (call) => {
    setBusy(true); setError(null);
    try { setData(await call()); setDraft(null); } catch (e) { setError(errText(e)); } finally { setBusy(false); }
  };

  const medical = data?.medical || {};
  const known = data && (data.dental.status !== 'unknown' || data.dental.carrier || Object.values(medical).some(Boolean) || data.plan_document);

  return (
    <div className="card !p-5">
      <div className="flex items-center gap-2 mb-3">
        <ShieldCheck className="w-4 h-4 text-text-muted" strokeWidth={1.5} />
        <h3 className="font-display text-lg font-medium flex-1">Insurance</h3>
        {data && !draft && <button onClick={() => setDraft({ dental: { ...data.dental }, medical: { ...data.medical } })} className="btn-ghost !h-9 !text-sm"><Pencil className="w-3.5 h-3.5" strokeWidth={1.5} /> {known ? 'Edit' : 'Add'}</button>}
      </div>

      {!data && !error && <Loader2 className="w-4 h-4 animate-spin text-text-muted" />}
      {error && <p className="text-sm text-danger-dark bg-danger-light rounded-2xl px-4 py-3 mb-3">{error}</p>}

      {data && !draft && (
        known ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div className="well">
              <div className="eyebrow mb-1">Dental</div>
              <p className="text-sm font-medium text-text-main">{label(data.dental.status)}</p>
              {data.dental.carrier && <p className="text-xs text-text-muted">{data.dental.carrier}</p>}
            </div>
            <div className="well">
              <div className="eyebrow mb-1">Medical</div>
              <p className="text-sm font-medium text-text-main">{[medical.insurer, medical.plan_type].filter(Boolean).join(' · ') || 'Not recorded'}</p>
              <p className="text-xs text-text-muted">{[medical.plan_name, medical.member_id && `ID ${medical.member_id}`].filter(Boolean).join(' · ')}</p>
            </div>
          </div>
        ) : <p className="text-sm text-text-muted">Nothing recorded yet. Add it whenever it is known; the visit's insurance step uses it.</p>
      )}

      {draft && (
        <div className="space-y-3 animate-fade-in">
          <InsuranceFields value={draft} onChange={setDraft} insurers={insurers} />
          <div className="flex items-center gap-2">
            <button onClick={() => run(() => api.setInsurance(patientId, draft))} disabled={busy} className="btn-primary">{busy ? <Loader2 className="w-4 h-4 animate-spin" /> : <Check className="w-4 h-4" />} Save insurance</button>
            <button onClick={() => setDraft(null)} className="btn-ghost">Cancel</button>
          </div>
        </div>
      )}

      {data && !draft && (
        <div className="well !p-3 mt-3">
          <input ref={fileRef} type="file" accept=".pdf,.txt,.md,application/pdf,text/plain" className="hidden"
            onChange={(e) => { const f = e.target.files?.[0]; e.target.value = ''; if (f) run(() => api.uploadPlanDocument(patientId, f)); }} />
          {data.plan_document ? (
            <div className="flex items-center gap-3">
              <FileText className="w-4 h-4 text-text-muted shrink-0" strokeWidth={1.5} />
              <div className="min-w-0 flex-1"><p className="text-sm text-text-main truncate">{data.plan_document.title}</p>
                <p className="text-[11px] text-text-muted">Medical plan document · kept on this machine</p></div>
              <button onClick={() => run(() => api.removePlanDocument(patientId))} disabled={busy} className="p-2 rounded-full hover:bg-danger-light text-danger" aria-label="Remove plan document"><Trash2 className="w-4 h-4" strokeWidth={1.5} /></button>
            </div>
          ) : (
            <button onClick={() => fileRef.current?.click()} disabled={busy} className="w-full flex items-center gap-3 text-left">
              {busy ? <Loader2 className="w-4 h-4 animate-spin text-text-muted shrink-0" /> : <FileUp className="w-4 h-4 text-text-muted shrink-0" strokeWidth={1.5} />}
              <span className="text-sm text-text-secondary">Upload the medical plan document (SBC or Certificate of Coverage), if the patient has it.</span>
            </button>
          )}
        </div>
      )}
    </div>
  );
}
