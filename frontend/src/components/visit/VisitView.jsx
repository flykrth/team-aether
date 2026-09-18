import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Check, ChevronRight, ClipboardList, ShieldAlert, Stethoscope, ShieldQuestion, Loader2, Pencil, UserPlus, AlertTriangle } from 'lucide-react';
import { api } from '../../services/api';
import { RiskCheckView } from '../manual/RiskCheckView';
import { CoverageRecoveryView } from '../coverage/CoverageRecoveryView';

const STEPS = [
  { id: 'history', label: 'History', Icon: ClipboardList },
  { id: 'risk', label: 'Risk check', Icon: ShieldAlert },
  { id: 'procedure', label: 'Procedure', Icon: Stethoscope },
  { id: 'insurance', label: 'Insurance', Icon: ShieldQuestion },
];
// Which step the visit's stage puts you on
const STEP_FOR_STAGE = { none: 'history', planned: 'risk', risk_checked: 'procedure', procedure_done: 'insurance', insurance_checked: 'insurance' };
const HAZARD = { LOW: 'bg-success-light text-success-dark', MODERATE: 'bg-warning-light text-warning-dark', CRITICAL: 'bg-danger-light text-danger-dark' };
const TYPE_LABEL = { condition: 'Conditions', medication: 'Medications', allergy: 'Allergies', observation: 'Labs' };
const errText = (err) => err?.detail || err?.message || 'Something went wrong';

