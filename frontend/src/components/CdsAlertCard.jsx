import React from 'react';
import { AlertTriangle, AlertCircle, Info, ArrowUpRight, CheckCircle } from 'lucide-react';

export function CdsAlertCard({ card }) {
  const isCritical = card.indicator === 'critical';
  const isWarning = card.indicator === 'warning';

  // Critical → charcoal feature card; warning / info → white card with a toned icon disc.
  const cardSurface = isCritical ? 'card-dark' : 'card';

  const badgeColor = isCritical
    ? 'bg-white/10 text-white/80'
    : isWarning
    ? 'bg-warning-light text-warning-dark'
    : 'bg-accent-soft text-accent-deep';

  const discColor = isCritical ? 'bg-danger text-white' : isWarning ? 'bg-warning text-white' : 'bg-accent text-white';

  const IconComponent = isCritical ? AlertTriangle : isWarning ? AlertCircle : Info;

  const titleColor = isCritical ? 'text-white' : 'text-text-main';
  const bodyColor = isCritical ? 'text-white/75' : 'text-text-secondary';
  const mutedColor = isCritical ? 'text-white/50' : 'text-text-muted';

  return (
    <div className={`${cardSurface} p-7 mb-4 last:mb-0 animate-fade-in`}>
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <span className={`inline-flex items-center h-7 px-3 rounded-full text-xs font-medium capitalize mb-4 ${badgeColor}`}>
            {card.indicator}
          </span>
          <h4 className={`font-display text-2xl font-medium leading-tight tracking-tight ${titleColor}`}>{card.summary}</h4>
          {card.detail && (
            <p className={`mt-3 text-sm leading-relaxed whitespace-pre-line ${bodyColor}`}>
              {card.detail}
            </p>
          )}
        </div>
        <span className={`inline-flex items-center justify-center w-12 h-12 rounded-full shrink-0 ${discColor}`}>
          <IconComponent className="w-5 h-5" strokeWidth={1.5} />
        </span>
      </div>

      {/* Actionable Suggestions */}
      {card.suggestions && card.suggestions.length > 0 && (
        <div className="mt-6">
          <p className={`text-sm mb-3 ${mutedColor}`}>Recommended Clinical Action</p>
          <div className="flex flex-wrap gap-2">
            {card.suggestions.map((sug, i) => (
              <div
                key={i}
                className={`inline-flex items-center gap-2 h-11 pl-2 pr-5 rounded-full font-display font-medium text-[15px] ${
                  isCritical ? 'bg-white/10 text-white' : 'bg-app-secondary text-text-main'
                }`}
              >
                <span className="inline-flex items-center justify-center w-7 h-7 rounded-full bg-success text-white shrink-0">
                  <CheckCircle className="w-4 h-4" strokeWidth={1.5} />
                </span>
                <span>{sug.label}</span>
                <span className={`text-xs font-sans ${mutedColor}`}>Auto-Order / EHR Sync</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Clinical Source / Guidelines Link */}
      <div className={`mt-6 flex flex-wrap items-center justify-between gap-3 text-xs ${mutedColor}`}>
        <span className="flex items-center gap-1">
          Source: <span className={`font-medium ${titleColor}`}>{card.source.label}</span>
        </span>
        {card.source.url && (
          <a
            href={card.source.url}
            target="_blank"
            rel="noreferrer"
            className={`inline-flex items-center gap-2 font-display font-medium text-sm ${titleColor}`}
          >
            Clinical Reference
            <span className={isCritical ? 'icon-btn-white' : 'icon-btn'}>
              <ArrowUpRight className="w-4 h-4" strokeWidth={1.5} />
            </span>
          </a>
        )}
      </div>
    </div>
  );
}
