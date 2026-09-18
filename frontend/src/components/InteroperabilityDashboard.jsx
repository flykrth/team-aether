import React from 'react';
import { Stethoscope, ShieldAlert, GitMerge, RefreshCw, CheckCircle2 } from 'lucide-react';

export function InteroperabilityDashboard({ carestackStatus, fhirOnline, onRefresh, syncing }) {
  return (
    <div className="card p-7 mb-6">
      <div className="flex flex-col md:flex-row md:items-start justify-between gap-4">
        <div>
          <div className="flex flex-wrap items-center gap-3">
            <h2 className="font-display text-2xl font-medium text-text-main tracking-tight leading-tight">
              Medical-Dental Interoperability Topology & Bridge Status
            </h2>
            <span className="chip bg-success-light text-success-dark">
              <CheckCircle2 className="w-3.5 h-3.5 text-success" strokeWidth={1.5} /> Node Active
            </span>
          </div>
          <p className="text-[13px] text-text-muted mt-1.5 max-w-2xl">
            Bi-directional pipeline connecting CareStack Dental PMS with Medical EHR via HL7 FHIR R4 & CDS Hooks v1.0
          </p>
        </div>
        <button onClick={onRefresh} disabled={syncing} className="btn-ghost shrink-0">
          <RefreshCw className={`w-4 h-4 ${syncing ? 'animate-spin' : ''}`} strokeWidth={1.5} />
          <span>Refresh Topology</span>
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mt-7">
        {/* CareStack PMS Node */}
        <div className="bg-app-secondary rounded-4xl p-6 flex flex-col">
          <div className="flex items-center justify-between gap-2 mb-6">
            <div className="icon-disc">
              <GitMerge className="w-5 h-5" strokeWidth={1.5} />
            </div>
            <span className="chip bg-white">CareStack REST</span>
          </div>
          <span className="text-xs text-text-muted">PMS Layer</span>
          <h3 className="font-display text-lg font-semibold text-text-main mt-0.5">CareStack Dental PMS</h3>
          <p className="text-[13px] text-text-secondary mt-1">
            {carestackStatus ? `${carestackStatus.synced_patients} Active Patients Synced` : 'Connecting...'}
          </p>
          <div className="mt-auto pt-6 flex items-center justify-between gap-2 text-xs text-text-muted">
            <span>PMS Endpoint:</span>
            <code className="font-mono text-[11px] bg-white px-2.5 py-1 rounded-full text-text-main">/api/carestack</code>
          </div>
        </div>

        {/* Medical EHR Node */}
        <div className="card-accent flex flex-col">
          <div className="flex items-center justify-between gap-2 mb-6">
            <div className="inline-flex items-center justify-center w-12 h-12 rounded-full bg-white text-accent shrink-0">
              <Stethoscope className="w-5 h-5" strokeWidth={1.5} />
            </div>
            <span className="chip bg-white/15 text-white">HL7 FHIR R4 (Live)</span>
          </div>
          <span className="text-xs text-white/70">Medical EHR</span>
          <h3 className="font-display text-lg font-semibold text-white mt-0.5">HAPI FHIR Reference Server</h3>
          <p className="text-[13px] text-white/80 mt-1">
            HL7 Public Test Directory (USCDI v5)
          </p>
          <div className="mt-auto pt-6 flex items-center justify-between gap-2 text-xs text-white/70">
            <span>Server URL:</span>
            <a
              href="https://hapi.fhir.org/baseR4"
              target="_blank"
              rel="noreferrer"
              className="font-mono text-[11px] bg-white px-2.5 py-1 rounded-full text-accent-deep hover:underline"
            >
              hapi.fhir.org/baseR4
            </a>
          </div>
        </div>

        {/* CDS Hooks Engine */}
        <div className="card-dark flex flex-col">
          <div className="flex items-center justify-between gap-2 mb-6">
            <div className="inline-flex items-center justify-center w-12 h-12 rounded-full bg-white text-ink shrink-0">
              <ShieldAlert className="w-5 h-5" strokeWidth={1.5} />
            </div>
            <span className="chip bg-white/10 text-white">CDS Hooks v1.0</span>
          </div>
          <span className="text-xs text-white/60">Decision Engine</span>
          <h3 className="font-display text-lg font-semibold text-white mt-0.5">Clinical Safety Rules</h3>
          <p className="text-[13px] text-white/70 mt-1">
            Real-Time Risk Engine
          </p>
          <div className="mt-auto pt-6 flex items-center justify-between gap-2 text-xs text-white/60">
            <span>Discovery:</span>
            <code className="font-mono text-[11px] bg-white/10 px-2.5 py-1 rounded-full text-white">/cds-services</code>
          </div>
        </div>
      </div>
    </div>
  );
}
