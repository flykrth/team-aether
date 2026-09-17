import React, { useState } from 'react';
import { AlertTriangle, ShieldCheck, Info, HeartPulse, CheckCircle2 } from 'lucide-react';

const INDICATOR_STYLES = {
  critical: {
    wrapper: 'border-red-500 bg-red-50 text-red-900',
    badge: 'bg-red-600 text-white animate-pulse',
    icon: AlertTriangle,
    label: 'CRITICAL HAZARD',
  },
  warning: {
    wrapper: 'border-amber-500 bg-amber-50 text-amber-900',
    badge: 'bg-amber-500 text-white',
    icon: HeartPulse,
    label: 'WARNING',
  },
  info: {
    wrapper: 'border-blue-500 bg-blue-50 text-blue-900',
    badge: 'bg-blue-600 text-white',
    icon: Info,
    label: 'INFO',
  },
};

/** Very small markdown-ish renderer: bold, bullet lists, and line breaks — enough for CDS `detail` text. */
function renderDetailMarkdown(detail) {
  if (!detail) return null;
  const lines = detail.split('\n');
  return lines.map((line, i) => {
    const trimmed = line.trim();
    const isBullet = trimmed.startsWith('- ') || trimmed.startsWith('* ');
    const content = isBullet ? trimmed.slice(2) : trimmed;
    const parts = content.split(/(\*\*[^*]+\*\*)/g).map((chunk, j) =>
      chunk.startsWith('**') && chunk.endsWith('**') ? (
        <strong key={j} className="font-bold">
          {chunk.slice(2, -2)}
        </strong>
      ) : (
        <React.Fragment key={j}>{chunk}</React.Fragment>
      )
    );

    if (!trimmed) return <div key={i} className="h-2" />;

    return isBullet ? (
      <div key={i} className="flex gap-2 pl-1">
        <span aria-hidden="true">•</span>
        <span>{parts}</span>
      </div>
    ) : (
      <p key={i}>{parts}</p>
    );
  });
}

/**
 * Renders a single CDS Hooks v1.0 Card (summary/indicator/detail/source/suggestions)
 * with the two canonical MDIN chairside actions: appending the alert to the CareStack
 * chart, and requesting a pre-op coagulation (INR) consult.
 */
export function CDSHookCard({ card, onAppendAlert, onRequestConsult }) {
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
    <div className={`rounded-xl border-2 p-5 shadow-sm mb-4 ${style.wrapper}`}>
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-start gap-3">
          <Icon className="w-5 h-5 mt-0.5 shrink-0" />
          <h3 className="font-bold text-base leading-tight">{card.summary}</h3>
        </div>
        <span
          className={`shrink-0 text-[10px] font-extrabold uppercase tracking-wider px-2 py-1 rounded ${style.badge}`}
        >
          {style.label}
        </span>
      </div>

      {card.detail && (
        <div className="mt-3 text-sm leading-relaxed space-y-1">{renderDetailMarkdown(card.detail)}</div>
      )}

      {card.source && (
        <div className="mt-3 inline-flex items-center gap-1.5 text-[11px] font-semibold bg-white/70 border border-current/20 px-2 py-1 rounded">
          <ShieldCheck className="w-3.5 h-3.5" />
          <span>Verified by {card.source.label}</span>
        </div>
      )}

      <div className="mt-4 pt-3 border-t border-current/20 flex flex-wrap gap-2">
        <button
          onClick={handleAppendAlert}
          disabled={appending || appended || !onAppendAlert}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-lg bg-slate-900 text-white hover:bg-slate-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          {appended ? <CheckCircle2 className="w-3.5 h-3.5" /> : null}
          {appended ? 'Appended to CareStack Chart' : appending ? 'Appending…' : 'Append Medical Alert to CareStack Chart'}
        </button>
        <button
          onClick={handleRequestConsult}
          disabled={requestingConsult || consultRequested || !onRequestConsult}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-lg bg-white text-slate-900 border border-slate-300 hover:bg-slate-50 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          {consultRequested ? <CheckCircle2 className="w-3.5 h-3.5" /> : null}
          {consultRequested
            ? 'Consult Requested'
            : requestingConsult
            ? 'Requesting…'
            : 'Request Pre-Op Coagulation Consult (INR)'}
        </button>
      </div>
    </div>
  );
}
