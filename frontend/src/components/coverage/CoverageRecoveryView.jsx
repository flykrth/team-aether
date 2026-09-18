import React, { useCallback, useEffect, useRef, useState } from 'react';
import {
  ShieldQuestion, Loader2, FileUp, RefreshCcw, Quote, ExternalLink, Check, X, HelpCircle, CircleDot, FileText,
  AlertTriangle, ChevronDown, Trash2,
} from 'lucide-react';
import { api } from '../../services/api';
import { VoiceButton } from '../manual/VoiceButton';

const DENTAL = [
  ['active', 'Active'], ['expired', 'Expired'], ['exhausted', 'Annual maximum used up'], ['denied', 'Claim denied'],
  ['none', 'No dental cover'], ['unknown', 'Not entered'],
];
const OUTCOME = {
  dental_active: 'bg-success-light text-success-dark',
  potential_pathway: 'bg-accent-soft text-accent-deep',
  no_pathway: 'bg-app-secondary text-text-main',
  needs_review: 'bg-warning-light text-warning-dark',
  unsupported_region: 'bg-app-secondary text-text-main',
};
const KIND = { supports: 'Supports', excludes: 'Excludes', documentation: 'Documentation', prior_authorization: 'Prior authorization' };
const errText = (err) => err?.detail || err?.message || 'Something went wrong';
const ago = (days) => (days === null || days === undefined ? 'not downloaded' : days === 0 ? 'today' : `${days} day${days === 1 ? '' : 's'} ago`);

function Tri({ label, value, onChange }) {
  const next = value === null || value === undefined ? true : value === true ? false : null;
  const tone = value === true ? 'bg-ink text-white' : value === false ? 'bg-white text-text-muted line-through' : 'bg-white text-text-secondary';
  return (
    <button type="button" onClick={() => onChange(next)} title="Click to cycle: not known / yes / no"
      className={`inline-flex items-center gap-1.5 h-8 px-3 rounded-full text-xs font-medium text-left ${tone}`}>
      {value === true ? <Check className="w-3 h-3 shrink-0" /> : value === false ? <X className="w-3 h-3 shrink-0" /> : <HelpCircle className="w-3 h-3 shrink-0 opacity-50" />}
      <span className="truncate max-w-[260px]">{label}</span>
    </button>
  );
}

