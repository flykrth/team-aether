import React from 'react';
import { User, Calendar, ShieldCheck, ChevronDown, Clock, MapPin, FileCheck } from 'lucide-react';

export function PatientHeader({ patients, selectedPatient, onSelectPatient, activeProcedure, documentsCount = 0 }) {
  if (!selectedPatient) return null;

  return (
    <div className="bg-app-surface rounded-lg border border-app-border p-4 shadow-xs mb-4">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-3">
        {/* Left: Patient Identity & Demographics */}
        <div className="flex items-center gap-3.5">
          <div className="w-11 h-11 rounded-full bg-teal-50 text-teal-700 font-bold text-base flex items-center justify-center border border-teal-200 shrink-0">
            {selectedPatient.first_name?.[0]}
            {selectedPatient.last_name?.[0]}
          </div>

          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-lg font-bold text-text-main leading-tight">
                {selectedPatient.first_name} {selectedPatient.last_name}
              </h1>
              <span className="px-2 py-0.5 text-[10px] font-bold rounded bg-teal-50 text-teal-700 border border-teal-200 uppercase">
                Active Chart
              </span>
            </div>

            <div className="flex flex-wrap items-center gap-x-3 gap-y-0.5 text-xs text-text-secondary mt-0.5">
              <span>DOB: <strong>{selectedPatient.birth_date}</strong></span>
              <span className="text-text-muted">•</span>
              <span>MRN: <strong className="text-teal-700">{selectedPatient.mrn}</strong></span>
              <span className="text-text-muted">•</span>
              <span>CareStack ID: <strong className="text-text-main">{selectedPatient.id}</strong></span>
              <span className="text-text-muted">•</span>
              <span>Provider: <strong className="text-text-main">{selectedPatient.primary_dentist}</strong></span>
            </div>
          </div>
        </div>

        {/* Right: Active Procedure, Documents Badge & Patient Switcher */}
        <div className="flex flex-wrap items-center gap-2 pt-2 md:pt-0 border-t md:border-t-0 border-app-border">
          {/* CareStack Documents Counter Badge */}
          <div className="bg-teal-50/80 px-2.5 py-1 rounded border border-teal-200 text-xs font-semibold text-teal-900 flex items-center gap-1.5 shadow-2xs">
            <FileCheck className="w-3.5 h-3.5 text-teal-600" />
            <span>CareStack Documents:</span>
            <span className="bg-teal-600 text-white text-[10px] font-bold px-1.5 py-0.2 rounded-full font-mono">
              {documentsCount} Synced
            </span>
          </div>

          {activeProcedure && (
            <div className="bg-app-bg px-3 py-1.5 rounded border border-app-border text-xs flex items-center gap-2">
              <span className="text-text-muted">Today's Procedure:</span>
              <span className="font-mono font-bold text-teal-800 bg-teal-50 px-1.5 py-0.5 rounded border border-teal-200">
                {activeProcedure.code}
              </span>
              <span className="font-medium text-text-main">{activeProcedure.label}</span>
            </div>
          )}

          <div className="relative">
            <label htmlFor="patient-switcher" className="sr-only">Switch Patient</label>
            <select
              id="patient-switcher"
              value={selectedPatient.id}
              onChange={(e) => onSelectPatient(e.target.value)}
              className="bg-app-surface border border-app-border text-text-main text-xs font-semibold rounded px-3 py-1.5 focus:outline-none focus:border-teal-500 cursor-pointer shadow-xs"
            >
              {patients.map((p) => (
                <option key={p.id} value={p.id}>
                  Switch Patient: {p.first_name} {p.last_name} ({p.id})
                </option>
              ))}
            </select>
          </div>
        </div>
      </div>
    </div>
  );
}
