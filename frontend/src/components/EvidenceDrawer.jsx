import React, { useState } from 'react';
import { X, ShieldCheck, FileText, ChevronDown, ExternalLink, Code } from 'lucide-react';

export function EvidenceDrawer({ card, procedure, patient, onClose }) {
  const [showTechnical, setShowTechnical] = useState(false);

  if (!card) return null;

  return (
    <div className="fixed inset-0 z-50 overflow-hidden bg-slate-900/40 backdrop-blur-xs flex justify-end">
      <div className="w-full max-w-lg bg-app-surface h-full shadow-2xl border-l border-app-border flex flex-col justify-between overflow-y-auto">
        {/* Drawer Header */}
        <div>
          <div className="px-5 py-4 border-b border-app-border flex items-center justify-between bg-app-bg">
            <div className="flex items-center gap-2">
              <ShieldCheck className="w-4 h-4 text-teal-600" />
              <h3 className="font-bold text-sm text-text-main">Clinical Evidence & Risk Rationale</h3>
            </div>
            <button
              onClick={onClose}
              className="text-text-muted hover:text-text-main p-1 rounded hover:bg-app-secondary transition-colors"
            >
              <X className="w-4 h-4" />
            </button>
          </div>

          <div className="p-5 space-y-4">
            {/* Finding Summary Banner */}
            <div className="p-3.5 rounded bg-warning-light border border-warning/40">
              <span className="text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded bg-warning text-white inline-block mb-1.5">
                {card.indicator || 'Clinical Review'}
              </span>
              <h4 className="font-bold text-sm text-text-main leading-snug">{card.summary}</h4>
            </div>

            {/* Why am I seeing this? */}
            <div className="space-y-1">
              <span className="text-[10px] font-bold uppercase tracking-wider text-text-secondary">
                Why am I seeing this finding?
              </span>
              <div className="text-xs text-text-main leading-relaxed bg-app-bg p-3 rounded border border-app-border">
                {card.detail || 'This clinical safety review was triggered because active medical factors in the patient’s hospital EHR conflict with proposed dental treatment.'}
              </div>
            </div>

            {/* Context Table */}
            <div className="space-y-1">
              <span className="text-[10px] font-bold uppercase tracking-wider text-text-secondary">
                Clinical Context & Source Attribution
              </span>
              <div className="bg-app-surface border border-app-border rounded divide-y divide-app-border text-xs">
                <div className="p-2.5 flex justify-between">
                  <span className="text-text-secondary">Patient</span>
                  <strong className="text-text-main">{patient?.first_name} {patient?.last_name} (MRN: {patient?.mrn})</strong>
                </div>
                <div className="p-2.5 flex justify-between">
                  <span className="text-text-secondary">Related Procedure</span>
                  <strong className="font-mono text-teal-800 bg-teal-50 px-1.5 py-0.5 rounded border border-teal-200">
                    CDT {procedure?.code || 'D7140'}
                  </strong>
                </div>
                <div className="p-2.5 flex justify-between">
                  <span className="text-text-secondary">Data Source</span>
                  <strong className="text-text-main">{card.source?.label || 'Connected Medical EHR (FHIR R4)'}</strong>
                </div>
                <div className="p-2.5 flex justify-between">
                  <span className="text-text-secondary">Last Synchronized</span>
                  <strong className="text-text-main">Today, {new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</strong>
                </div>
              </div>
            </div>

            {/* Actionable Suggestions */}
            {card.suggestions && card.suggestions.length > 0 && (
              <div className="space-y-1">
                <span className="text-[10px] font-bold uppercase tracking-wider text-text-secondary">
                  Recommended Clinical Workflow Action
                </span>
                <div className="space-y-1.5">
                  {card.suggestions.map((sug, idx) => (
                    <div key={idx} className="p-2.5 bg-teal-50 border border-teal-200 text-teal-900 rounded text-xs font-semibold">
                      {sug.label}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Technical FHIR Details Collapsible */}
            <div className="pt-3 border-t border-app-border">
              <button
                onClick={() => setShowTechnical((v) => !v)}
                className="w-full flex items-center justify-between text-xs font-semibold text-text-secondary hover:text-text-main p-2 rounded bg-app-bg hover:bg-app-secondary border border-app-border transition-colors"
              >
                <span className="flex items-center gap-1.5">
                  <Code className="w-3.5 h-3.5 text-teal-600" />
                  <span>{showTechnical ? 'Hide Technical FHIR Details' : 'View Technical FHIR Details'}</span>
                </span>
                <ChevronDown className={`w-3.5 h-3.5 transition-transform ${showTechnical ? 'rotate-180' : ''}`} />
              </button>

              {showTechnical && (
                <div className="mt-2.5 p-3 bg-text-main rounded text-[11px] font-mono text-teal-300 overflow-x-auto space-y-2">
                  <p className="text-[10px] text-slate-400 font-sans border-b border-slate-700 pb-1">
                    Raw FHIR R4 JSON & CDS Hooks Card Payload:
                  </p>
                  <pre className="whitespace-pre-wrap leading-relaxed">{JSON.stringify(card, null, 2)}</pre>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Drawer Footer */}
        <div className="p-4 border-t border-app-border bg-app-bg flex justify-end">
          <button
            onClick={onClose}
            className="px-4 py-2 text-xs font-semibold text-text-main bg-app-surface border border-app-border rounded hover:bg-app-secondary transition-colors"
          >
            Close Evidence Drawer
          </button>
        </div>
      </div>
    </div>
  );
}
