import React from 'react';
import { Stethoscope, ShieldAlert, GitMerge, RefreshCw, CheckCircle2 } from 'lucide-react';

export function InteroperabilityDashboard({ carestackStatus, fhirOnline, onRefresh, syncing }) {
  return (
    <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-sm mb-6">
      <div className="flex flex-col md:flex-row md:items-center justify-between pb-5 border-b border-slate-100 gap-4">
        <div>
          <h2 className="text-xl font-bold text-slate-900 tracking-tight flex items-center gap-2">
            <span>Interoperability Topology & Bridge Status</span>
            <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-emerald-100 text-emerald-800">
              <CheckCircle2 className="w-3 h-3 mr-1" /> Active Node
            </span>
          </h2>
          <p className="text-sm text-slate-500 mt-0.5">
            Real-time bi-directional pipeline bridging CareStack Dental PMS with Medical EHR via HL7 FHIR R4 & CDS Hooks v1.0
          </p>
        </div>
        <button
          onClick={onRefresh}
          disabled={syncing}
          className="inline-flex items-center gap-2 px-3.5 py-2 text-xs font-semibold text-slate-700 bg-slate-100 hover:bg-slate-200 rounded-lg transition-colors disabled:opacity-50"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${syncing ? 'animate-spin' : ''}`} />
          <span>Refresh Topology</span>
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-5 mt-5">
        {/* CareStack PMS Node */}
        <div className="rounded-lg border border-sky-100 bg-sky-50/50 p-4 relative overflow-hidden">
          <div className="flex items-center justify-between mb-3">
            <span className="text-xs font-bold uppercase tracking-wider text-sky-700">PMS Layer</span>
            <span className="text-[10px] bg-sky-200/60 text-sky-800 font-semibold px-2 py-0.5 rounded">
              CareStack REST
            </span>
          </div>
          <div className="flex items-center gap-3">
            <div className="p-2.5 bg-sky-600 text-white rounded-lg shadow-sm">
              <GitMerge className="w-5 h-5" />
            </div>
            <div>
              <h3 className="font-semibold text-slate-900 text-sm">CareStack Dental PMS</h3>
              <p className="text-xs text-slate-500 mt-0.5">
                {carestackStatus ? `${carestackStatus.synced_patients} Patients Synced` : 'Connecting...'}
              </p>
            </div>
          </div>
          <div className="mt-3 pt-3 border-t border-sky-100 text-[11px] text-sky-900 flex justify-between">
            <span>Endpoint:</span>
            <code className="font-mono bg-white/80 px-1 py-0.5 rounded">/api/carestack</code>
          </div>
        </div>

        {/* Medical EHR Node */}
        <div className="rounded-lg border border-teal-100 bg-teal-50/50 p-4 relative overflow-hidden">
          <div className="flex items-center justify-between mb-3">
            <span className="text-xs font-bold uppercase tracking-wider text-teal-700">Medical EHR</span>
            <span className="text-[10px] bg-teal-200/60 text-teal-800 font-semibold px-2 py-0.5 rounded">
              HL7 FHIR R4
            </span>
          </div>
          <div className="flex items-center gap-3">
            <div className="p-2.5 bg-teal-600 text-white rounded-lg shadow-sm">
              <Stethoscope className="w-5 h-5" />
            </div>
            <div>
              <h3 className="font-semibold text-slate-900 text-sm">Medical Health Record</h3>
              <p className="text-xs text-slate-500 mt-0.5">
                Conditions, Labs, Allergies
              </p>
            </div>
          </div>
          <div className="mt-3 pt-3 border-t border-teal-100 text-[11px] text-teal-900 flex justify-between">
            <span>Endpoint:</span>
            <code className="font-mono bg-white/80 px-1 py-0.5 rounded">/api/fhir</code>
          </div>
        </div>

        {/* CDS Hooks Engine */}
        <div className="rounded-lg border border-indigo-100 bg-indigo-50/50 p-4 relative overflow-hidden">
          <div className="flex items-center justify-between mb-3">
            <span className="text-xs font-bold uppercase tracking-wider text-indigo-700">Decision Engine</span>
            <span className="text-[10px] bg-indigo-200/60 text-indigo-800 font-semibold px-2 py-0.5 rounded">
              CDS Hooks v1.0
            </span>
          </div>
          <div className="flex items-center gap-3">
            <div className="p-2.5 bg-indigo-600 text-white rounded-lg shadow-sm">
              <ShieldAlert className="w-5 h-5" />
            </div>
            <div>
              <h3 className="font-semibold text-slate-900 text-sm">Clinical Safety Engine</h3>
              <p className="text-xs text-slate-500 mt-0.5">
                Active Cross-Specialty Rules
              </p>
            </div>
          </div>
          <div className="mt-3 pt-3 border-t border-indigo-100 text-[11px] text-indigo-900 flex justify-between">
            <span>Discovery:</span>
            <code className="font-mono bg-white/80 px-1 py-0.5 rounded">/cds-services</code>
          </div>
        </div>
      </div>
    </div>
  );
}
