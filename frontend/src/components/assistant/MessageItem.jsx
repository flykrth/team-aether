import React from 'react';
import { Zap, Search, Mic, UsersRound, Sparkles, FileText } from 'lucide-react';
import { FormattedText } from './format';
import { describeAction, providerLabel } from './toolLabels';
import { AssistantWidget } from './widgets';

function ActionChips({ actions, neutral }) {
  if (!actions?.length) return null;
  return (
    <div className="flex flex-wrap gap-1.5">
      {actions.map((a, i) => (
        <span key={i} className={`inline-flex items-center gap-1.5 text-[11px] font-medium min-h-6 px-2.5 py-0.5 rounded-full ${
          a.ok === false ? 'bg-danger-light text-danger-dark' : a.is_action ? 'bg-accent-soft text-accent-deep' : neutral}`}>
          {a.tool === 'consult_specialists' ? <UsersRound className="w-3 h-3" /> : a.is_action ? <Zap className="w-3 h-3" /> : <Search className="w-3 h-3" />}
          {describeAction(a)}{a.ok === false && ' · failed'}
        </span>
      ))}
    </div>
  );
}

/**
 * One turn. variant "page": the assistant speaks as plain text on the canvas with a small mark;
 * variant "panel": compact bubbles for the floating launcher.
 */
export function MessageItem({ message, variant = 'page', onAsk, onOpenIntake }) {
  const page = variant === 'page';

  if (message.role === 'user') {
    return (
      <div className="flex flex-col items-end gap-1 animate-fade-in">
        {(message.attachments || []).map((a) => (
          <span key={a.filename} className="inline-flex items-center gap-2 h-8 px-3 rounded-full bg-app-surface text-text-secondary text-xs max-w-[80%]">
            <FileText className="w-3.5 h-3.5 shrink-0" strokeWidth={1.5} />
            <span className="truncate">{a.filename}</span>
            {a.pages ? <span className="text-text-muted shrink-0">{a.pages} p</span> : null}
          </span>
        ))}
        <div className={`rounded-3xl bg-ink text-white whitespace-pre-wrap break-words leading-relaxed ${page ? 'max-w-[80%] px-5 py-3 text-[15px]' : 'max-w-[85%] px-4 py-3 text-sm'}`}>
          {message.content}
        </div>
        {message.viaVoice && (
          <span className="inline-flex items-center gap-1 text-[10px] text-text-muted pr-2"><Mic className="w-3 h-3" strokeWidth={1.5} /> sent by voice</span>
        )}
      </div>
    );
  }

  // read-only tool chips: white on the page canvas, grey on the panel's white sheet
  const neutral = page ? 'bg-app-surface text-text-secondary' : 'bg-app-secondary text-text-secondary';
  const body = (
    <div className="min-w-0 flex-1 space-y-3">
      <ActionChips actions={message.actions} neutral={neutral} />
      {message.content && (
        <div className={`leading-relaxed ${
          message.error ? 'rounded-3xl bg-danger-light text-danger-dark px-4 py-3 text-sm'
            : page ? 'text-[15px] text-text-main' : 'rounded-3xl bg-app-secondary text-text-main px-4 py-3 text-sm'}`}>
          <FormattedText text={message.content} />
        </div>
      )}
      {message.widgets?.map((w, i) => (
        <AssistantWidget
          key={`${w.type}-${i}`}
          widget={w}
          index={message.widgets.slice(0, i).filter((other) => other?.type === w.type).length}
          actions={message.actions}
          onAsk={onAsk}
          onOpenIntake={onOpenIntake}
        />
      ))}
      {page && !message.error && message.specialists?.length > 0 && (
        <div className="text-[10px] text-text-muted">
          {`${message.specialists.length} specialist${message.specialists.length === 1 ? '' : 's'} consulted in parallel`}
        </div>
      )}
    </div>
  );

  if (!page) return <div className="animate-fade-in">{body}</div>;
  return (
    <div className="flex gap-3 sm:gap-4 animate-fade-in">
      <span className={`inline-flex items-center justify-center w-8 h-8 rounded-full shrink-0 mt-0.5 ${message.error ? 'bg-danger-light text-danger-dark' : 'bg-ink text-white'}`}>
        <Sparkles className="w-4 h-4" strokeWidth={1.5} />
      </span>
      {body}
    </div>
  );
}
