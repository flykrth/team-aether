import React from 'react';
import { AlertTriangle, AlertCircle, Info, ExternalLink, CheckCircle } from 'lucide-react';

export function CdsAlertCard({ card }) {
  const isCritical = card.indicator === 'critical';
  const isWarning = card.indicator === 'warning';

  const badgeColor = isCritical
    ? 'bg-rose-100 text-rose-800 border-rose-200'
    : isWarning
    ? 'bg-amber-100 text-amber-800 border-amber-200'
    : 'bg-sky-100 text-sky-800 border-sky-200';

  const cardBorder = isCritical
    ? 'border-rose-300 bg-rose-50/40'
    : isWarning
    ? 'border-amber-300 bg-amber-50/40'
    : 'border-sky-300 bg-sky-50/40';

  const IconComponent = isCritical ? AlertTriangle : isWarning ? AlertCircle : Info;
  const iconColor = isCritical ? 'text-rose-600' : isWarning ? 'text-amber-600' : 'text-sky-600';

  return (
    <div className={`rounded-xl border ${cardBorder} p-5 shadow-sm transition-all hover:shadow-md mb-4`}>
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-start gap-3">
          <div className={`p-2 rounded-lg bg-white shadow-sm ${iconColor}`}>
            <IconComponent className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className={`text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded border ${badgeColor}`}>
                {card.indicator}
              </span>
              <h4 className="font-bold text-slate-900 text-sm">{card.summary}</h4>
            </div>
            {card.detail && (
              <p className="text-xs text-slate-700 mt-2 leading-relaxed whitespace-pre-line">
                {card.detail}
              </p>
            )}
          </div>
        </div>
      </div>

      {/* Actionable Suggestions */}
      {card.suggestions && card.suggestions.length > 0 && (
        <div className="mt-4 pt-3 border-t border-slate-200/60">
          <p className="text-[11px] font-semibold text-slate-600 uppercase tracking-wide mb-2">
            Recommended Clinical Action
          </p>
          <div className="space-y-2">
            {card.suggestions.map((sug, i) => (
              <div
                key={i}
                className="flex items-center justify-between p-2.5 bg-white rounded-lg border border-slate-200 text-xs shadow-xs"
              >
                <span className="font-medium text-slate-800 flex items-center gap-1.5">
                  <CheckCircle className="w-4 h-4 text-emerald-600 shrink-0" />
                  {sug.label}
                </span>
                <span className="text-[10px] bg-slate-100 text-slate-600 px-2 py-1 rounded font-medium">
                  Auto-Order / EHR Sync
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Clinical Source / Guidelines Link */}
      <div className="mt-3 pt-2 flex items-center justify-between text-[11px] text-slate-500">
        <span className="flex items-center gap-1">
          Source: <strong className="font-semibold text-slate-700">{card.source.label}</strong>
        </span>
        {card.source.url && (
          <a
            href={card.source.url}
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-1 text-sky-600 hover:text-sky-800 font-medium"
          >
            Guidelines <ExternalLink className="w-3 h-3" />
          </a>
        )}
      </div>
    </div>
  );
}
