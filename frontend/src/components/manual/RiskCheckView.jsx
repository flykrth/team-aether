import React, { useEffect, useMemo, useRef, useState } from 'react';
import { ShieldAlert, Loader2, Quote, ExternalLink, Sparkles, Check, Stethoscope, Undo2, SpellCheck, HelpCircle, Trash2 } from 'lucide-react';
import { api } from '../../services/api';
import { toApiEntries } from './RecordImporter';
import { VoiceButton } from './VoiceButton';

const HAZARD = {
  LOW: { cls: 'bg-success-light text-success-dark', label: 'Low risk', line: 'Nothing in the history changes how you would normally do this.' },
  MODERATE: { cls: 'bg-warning-light text-warning-dark', label: 'Proceed with precautions', line: 'The history changes how this should be done.' },
  CRITICAL: { cls: 'bg-danger-light text-danger-dark', label: 'Stop · physician clearance first', line: 'Do not proceed until the treating physician has signed off.' },
};
const QUICK = ['Surgical extraction', 'Simple extraction', 'Implant placement', 'Deep cleaning', 'Root canal', 'Routine cleaning'];
const TYPE_ORDER = ['condition', 'medication', 'allergy'];
const errText = (err) => err?.detail || err?.message || 'Something went wrong';

function Chips({ concepts, tone = 'bg-white' }) {
  const sorted = [...concepts].filter((c) => TYPE_ORDER.includes(c.type)).sort((a, b) => TYPE_ORDER.indexOf(a.type) - TYPE_ORDER.indexOf(b.type));
  if (!sorted.length) return <p className="text-sm text-text-muted">Nothing recorded.</p>;
  return (
    <div className="flex flex-wrap gap-1.5">
      {sorted.map((c, i) => (
        <span key={i} className={`chip h-auto py-1 ${tone}`} title={c.type}>
          {c.code && <span className="font-semibold text-text-main">{c.code}</span>}
          <span className="truncate max-w-[220px]">{c.display}</span>
        </span>
      ))}
    </div>
  );
}

