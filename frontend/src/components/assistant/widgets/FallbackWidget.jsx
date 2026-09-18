import React from 'react';
import { Braces } from 'lucide-react';
import { WidgetShell, Inner, pretty } from './parts';

// Unknown widget type (a newer backend than this frontend): show the data rather than nothing.
export function FallbackWidget({ type, data, title }) {
  let body = '';
  try { body = JSON.stringify(data ?? null, null, 2); } catch { body = String(data); }
  return (
    <WidgetShell Icon={Braces} title={title || pretty(type) || 'Result'} subtitle={type}>
      <Inner><pre className="font-mono text-[11px] leading-relaxed text-text-secondary whitespace-pre-wrap break-words max-h-48 overflow-y-auto">{body.slice(0, 4000)}</pre></Inner>
    </WidgetShell>
  );
}
