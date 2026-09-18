import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Sparkles, X, Loader2, RotateCcw, KeyRound, Maximize2, UserX } from 'lucide-react';
import { useAssistantChat } from './assistant/useAssistantChat';
import { Composer } from './assistant/Composer';
import { MessageItem } from './assistant/MessageItem';
import { WidgetTone } from './assistant/widgets';
import { providerLabel } from './assistant/toolLabels';

/**
 * Floating "Ask MAO" launcher. Shares its conversation, widgets and voice input with the full-page
 * AssistantWorkspace (same hook and store), so a chat started here continues there.
 * Optional: hidden (suppress the launcher while the workspace is on screen), onExpand (open the workspace).
 */
export function AssistantPanel({ patient, onPatientsChanged, onOpenIntake, onExpand, hidden = false }) {
  const [open, setOpen] = useState(false);
  const { status, messages, thinking, focus, focusIsFromChat, send, reset, clearFocus } = useAssistantChat({ patient, onPatientsChanged });
  const scrollRef = useRef(null);
  const composerRef = useRef(null);

  const patientName = patient ? `${patient.first_name} ${patient.last_name}` : null;
  const suggestions = [
    patientName ? `Summarize ${patientName}'s medical history` : 'Which patients are scheduled for surgery?',
    'Is a surgical extraction (D7210) safe for Robert Chen?',
    'Run the agents for Robert Chen, D7210',
    'Which patients are on blood thinners?',
  ];

  useEffect(() => {
    const el = scrollRef.current;
    if (open && el) el.scrollTo({ top: el.scrollHeight, behavior: 'smooth' });
  }, [open, messages, thinking]);

  const ask = useCallback((text) => composerRef.current?.prefill(text), []);
  const speech = status?.speech;
  const serverSpeech = !status ? undefined : status.offline ? false : speech ? Boolean(speech.configured) : undefined;

  if (hidden) return null;

  if (!open) {
    return (
      <button
        onClick={() => setOpen(true)}
        className="fixed bottom-6 right-6 z-40 inline-flex items-center gap-2 h-14 pl-5 pr-6 rounded-full bg-ink text-white font-display font-medium text-[15px] hover:bg-ink-soft"
        aria-label="Open MAO Assistant"
      >
        <Sparkles className="w-5 h-5" strokeWidth={1.5} />
        Ask MAO
      </button>
    );
  }

  return (
    <div className="fixed bottom-6 right-6 z-40 w-[min(440px,calc(100vw-2rem))] h-[min(680px,calc(100vh-3rem))] flex flex-col rounded-4xl bg-app-surface ring-1 ring-app-border animate-fade-in overflow-hidden">
      <header className="flex items-center gap-3 px-5 h-16 shrink-0 bg-ink text-white">
        <Sparkles className="w-5 h-5" strokeWidth={1.5} />
        <div className="min-w-0 flex-1">
          <div className="font-display font-medium leading-tight">MAO Assistant</div>
          <div className="text-[11px] text-white/50 truncate">
            {status?.configured ? 'Assistant ready' : 'Not connected'}
            {focus ? ` · viewing ${focus.name}` : ''}
          </div>
        </div>
        {focusIsFromChat && (
          <button onClick={clearFocus} className="p-2 rounded-full hover:bg-white/10"
            title={`Stop following ${focus.name}${patientName ? ` and go back to ${patientName}` : ''}`} aria-label="Clear the chat's patient focus">
            <UserX className="w-4 h-4" strokeWidth={1.5} />
          </button>
        )}
        {messages.length > 0 && (
          <button onClick={reset} className="p-2 rounded-full hover:bg-white/10" title="New conversation" aria-label="New conversation">
            <RotateCcw className="w-4 h-4" strokeWidth={1.5} />
          </button>
        )}
        {onExpand && (
          <button onClick={() => { setOpen(false); onExpand(); }} className="p-2 rounded-full hover:bg-white/10" title="Open the full chat" aria-label="Open the full chat">
            <Maximize2 className="w-4 h-4" strokeWidth={1.5} />
          </button>
        )}
        <button onClick={() => setOpen(false)} className="p-2 rounded-full hover:bg-white/10" aria-label="Close assistant">
          <X className="w-4 h-4" strokeWidth={1.5} />
        </button>
      </header>

      <div ref={scrollRef} className="flex-1 overflow-y-auto px-4 py-4 space-y-4">
        {status && !status.configured && (
          <div className="rounded-3xl bg-warning-light text-warning-dark p-4 text-sm flex gap-3">
            <KeyRound className="w-4 h-4 mt-0.5 shrink-0" strokeWidth={1.5} />
            <span>
              {status.offline
                ? 'The backend is not reachable.'
                : <>Add an AI provider key to <code className="font-mono text-xs">backend/.env</code> and restart the backend to switch the assistant on.</>}
            </span>
          </div>
        )}

        {messages.length === 0 && (
          <div className="pt-2">
            <p className="text-sm text-text-secondary px-1">
              Ask about any patient's history, check whether a procedure is safe, or tell me to run the agents, add a patient, record new history or post a chart alert.
            </p>
            <div className="mt-4 space-y-2">
              {suggestions.map((s) => (
                <button key={s} onClick={() => send(s)} className="w-full text-left well text-sm text-text-main hover:bg-app-bg">
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}

        <WidgetTone.Provider value="well">
          {messages.map((m) => <MessageItem key={m.id} message={m} variant="panel" onAsk={ask} onOpenIntake={onOpenIntake} />)}
        </WidgetTone.Provider>

        {thinking && (
          <div className="inline-flex items-center gap-2 text-sm text-text-muted px-1">
            <Loader2 className="w-4 h-4 animate-spin" /> Working…
          </div>
        )}
      </div>

      <div className="p-3 shrink-0">
        <Composer ref={composerRef} onSend={send} busy={thinking} serverSpeech={serverSpeech} compact autoFocus />
        <p className="text-[10px] text-text-muted text-center mt-2">Decision support on synthetic data. Verify before acting clinically.</p>
      </div>
    </div>
  );
}
