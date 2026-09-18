import React from 'react';
import { Workflow, ClipboardList, ShieldAlert, Stethoscope, Receipt, Check, Minus, CalendarClock, PiggyBank, FileText } from 'lucide-react';
import { WidgetShell, Inner, Group, Badge, ConceptChips, Fact, Notice, failureMessage, asList, pretty, money, HAZARD_CLS, APPOINTMENT_TILE } from './parts';

const AGENTS = [
  { name: 'Intake Agent', short: 'Intake', Icon: ClipboardList },
  { name: 'Clinical Risk Agent', short: 'Risk', Icon: ShieldAlert },
  { name: 'Medical Clearance Agent', short: 'Clearance', Icon: Stethoscope },
  { name: 'Commercial Billing Agent', short: 'Billing', Icon: Receipt },
];

const CLEARANCE_CLS = {
  NOT_REQUIRED: 'bg-app-secondary text-text-secondary',
  REQUIRED_PENDING: 'bg-warning-light text-warning-dark',
  TRANSMITTED_TO_EHR: 'bg-accent-soft text-accent-deep',
  APPROVED_WITH_CONDITIONS: 'bg-success-light text-success-dark',
  CLEARED: 'bg-success-light text-success-dark',
};

export function AgentWorkflowWidget({ data, title }) {
  const failure = failureMessage(data);
  if (failure) return <Notice Icon={Workflow} title={title || 'Agent workflow'} message={failure} />;

  const log = asList(data.agent_log).map(String);
  const ran = (agent) => log.filter((line) => line.startsWith(`${agent.name}:`));
  const appointment = data.appointment || {};
  const tile = APPOINTMENT_TILE[appointment.status] || APPOINTMENT_TILE.SCHEDULED;
  const evaluations = asList(data.risk_evaluations);
  // The backend sends an all-empty physician object when no clearance was needed
  const physician = data.assigned_physician?.name ? data.assigned_physician : null;
  const protocol = data.clearance_protocol || {};
  const restrictions = asList(protocol.restrictions);
  const claims = data.commercial_claims || {};
  const hasClaim = Boolean(claims.suggested_cpt);

  return (
    <WidgetShell
      Icon={Workflow}
      title={title || 'Agent workflow'}
      subtitle={[data.patient_name, data.patient_id, asList(appointment.cdt_codes).join(', ')].filter(Boolean).join(' · ')}
      badge={data.thread_status && <Badge cls={data.error ? 'bg-danger-light text-danger-dark' : 'bg-app-secondary text-text-secondary'}>{pretty(data.thread_status)}</Badge>}
    >
      {data.error && <p className="rounded-2xl bg-danger-light text-danger-dark text-[13px] p-3">{String(data.error)}</p>}

      {/* four-agent status strip */}
      <div className="grid grid-cols-4 gap-1.5">
        {AGENTS.map((agent) => {
          const lines = ran(agent);
          const done = lines.length > 0;
          return (
            <div key={agent.name} title={lines.join('\n') || 'Did not run'}
              className={`rounded-2xl px-2 py-2.5 flex flex-col items-center gap-1.5 text-center ${done ? 'bg-ink text-white' : 'bg-app-secondary text-text-muted'}`}>
              <agent.Icon className="w-4 h-4" strokeWidth={1.5} />
              <span className="text-[11px] font-medium leading-none">{agent.short}</span>
              {done ? <Check className="w-3 h-3 opacity-70" /> : <Minus className="w-3 h-3 opacity-50" />}
            </div>
          );
        })}
      </div>

      {/* appointment tile, coloured by status */}
      <div className={`rounded-2xl p-3 flex items-center gap-3 ${tile.cls}`}>
        <CalendarClock className="w-4 h-4 shrink-0" strokeWidth={1.5} />
        <div className="min-w-0 flex-1">
          <div className="text-[13px] font-medium flex items-center gap-2">
            <span className={`w-1.5 h-1.5 rounded-full ${tile.dot}`} />{tile.label}
          </div>
          <div className="text-[11px] opacity-80 mt-0.5">
            Appointment{asList(appointment.cdt_codes).length ? ` · ${asList(appointment.cdt_codes).join(', ')}` : ''}{appointment.operatory ? ` · ${appointment.operatory}` : ''}
          </div>
        </div>
        {data.clearance_status && <Badge cls={CLEARANCE_CLS[data.clearance_status] || 'bg-white/60 text-text-secondary'}>{pretty(data.clearance_status)}</Badge>}
      </div>

      {evaluations.map((e, i) => (
        <Group key={i} label={`Risk · ${e.cdt_code || ''}`}>
          <div className="flex items-start gap-2.5">
            <Badge cls={HAZARD_CLS[e.hazard_level] || HAZARD_CLS.LOW}>{e.hazard_level}</Badge>
            <p className="text-[13px] leading-snug text-text-main min-w-0">
              {asList(e.contraindications)[0] || 'No systemic contraindications found.'}
              {asList(e.contraindications).length > 1 && <span className="text-text-muted"> +{asList(e.contraindications).length - 1} more</span>}
            </p>
          </div>
        </Group>
      ))}

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
        {physician && (
          <Inner>
            <div className="eyebrow mb-2 flex items-center gap-1.5"><Stethoscope className="w-3 h-3" /> Physician</div>
            <div className="text-[13px] font-medium text-ink">{physician.name}</div>
            <div className="text-xs text-text-secondary mt-0.5">{[physician.specialty, physician.facility].filter(Boolean).join(' · ')}</div>
            {physician.npi && <div className="font-mono text-[10px] text-text-muted mt-1">NPI {physician.npi}</div>}
            {protocol.signed_by && <div className="text-[11px] text-success-dark mt-1">Signed by {protocol.signed_by}</div>}
          </Inner>
        )}
        {hasClaim && (
          <Inner>
            <div className="eyebrow mb-2 flex items-center gap-1.5"><PiggyBank className="w-3 h-3" /> Medical cross-billing</div>
            <div className="flex items-baseline gap-2">
              <span className="font-display text-xl font-medium text-ink">{money(claims.estimated_savings) || '—'}</span>
              <span className="text-[11px] text-text-muted">estimated patient savings</span>
            </div>
            <div className="grid grid-cols-2 gap-2 mt-2">
              <Fact label="CPT" value={[claims.suggested_cpt, claims.alternate_cpt].filter(Boolean).join(' / ')} mono />
              <Fact label="ICD-10" value={asList(claims.justifying_icd10).join(', ')} mono />
            </div>
            <div className="flex flex-wrap gap-1.5 mt-2">
              {claims.cms1500_ready && <Badge cls="bg-success-light text-success-dark"><Check className="w-3 h-3" />CMS-1500</Badge>}
              {claims.lomn_attached && <Badge cls="bg-success-light text-success-dark"><FileText className="w-3 h-3" />LOMN attached</Badge>}
            </div>
          </Inner>
        )}
      </div>

      {(restrictions.length > 0 || protocol.hold_medications || protocol.inr_target) && (
        <Group label="Physician restrictions" count={restrictions.length}>
          <ConceptChips items={restrictions} tone="warning" empty="No restrictions" />
          <div className="flex flex-wrap gap-1.5 mt-1.5">
            {protocol.hold_medications && <Badge cls="bg-danger-light text-danger-dark">Hold medications</Badge>}
            {protocol.inr_target && <Badge cls="bg-accent-soft text-accent-deep">INR target {protocol.inr_target}</Badge>}
          </div>
        </Group>
      )}

      {!hasClaim && data.cross_bill_eligible === false && (
        <p className="text-[11px] text-text-muted">Not eligible for medical cross-billing.</p>
      )}
    </WidgetShell>
  );
}
