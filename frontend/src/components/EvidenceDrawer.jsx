import React, { useState } from 'react';
import { X, ShieldCheck, FileText, ChevronDown, ExternalLink, Code } from 'lucide-react';

export function EvidenceDrawer({ card, procedure, patient, onClose }) {
  const [showTechnical, setShowTechnical] = useState(false);

  if (!card) return null;

  return (
    <div className="fixed inset-0 z-50 overflow-hidden bg-ink/20 backdrop-blur-sm flex justify-end">
      <div className="w-full max-w-xl bg-app-surface h-full rounded-l-5xl flex flex-col justify-between overflow-y-auto animate-fade-in">
        {/* Drawer Header */}
        <div>
          <div className="px-8 pt-8 pb-4 flex items-center justify-between gap-4">
            <div className="flex items-center gap-3">
              <span className="icon-disc">
                <ShieldCheck className="w-5 h-5" strokeWidth={1.5} />
              </span>
              <h3 className="font-display text-xl font-medium text-text-main">Clinical Evidence & Risk Rationale</h3>
            </div>
            <button onClick={onClose} className="icon-btn" aria-label="Close">
              <X className="w-5 h-5" strokeWidth={1.5} />
            </button>
          </div>

          <div className="px-8 pb-8 pt-2 space-y-4">
            {/* Finding Summary Banner */}
            <div className="card-dark p-6">
              <span className="inline-flex items-center h-7 px-3 rounded-full bg-white/10 text-white/80 text-xs font-medium capitalize mb-4">
                {card.indicator || 'Clinical Review'}
              </span>
              <h4 className="font-display text-2xl font-medium leading-tight tracking-tight text-white">{card.summary}</h4>
            </div>

            {/* Why am I seeing this? */}
            <div className="well p-5">
              <span className="block text-sm text-text-muted mb-2">Why am I seeing this finding?</span>
              <div className="text-sm text-text-main leading-relaxed">
                {card.detail || 'This clinical safety review was triggered because active medical factors in the patient’s hospital EHR conflict with proposed dental treatment.'}
              </div>
            </div>

            {/* Context Table */}
            <div className="well p-5">
              <span className="block text-sm text-text-muted mb-3">Clinical Context & Source Attribution</span>
              <div className="space-y-3 text-sm">
                <div className="flex justify-between gap-4">
                  <span className="text-text-secondary">Patient</span>
                  <span className="text-text-main font-medium text-right">{patient?.first_name} {patient?.last_name} (MRN: {patient?.mrn})</span>
                </div>
                <div className="flex justify-between items-center gap-4">
                  <span className="text-text-secondary">Related Procedure</span>
                  <span className="chip chip-accent font-mono">
                    CDT {procedure?.code || 'D7140'}
                  </span>
                </div>
                <div className="flex justify-between gap-4">
                  <span className="text-text-secondary">Data Source</span>
                  <span className="text-text-main font-medium text-right">{card.source?.label || 'Connected Medical EHR (FHIR R4)'}</span>
                </div>
                <div className="flex justify-between gap-4">
                  <span className="text-text-secondary">Last Synchronized</span>
                  <span className="text-text-main font-medium text-right">Today, {new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
                </div>
              </div>
            </div>

            {/* Actionable Suggestions */}
            {card.suggestions && card.suggestions.length > 0 && (
              <div className="well p-5">
                <span className="block text-sm text-text-muted mb-3">Recommended Clinical Workflow Action</span>
                <div className="flex flex-wrap gap-2">
                  {card.suggestions.map((sug, idx) => (
                    <div key={idx} className="pill bg-accent text-white hover:text-white">
                      {sug.label}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Technical FHIR Details Collapsible */}
            <div>
              <button
                onClick={() => setShowTechnical((v) => !v)}
                className="w-full flex items-center justify-between h-12 pl-5 pr-2 rounded-full bg-app-secondary hover:bg-app-bg font-display font-medium text-[15px] text-text-main"
              >
                <span className="flex items-center gap-2">
                  <Code className="w-4 h-4 text-accent" strokeWidth={1.5} />
                  <span>{showTechnical ? 'Hide Technical FHIR Details' : 'View Technical FHIR Details'}</span>
                </span>
                <span className="inline-flex items-center justify-center w-8 h-8 rounded-full bg-white">
                  <ChevronDown className={`w-4 h-4 transition-transform ${showTechnical ? 'rotate-180' : ''}`} strokeWidth={1.5} />
                </span>
              </button>

              {showTechnical && (
                <div className="mt-3 p-5 bg-ink rounded-3xl text-xs font-mono text-accent-soft/90 overflow-x-auto space-y-3">
                  <p className="text-xs text-white/50 font-sans">
                    Raw FHIR R4 JSON & CDS Hooks Card Payload:
                  </p>
                  <pre className="whitespace-pre-wrap leading-relaxed">{JSON.stringify(card, null, 2)}</pre>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Drawer Footer */}
        <div className="px-8 pb-8 flex justify-end">
          <button onClick={onClose} className="btn-dark">
            Close Evidence Drawer
          </button>
        </div>
      </div>
    </div>
  );
}
