import React from 'react';
import { Users, ArrowUpRight } from 'lucide-react';
import { WidgetShell, Notice, failureMessage, asList } from './parts';

export function PatientListWidget({ data, title, onAsk }) {
  const failure = failureMessage(data);
  if (failure) return <Notice Icon={Users} title={title || 'Patients'} message={failure} />;
  const patients = asList(data.patients);

  return (
    <WidgetShell Icon={Users} title={title || 'Patients'} subtitle={`${patients.length} in the practice${onAsk ? ' · pick one to ask about' : ''}`}>
      <ul className="-mx-2 -my-1">
        {patients.map((p) => {
          const procedures = asList(p.planned_procedures).map((x) => (typeof x === 'string' ? x : [x.code, x.description].filter(Boolean).join(' ')));
          const Row = onAsk ? 'button' : 'div';
          return (
            <li key={p.patient_id}>
              <Row
                {...(onAsk ? { type: 'button', onClick: () => onAsk(`Summarize the medical history of ${p.name} (${p.patient_id})`) } : {})}
                className={`group w-full text-left flex items-center gap-3 rounded-2xl px-2 py-2 ${onAsk ? 'hover:bg-app-secondary cursor-pointer' : ''}`}
              >
                <span className="inline-flex items-center justify-center w-8 h-8 rounded-full bg-app-secondary group-hover:bg-app-surface text-[11px] font-display font-semibold text-text-secondary shrink-0">
                  {(p.name || '?').split(/\s+/).map((w) => w[0]).slice(0, 2).join('').toUpperCase()}
                </span>
                <span className="min-w-0 flex-1">
                  <span className="block text-[13px] font-medium text-ink truncate">{p.name}</span>
                  <span className="block text-[11px] text-text-muted truncate">
                    {procedures.length ? procedures.join(' · ') : 'No planned procedures'}
                  </span>
                </span>
                <span className="hidden sm:block text-right shrink-0">
                  <span className="block font-mono text-[11px] text-text-secondary">{p.patient_id}</span>
                  {p.next_appointment && <span className="block text-[10px] text-text-muted">{String(p.next_appointment).slice(0, 10)}</span>}
                </span>
                {onAsk && <ArrowUpRight className="w-3.5 h-3.5 text-text-muted opacity-0 group-hover:opacity-100 shrink-0" strokeWidth={1.5} />}
              </Row>
            </li>
          );
        })}
      </ul>
    </WidgetShell>
  );
}
