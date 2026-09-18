import React from 'react';
import { ChevronDown, FileCheck, Stethoscope, ShieldCheck } from 'lucide-react';

function Meta({ label, children, mono = false }) {
  return (
    <div className="min-w-0">
      <div className="text-xs text-text-muted">{label}</div>
      <div className={`mt-1 text-[15px] text-text-main truncate ${mono ? 'font-mono text-sm' : 'font-display font-medium'}`}>
        {children}
      </div>
    </div>
  );
}

export function PatientHeader({ patients, selectedPatient, onSelectPatient, activeProcedure, documentsCount = 0 }) {
  if (!selectedPatient) return null;

  return (
    <section className="grid grid-cols-1 xl:grid-cols-12 gap-6 mb-8 animate-fade-in">
      {/* Hero: identity */}
      <div className="xl:col-span-7 flex flex-col justify-between gap-8 py-2">
        <div className="flex items-start justify-between gap-4">
          <div className="flex items-center gap-4">
            <div className="w-14 h-14 rounded-full bg-accent text-white font-display font-medium text-lg flex items-center justify-center shrink-0">
              {selectedPatient.first_name?.[0]}
              {selectedPatient.last_name?.[0]}
            </div>
            <div className="flex flex-col gap-1.5">
              <span className="chip chip-accent w-fit">
                <span className="w-1.5 h-1.5 rounded-full bg-accent" />
                Active Chart
              </span>
              <span className="text-sm text-text-muted">Patient overview</span>
            </div>
          </div>

          {/* Patient switcher */}
          <div className="relative shrink-0">
            <label htmlFor="patient-switcher" className="sr-only">Switch Patient</label>
            <select
              id="patient-switcher"
              value={selectedPatient.id}
              onChange={(e) => onSelectPatient(e.target.value)}
              className="appearance-none h-11 pl-5 pr-11 rounded-full bg-app-surface text-text-main font-display font-medium text-sm cursor-pointer outline-none focus:ring-2 focus:ring-accent/30 max-w-[18rem] truncate"
            >
              {patients.map((p) => (
                <option key={p.id} value={p.id}>
                  Switch Patient: {p.first_name} {p.last_name} ({p.id})
                </option>
              ))}
            </select>
            <ChevronDown
              className="pointer-events-none absolute right-4 top-1/2 -translate-y-1/2 w-4 h-4 text-text-secondary"
              strokeWidth={1.5}
            />
          </div>
        </div>

        <h1 className="font-display text-5xl md:text-6xl font-light leading-[0.95] tracking-tight text-ink">
          {selectedPatient.first_name}
          <br />
          {selectedPatient.last_name}
        </h1>

        <div className="flex flex-wrap items-center gap-2">
          {activeProcedure && (
            <span className="chip bg-app-surface h-9 px-4 text-sm">
              <Stethoscope className="w-4 h-4 text-accent" strokeWidth={1.5} />
              <span className="text-text-muted">Today's Procedure:</span>
              <span className="font-mono text-accent-deep">{activeProcedure.code}</span>
              <span className="text-text-main">{activeProcedure.label}</span>
            </span>
          )}
          <span className="chip bg-app-surface h-9 px-4 text-sm">
            <FileCheck className="w-4 h-4 text-accent" strokeWidth={1.5} />
            <span>CareStack Documents:</span>
            <span className="chip chip-accent h-6 px-2.5 font-mono text-[11px]">{documentsCount} Synced</span>
          </span>
          {selectedPatient?.medical_clearance && (
            <span
              className={`chip h-9 px-4 text-sm ${
                selectedPatient.medical_clearance.is_cleared_for_surgery
                  ? 'bg-success-light text-success-dark'
                  : 'bg-danger-light text-danger-dark'
              }`}
            >
              <ShieldCheck
                className={`w-4 h-4 ${selectedPatient.medical_clearance.is_cleared_for_surgery ? 'text-success' : 'text-danger'}`}
                strokeWidth={1.5}
              />
              <span>Cardiology Clearance:</span>
              <span className="font-display font-semibold capitalize">
                {selectedPatient.medical_clearance.status?.replace(/_/g, ' ').toLowerCase()}
              </span>
            </span>
          )}
        </div>
      </div>

      {/* Meta card */}
      <div className="xl:col-span-5 card grid grid-cols-2 gap-x-6 gap-y-6 content-center">
        <Meta label="Date of birth">{selectedPatient.birth_date}</Meta>
        <Meta label="MRN" mono>
          <span className="text-accent-deep">{selectedPatient.mrn}</span>
        </Meta>
        <Meta label="CareStack ID" mono>{selectedPatient.id}</Meta>
        <Meta label="Provider">{selectedPatient.primary_dentist}</Meta>
      </div>
    </section>
  );
}
