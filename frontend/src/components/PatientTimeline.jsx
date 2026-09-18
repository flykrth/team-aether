import React from 'react';
import { RefreshCcw, FileText, CheckCircle2, Stethoscope, AlertTriangle } from 'lucide-react';

export function PatientTimeline({ patient, alertsCount }) {
  if (!patient) return null;

  const events = [
    {
      time: 'Today, 09:42 AM',
      title: 'Medical record synchronized via FHIR R4',
      description: 'Hospital EHR records successfully fetched & mapped against CareStack MRN.',
      icon: RefreshCcw,
      iconBg: 'bg-accent text-white',
    },
    {
      time: 'Today, 09:35 AM',
      title: 'Dental treatment plan updated',
      description: 'CDT procedure D7140 (Extraction, Erupted Tooth) queued for Operatory 3.',
      icon: FileText,
      iconBg: 'bg-accent text-white',
    },
    {
      time: 'Today, 09:20 AM',
      title: 'Patient check-in recorded',
      description: `${patient.first_name} ${patient.last_name} checked in at Main Clinic desk.`,
      icon: CheckCircle2,
      iconBg: 'bg-accent text-white',
    },
    {
      time: 'Today, 09:10 AM',
      title: 'Real-time CDS Hooks safety scan',
      description: alertsCount > 0 ? `${alertsCount} clinical safety findings flagged for review.` : 'Clean risk evaluation — no contraindications detected.',
      icon: alertsCount > 0 ? AlertTriangle : Stethoscope,
      iconBg: alertsCount > 0 ? 'bg-warning text-white' : 'bg-ink text-white',
    },
  ];

  return (
    <div className="card">
      <div className="flex items-end justify-between gap-3 mb-7">
        <h3 className="font-display text-xl font-medium text-text-main leading-tight">
          Patient Encounter Timeline
        </h3>
        <span className="font-display text-sm text-text-muted tabular-nums shrink-0">Today</span>
      </div>

      <ol className="relative">
        {events.map((ev, i) => {
          const Icon = ev.icon;
          const isLast = i === events.length - 1;
          return (
            <li key={i} className="relative flex items-start gap-4 pb-7 last:pb-0">
              {!isLast && (
                <span
                  aria-hidden="true"
                  className="absolute left-[21px] top-11 bottom-0 w-[1.5px] bg-accent/40 rounded-full"
                />
              )}
              <div className={`icon-disc w-11 h-11 ${ev.iconBg}`}>
                <Icon className="w-[18px] h-[18px]" strokeWidth={1.5} />
              </div>
              <div className="min-w-0 flex-1 pt-0.5">
                <div className="font-display text-[15px] font-semibold text-text-main leading-snug">{ev.title}</div>
                <div className="text-[13px] text-text-secondary mt-1 leading-relaxed">{ev.description}</div>
                <div className="text-xs text-text-muted mt-1.5 tabular-nums">{ev.time}</div>
              </div>
            </li>
          );
        })}
      </ol>
    </div>
  );
}
