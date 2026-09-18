import React from 'react';
import { Clock, RefreshCcw, FileText, CheckCircle2, Stethoscope, AlertTriangle } from 'lucide-react';

export function PatientTimeline({ patient, alertsCount }) {
  if (!patient) return null;

  const events = [
    {
      time: 'Today, 09:42 AM',
      title: 'Medical record synchronized via FHIR R4',
      description: 'Hospital EHR records successfully fetched & mapped against CareStack MRN.',
      icon: RefreshCcw,
      iconBg: 'bg-teal-50 text-teal-700 border-teal-200',
    },
    {
      time: 'Today, 09:35 AM',
      title: 'Dental treatment plan updated',
      description: 'CDT procedure D7140 (Extraction, Erupted Tooth) queued for Operatory 3.',
      icon: FileText,
      iconBg: 'bg-info-light text-info-dark border-info/30',
    },
    {
      time: 'Today, 09:20 AM',
      title: 'Patient check-in recorded',
      description: `${patient.first_name} ${patient.last_name} checked in at Main Clinic desk.`,
      icon: CheckCircle2,
      iconBg: 'bg-success-light text-success-dark border-success/30',
    },
    {
      time: 'Today, 09:10 AM',
      title: 'Real-time CDS Hooks safety scan',
      description: alertsCount > 0 ? `${alertsCount} clinical safety findings flagged for review.` : 'Clean risk evaluation — no contraindications detected.',
      icon: alertsCount > 0 ? AlertTriangle : Stethoscope,
      iconBg: alertsCount > 0 ? 'bg-warning-light text-warning-dark border-warning/40' : 'bg-success-light text-success-dark border-success/30',
    },
  ];

  return (
    <div className="bg-app-surface rounded-lg border border-app-border p-4 shadow-xs">
      <div className="flex items-center gap-1.5 pb-2.5 border-b border-app-border mb-3">
        <Clock className="w-4 h-4 text-teal-600" />
        <h3 className="text-xs font-bold uppercase tracking-wider text-text-secondary">
          Patient Encounter Timeline
        </h3>
      </div>

      <div className="relative pl-4 space-y-3.5 before:absolute before:left-2 before:top-2 before:bottom-2 before:w-0.5 before:bg-app-border">
        {events.map((ev, i) => {
          const Icon = ev.icon;
          return (
            <div key={i} className="relative flex items-start gap-3 text-xs">
              <div className={`absolute -left-4 mt-0.5 w-4 h-4 rounded-full flex items-center justify-center border text-[9px] font-bold shrink-0 ${ev.iconBg}`}>
                <Icon className="w-2.5 h-2.5" />
              </div>
              <div>
                <div className="font-semibold text-text-main leading-tight">{ev.title}</div>
                <div className="text-[11px] text-text-secondary mt-0.5 leading-normal">{ev.description}</div>
                <div className="text-[10px] text-text-muted mt-0.5 font-mono">{ev.time}</div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