export function RiskCheckView({ initialPatientId, onChartChanged, embedded = false, initialProcedure = '', initialNotes = '', onChecked }) {
  const [patients, setPatients] = useState([]);
  const [patientId, setPatientId] = useState(initialPatientId || '');
  const [onFile, setOnFile] = useState(null);
  const [notes, setNotes] = useState(initialNotes);
  const [procedure, setProcedure] = useState(initialProcedure);
  const [result, setResult] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [saved, setSaved] = useState(null);     // null | 'saving' | { items: [{resource_id, text}], undone }
  const [removed, setRemoved] = useState({});   // resource_id -> true once a stopped item was taken off the chart
  const [fixes, setFixes] = useState({ notes: null, procedure: null });     // { original, corrections } shown with undo
  const [doubt, setDoubt] = useState(null);     // { field, text, reason } waiting for the user to confirm or edit
  const [serverSpeech, setServerSpeech] = useState(undefined);

  useEffect(() => {
    api.listRecordPatients().then((list) => {
      setPatients(list);
      setPatientId((current) => current || list[0]?.patient_id || '');
    }).catch((err) => setError(errText(err)));
    api.getAssistantStatus().then((st) => setServerSpeech(Boolean(st?.speech?.configured))).catch(() => setServerSpeech(false));
  }, []);

  useEffect(() => { if (initialPatientId) setPatientId(initialPatientId); }, [initialPatientId]);

  useEffect(() => {
    if (!patientId) return undefined;
    let stale = false;
    setOnFile(null); setResult(null); setSaved(null); setRemoved({}); setDoubt(null);
    api.getPatientChart(patientId)
      .then((chart) => { if (!stale) setOnFile(chart.entries.map((e) => ({ type: e.type, code: e.code, display: e.text }))); })
      .catch(() => { if (!stale) setOnFile([]); });
    return () => { stale = true; };
  }, [patientId]);

  const setters = { notes: setNotes, procedure: setProcedure };
  // Text the user explicitly confirmed despite the warning, per field. Editing the field invalidates it (the text differs).
  const confirmedText = useRef({});

  // Spell-fix and sanity-check one field. Returns the text to use, or null when the user has to decide first.
  const validate = async (field, text) => {
    if (!text.trim()) return text;
    let verdict;
    try { verdict = await api.validateRiskInput(field, text); } catch { return text; } // the check is a convenience, never a blocker
    const clean = verdict.corrected_text;
    if (verdict.corrections.length) {
      setters[field](clean);
      setFixes((f) => ({ ...f, [field]: { original: text, corrections: verdict.corrections } }));
    }
    if (!verdict.in_context && confirmedText.current[field] !== clean) {
      setDoubt({ field, text: clean, reason: verdict.reason });
      return null;
    }
    return clean;
  };

  const runCheck = async () => {
    if (!patientId || !procedure.trim() || busy) return;
    setBusy(true); setError(null); setSaved(null); setDoubt(null); setRemoved({});
    try {
      const cleanProcedure = await validate('procedure', procedure);
      if (cleanProcedure === null) return;
      const cleanNotes = await validate('notes', notes);
      if (cleanNotes === null) return;
      const res = await api.riskCheck({ patient_id: patientId, procedure: cleanProcedure.trim(), current_notes: cleanNotes });
      setResult(res);
      onChecked?.(res);
      // What the doctor learned today belongs on the chart: save it now, visibly, with undo.
      if (res.todays_entries?.length && res.reported_today?.length) {
        setSaved('saving');
        try {
          const written = await api.addHistoryEntries(patientId, toApiEntries(res.todays_entries), 'risk-check');
          setSaved({ items: (written.added || []).map((e) => ({ resource_id: e.resource_id, text: e.display || e.text })), undone: false });
          if (written.added?.length) { onChartChanged?.(patientId); refreshOnFile(patientId); }
        } catch (err) { setSaved(null); setError(`Today's findings were not saved: ${errText(err)}`); }
      }
    } catch (err) { setError(errText(err)); } finally { setBusy(false); }
  };
  const check = () => runCheck();

  const refreshOnFile = (id) => api.getPatientChart(id)
    .then((chart) => setOnFile(chart.entries.map((e) => ({ type: e.type, code: e.code, display: e.text }))))
    .catch(() => {});

  const undoSave = async () => {
    const items = saved?.items || [];
    setSaved('saving');
    try {
      await Promise.all(items.map((i) => api.deleteHistoryEntry(patientId, i.resource_id)));
      setSaved({ items, undone: true }); onChartChanged?.(patientId); refreshOnFile(patientId);
    } catch (err) { setError(errText(err)); setSaved({ items, undone: false }); }
  };

  const removeStopped = async (item) => {
    try {
      await api.deleteHistoryEntry(patientId, item.resource_id);
      setRemoved((r) => ({ ...r, [item.resource_id]: true })); onChartChanged?.(patientId); refreshOnFile(patientId);
    } catch (err) { setError(errText(err)); }
  };

  const undoFix = (field) => { setters[field](fixes[field].original); setFixes((f) => ({ ...f, [field]: null })); };

  // Dictation lands in the field and is checked straight away, because speech-to-text mishears drug names
  const dictated = (field) => async (spoken) => {
    const current = field === 'notes' ? notes : procedure;
    const joined = field === 'notes' && current.trim() ? `${current.trimEnd()} ${spoken}` : spoken;
    setters[field](joined); setFixes((f) => ({ ...f, [field]: null }));
    await validate(field, joined);
  };

  const FixNote = ({ field }) => (fixes[field] ? (
    <p className="flex flex-wrap items-center gap-1.5 text-xs text-text-secondary mt-2">
      <SpellCheck className="w-3.5 h-3.5 text-accent shrink-0" strokeWidth={1.5} />
      Corrected {fixes[field].corrections.map((c) => `${c.from} → ${c.to}`).join(', ')}
      <button onClick={() => undoFix(field)} className="font-medium text-accent-deep hover:underline">Undo correction</button>
    </p>
  ) : null);

  const hazard = result && HAZARD[result.hazard_level];
  const patientName = useMemo(() => patients.find((p) => p.patient_id === patientId)?.name, [patients, patientId]);

  return (
    <div className="space-y-5">
      <div className="card">
        {!embedded && (
        <div className="flex flex-wrap items-end gap-4 mb-6">
          <div className="flex-1 min-w-[220px]">
            <h1 className="display-lg">Risk check</h1>
            <p className="text-sm text-text-muted mt-1">What could be missed before this procedure, for this patient.</p>
          </div>
          <label className="block w-full sm:w-72">
            <span className="eyebrow block mb-1">Patient</span>
            <select value={patientId} onChange={(e) => setPatientId(e.target.value)} className="field">
              {patients.map((p) => <option key={p.patient_id} value={p.patient_id}>{p.name} · {p.patient_id}</option>)}
            </select>
          </label>
        </div>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <div className="well">
            <div className="eyebrow mb-3">History on file</div>
            {onFile === null ? <Loader2 className="w-4 h-4 animate-spin text-text-muted" /> : <Chips concepts={onFile} />}
          </div>
          <div className="well">
            <div className="flex items-center justify-between mb-3">
              <span className="eyebrow">What you learned today</span>
              <VoiceButton onText={dictated('notes')} serverSpeech={serverSpeech} label="Dictate today's notes" />
            </div>
            <textarea value={notes} onChange={(e) => { setNotes(e.target.value); setFixes((f) => ({ ...f, notes: null })); }} rows={4}
              placeholder="e.g. Started warfarin last month after a clot. Allergic to penicillin. Denies diabetes."
              className="w-full rounded-2xl bg-white px-4 py-3 text-sm text-text-main placeholder:text-text-muted outline-none focus:ring-2 focus:ring-accent/30 resize-y" />
            <FixNote field="notes" />
          </div>
        </div>

        <div className="mt-4">
          <span className="eyebrow block mb-2">Planned procedure</span>
          <div className="flex flex-wrap gap-2">
            <div className="flex items-center gap-2 flex-1 min-w-[240px] rounded-full bg-app-secondary pr-1">
              <input value={procedure} onChange={(e) => { setProcedure(e.target.value); setFixes((f) => ({ ...f, procedure: null })); }} onKeyDown={(e) => e.key === 'Enter' && check()}
                placeholder="In your own words, or a CDT code" className="field !bg-transparent flex-1" aria-label="Planned procedure" />
              <VoiceButton onText={dictated('procedure')} serverSpeech={serverSpeech} label="Dictate the procedure" />
            </div>
            <button onClick={check} disabled={busy || !procedure.trim() || !patientId} className="btn-primary">
              {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : <ShieldAlert className="w-4 h-4" strokeWidth={1.5} />} Check risks
            </button>
          </div>
          <FixNote field="procedure" />
          <div className="flex flex-wrap gap-1.5 mt-3">
            {QUICK.map((q) => <button key={q} onClick={() => setProcedure(q)} className="chip hover:bg-app-bg">{q}</button>)}
          </div>
        </div>
        {doubt && (
          <div className="mt-4 rounded-3xl bg-warning-light text-warning-dark p-4 animate-fade-in" role="alertdialog" aria-label="Confirm input">
            <div className="flex gap-3">
              <HelpCircle className="w-4 h-4 mt-0.5 shrink-0" strokeWidth={1.5} />
              <div className="min-w-0">
                <p className="text-sm font-medium">
                  {doubt.field === 'procedure' ? 'That does not sound like a dental procedure.' : 'That does not sound like a clinical note.'}
                </p>
                <p className="text-sm mt-1 break-words">“{doubt.text}”{doubt.reason ? ` · ${doubt.reason}` : ''}</p>
                <div className="flex flex-wrap gap-2 mt-3">
                  <button onClick={() => { confirmedText.current[doubt.field] = doubt.text; if (procedure.trim()) runCheck(); else setDoubt(null); }} className="btn-dark !h-9 !text-sm">Use it anyway</button>
                  <button onClick={() => setDoubt(null)} className="btn-ghost !h-9 !text-sm !bg-white">Let me fix it</button>
                  {doubt.field === 'notes' && <button onClick={() => { setNotes(''); setDoubt(null); }} className="btn-ghost !h-9 !text-sm !bg-white">Discard the note</button>}
                </div>
              </div>
            </div>
          </div>
        )}
        {error && <p className="text-sm text-danger-dark bg-danger-light rounded-2xl px-4 py-3 mt-4">{error}</p>}
      </div>

      {result && (
        <div className="space-y-5 animate-fade-in">
          <div className={`rounded-4xl p-6 lg:p-8 ${hazard.cls}`}>
            <div className="text-xs font-medium uppercase tracking-[0.14em] opacity-70">
              {patientName} · {result.procedure.label} · {result.procedure.cdt_code}
            </div>
            <div className="font-display text-3xl font-medium mt-2 leading-tight">{hazard.label}</div>
            <p className="text-sm mt-2 opacity-90">{hazard.line}</p>
            {!result.procedure.matched && <p className="text-sm mt-2 opacity-90">"{result.procedure.input}" was not recognised, so it was assessed as a surgical procedure to be safe.</p>}
            {!result.record_found && <p className="text-sm mt-2 opacity-90">No medical record is linked to this patient: this result only reflects today's notes.</p>}
          </div>

          {(result.reported_today.length > 0 || result.excluded_from_notes.length > 0) && (
            <div className="card !p-5">
              {result.reported_today.length > 0 && (
                <div className="flex flex-wrap items-center gap-3">
                  <div className="flex-1 min-w-[200px]">
                    <div className="eyebrow mb-2">
                      {saved?.undone ? 'Learned today · not saved' : saved?.items ? 'Learned today · added to the chart' : 'Learned today'}
                    </div>
                    <Chips concepts={result.reported_today} tone="bg-accent-soft text-accent-deep" />
                  </div>
                  {saved === 'saving' && <Loader2 className="w-4 h-4 animate-spin text-text-muted" />}
                  {saved?.items && !saved.undone && (
                    <span className="inline-flex items-center gap-2">
                      <span className="chip bg-success-light text-success-dark"><Check className="w-3.5 h-3.5" /> In medications and history</span>
                      <button onClick={undoSave} className="btn-ghost !h-8 !px-3 !text-sm"><Undo2 className="w-3.5 h-3.5" /> Remove from chart</button>
                    </span>
                  )}
                </div>
              )}
              {(result.suggested_removals || []).map((item) => (
                <div key={item.resource_id} className="flex flex-wrap items-center gap-3 mt-4 rounded-2xl bg-warning-light text-warning-dark px-4 py-3">
                  <p className="text-sm flex-1 min-w-[200px]">
                    You said the patient stopped <span className="font-medium">{item.text}</span>, but it is still on the chart.
                  </p>
                  {removed[item.resource_id]
                    ? <span className="chip bg-white"><Check className="w-3.5 h-3.5" /> Removed</span>
                    : <button onClick={() => removeStopped(item)} className="btn-dark !h-8 !px-3 !text-sm"><Trash2 className="w-3.5 h-3.5" /> Remove from chart</button>}
                </div>
              ))}
              {result.excluded_from_notes.length > 0 && (
                <p className="text-xs text-text-muted mt-3">Not added: {result.excluded_from_notes.map((e) => `${e.display || e.text} (${e.reason})`).join(', ')}.</p>
              )}
            </div>
          )}

          {result.findings.map((f) => (
            <div key={f.rule_id} className="card">
              <div className="flex flex-wrap items-center gap-2">
                <span className={`chip ${HAZARD[f.hazard_level].cls}`}>{f.hazard_level}</span>
                {f.from_todays_notes && <span className="chip chip-accent">From today's notes</span>}
              </div>
              <h3 className="font-display text-xl font-medium mt-3 leading-snug">{f.contraindication}</h3>
              <ul className="mt-3 space-y-2">
                {f.recommendations.map((r) => (
                  <li key={r} className="flex gap-3 text-sm text-text-main leading-relaxed"><Check className="w-4 h-4 text-accent mt-0.5 shrink-0" />{r}</li>
                ))}
              </ul>
              {f.literature?.length > 0 && (
                <div className="mt-5 space-y-2">
                  <div className="eyebrow">From the literature</div>
                  {f.literature.map((l) => (
                    <a key={l.url} href={l.url} target="_blank" rel="noreferrer" className="block well hover:bg-app-bg transition-colors">
                      <div className="flex gap-3">
                        <Quote className="w-4 h-4 text-text-muted mt-0.5 shrink-0" strokeWidth={1.5} />
                        <div className="min-w-0">
                          <p className="text-sm text-text-main leading-relaxed">{l.quote}</p>
                          <p className="text-xs text-text-muted mt-2 flex items-center gap-1.5">
                            <span className="truncate">{l.title}. {l.journal} {l.year}</span>
                            <ExternalLink className="w-3 h-3 shrink-0" />
                          </p>
                        </div>
                      </div>
                    </a>
                  ))}
                </div>
              )}
            </div>
          ))}

          {result.findings.length === 0 && <div className="card text-sm text-text-secondary">No rule fired for this history and procedure.</div>}

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
            {result.second_look && (
              <div className="card">
                <div className="flex items-center gap-2"><Sparkles className="w-4 h-4 text-accent" strokeWidth={1.5} /><h3 className="font-display text-lg font-medium">Second look</h3></div>
                <p className="text-xs text-text-muted mt-1">AI suggestions. Not verified by the rule engine: use your judgement.</p>
                <ul className="mt-3 space-y-2">
                  {result.second_look.points.map((p) => <li key={p} className="text-sm text-text-main leading-relaxed">{p}</li>)}
                </ul>
              </div>
            )}
            <div className="card space-y-4">
              {result.physician_clearance_required && (
                <div className="flex gap-3">
                  <Stethoscope className="w-4 h-4 text-text-muted mt-0.5 shrink-0" strokeWidth={1.5} />
                  <p className="text-sm text-text-main">Clearance is required. Ask the assistant to run the agents: it requests clearance from the treating physician and tracks the reply.</p>
                </div>
              )}
              <p className="text-sm text-text-muted">Insurance questions are answered in Coverage recovery, from the payer's published policy. A risky medical history is not a reason to bill medical.</p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
