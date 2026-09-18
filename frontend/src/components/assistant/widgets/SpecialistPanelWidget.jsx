import React from 'react';
import { UsersRound, Timer, TriangleAlert } from 'lucide-react';
import { WidgetShell, Inner, Badge, Notice, failureMessage, asList, pretty } from './parts';
import { FormattedText } from '../format';
import { providerLabel } from '../toolLabels';

const COLUMNS = { 1: 'lg:grid-cols-1', 2: 'lg:grid-cols-2', 3: 'lg:grid-cols-3' };

export function SpecialistPanelWidget({ data, title }) {
  const failure = failureMessage(data);
  if (failure) return <Notice Icon={UsersRound} title={title || 'Specialist panel'} message={failure} />;

  const opinions = asList(data.opinions);
  const answered = opinions.filter((o) => o.ok !== false);
  // Specialists run concurrently, so the wall-clock cost is the slowest one, not the sum.
  const slowest = Math.max(0, ...answered.map((o) => Number(o.latency_ms) || 0));

  return (
    <WidgetShell
      Icon={UsersRound}
      title={title || 'Specialist panel'}
      subtitle={`${answered.length} of ${opinions.length} answered in parallel${slowest ? ` · ${(slowest / 1000).toFixed(1)}s wall clock` : ''}`}
      badge={<Badge cls="bg-accent-soft text-accent-deep">Advisory only</Badge>}
    >
      <div className={`grid grid-cols-1 gap-2 ${COLUMNS[Math.min(opinions.length, 3)] || ''}`}>
        {opinions.map((o, i) => (
          <Inner key={`${o.role}-${i}`} className="flex flex-col min-w-0">
            <div className="font-display font-medium text-[13px] text-ink leading-tight">{o.label || pretty(o.role || 'specialist')}</div>
            <div className="flex flex-wrap items-center gap-x-2 gap-y-0.5 mt-1 text-[10px] text-text-muted">
              {o.latency_ms != null && <span className="inline-flex items-center gap-0.5"><Timer className="w-3 h-3" />{Math.round(o.latency_ms)} ms</span>}
            </div>
            <div className={`mt-2.5 text-[13px] leading-relaxed max-h-56 overflow-y-auto pr-1 ${o.ok === false ? 'text-danger-dark' : 'text-text-main'}`}>
              {o.ok === false
                ? <span className="inline-flex gap-1.5"><TriangleAlert className="w-3.5 h-3.5 mt-0.5 shrink-0" strokeWidth={1.5} />{o.error || o.text || 'This specialist did not answer.'}</span>
                : <FormattedText text={o.text || ''} />}
            </div>
          </Inner>
        ))}
      </div>
      <p className="text-[11px] text-text-muted">Specialists have no tools and cannot take actions. Coded findings still come from the deterministic rules.</p>
    </WidgetShell>
  );
}
