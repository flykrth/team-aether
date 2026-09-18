import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  ClipboardList, ShieldAlert, Stethoscope, Receipt, Play, RotateCcw, Send, BellRing, Check, Loader2,
  CalendarClock, ArrowRight, MessageSquare, AlertTriangle, FileText, PiggyBank, CheckCircle2, Minus,
} from 'lucide-react';
import { api } from '../services/api';

// Backend runs the whole graph in a few milliseconds; reveal it at a pace a room can follow.
const REVEAL_MS = 650;

const SCENARIOS = [
  { id: 'CS-9921', cdt: 'D7210', label: 'Robert Chen', note: 'Recent coronary stent · surgical extraction D7210' },
  { id: 'walk-in-demo', cdt: 'D7210', label: 'Walk-in, no portal', note: 'Conversational intake · alendronate + stent' },
  { id: 'pat-1', cdt: 'D7140', label: 'John Doe', note: 'Warfarin + AFib · extraction D7140' },
  { id: 'CS-2002', cdt: 'D1110', label: 'Jane Smith', note: 'Prophylaxis D1110 · no clearance needed' },
];

const AGENTS = [
  { node: 'intake_agent', name: 'Intake Agent', role: 'Links the medical record, normalizes to ICD-10 / RxNorm', Icon: ClipboardList },
  { node: 'risk_agent', name: 'Clinical Risk Agent', role: 'Weighs the procedure against systemic risk', Icon: ShieldAlert },
  { node: 'clearance_agent', name: 'Medical Clearance Agent', role: 'Gets the physician sign-off over FHIR', Icon: Stethoscope },
  { node: 'billing_agent', name: 'Commercial Billing Agent', role: 'Cross-bills medical, builds CMS-1500 + LOMN', Icon: Receipt },
];
const AGENT_BY_NAME = Object.fromEntries(AGENTS.map((a) => [a.name, a]));

const LOG_ICONS = {
  'message-square': MessageSquare, 'arrow-right': ArrowRight, 'alert-triangle': AlertTriangle, send: Send,
  'bell-ring': BellRing, 'check-circle': CheckCircle2, 'file-text': FileText, 'piggy-bank': PiggyBank,
};

const DEFAULT_REPLY =
  'Cleared for extractions, keep epinephrine minimal, limit to 2 carpules 1:100k epi, maintain Aspirin';

const TILE = {
  SCHEDULED: { label: 'Scheduled', cls: 'bg-app-secondary text-text-secondary', dot: 'bg-ink-muted' },
  REQUIRES_ACTION: { label: 'On hold · requires action', cls: 'bg-warning-light text-warning-dark', dot: 'bg-warning' },
  CLEARED_FOR_CARE: { label: 'Cleared for care', cls: 'bg-success-light text-success-dark', dot: 'bg-success' },
};

const HAZARD_CLS = {
  LOW: 'bg-success-light text-success-dark',
  MODERATE: 'bg-warning-light text-warning-dark',
  CRITICAL: 'bg-danger-light text-danger-dark',
};

const pretty = (s) => (s || '').replace(/_/g, ' ').toLowerCase().replace(/^\w/, (c) => c.toUpperCase());
const clock = (iso) => (iso ? new Date(iso).toLocaleTimeString([], { hour12: false }) : '');

function AgentNode({ agent, status }) {
  const { Icon } = agent;
  const tone = {
    idle: 'bg-app-secondary text-text-muted',
    running: 'bg-accent text-white',
    done: 'bg-ink text-white',
    skipped: 'bg-app-secondary text-text-muted opacity-60',
  }[status];
  return (
    <div className={`rounded-3xl p-4 transition-colors duration-300 ${tone}`}>
      <div className="flex items-center gap-3">
        <span className={`inline-flex items-center justify-center w-10 h-10 rounded-full shrink-0 ${status === 'idle' || status === 'skipped' ? 'bg-white text-text-muted' : 'bg-white/15'}`}>
          <Icon className="w-5 h-5" strokeWidth={1.5} />
        </span>
        <div className="min-w-0 flex-1">
          <div className="font-display font-medium text-[15px] leading-tight truncate">{agent.name}</div>
          <div className="text-xs opacity-70 leading-snug mt-0.5">{agent.role}</div>
        </div>
        <span className="shrink-0">
          {status === 'running' && <Loader2 className="w-4 h-4 animate-spin" />}
          {status === 'done' && <Check className="w-4 h-4" />}
          {status === 'skipped' && <Minus className="w-4 h-4" />}
        </span>
      </div>
    </div>
  );
}

