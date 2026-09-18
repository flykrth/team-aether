import React from 'react';
import { AlertTriangle, AlertCircle, Info, ExternalLink, CheckCircle } from 'lucide-react';

export function CdsAlertCard({ card }) {
  const isCritical = card.indicator === 'critical';
  const isWarning = card.indicator === 'warning';

  const badgeColor = isCritical
    ? 'bg-danger text-white'
    : isWarning
    ? 'bg-warning text-white'
    : 'bg-info text-white';

  const cardBorder = isCritical
    ? 'border-danger/30 bg-danger-light text-danger-dark'
    : isWarning
    ? 'border-warning/40 bg-warning-light text-warning-dark'
    : 'border-info/30 bg-info-light text-info-dark';

  const IconComponent = isCritical ? AlertTriangle : isWarning ? AlertCircle : Info;
  const iconColor = isCritical ? 'text-danger' : isWarning ? 'text-warning-dark' : 'text-info';

  return (
    <div className={`rounded-lg border ${cardBorder} p-4 mb-3 shadow-xs transition-all`}>
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-start gap-2.5">
          <div className="p-1.5 rounded bg-white shadow-xs shrink-0 mt-0.5">
            <IconComponent className={`w-4 h-4 ${iconColor}`} />
          </div>
          <div>
            <div className="flex items-center gap-2 mb-1">
              <span className={`text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded ${badgeColor}`}>
                {card.indicator}
              </span>
              <h4 className="font-semibold text-text-main text-sm">{card.summary}</h4>
            </div>
            {card.detail && (
              <p className="text-xs text-text-main leading-relaxed whitespace-pre-line">
                {card.detail}
              </p>
            )}
          </div>
        </div>
      </div>

      {/* Actionable Suggestions */}
      {card.suggestions && card.suggestions.length > 0 && (
        <div className="mt-3 pt-2.5 border-t border-app-border">
          <p className="text-[10px] font-bold text-text-secondary uppercase tracking-wider mb-1.5">
            Recommended Clinical Action
          </p>
          <div className="space-y-1.5">
            {card.suggestions.map((sug, i) => (
              <div
                key={i}
                className="flex items-center justify-between p-2 bg-white rounded border border-app-border text-xs"
              >
                <span className="font-medium text-text-main flex items-center gap-1.5">
                  <CheckCircle className="w-3.5 h-3.5 text-success shrink-0" />
                  {sug.label}
                </span>
                <span className="text-[10px] bg-teal-50 text-teal-700 px-2 py-0.5 rounded font-semibold border border-teal-200">
                  Auto-Order / EHR Sync
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Clinical Source / Guidelines Link */}
      <div className="mt-2.5 pt-2 flex items-center justify-between text-[11px] text-text-secondary border-t border-app-border/40">
        <span className="flex items-center gap-1">
          Source: <strong className="font-semibold text-text-main">{card.source.label}</strong>
        </span>
        {card.source.url && (
          <a
            href={card.source.url}
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-1 text-teal-700 hover:text-teal-800 font-semibold"
          >
            Clinical Reference <ExternalLink className="w-3 h-3" />
          </a>
        )}
      </div>
    </div>
  );
}

