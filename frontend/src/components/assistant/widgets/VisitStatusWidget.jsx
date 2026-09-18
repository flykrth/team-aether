import React from 'react';
import { Route, Check } from 'lucide-react';
import { WidgetShell, Badge, Notice, failureMessage, HAZARD_CLS, pretty } from './parts';

const STAGES = [['risk_checked', 'Risk check'], ['procedure_done', 'Procedure'], ['insurance_checked', 'Insurance']];
const ORDER = ['none', 'planned', 'risk_checked', 'procedure_done', 'insurance_checked', 'closed'];

export function VisitStatusWidget({ data, title }) {
  const failure = failureMessage(data);
  if (failure) return <Notice Icon={Route} title={title || 'Visit'} message={failure} />;
  const visit = data.visit; const insurance = data.insurance || {};
  const at = ORDER.indexOf(visit?.stage || 'none');
  return (
    <WidgetShell Icon={Route} title={title || 'Visit'} subtitle={[data.patient_id, visit?.procedure?.label].filter(Boolean).join(' · ')}
      badge={data.change ? <Badge cls="bg-success-light text-success-dark"><Check className="w-3 h-3" />{data.change}</Badge> : null}>
      <div className="grid grid-cols-3 gap-1.5">
        {STAGES.map(([stage, label]) => {
          const done = at >= ORDER.indexOf(stage);
          return <div key={stage} className={`rounded-full h-7 px-3 flex items-center gap-1.5 text-[11px] font-medium ${done ? 'bg-ink text-white' : 'bg-white/60 text-text-muted'}`}>{done && <Check className="w-3 h-3" />}<span className="truncate">{label}</span></div>;
        })}
      </div>
      <div className="flex flex-wrap gap-1.5">
        {visit?.risk && <Badge cls={HAZARD_CLS[visit.risk.hazard_level] || HAZARD_CLS.LOW}>{visit.risk.hazard_level} risk</Badge>}
        {visit?.risk?.physician_clearance_required && <Badge cls="bg-danger-light text-danger-dark">Clearance required</Badge>}
        <Badge cls="bg-white/60 text-text-secondary">Dental benefit: {pretty(insurance.dental_status || 'unknown')}</Badge>
        {insurance.medical_insurer && <Badge cls="bg-white/60 text-text-secondary">{insurance.medical_insurer}{insurance.plan_type ? ` ${insurance.plan_type}` : ''}</Badge>}
        {insurance.plan_document && <Badge cls="bg-white/60 text-text-secondary">Plan document on file</Badge>}
        {visit?.insurance && <Badge cls="bg-accent-soft text-accent-deep">{visit.insurance.headline}</Badge>}
      </div>
      {data.next_step?.next && <p className="text-[13px] text-text-main">Next: {data.next_step.next}</p>}
    </WidgetShell>
  );
}
