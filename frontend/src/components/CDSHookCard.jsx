import React, { useState } from 'react';
import { AlertTriangle, ShieldCheck, Info, HeartPulse, CheckCircle2, Stethoscope, ArrowRight } from 'lucide-react';

const INDICATOR_STYLES = {
  critical: {
    wrapper: 'border-danger/30 bg-danger-light text-danger-dark',
    badge: 'bg-danger text-white font-bold',
    icon: AlertTriangle,
    iconColor: 'text-danger',
    label: 'CRITICAL CLINICAL HAZARD',
  },
  warning: {
    wrapper: 'border-warning/40 bg-warning-light text-warning-dark',
    badge: 'bg-warning text-white font-bold',
    icon: HeartPulse,
    iconColor: 'text-warning-dark',
    label: 'CLINICAL REVIEW REQUIRED',
  },
  info: {
    wrapper: 'border-info/30 bg-info-light text-info-dark',
    badge: 'bg-info text-white font-bold',
    icon: Info,
    iconColor: 'text-info',
    label: 'CLINICAL INFORMATIONAL',
  },
};

/**
 * Very small markdown renderer for CDS detail text (supports bolding, bullet points, and line breaks).
 */
function renderDetailMarkdown(detail) {
  if (!detail) return null;
  const lines = detail.split('\n');
  return lines.map((line, i) => {
    const trimmed = line.trim();
    const isBullet = trimmed.startsWith('- ') || trimmed.startsWith('* ');
    const content = isBullet ? trimmed.slice(2) : trimmed;
    const parts = content.split(/(\*\*[^*]+\*\*)/g).map((chunk, j) =>
      chunk.startsWith('**') && chunk.endsWith('**') ? (
        <strong key={j} className="font-semibold text-text-main">
          {chunk.slice(2, -2)}
        </strong>
      ) : (
        <React.Fragment key={j}>{chunk}</React.Fragment>
      )
    );

    if (!trimmed) return <div key={i} className="h-1.5" />;

    return isBullet ? (
      <div key={i} className="flex gap-2 pl-1 text-xs text-text-main leading-relaxed">
        <span aria-hidden="true" className="text-text-muted">•</span>
        <span>{parts}</span>
      </div>
    ) : (
      <p key={i} className="text-xs text-text-main leading-relaxed">{parts}</p>
    );
  });
}

/**
 * Enterprise CareStack CDS Hooks v1.0 Decision Card Component
 */
export function CDSHookCard({ card, onAppendAlert, onRequestConsult, onViewEvidence }) {
  const [appending, setAppending] = useState(false);
  const [appended, setAppended] = useState(false);
  const [requestingConsult, setRequestingConsult] = useState(false);
  const [consultRequested, setConsultRequested] = useState(false);

  const style = INDICATOR_STYLES[card.indicator] || INDICATOR_STYLES.info;
  const Icon = style.icon;

  const handleAppendAlert = async () => {
    if (!onAppendAlert || appending) return;
    setAppending(true);
    try {
      await onAppendAlert(card);
      setAppended(true);
    } finally {
      setAppending(false);
    }
  };

  const handleRequestConsult = async () => {
    if (!onRequestConsult || requestingConsult) return;
    setRequestingConsult(true);
    try {
      await onRequestConsult(card);
      setConsultRequested(true);
    } finally {
      setRequestingConsult(false);
    }
  };

  return (
    <div className={`rounded-lg border p-4 mb-3 bg-app-surface shadow-xs transition-all ${style.wrapper}`}>
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-start gap-2.5">
          <div className="mt-0.5 shrink-0">
            <Icon className={`w-4 h-4 ${style.iconColor}`} />
          </div>
          <div>
            <span className={`inline-block text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded mb-1 ${style.badge}`}>
              {style.label}
            </span>
            <h3 className="font-semibold text-sm text-text-main leading-snug">{card.summary}</h3>
          </div>
        </div>
      </div>

      {card.detail && (
        <div className="mt-2.5 pt-2.5 border-t border-app-border/60 space-y-1">
          {renderDetailMarkdown(card.detail)}
        </div>
      )}

      {/* Verified Source Attribution */}
      {card.source && (
        <div className="mt-3 flex items-center justify-between text-[11px] text-text-secondary bg-app-bg px-2.5 py-1.5 rounded border border-app-border">
          <span className="flex items-center gap-1.5 font-medium">
            <ShieldCheck className="w-3.5 h-3.5 text-teal-500 shrink-0" />
            <span>Source: <strong className="text-text-main font-semibold">{card.source.label}</strong></span>
          </span>
          <span className="text-[10px] text-text-muted font-mono">HL7 FHIR R4 Engine</span>
        </div>
      )}

      {/* Clinical Workflow Action Buttons */}
      <div className="mt-3 pt-2.5 border-t border-app-border flex flex-wrap items-center gap-2">
        {onViewEvidence && (
          <button
            onClick={() => onViewEvidence(card)}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded bg-app-bg text-text-main border border-app-border hover:bg-app-secondary transition-colors"
          >
            <ShieldCheck className="w-3.5 h-3.5 text-teal-600" />
            <span>View Evidence</span>
          </button>
        )}
        <button
          onClick={handleAppendAlert}
          disabled={appending || appended || !onAppendAlert}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded bg-teal-500 text-white hover:bg-teal-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors shadow-xs"
        >
          {appended ? <CheckCircle2 className="w-3.5 h-3.5" /> : null}
          {appended ? 'Medical Alert Appended to Chart' : appending ? 'Appending…' : 'Post Medical Alert to CareStack Chart'}
        </button>
        <button
          onClick={handleRequestConsult}
          disabled={requestingConsult || consultRequested || !onRequestConsult}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded bg-white text-text-main border border-app-border hover:bg-app-secondary disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          {consultRequested ? <CheckCircle2 className="w-3.5 h-3.5 text-success" /> : <Stethoscope className="w-3.5 h-3.5 text-info" />}
          {consultRequested
            ? 'Physician Consult Requested'
            : requestingConsult
            ? 'Requesting…'
            : 'Request Physician Consult (INR)'}
        </button>
      </div>
    </div>
  );
}


