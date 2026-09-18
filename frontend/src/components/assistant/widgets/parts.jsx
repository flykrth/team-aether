import React, { createContext, useContext } from 'react';

// Widgets sit on the grey canvas in the workspace ("surface": white card, grey inner wells) and on a
// white sheet in the floating panel ("well": grey card, white inner wells).
export const WidgetTone = createContext('surface');

export const HAZARD_CLS = {
  LOW: 'bg-success-light text-success-dark',
  MODERATE: 'bg-warning-light text-warning-dark',
  CRITICAL: 'bg-danger-light text-danger-dark',
};

export const APPOINTMENT_TILE = {
  SCHEDULED: { label: 'Scheduled', cls: 'bg-app-secondary text-text-secondary', dot: 'bg-ink-muted' },
  REQUIRES_ACTION: { label: 'On hold · requires action', cls: 'bg-warning-light text-warning-dark', dot: 'bg-warning' },
  CLEARED_FOR_CARE: { label: 'Cleared for care', cls: 'bg-success-light text-success-dark', dot: 'bg-success' },
};

export const pretty = (s) => (s || '').replace(/_/g, ' ').toLowerCase().replace(/^\w/, (c) => c.toUpperCase());
export const asList = (value) => (Array.isArray(value) ? value : value == null || value === '' ? [] : [value]);
export const money = (n) => (typeof n === 'number' ? `$${n.toLocaleString(undefined, { maximumFractionDigits: 0 })}` : null);

// Coded concepts arrive as {code, display} from get_patient_history, as "CODE Display" strings from
// the agent state, and as {type, text, code} history entries. Normalize to {code, label}.
export const toConcept = (item) => {
  if (item == null) return null;
  if (typeof item === 'string') return { code: null, label: item };
  const label = item.display || item.text || item.description || item.name || item.test || item.code || '';
  const code = item.code && item.code !== label ? item.code : item.cdt_code || null;
  return { code, label: String(label), type: item.type || null, detail: item.onset || item.drug_class || null };
};

export function WidgetShell({ Icon, title, subtitle, badge, children, className = '' }) {
  const tone = useContext(WidgetTone);
  return (
    <section className={`rounded-3xl p-4 sm:p-5 animate-fade-in ${tone === 'well' ? 'bg-app-secondary' : 'bg-app-surface'} ${className}`}>
      <header className="flex items-center gap-3">
        {Icon && (
          <span className="inline-flex items-center justify-center w-9 h-9 rounded-full bg-accent-soft text-accent-deep shrink-0">
            <Icon className="w-4 h-4" strokeWidth={1.5} />
          </span>
        )}
        <div className="min-w-0 flex-1">
          <div className="font-display font-medium text-[15px] leading-tight text-ink truncate">{title}</div>
          {subtitle && <div className="text-xs text-text-muted truncate mt-0.5">{subtitle}</div>}
        </div>
        {badge}
      </header>
      {children && <div className="mt-4 space-y-4">{children}</div>}
    </section>
  );
}

export function Inner({ children, className = '' }) {
  const tone = useContext(WidgetTone);
  return <div className={`rounded-2xl p-3 ${tone === 'well' ? 'bg-app-surface' : 'bg-app-secondary'} ${className}`}>{children}</div>;
}

export function Group({ label, count, children }) {
  return (
    <div>
      <div className="eyebrow mb-2">{label}{typeof count === 'number' ? ` · ${count}` : ''}</div>
      {children}
    </div>
  );
}

export function Badge({ children, cls = 'bg-app-secondary text-text-secondary' }) {
  return <span className={`inline-flex items-center gap-1.5 h-6 px-2.5 rounded-full text-[11px] font-medium shrink-0 whitespace-nowrap ${cls}`}>{children}</span>;
}

const CONCEPT_CLS = {
  neutral: 'bg-app-bg text-text-main',
  accent: 'bg-accent-soft text-accent-deep',
  danger: 'bg-danger-light text-danger-dark',
  warning: 'bg-warning-light text-warning-dark',
  success: 'bg-success-light text-success-dark',
  muted: 'bg-app-bg text-text-muted',
};

// Chips wrap instead of truncating: clinical text must never be cut off.
export function ConceptChips({ items, tone = 'neutral', empty = 'None recorded' }) {
  const concepts = asList(items).map(toConcept).filter((c) => c && c.label);
  if (!concepts.length) return <p className="text-xs text-text-muted">{empty}</p>;
  return (
    <div className="flex flex-wrap gap-1.5">
      {concepts.map((c, i) => (
        <span key={`${c.code}-${c.label}-${i}`} className={`inline-flex items-baseline gap-1.5 min-h-7 px-3 py-1 rounded-2xl text-xs font-medium ${CONCEPT_CLS[tone]}`}>
          {c.code && <span className="font-mono text-[10px] opacity-70 shrink-0">{c.code}</span>}
          <span>{c.label}</span>
        </span>
      ))}
    </div>
  );
}

export function BulletList({ items, dot = 'bg-ink-muted' }) {
  return (
    <ul className="space-y-1.5">
      {asList(items).map((item, i) => (
        <li key={i} className="flex gap-2.5 text-[13px] leading-snug text-text-main">
          <span className={`mt-[0.45em] w-1.5 h-1.5 rounded-full shrink-0 ${dot}`} />
          <span className="min-w-0">{String(item)}</span>
        </li>
      ))}
    </ul>
  );
}

export function Fact({ label, value, mono = false }) {
  if (value == null || value === '') return null;
  return (
    <div className="min-w-0">
      <div className="text-[10px] uppercase tracking-[0.12em] text-text-muted">{label}</div>
      <div className={`text-[13px] text-text-main break-words ${mono ? 'font-mono' : ''}`}>{value}</div>
    </div>
  );
}

// Tool results that came back as "not found" / error dicts still get a calm card.
export function Notice({ Icon, title, message }) {
  return (
    <WidgetShell Icon={Icon} title={title}>
      <p className="text-[13px] text-text-secondary">{message}</p>
    </WidgetShell>
  );
}

export const failureMessage = (data) => {
  if (!data || typeof data !== 'object') return 'No data was returned.';
  if (data.error) return String(data.error);
  if (data.found === false || data.ok === false) return String(data.message || 'Nothing was found.');
  return null;
};
