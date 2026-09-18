import React from 'react';
import { ShieldAlert, ShieldCheck, Stethoscope } from 'lucide-react';
import { WidgetShell, Group, Badge, BulletList, Notice, failureMessage, asList, HAZARD_CLS } from './parts';

const DOT = { LOW: 'bg-success', MODERATE: 'bg-warning', CRITICAL: 'bg-danger' };

export function RiskAssessmentWidget({ data, title }) {
  const failure = failureMessage(data);
  if (failure) return <Notice Icon={ShieldAlert} title={title || 'Risk assessment'} message={failure} />;

  const hazard = String(data.hazard_level || 'LOW').toUpperCase();
  const contraindications = asList(data.contraindications);
  const recommendations = asList(data.clinical_recommendations);

  return (
    <WidgetShell
      Icon={hazard === 'LOW' ? ShieldCheck : ShieldAlert}
      title={title || 'Clinical risk assessment'}
      subtitle={[data.patient_name, data.cdt_code].filter(Boolean).join(' · ')}
      badge={<Badge cls={HAZARD_CLS[hazard] || HAZARD_CLS.LOW}><span className={`w-1.5 h-1.5 rounded-full ${DOT[hazard] || DOT.LOW}`} />{hazard} hazard</Badge>}
    >
      {data.record_found === false && (
        <p className="rounded-2xl bg-warning-light text-warning-dark text-[13px] p-3">
          No medical record is linked for this patient, so this assessment is based on dental data only.
        </p>
      )}

      <div className={`rounded-2xl p-3 flex items-center gap-2.5 text-[13px] font-medium ${data.physician_clearance_required ? 'bg-danger-light text-danger-dark' : 'bg-success-light text-success-dark'}`}>
        <Stethoscope className="w-4 h-4 shrink-0" strokeWidth={1.5} />
        {data.physician_clearance_required ? 'Physician clearance required before this procedure' : 'No physician clearance required'}
      </div>

      <Group label="Contraindications" count={contraindications.length}>
        {contraindications.length ? <BulletList items={contraindications} dot={DOT[hazard] || 'bg-ink-muted'} /> : <p className="text-xs text-text-muted">None identified by the rules.</p>}
      </Group>

      {recommendations.length > 0 && (
        <Group label="Recommendations" count={recommendations.length}>
          <BulletList items={recommendations} dot="bg-accent" />
        </Group>
      )}
    </WidgetShell>
  );
}