export function VisitView({ initialPatientId, onEditChart, onNewPatient }) {
  const [patients, setPatients] = useState([]);
  const [patientId, setPatientId] = useState(initialPatientId || '');
  const [chart, setChart] = useState(null);
  const [view, setView] = useState(null);        // { visit, next_step, insurance, past_visits }
  const [step, setStep] = useState('history');
  const [note, setNote] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    api.listRecordPatients().then((list) => { setPatients(list); setPatientId((c) => c || list[0]?.patient_id || ''); }).catch((e) => setError(errText(e)));
  }, []);
  useEffect(() => { if (initialPatientId) setPatientId(initialPatientId); }, [initialPatientId]);

  const refresh = useCallback(async (id, follow = false) => {
    if (!id) return;
    try {
      const next = await api.getVisit(id);
      setView(next);
      if (follow) setStep(STEP_FOR_STAGE[next.next_step.stage] || 'history');
    } catch (e) { setError(errText(e)); }
  }, []);

  useEffect(() => {
    if (!patientId) return;
    setChart(null); setView(null); setError(null); setNote('');
    api.getPatientChart(patientId).then(setChart).catch((e) => setError(errText(e)));
    refresh(patientId, true);
  }, [patientId, refresh]);

  const visit = view?.visit;
  const reached = useMemo(() => {
    const stage = view?.next_step?.stage || 'none';
    const order = ['none', 'planned', 'risk_checked', 'procedure_done', 'insurance_checked'];
    const at = order.indexOf(stage);
    return { history: true, risk: true, procedure: at >= 2, insurance: at >= 3 };
  }, [view]);

  const act = async (call) => {
    setBusy(true); setError(null);
    try { await call(); await refresh(patientId, true); } catch (e) { setError(errText(e)); } finally { setBusy(false); }
  };

  const grouped = useMemo(() => {
    const groups = {};
    (chart?.entries || []).forEach((e) => { (groups[e.type] ||= []).push(e); });
    return groups;
  }, [chart]);

  const context = useMemo(() => (visit ? {
    procedure: visit.procedure?.input || visit.procedure?.label || '',
    clinical_note: [visit.clinical?.clinical_note, visit.todays_notes, visit.outcome_note].filter(Boolean).join('\n'),
    diagnosis: visit.clinical?.diagnosis || '', imaging: visit.clinical?.imaging || '',
  } : null), [visit]);

  return (
    <div className="space-y-5">
      {/* Who, and where the visit stands */}
      <div className="card">
        <div className="flex flex-wrap items-end gap-4">
          <div className="flex-1 min-w-[220px]">
            <h1 className="display-lg">Visit</h1>
            <p className="text-sm text-text-muted mt-1">{view?.next_step?.next || 'Pick a patient to begin.'}</p>
          </div>
          <label className="block w-full sm:w-72"><span className="eyebrow block mb-1">Patient</span>
            <select value={patientId} onChange={(e) => setPatientId(e.target.value)} className="field">
              {patients.map((p) => <option key={p.patient_id} value={p.patient_id}>{p.name} · {p.patient_id}</option>)}
            </select>
          </label>
          <button onClick={onNewPatient} className="btn-ghost"><UserPlus className="w-4 h-4" strokeWidth={1.5} /> New patient</button>
        </div>

        <ol className="grid grid-cols-2 md:grid-cols-4 gap-2 mt-6">
          {STEPS.map(({ id, label, Icon }, i) => {
            const active = step === id; const open = reached[id];
            const complete = STEPS.findIndex((s) => s.id === (STEP_FOR_STAGE[view?.next_step?.stage] || 'history')) > i
              || (id === 'insurance' && view?.next_step?.stage === 'insurance_checked');
            return (
              <li key={id}>
                <button onClick={() => open && setStep(id)} disabled={!open} aria-current={active ? 'step' : undefined}
                  className={`w-full flex items-center gap-2 h-11 px-4 rounded-full text-sm font-display font-medium transition-colors ${active ? 'bg-ink text-white' : open ? 'bg-app-secondary text-text-main hover:bg-app-bg' : 'bg-app-secondary text-text-muted opacity-50'}`}>
                  {complete ? <Check className="w-4 h-4 shrink-0" /> : <Icon className="w-4 h-4 shrink-0" strokeWidth={1.5} />}
                  <span className="truncate">{i + 1}. {label}</span>
                </button>
              </li>
            );
          })}
        </ol>

        {visit && (
          <div className="flex flex-wrap items-center gap-1.5 mt-4 text-xs">
            <span className="chip bg-white">{visit.procedure?.label} · {visit.procedure?.cdt_code}</span>
            {visit.risk && <span className={`chip ${HAZARD[visit.risk.hazard_level]}`}>{visit.risk.hazard_level} risk</span>}
            {visit.risk?.physician_clearance_required && <span className="chip bg-danger-light text-danger-dark">Physician clearance required</span>}
            {visit.procedure_done_at && <span className="chip bg-success-light text-success-dark"><Check className="w-3 h-3" /> Procedure done</span>}
            {visit.insurance && <span className="chip chip-accent">{visit.insurance.headline}</span>}
          </div>
        )}
      </div>

      {error && <p className="text-sm text-danger-dark bg-danger-light rounded-3xl px-5 py-4">{error}</p>}

      {/* 1. History */}
      {step === 'history' && (
        <div className="card animate-fade-in">
          <div className="flex flex-wrap items-center gap-3 mb-4">
            <h2 className="font-display text-xl font-medium flex-1">{chart?.name || 'History'} <span className="text-sm text-text-muted font-sans">on file</span></h2>
            <button onClick={() => onEditChart?.(patientId)} className="btn-ghost"><Pencil className="w-4 h-4" strokeWidth={1.5} /> Edit or add records</button>
          </div>
          {!chart ? <Loader2 className="w-4 h-4 animate-spin text-text-muted" /> : chart.entries.length === 0 ? (
            <p className="text-sm text-text-secondary">Nothing on file yet. Add history or upload a previous record in Patients, or just carry on: anything you learn today can be typed or dictated in the risk check and is saved to the chart.</p>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {Object.entries(TYPE_LABEL).filter(([type]) => grouped[type]?.length).map(([type, label]) => (
                <div key={type} className="well">
                  <div className="eyebrow mb-2">{label}</div>
                  <div className="flex flex-wrap gap-1.5">
                    {grouped[type].map((e) => (
                      <span key={e.resource_id} className="chip bg-white h-auto py-1">
                        {e.code && <span className="font-semibold text-text-main">{e.code}</span>}
                        <span className="truncate max-w-[220px]">{e.text}{e.value !== null && e.value !== undefined && e.value !== '' ? ` · ${e.value} ${e.unit}` : ''}</span>
                      </span>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          )}
          <button onClick={() => setStep('risk')} className="btn-primary mt-5">Continue to the risk check <ChevronRight className="w-4 h-4" /></button>
        </div>
      )}

      {/* 2. Risk check: starts the visit and remembers what was said */}
      {step === 'risk' && patientId && (
        <div className="animate-fade-in space-y-5">
          <RiskCheckView key={patientId} embedded initialPatientId={patientId}
            initialProcedure={visit?.procedure?.input || ''} initialNotes={visit?.todays_notes || ''}
            onChartChanged={() => api.getPatientChart(patientId).then(setChart).catch(() => {})}
            onChecked={() => refresh(patientId)} />
          {visit?.risk && (
            <div className="card flex flex-wrap items-center gap-3">
              <p className="text-sm text-text-secondary flex-1 min-w-[220px]">The procedure, today's notes and these findings are saved on the visit. The insurance step will start from them.</p>
              <button onClick={() => setStep('procedure')} className="btn-primary">Continue <ChevronRight className="w-4 h-4" /></button>
            </div>
          )}
        </div>
      )}

      {/* 3. Procedure */}
      {step === 'procedure' && visit && (
        <div className="card animate-fade-in">
          <h2 className="font-display text-xl font-medium">{visit.procedure?.label}</h2>
          {visit.risk?.physician_clearance_required && !visit.procedure_done_at && (
            <p className="flex gap-2 mt-3 rounded-2xl bg-danger-light text-danger-dark text-sm px-4 py-3">
              <AlertTriangle className="w-4 h-4 mt-0.5 shrink-0" strokeWidth={1.5} />
              The risk check says physician clearance is needed before this procedure. Do not mark it done until it has actually been carried out.
            </p>
          )}
          {visit.risk?.findings?.length > 0 && (
            <ul className="mt-4 space-y-1.5">
              {visit.risk.findings.map((f) => <li key={f.rule_id} className="flex gap-2 text-sm text-text-main"><span className={`chip h-5 shrink-0 ${HAZARD[f.hazard_level]}`}>{f.hazard_level}</span>{f.contraindication}</li>)}
            </ul>
          )}
          {visit.procedure_done_at ? (
            <div className="flex flex-wrap items-center gap-3 mt-5">
              <span className="chip bg-success-light text-success-dark"><Check className="w-3.5 h-3.5" /> Done {visit.procedure_done_at.slice(0, 10)}</span>
              <button onClick={() => setStep('insurance')} className="btn-primary">Continue to insurance <ChevronRight className="w-4 h-4" /></button>
            </div>
          ) : (
            <div className="mt-5 space-y-3">
              <textarea value={note} onChange={(e) => setNote(e.target.value)} rows={2} placeholder="Optional: anything worth keeping about how it went. It is passed on to the insurance step."
                className="w-full rounded-2xl bg-app-secondary px-4 py-3 text-sm text-text-main placeholder:text-text-muted outline-none focus:bg-white focus:ring-2 focus:ring-accent/30 resize-y" />
              <button onClick={() => act(() => api.markProcedureDone(patientId, note))} disabled={busy} className="btn-primary">
                {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : <Check className="w-4 h-4" />} The procedure has been carried out
              </button>
            </div>
          )}
        </div>
      )}

      {/* 4. Insurance: dental first, then a medical pathway */}
      {step === 'insurance' && visit && (
        <div className="animate-fade-in space-y-5">
          <CoverageRecoveryView key={`${patientId}-${visit.visit_id}`} embedded initialPatientId={patientId} context={context}
            onChecked={() => refresh(patientId)} onDocument={() => refresh(patientId)} />
          {visit.insurance && (
            <div className="card flex flex-wrap items-center gap-3">
              <p className="text-sm text-text-secondary flex-1 min-w-[220px]">
                {visit.insurance.outcome === 'needs_review'
                  ? 'This needs a person to review it. Answer the open questions above and check again, or close the visit and come back to it.'
                  : `${visit.documents?.length ? `${visit.documents.length} document${visit.documents.length > 1 ? 's' : ''} filed to the chart. ` : ''}Insurance is settled for this visit.`}
              </p>
              <button onClick={() => act(() => api.closeVisit(patientId))} disabled={busy} className={visit.insurance.outcome === 'needs_review' ? 'btn-ghost' : 'btn-dark'}>
                <Check className="w-4 h-4" /> {visit.insurance.outcome === 'needs_review' ? 'Close without settling insurance' : 'Close the visit'}
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
