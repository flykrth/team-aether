import React from 'react';
import { ShieldQuestion, Quote, ExternalLink } from 'lucide-react';
import { WidgetShell, Group, Badge, BulletList, Notice, failureMessage, asList } from './parts';

const TONE = {
  potential_pathway: 'bg-accent-soft text-accent-deep', no_pathway: 'bg-app-secondary text-text-main',
  needs_review: 'bg-warning-light text-warning-dark', dental_active: 'bg-success-light text-success-dark',
};

export function CoverageResultWidget({ data, title }) {
  const failure = failureMessage(data);
  if (failure) return <Notice Icon={ShieldQuestion} title={title || 'Insurance check'} message={failure} />;
  const quotes = asList(data.policy_quotes);
  const missing = asList(data.missing_information);
  return (
    <WidgetShell Icon={ShieldQuestion} title={title || 'Insurance check'}
      subtitle={[data.patient_name, `dental benefit ${data.dental_benefit}`, data.medical_insurer].filter(Boolean).join(' · ')}
      badge={<Badge cls={TONE[data.outcome] || TONE.needs_review}>{data.headline}</Badge>}>
      <p className="text-[13px] text-text-main leading-relaxed">{data.reason}</p>
      {quotes.length > 0 && (
        <Group label="What the documents say" count={quotes.length}>
          <div className="space-y-2">
            {quotes.slice(0, 3).map((q, i) => (
              <div key={i} className="flex gap-2">
                <Quote className="w-3.5 h-3.5 text-text-muted mt-0.5 shrink-0" strokeWidth={1.5} />
                <div className="min-w-0">
                  <p className="text-[13px] text-text-main leading-relaxed">{q.quote}</p>
                  <p className="text-[11px] text-text-muted mt-1">{q.source}
                    {q.url && <a href={q.url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 ml-2 text-accent-deep hover:underline">source <ExternalLink className="w-3 h-3" /></a>}</p>
                </div>
              </div>
            ))}
          </div>
        </Group>
      )}
      {missing.length > 0 && <Group label="The chart still needs to answer" count={missing.length}><BulletList items={missing} dot="bg-warning" /></Group>}
      {data.next_step?.next && <p className="text-[11px] text-text-muted">Next: {data.next_step.next}</p>}
    </WidgetShell>
  );
}