function Panel({ title, Icon, children, empty }) {
  return (
    <div className="well">
      <div className="flex items-center gap-2 mb-3">
        <Icon className="w-4 h-4 text-text-muted" strokeWidth={1.5} />
        <span className="eyebrow">{title}</span>
      </div>
      {empty ? <p className="text-sm text-text-muted">{empty}</p> : children}
    </div>
  );
}

const Row = ({ k, children }) => (
  <div className="flex items-baseline justify-between gap-4 py-1 text-sm">
    <span className="text-text-muted shrink-0">{k}</span>
    <span className="text-text-main text-right font-medium min-w-0">{children}</span>
  </div>
);

export function AgentOpsDashboard() {
  const [scenario, setScenario] = useState(SCENARIOS[0]);
  const [state, setState] = useState(null);      // MAOState as revealed so far
  const [logs, setLogs] = useState([]);          // revealed reasoning steps
  const [doneNodes, setDoneNodes] = useState([]);
  const [phase, setPhase] = useState('idle');    // idle | running | complete | failed
  const [reply, setReply] = useState(DEFAULT_REPLY);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  const queue = useRef([]);
  const seenLogs = useRef(0);
  const source = useRef(null);
  const feedEnd = useRef(null);

  // Every state snapshot (SSE step or POST response) is turned into: its new logs, one by one, then the state.
  const enqueueState = useCallback((next, node) => {
    const all = next?.agent_logs || [];
    all.slice(seenLogs.current).forEach((log) => queue.current.push({ log }));
    seenLogs.current = Math.max(seenLogs.current, all.length);
    queue.current.push({ state: next, node });
  }, []);

  useEffect(() => {
    const timer = setInterval(() => {
      // State snapshots apply immediately; only reasoning lines are paced.
      let item = queue.current.shift();
      while (item && !item.log) {
        // Capture before the loop reassigns `item`: React runs these updaters later.
        const { state: nextState, node, phase: nextPhase } = item;
        if (nextState) setState(nextState);
        if (node) setDoneNodes((d) => (d.includes(node) ? d : [...d, node]));
        if (nextPhase) setPhase(nextPhase);
        item = queue.current.shift();
      }
      if (item?.log) {
        const { log } = item;
        setLogs((l) => [...l, log]);
      }
    }, REVEAL_MS);
    return () => clearInterval(timer);
  }, []);

  useEffect(() => { feedEnd.current?.scrollIntoView({ behavior: 'smooth', block: 'nearest' }); }, [logs]);
  useEffect(() => () => source.current?.close(), []);

  const reset = useCallback(() => {
    source.current?.close();
    queue.current = [];
    seenLogs.current = 0;
    setState(null); setLogs([]); setDoneNodes([]); setPhase('idle'); setError(null); setReply(DEFAULT_REPLY);
  }, []);

  const runAct1 = async () => {
    reset();
    setPhase('running');
    try {
      await api.submitAgentEvent({ event_type: 'appointment.booked', patient_id: scenario.id, cdt_codes: [scenario.cdt] });
      const es = new EventSource(api.agentStreamUrl(scenario.id));
      source.current = es;
      es.addEventListener('agent_step', (e) => {
        const evt = JSON.parse(e.data);
        enqueueState(evt.data.state, evt.node);
      });
      es.addEventListener('thread_completed', () => { queue.current.push({ phase: 'complete' }); es.close(); });
      es.addEventListener('thread_failed', (e) => {
        setError(JSON.parse(e.data).data?.error || 'Supervisor thread failed');
        queue.current.push({ phase: 'failed' }); es.close();
      });
      es.onerror = () => {
        if (es.readyState === EventSource.CLOSED) return;
        es.close();
        setError('Lost the agent stream. Is the backend running with the /api/agents routes?');
        setPhase('failed');
      };
    } catch (err) {
      setError(`Could not reach the agent supervisor (${err.message}).`);
      setPhase('failed');
    }
  };

  const followUp = async (call) => {
    setBusy(true); setError(null);
    try {
      const res = await call();
      if (res?.state) enqueueState(res.state);
      else if (res?.escalated) enqueueState((await api.getAgentState(scenario.id)).state);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  const running = useMemo(() => {
    const last = logs[logs.length - 1];
    const node = last && AGENT_BY_NAME[last.agent_name]?.node;
    return node && !doneNodes.includes(node) ? node : null;
  }, [logs, doneNodes]);

  const statusOf = (node) => {
    if (doneNodes.includes(node)) return 'done';
    if (running === node) return 'running';
    if (phase === 'complete') return 'skipped';
    return 'idle';
  };

  const appt = state?.appointment?.status || 'SCHEDULED';
  const tile = TILE[appt] || TILE.SCHEDULED;
  const risk = state?.risk_evaluations?.[state.risk_evaluations.length - 1];
  const protocol = state?.clearance_protocol || {};
  const claims = state?.commercial_claims || {};
  const md = state?.assigned_medical_md || {};
  const awaitingReply = phase === 'complete' && state?.clearance_status === 'TRANSMITTED_TO_EHR';
  const act = appt === 'CLEARED_FOR_CARE' ? 3 : awaitingReply ? 2 : 1;

  return (
    <div className="space-y-8 animate-fade-in">
      {/* Control deck */}
      <section className="card-dark">
        <div className="flex flex-col xl:flex-row xl:items-end gap-8">
          <div className="flex-1 min-w-0">
            <div className="eyebrow !text-white/50">Multi-Agent Orchestrator · Live Ops</div>
            <h1 className="display-lg mt-2">Four agents working the chart while the front desk does something else.</h1>
            <div className="flex flex-wrap gap-2 mt-6">
              {SCENARIOS.map((s) => (
                <button
                  key={s.id}
                  onClick={() => { setScenario(s); reset(); }}
                  disabled={phase === 'running'}
                  title={s.note}
                  className={`h-9 px-4 rounded-full text-sm font-medium transition-colors ${scenario.id === s.id ? 'bg-white text-ink' : 'bg-white/10 text-white/70 hover:text-white'}`}
                >
                  {s.label}
                </button>
              ))}
            </div>
            <p className="text-sm text-white/50 mt-3">{scenario.note}</p>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            <button onClick={runAct1} disabled={phase === 'running'} className="btn-primary">
              {phase === 'running' ? <Loader2 className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4" />}
              <span>{phase === 'idle' ? 'Book appointment' : 'Book again'}</span>
            </button>
            <button onClick={reset} className="icon-btn-white" title="Reset" aria-label="Reset demo">
              <RotateCcw className="w-[18px] h-[18px]" strokeWidth={1.5} />
            </button>
          </div>
        </div>
        <div className="grid grid-cols-3 gap-2 mt-8">
          {['Act 1 · The invisible work', 'Act 2 · The physician loop', 'Act 3 · The financial payoff'].map((label, i) => (
            <div key={label} className={`rounded-full h-9 px-4 flex items-center text-xs font-medium truncate ${phase !== 'idle' && act >= i + 1 ? 'bg-accent text-white' : 'bg-white/10 text-white/50'}`}>
              {label}
            </div>
          ))}
        </div>
      </section>

      {error && (
        <div className="rounded-3xl bg-danger-light text-danger-dark px-5 py-4 text-sm flex items-start gap-3">
          <AlertTriangle className="w-4 h-4 mt-0.5 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* State graph + schedule tile */}
      <section className="card">
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-4 items-stretch">
          <div className="lg:col-span-9 grid grid-cols-1 md:grid-cols-3 gap-4 items-center">
            <AgentNode agent={AGENTS[0]} status={statusOf('intake_agent')} />
            <AgentNode agent={AGENTS[1]} status={statusOf('risk_agent')} />
            <div className="space-y-3">
              <AgentNode agent={AGENTS[2]} status={statusOf('clearance_agent')} />
              <AgentNode agent={AGENTS[3]} status={statusOf('billing_agent')} />
              <p className="text-[11px] text-text-muted px-2">Clearance and billing run in parallel. Clearance only fires on a critical hazard.</p>
            </div>
          </div>
          <div className={`lg:col-span-3 rounded-3xl p-5 flex flex-col justify-between transition-colors duration-500 ${tile.cls}`}>
            <div className="flex items-center gap-2 text-xs font-medium uppercase tracking-[0.14em] opacity-70">
              <CalendarClock className="w-4 h-4" strokeWidth={1.5} /> Schedule tile
            </div>
            <div className="mt-6">
              <div className="font-display text-xl font-medium leading-tight">{state?.patient_name || scenario.label}</div>
              <div className="text-sm opacity-80 mt-1">{scenario.cdt} · Operatory 3</div>
              <div className="flex items-center gap-2 mt-4 text-sm font-medium">
                <span className={`w-2 h-2 rounded-full ${tile.dot} ${appt === 'REQUIRES_ACTION' ? 'animate-pulse' : ''}`} />
                {tile.label}
              </div>
              {state?.appointment?.front_desk_flag && <div className="text-xs mt-2 opacity-80">Front desk flagged: clearance overdue</div>}
            </div>
          </div>
        </div>
      </section>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
        {/* Reasoning feed */}
        <section className="card lg:col-span-5">
          <div className="flex items-center justify-between mb-4">
            <h2 className="font-display text-xl font-medium">Agent reasoning</h2>
            <span className="chip">{logs.length} steps</span>
          </div>
          <div className="space-y-2 max-h-[560px] overflow-y-auto pr-1">
            {logs.length === 0 && (
              <p className="text-sm text-text-muted py-10 text-center">Book the appointment. Nobody has to click anything after that.</p>
            )}
            {logs.map((log, i) => {
              const Icon = LOG_ICONS[log.icon] || AGENT_BY_NAME[log.agent_name]?.Icon || ArrowRight;
              return (
                <div key={i} className="well animate-fade-in">
                  <div className="flex items-start gap-3">
                    <span className="inline-flex items-center justify-center w-8 h-8 rounded-full bg-white text-ink shrink-0">
                      <Icon className="w-4 h-4" strokeWidth={1.5} />
                    </span>
                    <div className="min-w-0 flex-1">
                      <div className="flex items-baseline justify-between gap-3">
                        <span className="text-xs text-text-muted truncate">{log.agent_name}</span>
                        <span className="text-[11px] text-text-muted tabular-nums shrink-0">{clock(log.timestamp)}</span>
                      </div>
                      <div className="text-sm font-medium text-text-main mt-0.5">{log.action}</div>
                      {log.details && <div className="text-[13px] text-text-secondary mt-1 leading-relaxed break-words">{log.details}</div>}
                    </div>
                  </div>
                </div>
              );
            })}
            <div ref={feedEnd} />
          </div>
        </section>

        {/* Shared state */}
        <section className="card lg:col-span-7">
          <div className="flex items-center justify-between mb-4">
            <h2 className="font-display text-xl font-medium">Shared state</h2>
            {state && <span className="chip">{pretty(state.intake_status)}</span>}
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <Panel title="Medical record" Icon={ClipboardList} empty={!state?.medical_records?.normalized_concepts?.length && 'Waiting for intake.'}>
              <div className="flex flex-wrap gap-1.5">
                {(state?.medical_records?.normalized_concepts || []).map((c, i) => (
                  <span key={i} className="chip bg-white h-auto py-1" title={c.source === 'conversational' ? `From intake: "${c.evidence}"` : 'From FHIR record'}>
                    <span className="font-semibold text-text-main">{c.code}</span>
                    <span className="truncate max-w-[180px]">{c.display}</span>
                  </span>
                ))}
              </div>
            </Panel>

            <Panel title="Risk evaluation" Icon={ShieldAlert} empty={!risk && 'Waiting for the risk agent.'}>
              {risk && (
                <>
                  <span className={`chip ${HAZARD_CLS[risk.hazard_level]}`}>{risk.hazard_level} · {risk.cdt_code}</span>
                  <ul className="mt-3 space-y-2">
                    {risk.contraindications.map((c) => <li key={c} className="text-[13px] text-text-main leading-snug">{c}</li>)}
                    {risk.contraindications.length === 0 && <li className="text-[13px] text-text-muted">No systemic contraindications.</li>}
                  </ul>
                </>
              )}
            </Panel>

            <Panel title="Medical clearance" Icon={Stethoscope} empty={!state && 'Waiting for the risk agent.'}>
              {state && (
                <>
                  <Row k="Status">{pretty(state.clearance_status)}</Row>
                  {md.name && <Row k="Physician">{md.name}<span className="block text-xs font-normal text-text-muted">{md.facility}</span></Row>}
                  {protocol.escalation && <Row k="Escalation">Nudge SMS sent · {protocol.escalation.hours_without_response}h</Row>}
                  {(protocol.restrictions || []).length > 0 && (
                    <div className="flex flex-wrap gap-1.5 mt-2">
                      {protocol.restrictions.map((r) => <span key={r} className="chip chip-accent">{pretty(r)}</span>)}
                    </div>
                  )}
                  {protocol.requires_staff_review && <p className="text-[13px] text-danger-dark mt-2">Reply was not a clear approval. Left on hold for staff review.</p>}
                </>
              )}
            </Panel>

            <Panel title="Medical cross-billing" Icon={Receipt} empty={!doneNodes.includes('billing_agent') && 'Waiting for the billing agent.'}>
              {state?.cross_bill_eligible ? (
                <>
                  <div className="font-display text-4xl font-medium tracking-tight text-text-main">
                    ${Number(claims.estimated_savings || 0).toLocaleString()}
                  </div>
                  <div className="text-xs text-text-muted mb-2">of the dental annual maximum preserved (estimate)</div>
                  <Row k="CPT">{claims.suggested_cpt}</Row>
                  <Row k="Justified by">{(claims.justifying_icd10 || []).join(', ')}</Row>
                  <Row k="CMS-1500">{claims.cms1500_ready ? 'Boxes 1-33 ready' : 'Not ready'}</Row>
                  <Row k="LOMN">{claims.lomn_document_id || 'Not attached'}</Row>
                </>
              ) : (
                <p className="text-sm text-text-muted">No qualifying medical diagnosis. Claim stays with the dental carrier.</p>
              )}
            </Panel>
          </div>

          {/* Act 2: the physician answers */}
          {awaitingReply && (
            <div className="mt-6 rounded-3xl bg-accent-soft p-5 animate-fade-in">
              <div className="eyebrow !text-accent-deep">Act 2 · {md.name || 'The physician'} replies from their EHR inbox</div>
              <textarea
                value={reply}
                onChange={(e) => setReply(e.target.value)}
                rows={2}
                className="mt-3 w-full rounded-2xl bg-white px-4 py-3 text-sm text-text-main outline-none focus:ring-2 focus:ring-accent/30 resize-none"
              />
              <div className="flex flex-wrap gap-2 mt-3">
                <button onClick={() => followUp(() => api.sendClearanceResponse(scenario.id, reply))} disabled={busy || !reply.trim()} className="btn-primary">
                  <Send className="w-4 h-4" /> <span>Send physician reply</span>
                </button>
                {!protocol.escalation && (
                  <button onClick={() => followUp(() => api.checkAgentEscalations(50))} disabled={busy} className="btn-ghost !bg-white">
                    <BellRing className="w-4 h-4" strokeWidth={1.5} /> <span>Or: 48 hours of silence</span>
                  </button>
                )}
              </div>
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