function Criterion({ c }) {
  const met = c.kind !== 'supports' ? null : c.met;
  const Icon = met === 'yes' ? Check : met === 'no' ? X : HelpCircle;
  return (
    <div className="well">
      <div className="flex flex-wrap items-center gap-1.5">
        <span className={`chip ${c.kind === 'excludes' ? 'bg-danger-light text-danger-dark' : c.kind === 'supports' ? 'chip-accent' : 'bg-white'}`}>{KIND[c.kind]}</span>
        {met && (
          <span className={`chip ${met === 'yes' ? 'bg-success-light text-success-dark' : met === 'no' ? 'bg-danger-light text-danger-dark' : 'bg-warning-light text-warning-dark'}`}>
            <Icon className="w-3 h-3" /> {met === 'yes' ? 'Met by the chart' : met === 'no' ? 'Not met' : 'Chart does not say'}
          </span>
        )}
        {c.source.is_member_plan && <span className="chip bg-white">Member's own plan</span>}
      </div>
      <p className="text-sm font-medium text-text-main mt-2">{c.requirement}</p>
      {c.fact && <p className="text-xs text-text-secondary mt-1">From the chart: {c.fact}</p>}
      <div className="flex gap-2 mt-3">
        <Quote className="w-3.5 h-3.5 text-text-muted mt-0.5 shrink-0" strokeWidth={1.5} />
        <div className="min-w-0">
          <p className="text-[13px] text-text-main leading-relaxed">{c.quote}</p>
          <p className="text-[11px] text-text-muted mt-1.5">
            {c.source.insurer} · {c.source.title}{c.source.heading ? ` · ${c.source.heading}` : ''}{c.source.review ? ` · ${c.source.review}` : ''}
            {c.source.url && <a href={c.source.url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 ml-2 text-accent-deep hover:underline">source <ExternalLink className="w-3 h-3" /></a>}
          </p>
        </div>
      </div>
    </div>
  );
}

export function CoverageRecoveryView({ initialPatientId }) {
  const [library, setLibrary] = useState(null);
  const [region, setRegion] = useState('US');
  const [patients, setPatients] = useState([]);
  const [patientId, setPatientId] = useState(initialPatientId || '');
  const [insurance, setInsurance] = useState(null);
  const [form, setForm] = useState({ procedure: '', diagnosis: '', imaging: '', clinical_note: '' });
  const [flags, setFlags] = useState({});
  const [result, setResult] = useState(null);
  const [shown, setShown] = useState(0);
  const [busy, setBusy] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState(null);
  const [reviewer, setReviewer] = useState('');
  const [packet, setPacket] = useState(null);
  const [openPassages, setOpenPassages] = useState(false);
  const [serverSpeech, setServerSpeech] = useState(undefined);
  const fileRef = useRef(null);

  const loadLibrary = useCallback((r) => api.getCoverageSources(r).then(setLibrary).catch((e) => setError(errText(e))), []);

  useEffect(() => {
    api.listRecordPatients().then((list) => { setPatients(list); setPatientId((c) => c || list[0]?.patient_id || ''); }).catch((e) => setError(errText(e)));
    api.getAssistantStatus().then((st) => setServerSpeech(Boolean(st?.speech?.configured))).catch(() => setServerSpeech(false));
  }, []);
  useEffect(() => { loadLibrary(region); }, [region, loadLibrary]);
  useEffect(() => {
    if (!patientId) return;
    setResult(null); setPacket(null); setInsurance(null);
    api.getInsurance(patientId).then(setInsurance).catch((e) => setError(errText(e)));
  }, [patientId]);

  // While the embedding index is being built in the background, keep the progress fresh
  useEffect(() => {
    if (library?.index?.state !== 'indexing') return undefined;
    const timer = setInterval(() => loadLibrary(region), 5000);
    return () => clearInterval(timer);
  }, [library?.index?.state, region, loadLibrary]);

  // Replay the path the agent took through the decision tree, one node at a time
  useEffect(() => {
    if (!result) return undefined;
    setShown(0);
    const timer = setInterval(() => setShown((n) => { if (n >= result.steps.length) { clearInterval(timer); return n; } return n + 1; }), 450);
    return () => clearInterval(timer);
  }, [result]);

  const saveInsurance = async (patch) => {
    setError(null);
    try { setInsurance(await api.setInsurance(patientId, patch)); setResult(null); } catch (e) { setError(errText(e)); }
  };
  const uploadPlan = async (file) => {
    if (!file) return;
    setBusy(true); setError(null);
    try { setInsurance(await api.uploadPlanDocument(patientId, file)); setResult(null); } catch (e) { setError(errText(e)); } finally { setBusy(false); }
  };
  const refresh = async () => {
    setRefreshing(true); setError(null);
    try { await api.refreshCoverageSources(region); await loadLibrary(region); } catch (e) { setError(errText(e)); } finally { setRefreshing(false); }
  };
  const run = async () => {
    setBusy(true); setError(null); setPacket(null);
    try {
      const known = Object.fromEntries(Object.entries(flags).filter(([, v]) => v === true || v === false));
      setResult(await api.analyzeCoverage({ patient_id: patientId, region, ...form, flags: known }));
    } catch (e) { setError(errText(e)); } finally { setBusy(false); }
  };
  const makePacket = async () => {
    setError(null);
    try { setPacket(await api.makeCoveragePacket(patientId, reviewer)); } catch (e) { setError(errText(e)); }
  };

  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });
  const dictated = (k) => (text) => setForm((f) => ({ ...f, [k]: f[k]?.trim() ? `${f[k].trimEnd()} ${text}` : text }));
  const supported = library?.regions?.[region]?.supported;
  const done = result && shown >= result.steps.length;
  const determination = result?.determination;
  const cached = (library?.sources || []).filter((s) => s.cached).length;

  return (
    <div className="space-y-5">
      <div className="card">
        <div className="flex flex-wrap items-end gap-4">
          <div className="flex-1 min-w-[240px]">
            <h1 className="display-lg">Coverage recovery</h1>
            <p className="text-sm text-text-muted mt-1">When the dental benefit cannot pay: is there a genuine medical reason, and does this patient's medical plan have a pathway for it?</p>
          </div>
          <label className="block w-36"><span className="eyebrow block mb-1">Region</span>
            <select value={region} onChange={(e) => setRegion(e.target.value)} className="field">
              {Object.entries(library?.regions || { US: { label: 'United States' } }).map(([id, r]) => <option key={id} value={id}>{r.label}</option>)}
            </select>
          </label>
          <label className="block w-full sm:w-72"><span className="eyebrow block mb-1">Patient</span>
            <select value={patientId} onChange={(e) => setPatientId(e.target.value)} className="field">
              {patients.map((p) => <option key={p.patient_id} value={p.patient_id}>{p.name} · {p.patient_id}</option>)}
            </select>
          </label>
        </div>
        {library && !supported && (
          <p className="mt-4 rounded-2xl bg-warning-light text-warning-dark text-sm px-4 py-3">{library.regions[region]?.note} No answer will be guessed for this region.</p>
        )}
      </div>

      {error && <p className="text-sm text-danger-dark bg-danger-light rounded-3xl px-5 py-4">{error}</p>}

      <div className="grid grid-cols-1 xl:grid-cols-12 gap-5 items-start">
        {/* Inputs */}
        <div className="xl:col-span-5 space-y-5">
          <div className="card !p-5">
            <h2 className="font-display text-lg font-medium mb-3">Insurance</h2>
            {!insurance ? <Loader2 className="w-4 h-4 animate-spin text-text-muted" /> : (
              <div className="space-y-3">
                <label className="block"><span className="eyebrow block mb-1">Dental benefit</span>
                  <select value={insurance.dental.status} onChange={(e) => saveInsurance({ dental: { ...insurance.dental, status: e.target.value } })} className="field">
                    {DENTAL.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
                  </select>
                </label>
                <div className="grid grid-cols-2 gap-3">
                  <label className="block"><span className="eyebrow block mb-1">Medical insurer</span>
                    <select value={insurance.medical.insurer} onChange={(e) => saveInsurance({ medical: { ...insurance.medical, insurer: e.target.value } })} className="field">
                      <option value="">Not recorded</option>
                      {(library?.insurers || []).map((i) => <option key={i} value={i}>{i}</option>)}
                      {insurance.medical.insurer && !(library?.insurers || []).includes(insurance.medical.insurer) && <option value={insurance.medical.insurer}>{insurance.medical.insurer}</option>}
                    </select>
                  </label>
                  <label className="block"><span className="eyebrow block mb-1">Plan type</span>
                    <select value={insurance.medical.plan_type} onChange={(e) => saveInsurance({ medical: { ...insurance.medical, plan_type: e.target.value } })} className="field">
                      {['', 'HMO', 'PPO', 'POS', 'EPO', 'Traditional'].map((t) => <option key={t} value={t}>{t || 'Not recorded'}</option>)}
                    </select>
                  </label>
                </div>
                <div className="well !p-3">
                  <input ref={fileRef} type="file" accept=".pdf,.txt,.md,application/pdf,text/plain" className="hidden" onChange={(e) => { uploadPlan(e.target.files?.[0]); e.target.value = ''; }} />
                  {insurance.plan_document ? (
                    <div className="flex items-center gap-3">
                      <FileText className="w-4 h-4 text-text-muted shrink-0" strokeWidth={1.5} />
                      <div className="min-w-0 flex-1"><p className="text-sm text-text-main truncate">{insurance.plan_document.title}</p>
                        <p className="text-[11px] text-text-muted">Member's plan document · {Math.round(insurance.plan_document.chars / 1000)}k characters · kept on this machine</p></div>
                      <button onClick={async () => setInsurance(await api.removePlanDocument(patientId))} className="p-2 rounded-full hover:bg-danger-light text-danger" aria-label="Remove plan document"><Trash2 className="w-4 h-4" strokeWidth={1.5} /></button>
                    </div>
                  ) : (
                    <button onClick={() => fileRef.current?.click()} className="w-full flex items-center gap-3 text-left">
                      <FileUp className="w-4 h-4 text-text-muted shrink-0" strokeWidth={1.5} />
                      <span className="text-sm text-text-secondary">Upload the member's plan document (SBC or Certificate of Coverage). Without it the plan-level question stays open.</span>
                    </button>
                  )}
                </div>
              </div>
            )}
          </div>

          <div className="card !p-5">
            <h2 className="font-display text-lg font-medium mb-3">The case</h2>
            <div className="space-y-3">
              <label className="block"><span className="eyebrow block mb-1">Planned procedure</span>
                <div className="flex items-center gap-2 rounded-full bg-app-secondary pr-1">
                  <input value={form.procedure} onChange={set('procedure')} placeholder="In your own words, or a CDT code" className="field !bg-transparent flex-1" />
                  <VoiceButton onText={dictated('procedure')} serverSpeech={serverSpeech} label="Dictate the procedure" />
                </div>
              </label>
              <label className="block"><span className="eyebrow block mb-1">Diagnosis (ICD-10 if you have it)</span><input value={form.diagnosis} onChange={set('diagnosis')} className="field" placeholder="e.g. impacted mandibular third molar K01.1" /></label>
              <label className="block"><span className="eyebrow block mb-1">Imaging finding</span><input value={form.imaging} onChange={set('imaging')} className="field" placeholder="e.g. completely bony impaction on panoramic radiograph" /></label>
              <div>
                <div className="flex items-center justify-between mb-1"><span className="eyebrow">Clinical note</span><VoiceButton onText={dictated('clinical_note')} serverSpeech={serverSpeech} label="Dictate the clinical note" /></div>
                <textarea value={form.clinical_note} onChange={set('clinical_note')} rows={4} placeholder="Why the procedure is needed: symptoms, cause, what was tried."
                  className="w-full rounded-2xl bg-app-secondary px-4 py-3 text-sm text-text-main placeholder:text-text-muted outline-none focus:bg-white focus:ring-2 focus:ring-accent/30 resize-y" />
              </div>
              <div>
                <span className="eyebrow block mb-2">Medical indications · leave as "?" if nobody has checked</span>
                <div className="flex flex-wrap gap-1.5 rounded-3xl bg-app-secondary p-2">
                  {Object.entries(library?.case_flags || {}).map(([id, label]) => <Tri key={id} label={label} value={flags[id]} onChange={(v) => setFlags({ ...flags, [id]: v })} />)}
                </div>
              </div>
              <button onClick={run} disabled={busy || !patientId || form.procedure.trim().length < 2} className="btn-primary w-full">
                {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : <ShieldQuestion className="w-4 h-4" strokeWidth={1.5} />} Check for a medical pathway
              </button>
            </div>
          </div>
        </div>

        {/* Result */}
        <div className="xl:col-span-7 space-y-5">
          {!result && (
            <div className="card text-sm text-text-secondary">
              <p className="font-display text-lg text-text-main mb-2">What this does, and what it refuses to do</p>
              <p>It starts from the patient's condition, not from the bill. It reads the insurer's published policy and the member's own plan, and shows you their exact words. It will not re-label dental care as medical, and it never says "covered": only the payer decides that.</p>
            </div>
          )}

          {result && (
            <div className="card !p-5">
              <h2 className="font-display text-lg font-medium mb-3">Decision path</h2>
              <ol className="space-y-2">
                {result.steps.slice(0, shown).map((s, i) => (
                  <li key={i} className="flex gap-3 animate-fade-in">
                    <CircleDot className={`w-4 h-4 mt-0.5 shrink-0 ${i === result.steps.length - 1 ? 'text-accent' : 'text-text-muted'}`} strokeWidth={1.5} />
                    <div className="min-w-0"><p className="text-sm font-medium text-text-main">{s.title}{s.branch ? <span className="chip h-5 ml-2 align-middle">{s.branch}</span> : null}</p>
                      <p className="text-[13px] text-text-secondary">{s.detail}</p></div>
                  </li>
                ))}
              </ol>
            </div>
          )}

          {done && (
            <>
              <div className={`rounded-4xl p-6 lg:p-8 animate-fade-in ${OUTCOME[determination.outcome]}`}>
                <div className="text-xs font-medium uppercase tracking-[0.14em] opacity-70">{result.patient_name} · {result.insurance.medical.insurer || 'insurer not recorded'}</div>
                <div className="font-display text-3xl font-medium mt-2 leading-tight">{determination.headline}</div>
                <p className="text-sm mt-2 opacity-90">{determination.reason}</p>
                {result.dropped_ungrounded > 0 && <p className="text-xs mt-3 opacity-80">{result.dropped_ungrounded} statement{result.dropped_ungrounded > 1 ? 's' : ''} from the AI could not be found in the source text and {result.dropped_ungrounded > 1 ? 'were' : 'was'} discarded.</p>}
              </div>

              {result.missing_information?.length > 0 && (
                <div className="card !p-5"><h3 className="font-display text-lg font-medium mb-2">What the chart still needs to answer</h3>
                  <ul className="space-y-1.5">{result.missing_information.map((m) => <li key={m} className="flex gap-2 text-sm text-text-main"><HelpCircle className="w-4 h-4 text-warning mt-0.5 shrink-0" strokeWidth={1.5} />{m}</li>)}</ul>
                </div>
              )}

              {result.criteria?.length > 0 && (
                <div className="card !p-5 space-y-3"><h3 className="font-display text-lg font-medium">What the documents say</h3>
                  {result.criteria.map((c, i) => <Criterion key={i} c={c} />)}
                </div>
              )}

              {result.code_tables?.length > 0 && (
                <div className="card !p-5"><h3 className="font-display text-lg font-medium mb-2">In the payer's own code tables</h3>
                  {result.code_tables.map((t, i) => (
                    <p key={i} className="text-sm text-text-main"><span className="font-mono">{t.code}</span> is listed by {t.insurer} under "{t.listed_under}".
                      <a href={t.url} target="_blank" rel="noreferrer" className="ml-2 text-accent-deep hover:underline text-xs">source</a></p>
                  ))}
                  <p className="text-xs text-text-muted mt-2">A medical procedure code is for a certified coder to choose. None is suggested here.</p>
                </div>
              )}

              {(determination.outcome === 'potential_pathway' || determination.outcome === 'no_pathway') && (
                <div className="card !p-5">
                  <h3 className="font-display text-lg font-medium">{determination.outcome === 'potential_pathway' ? 'Pre-treatment estimate request' : 'Explanation for the patient'}</h3>
                  <p className="text-sm text-text-muted mt-1">{determination.outcome === 'potential_pathway' ? 'A request for a decision before treatment, not a claim. A named person signs it off.' : 'Plain-language reasons, with the insurer\'s wording.'}</p>
                  <div className="flex flex-wrap gap-2 mt-3">
                    {determination.outcome === 'potential_pathway' && <input value={reviewer} onChange={(e) => setReviewer(e.target.value)} placeholder="Reviewed by (name)" className="field flex-1 min-w-[200px]" />}
                    <button onClick={makePacket} disabled={determination.outcome === 'potential_pathway' && reviewer.trim().length < 3} className="btn-dark"><FileText className="w-4 h-4" strokeWidth={1.5} /> Create and file to chart</button>
                  </div>
                  {packet && <pre className="mt-4 well text-xs whitespace-pre-wrap leading-relaxed max-h-96 overflow-y-auto">{packet.content_markdown}</pre>}
                </div>
              )}

              {result.passages?.length > 0 && (
                <div className="card !p-5">
                  <button onClick={() => setOpenPassages(!openPassages)} className="w-full flex items-center justify-between">
                    <h3 className="font-display text-lg font-medium">Passages that were read <span className="text-sm text-text-muted font-sans">· {result.passages.length} · {result.retrieval_mode} search</span></h3>
                    <ChevronDown className={`w-4 h-4 transition-transform ${openPassages ? 'rotate-180' : ''}`} />
                  </button>
                  {openPassages && <div className="space-y-2 mt-3">{result.passages.map((p) => (
                    <div key={p.id} className="well"><p className="text-[11px] text-text-muted">{p.insurer} · {p.heading || p.title} · matched by {p.matched_by.join(', ')}</p><p className="text-[13px] text-text-main mt-1">{p.text}</p></div>
                  ))}</div>}
                </div>
              )}
            </>
          )}

          {/* Library */}
          <div className="card !p-5">
            <div className="flex flex-wrap items-center gap-3">
              <div className="flex-1 min-w-[200px]"><h3 className="font-display text-lg font-medium">Policy library</h3>
                <p className="text-xs text-text-muted">{cached} of {library?.sources?.length || 0} published policies downloaded to this machine. Nothing about coverage is written into the app itself.</p></div>
              <button onClick={refresh} disabled={refreshing || !supported} className="btn-ghost"><RefreshCcw className={`w-4 h-4 ${refreshing ? 'animate-spin' : ''}`} strokeWidth={1.5} /> Refresh sources</button>
            </div>
            {library?.index && (
              <p className="text-xs text-text-muted mt-2">
                Search: {library.index.mode === 'semantic' ? `AI embeddings, ${library.index.indexed} of ${library.index.total} passages indexed` : 'keyword and code matching'}
                {library.index.state === 'indexing' ? ' · indexing in the background' : ''}{library.index.note ? ` · ${library.index.note}` : ''}
              </p>
            )}
            <div className="mt-3 space-y-1">
              {(library?.sources || []).map((s) => (
                <div key={s.id} className="flex items-center gap-3 rounded-2xl bg-app-secondary px-4 py-2.5 text-sm">
                  {s.error ? <AlertTriangle className="w-4 h-4 text-danger shrink-0" strokeWidth={1.5} /> : <Check className={`w-4 h-4 shrink-0 ${s.cached ? 'text-success' : 'text-text-muted'}`} />}
                  <a href={s.url} target="_blank" rel="noreferrer" className="min-w-0 flex-1 truncate text-text-main hover:underline">{s.insurer} · {s.title}</a>
                  <span className="text-[11px] text-text-muted shrink-0 text-right">{s.error ? s.error : `${s.review || 'no review date'} · fetched ${ago(s.age_days)}`}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
