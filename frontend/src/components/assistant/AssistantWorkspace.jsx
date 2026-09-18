import React, { useCallback, useEffect, useRef, useState } from 'react';
import {
  Sparkles, RotateCcw, FolderPlus, KeyRound, WifiOff, Loader2, Cpu, Mic, MicOff, UserRound, X,
  Search, ShieldAlert, Zap, UserPlus,
} from 'lucide-react';
import { useAssistantChat } from './useAssistantChat';
import { Composer } from './Composer';
import { MessageItem } from './MessageItem';
import { providerLabel } from './toolLabels';

// Example prompts grouped by intent. send:false prompts are templates the user finishes first.
const promptGroups = (name) => [
  {
    label: 'Ask about a patient', Icon: Search,
    prompts: [
      { text: name ? `Summarize ${name}'s medical history` : "Summarize Robert Chen's medical history", send: true },
      { text: 'Which patients are on blood thinners?', send: true },
    ],
  },
  {
    label: 'Check a procedure', Icon: ShieldAlert,
    prompts: [
      { text: `Is a surgical extraction (D7210) safe for ${name || 'Robert Chen'}?`, send: true },
      { text: 'Get a second opinion from the specialists on extracting a tooth for John Doe while he is on warfarin', send: true },
    ],
  },
  {
    label: 'Take an action', Icon: Zap,
    prompts: [
      { text: 'Run the agents for Robert Chen, D7210', send: true },
      { text: 'File the physician reply for Robert Chen: cleared for extraction, max 2 carpules of 1:100k epinephrine, continue aspirin', send: true },
    ],
  },
  {
    label: 'Add a patient or history, just describe it', Icon: UserPlus,
    prompts: [
      { text: 'New patient Maria Alvarez, born 1968-04-12, female. She has type 2 diabetes and takes metformin and lisinopril, allergic to penicillin. Planned D7140 on tooth 30.', send: false },
      { text: `Add to ${name || "Jane Smith"}'s history: diagnosed with atrial fibrillation last year, now on apixaban`, send: false },
    ],
  },
];

function HeaderChip({ Icon, children, title, tone = 'bg-app-surface text-text-secondary' }) {
  return (
    <span title={title} className={`inline-flex items-center gap-1.5 h-7 px-3 rounded-full text-xs font-medium max-w-full ${tone}`}>
      <Icon className="w-3.5 h-3.5 shrink-0" strokeWidth={1.5} />
      <span className="truncate">{children}</span>
    </span>
  );
}

/**
 * AssistantWorkspace({ patient, onPatientsChanged, onOpenIntake })
 * The dedicated full-page chat: one centered conversation column, composer pinned at the bottom.
 */
