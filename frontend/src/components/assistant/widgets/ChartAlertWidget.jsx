import React from 'react';
import { BellRing } from 'lucide-react';
import { WidgetShell, Badge, Notice, failureMessage } from './parts';

// The tool result is self-contained ({ok, alert_id, message, patient_id, title, details}); `args` (the matching
// action's arguments) only backs up results stored before the result carried the alert text.
export function ChartAlertWidget({ data, title, args }) {
  const failure = failureMessage(data);
  if (failure) return <Notice Icon={BellRing} title={title || 'Chart alert'} message={failure} />;

  return (
    <WidgetShell
      Icon={BellRing}
      title={title || 'Chart alert posted'}
      subtitle={[data.patient_id || args?.patient_id, data.alert_id].filter(Boolean).join(' · ')}
      badge={<Badge cls="bg-success-light text-success-dark">Posted to CareStack</Badge>}
    >
      <div className="rounded-2xl bg-warning-light text-warning-dark p-3 text-[13px] leading-snug">
        <div className="font-medium">{data.title || args?.title || data.message || 'Medical alert'}</div>
        {(data.details || args?.details) && <div className="opacity-90 mt-0.5">{data.details || args.details}</div>}
      </div>
    </WidgetShell>
  );
}
