import React from 'react';
import { Stethoscope, ShieldAlert, GitMerge, RefreshCw, CheckCircle2, Server, Network } from 'lucide-react';

export function InteroperabilityDashboard({ carestackStatus, fhirOnline, onRefresh, syncing }) {
  return (
    <div className="bg-app-surface rounded-lg border border-app-border p-5 shadow-xs mb-6">
      <div className="flex flex-col md:flex-row md:items-center justify-between pb-4 border-b border-app-border gap-3">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-base font-bold text-text-main tracking-tight">
              Medical-Dental Interoperability Topology & Bridge Status
            </h2>
            <span className="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-bold bg-success-light text-success-dark border border-success/30 uppercase">
              <CheckCircle2 className="w-3 h-3 mr-1 text-success" /> Node Active
            </span>
          </div>
          <p className="text-xs text-text-secondary mt-0.5">
            Bi-directional pipeline connecting CareStack Dental PMS with Medical EHR via HL7 FHIR R4 & CDS Hooks v1.0
          </p>
        </div>
        <button
          onClick={onRefresh}
          disabled={syncing}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-text-main bg-app-surface hover:bg-app-secondary border border-app-border rounded transition-colors disabled:opacity-50 shrink-0"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${syncing ? 'animate-spin' : ''}`} />
          <span>Refresh Topology</span>
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mt-4">
        {/* CareStack PMS Node */}
        <div className="rounded border border-info/30 bg-info-light/40 p-3.5 relative overflow-hidden">
          <div className="flex items-center justify-between mb-2">
            <span className="text-[10px] font-bold uppercase tracking-wider text-info-dark">PMS Layer</span>
            <span className="text-[10px] bg-info-light text-info-dark font-semibold px-2 py-0.5 rounded border border-info/20">
              CareStack REST
            </span>
          </div>
          <div className="flex items-center gap-3">
            <div className="p-2 bg-info text-white rounded shrink-0 shadow-xs">
              <GitMerge className="w-4 h-4" />
            </div>
            <div>
              <h3 className="font-semibold text-text-main text-xs">CareStack Dental PMS</h3>
              <p className="text-[11px] text-text-secondary mt-0.5">
                {carestackStatus ? `${carestackStatus.synced_patients} Active Patients Synced` : 'Connecting...'}
              </p>
            </div>
          </div>
          <div className="mt-3 pt-2 border-t border-info/20 text-[10px] text-text-secondary flex justify-between">
            <span>PMS Endpoint:</span>
            <code className="font-mono bg-white px-1 py-0.5 rounded border border-app-border text-text-main">/api/carestack</code>
          </div>
        </div>

        {/* Medical EHR Node */}
        <div className="rounded border border-teal-300 bg-teal-50/50 p-3.5 relative overflow-hidden">
          <div className="flex items-center justify-between mb-2">
            <span className="text-[10px] font-bold uppercase tracking-wider text-teal-800">Medical EHR</span>
            <span className="text-[10px] bg-teal-100 text-teal-800 font-semibold px-2 py-0.5 rounded border border-teal-200">
              HL7 FHIR R4
            </span>
          </div>
          <div className="flex items-center gap-3">
            <div className="p-2 bg-teal-500 text-white rounded shrink-0 shadow-xs">
              <Stethoscope className="w-4 h-4" />
            </div>
            <div>
              <h3 className="font-semibold text-text-main text-xs">Medical Health Record</h3>
              <p className="text-[11px] text-text-secondary mt-0.5">
                Conditions, Labs, Rx, Allergies
              </p>
            </div>
          </div>
          <div className="mt-3 pt-2 border-t border-teal-200 text-[10px] text-text-secondary flex justify-between">
            <span>FHIR Endpoint:</span>
            <code className="font-mono bg-white px-1 py-0.5 rounded border border-app-border text-text-main">/api/fhir</code>
          </div>
        </div>

        {/* CDS Hooks Engine */}
        <div className="rounded border border-app-border bg-app-bg p-3.5 relative overflow-hidden">
          <div className="flex items-center justify-between mb-2">
            <span className="text-[10px] font-bold uppercase tracking-wider text-text-secondary">Decision Engine</span>
            <span className="text-[10px] bg-app-surface text-text-main font-semibold px-2 py-0.5 rounded border border-app-border">
              CDS Hooks v1.0
            </span>
          </div>
          <div className="flex items-center gap-3">
            <div className="p-2 bg-text-main text-white rounded shrink-0 shadow-xs">
              <ShieldAlert className="w-4 h-4" />
            </div>
            <div>
              <h3 className="font-semibold text-text-main text-xs">Clinical Safety Rules</h3>
              <p className="text-[11px] text-text-secondary mt-0.5">
                Real-Time Risk Engine
              </p>
            </div>
          </div>
          <div className="mt-3 pt-2 border-t border-app-border text-[10px] text-text-secondary flex justify-between">
            <span>Discovery:</span>
            <code className="font-mono bg-white px-1 py-0.5 rounded border border-app-border text-text-main">/cds-services</code>
          </div>
        </div>
      </div>
    </div>
  );
}