export function AssistantWorkspace({ patient, onPatientsChanged, onOpenIntake, heightClass = 'h-[calc(100vh-13rem)]' }) {
  const { status, messages, thinking, focus, focusIsFromChat, send, reset, clearFocus, refreshStatus } =
    useAssistantChat({ patient, onPatientsChanged });
  const [voiceMode, setVoiceMode] = useState(null);
  const scrollRef = useRef(null);
  const composerRef = useRef(null);

  useEffect(() => {
    const el = scrollRef.current;
    if (el) el.scrollTo({ top: el.scrollHeight, behavior: 'smooth' });
  }, [messages, thinking]);

  const ask = useCallback((text) => composerRef.current?.prefill(text), []);
  const patientName = patient ? `${patient.first_name} ${patient.last_name}` : null;

  const offline = Boolean(status?.offline);
  const ready = Boolean(status?.configured);
  const speech = status?.speech;
  const serverSpeech = !status ? undefined : offline ? false : speech ? Boolean(speech.configured) : undefined;
  const speechLabel = voiceMode === 'server'
    ? 'Voice on'
    : voiceMode === 'browser' ? 'Browser dictation' : 'Voice unavailable';

  return (
    <section className={`flex flex-col ${heightClass} min-h-[520px] animate-fade-in`} aria-label="MAO Assistant">
      {/* header: master model, speech path, patient in focus */}
      <header className="shrink-0 w-full max-w-3xl mx-auto flex flex-wrap items-center gap-2 pb-4">
        <HeaderChip
          Icon={!status ? Loader2 : offline ? WifiOff : ready ? Cpu : KeyRound}
          tone={!status || ready ? 'bg-app-surface text-text-secondary' : 'bg-warning-light text-warning-dark'}
        >
          {!status ? 'Connecting…' : offline ? 'Backend offline' : ready
            ? 'Assistant ready'
            : 'Not connected'}
        </HeaderChip>
        <HeaderChip Icon={voiceMode ? Mic : MicOff} title={undefined}>
          {speechLabel}
        </HeaderChip>
        {focus && (
          <span className="inline-flex items-center gap-1.5 h-7 pl-3 pr-1.5 rounded-full text-xs font-medium bg-accent-soft text-accent-deep max-w-full" title="Patient in focus for this conversation">
            <UserRound className="w-3.5 h-3.5 shrink-0" strokeWidth={1.5} />
            <span className="truncate">{focus.name}</span>
            <span className="font-mono text-[10px] opacity-70 shrink-0">{focus.id}</span>
            {focusIsFromChat
              ? <button type="button" onClick={clearFocus} aria-label="Clear patient focus" title={patientName ? `Back to ${patientName}` : 'Clear focus'} className="inline-flex items-center justify-center w-5 h-5 rounded-full hover:bg-white/70 shrink-0"><X className="w-3 h-3" /></button>
              : <span className="w-1.5" />}
          </span>
        )}
        <div className="flex items-center gap-2 ml-auto">
          {onOpenIntake && (
            <button type="button" onClick={() => onOpenIntake(focus?.id)} className="inline-flex items-center gap-1.5 h-9 px-4 rounded-full bg-app-surface text-text-main text-[13px] font-display font-medium hover:bg-app-secondary">
              <FolderPlus className="w-4 h-4" strokeWidth={1.5} /> Patient records
            </button>
          )}
          {messages.length > 0 && (
            <button type="button" onClick={reset} title="New conversation" aria-label="New conversation" className="inline-flex items-center justify-center w-9 h-9 rounded-full bg-app-surface text-text-main hover:bg-app-secondary">
              <RotateCcw className="w-4 h-4" strokeWidth={1.5} />
            </button>
          )}
        </div>
      </header>

      {/* conversation */}
      <div ref={scrollRef} className="flex-1 min-h-0 overflow-y-auto -mx-2 px-2">
        <div className="w-full max-w-3xl mx-auto pb-6">
          {status && !ready && (
            <div className="rounded-3xl bg-warning-light text-warning-dark p-4 text-sm flex items-start gap-3 mb-6">
              {offline ? <WifiOff className="w-4 h-4 mt-0.5 shrink-0" strokeWidth={1.5} /> : <KeyRound className="w-4 h-4 mt-0.5 shrink-0" strokeWidth={1.5} />}
              <span className="min-w-0 flex-1">
                {offline
                  ? 'The backend is not reachable, so the assistant cannot answer yet.'
                  : <>No AI provider is configured. Add a provider key to <code className="font-mono text-xs">backend/.env</code> (see <code className="font-mono text-xs">.env.example</code>) and restart the backend.</>}
              </span>
              <button type="button" onClick={refreshStatus} className="font-semibold text-xs shrink-0 hover:underline">Check again</button>
            </div>
          )}

          {messages.length === 0 ? (
            <div className="pt-6 sm:pt-12">
              <span className="inline-flex items-center justify-center w-12 h-12 rounded-full bg-ink text-white">
                <Sparkles className="w-5 h-5" strokeWidth={1.5} />
              </span>
              <h2 className="display-lg text-ink mt-5">What do you need{patientName ? ` for ${patient.first_name}` : ''}?</h2>
              <p className="text-text-secondary mt-2">Ask, or tell me what to do. Type or talk.</p>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-6 gap-y-7 mt-10">
                {promptGroups(patientName).map(({ label, Icon, prompts }) => (
                  <div key={label}>
                    <div className="eyebrow flex items-center gap-1.5 mb-2.5"><Icon className="w-3.5 h-3.5" strokeWidth={1.5} />{label}</div>
                    <div className="space-y-2">
                      {prompts.map((p) => (
                        <button
                          key={p.text}
                          type="button"
                          onClick={() => (p.send && ready ? send(p.text) : ask(p.text))}
                          className="w-full text-left rounded-3xl bg-app-surface hover:bg-app-secondary px-4 py-3 text-sm text-text-main leading-snug"
                        >
                          {p.text}
                          {!p.send && <span className="block text-[11px] text-text-muted mt-1">Fills the box so you can edit it first</span>}
                        </button>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <div className="space-y-8 pt-2">
              {messages.map((m) => <MessageItem key={m.id} message={m} onAsk={ask} onOpenIntake={onOpenIntake} />)}
            </div>
          )}

          {thinking && (
            <div className="flex items-center gap-3 sm:gap-4 mt-8 text-sm text-text-muted animate-fade-in" role="status">
              <span className="inline-flex items-center justify-center w-8 h-8 rounded-full bg-ink text-white shrink-0"><Loader2 className="w-4 h-4 animate-spin" /></span>
              Working: reading records and calling tools…
            </div>
          )}
        </div>
      </div>

      {/* composer pinned at the bottom */}
      <div className="shrink-0 w-full max-w-3xl mx-auto pt-3">
        <Composer
          ref={composerRef}
          onSend={send}
          busy={thinking}
          serverSpeech={serverSpeech}
          onVoiceMode={setVoiceMode}
          autoFocus
          placeholder={focus ? `Ask about ${focus.name}, or describe a patient or history to add` : 'Ask about a patient, or describe one to add'}
        />
        <p className="text-[11px] text-text-muted text-center mt-2.5">
          Enter to send · Shift+Enter for a new line · Esc stops the mic · Decision support on synthetic data, verify before acting clinically.
        </p>
      </div>
    </section>
  );
}
