import React from 'react';
import { UserRound, Link2, Link2Off, FolderPlus, BellRing } from 'lucide-react';
import { WidgetShell, Inner, Group, Badge, ConceptChips, Fact, Notice, failureMessage, asList, pretty, money } from './parts';

const CLEARANCE_CLS = {
  CLEARED: 'bg-success-light text-success-dark',
  APPROVED: 'bg-success-light text-success-dark',
  APPROVED_WITH_CONDITIONS: 'bg-success-light text-success-dark',
  DENIED: 'bg-danger-light text-danger-dark',
};

export function PatientSummaryWidget({ data, title, onOpenIntake }) {
  const failure = failureMessage(data);
  if (failure) return <Notice Icon={UserRound} title={title || 'Patient summary'} message={failure} />;

  const dental = data.dental || null;
  const plan = asList(dental?.treatment_plan);
  const labs = asList(data.observations).filter((o) => o && (o.test || o.value != null));
  const alerts = asList(data.chart_alerts);
  const clearances = asList(data.clearance_requests);
  const documents = asList(dental?.documents);
  const demographics = [data.patient_id, data.birth_date && `DOB ${data.birth_date}`, data.gender && pretty(data.gender)].filter(Boolean).join(' · ');

  return (
    <WidgetShell
      Icon={UserRound}
      title={data.name || title || 'Patient summary'}
      subtitle={demographics}
      badge={
        <Badge cls={data.medical_record_linked ? 'bg-success-light text-success-dark' : 'bg-warning-light text-warning-dark'}>
          {data.medical_record_linked ? <Link2 className="w-3 h-3" /> : <Link2Off className="w-3 h-3" />}
          {data.medical_record_linked ? 'Medical record linked' : 'No medical record'}
        </Badge>
      }
    >
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <Group label="Conditions" count={asList(data.conditions).length}><ConceptChips items={data.conditions} /></Group>
        <Group label="Medications" count={asList(data.medications).length}><ConceptChips items={data.medications} tone="accent" /></Group>
        <Group label="Allergies" count={asList(data.allergies).length}><ConceptChips items={data.allergies} tone="danger" empty="No known allergies" /></Group>
      </div>

      {labs.length > 0 && (
        <Group label="Labs and vitals" count={labs.length}>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
            {labs.slice(0, 8).map((o, i) => (
              <Inner key={i}>
                <div className="text-[11px] text-text-muted leading-tight">{o.test || 'Observation'}</div>
                <div className="font-display text-lg font-medium text-ink leading-tight mt-1">
                  {o.value ?? '—'} <span className="text-xs font-sans font-normal text-text-muted">{o.unit}</span>
                </div>
                {o.date && <div className="text-[10px] text-text-muted mt-0.5">{o.date}</div>}
              </Inner>
            ))}
          </div>
        </Group>
      )}

      {dental && (
        <Group label="Dental treatment plan" count={plan.length}>
          <Inner className="space-y-2">
            {plan.length === 0 && <p className="text-xs text-text-muted">No planned procedures.</p>}
            {plan.map((t, i) => (
              <div key={i} className="flex items-baseline gap-3 text-[13px]">
                <span className="font-mono text-xs text-accent-deep shrink-0">{t.cdt_code}</span>
                <span className="min-w-0 flex-1 text-text-main">{t.description}{t.tooth ? ` · tooth ${t.tooth}` : ''}</span>
                {t.status && <span className="text-[11px] text-text-muted shrink-0">{pretty(t.status)}</span>}
                {money(t.fee) && <span className="font-mono text-xs text-text-secondary shrink-0">{money(t.fee)}</span>}
              </div>
            ))}
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 pt-2">
              <Fact label="Next appointment" value={dental.next_appointment} />
              <Fact label="Last visit" value={dental.last_visit} />
              <Fact label="Dentist" value={dental.primary_dentist} />
            </div>
          </Inner>
        </Group>
      )}

      {alerts.length > 0 && (
        <Group label="Chart alerts" count={alerts.length}>
          <div className="space-y-2">
            {alerts.map((a, i) => (
              <div key={i} className="rounded-2xl bg-warning-light text-warning-dark p-3 flex gap-2.5">
                <BellRing className="w-4 h-4 mt-0.5 shrink-0" strokeWidth={1.5} />
                <div className="min-w-0 text-[13px] leading-snug">
                  <div className="font-medium">{a.title}</div>
                  {a.details && <div className="opacity-90 mt-0.5">{a.details}</div>}
                  {a.source && <div className="text-[11px] opacity-70 mt-1">{a.source}</div>}
                </div>
              </div>
            ))}
          </div>
        </Group>
      )}

      {clearances.length > 0 && (
        <Group label="Clearance requests" count={clearances.length}>
          <div className="space-y-2">
            {clearances.map((c, i) => (
              <Inner key={c.request_id || i} className="text-[13px]">
                <div className="flex flex-wrap items-center gap-2">
                  <Badge cls={CLEARANCE_CLS[String(c.status).toUpperCase()] || 'bg-warning-light text-warning-dark'}>{pretty(String(c.status))}</Badge>
                  <span className="text-text-main">{c.physician}</span>
                  <span className="font-mono text-xs text-text-muted">{asList(c.procedures).join(', ')}</span>
                </div>
                {c.physician_notes && <p className="text-text-secondary mt-2 leading-snug">{c.physician_notes}</p>}
              </Inner>
            ))}
          </div>
        </Group>
      )}

      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="text-[11px] text-text-muted">
          {documents.length > 0 ? `${documents.length} document${documents.length === 1 ? '' : 's'} on file` : 'No documents on file'}
        </span>
        {onOpenIntake && (
          <button type="button" onClick={() => onOpenIntake(data.patient_id)} className="chip hover:bg-app-bg cursor-pointer">
            <FolderPlus className="w-3.5 h-3.5" strokeWidth={1.5} /> Add history or records
          </button>
        )}
      </div>
    </WidgetShell>
  );
}
