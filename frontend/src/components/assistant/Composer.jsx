import React, { useCallback, useEffect, useImperativeHandle, useRef, useState, forwardRef } from 'react';
import { ArrowUp, Mic, Square, Loader2, X, AudioLines, Paperclip, FileText } from 'lucide-react';
import { api } from '../../services/api';
import { useVoiceInput } from './useVoiceInput';
import { providerLabel } from './toolLabels';

// How long a voice transcript sits in the input, visibly counting down, before it sends itself.
const VOICE_SEND_DELAY_S = 3;

const clock = (s) => `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`;

/**
 * Message composer: textarea + mic + send. Typed text is only ever sent by the user (Enter / button).
 * A voice transcript lands in the input and auto-sends after a short, cancellable countdown.
 * Keyboard: Enter sends, Shift+Enter newline, Esc stops recording (transcript stays in the input, unsent)
 * or cancels a pending voice send.
 */
export const Composer = forwardRef(function Composer(
  { onSend, busy = false, disabled = false, serverSpeech, onVoiceMode, compact = false, placeholder, autoFocus = false },
  ref,
) {
  const [draft, setDraft] = useState('');
  const [pending, setPending] = useState(null); // { provider, seconds } while a voice transcript counts down
  const [files, setFiles] = useState([]);       // [{ filename, text, method, pages, found }] read and waiting to be sent
  const [reading, setReading] = useState(false);
  const [fileError, setFileError] = useState(null);
  const [dragging, setDragging] = useState(false);
  const fileRef = useRef(null);
  const filesRef = useRef(files);
  filesRef.current = files;

  // The file is read once, server-side (local PDF text layer, else an OCR model); the chat then
  // carries its text. Nothing is charted by attaching: the agent only imports when asked.
  const attach = useCallback(async (file) => {
    if (!file) return;
    setReading(true); setFileError(null);
    try {
      const doc = await api.extractRecordFile(file);
      setFiles((current) => [...current.filter((f) => f.filename !== file.name), {
        filename: file.name, text: doc.text, method: doc.method, pages: doc.pages, found: (doc.entries || []).length,
      }].slice(-3));
      inputRef.current?.focus();
    } catch (err) {
      setFileError(err.detail || err.message || 'That file could not be read.');
    } finally {
      setReading(false);
    }
  }, []);
  const inputRef = useRef(null);
  const draftRef = useRef(draft);
  draftRef.current = draft;

  const submit = useCallback((viaVoice = false) => {
    const attachments = filesRef.current;
    const text = draftRef.current.trim() || (attachments.length ? 'What does this document say about the patient?' : '');
    setPending(null);
    if (!text || busy || disabled) return;
    onSend(text, { viaVoice, attachments });
    setDraft('');
    setFiles([]);
  }, [busy, disabled, onSend]);

  const voice = useVoiceInput({
    serverSpeech,
    onTranscript: (text, { provider, send }) => {
      setDraft((current) => (current.trim() ? `${current.trimEnd()} ${text}` : text));
      inputRef.current?.focus();
      if (send) setPending({ provider, seconds: VOICE_SEND_DELAY_S });
    },
  });

  useEffect(() => { onVoiceMode?.(voice.mode); }, [voice.mode, onVoiceMode]);

  // parent can prefill a question (patient list rows, widget shortcuts)
  useImperativeHandle(ref, () => ({
    prefill: (text) => { setPending(null); setDraft(text); requestAnimationFrame(() => inputRef.current?.focus()); },
    focus: () => inputRef.current?.focus(),
  }), []);

  useEffect(() => { if (autoFocus) inputRef.current?.focus(); }, [autoFocus]);

  // voice countdown -> auto-send
  useEffect(() => {
    if (!pending) return undefined;
    if (pending.seconds <= 0) { submit(true); return undefined; }
    const timer = setTimeout(() => setPending((p) => (p ? { ...p, seconds: p.seconds - 1 } : p)), 1000);
    return () => clearTimeout(timer);
  }, [pending, submit]);

  // Esc must work wherever focus is while the mic is live
  const recording = voice.state === 'recording';
  useEffect(() => {
    if (!recording && !pending) return undefined;
    const onKey = (e) => {
      if (e.key !== 'Escape') return;
      e.preventDefault();
      if (recording) voice.stop(false);
      else setPending(null);
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [recording, pending, voice.stop]); // eslint-disable-line react-hooks/exhaustive-deps

  // the textarea is swapped out while the mic is live: hand focus back once it returns
  const voiceState = voice.state;
  const wasVoiceActive = useRef(false);
  useEffect(() => {
    if (voiceState !== 'idle') wasVoiceActive.current = true;
    else if (wasVoiceActive.current) { wasVoiceActive.current = false; inputRef.current?.focus(); }
  }, [voiceState]);

  // grow with the text, up to a cap
  useEffect(() => {
    const el = inputRef.current;
    if (!el) return;
    el.style.height = 'auto';
    el.style.height = `${Math.min(el.scrollHeight, compact ? 128 : 200)}px`;
  }, [draft, compact, voiceState]);

  const transcribing = voice.state === 'transcribing';
  const size = compact ? 'w-9 h-9' : 'w-11 h-11';

  return (
    <div>
      {voice.error && (
        <div className="mb-2 flex items-start gap-2 rounded-2xl bg-warning-light text-warning-dark text-xs px-3 py-2 animate-fade-in">
          <span className="min-w-0 flex-1">{voice.error}</span>
          <button type="button" onClick={voice.clearError} aria-label="Dismiss" className="shrink-0 opacity-70 hover:opacity-100"><X className="w-3.5 h-3.5" /></button>
        </div>
      )}

      {(files.length > 0 || reading || fileError) && (
        <div className="mb-2 flex flex-wrap items-center gap-2 animate-fade-in">
          {files.map((f) => (
            <span key={f.filename} className="inline-flex items-center gap-2 h-8 pl-3 pr-1.5 rounded-full bg-accent-soft text-accent-deep text-xs font-medium max-w-full"
              title={`${f.method === 'pdf-text-layer' ? 'Read on this machine' : f.method === 'nvidia-nemotron-parse' || f.method === 'gemini-transcription' ? 'Scanned document, read by AI' : 'Text file'}${f.pages ? ` · ${f.pages} page${f.pages > 1 ? 's' : ''}` : ''}`}>
              <FileText className="w-3.5 h-3.5 shrink-0" strokeWidth={1.5} />
              <span className="truncate max-w-[220px]">{f.filename}</span>
              <span className="opacity-70 shrink-0">{f.found} finding{f.found === 1 ? '' : 's'}</span>
              <button type="button" onClick={() => setFiles((c) => c.filter((x) => x.filename !== f.filename))} aria-label={`Remove ${f.filename}`} className="p-1 rounded-full hover:bg-white/60"><X className="w-3 h-3" /></button>
            </span>
          ))}
          {reading && <span className="inline-flex items-center gap-2 text-xs text-text-muted"><Loader2 className="w-3.5 h-3.5 animate-spin" /> Reading document…</span>}
          {fileError && (
            <span className="inline-flex items-center gap-2 text-xs text-danger-dark bg-danger-light rounded-full px-3 h-8">
              {fileError}
              <button type="button" onClick={() => setFileError(null)} aria-label="Dismiss"><X className="w-3 h-3" /></button>
            </span>
          )}
        </div>
      )}

      {pending && (
        <div className="mb-2 flex flex-wrap items-center gap-2 rounded-2xl bg-accent-soft text-accent-deep text-xs px-3 py-2 animate-fade-in" role="status">
          <AudioLines className="w-3.5 h-3.5 shrink-0" strokeWidth={1.5} />
          <span className="min-w-0 flex-1">
            Voice message{pending.provider ? ' · transcribed' : ''} · sending in {pending.seconds}s
          </span>
          <button type="button" onClick={() => submit(true)} className="font-semibold hover:underline">Send now</button>
          <button type="button" onClick={() => { setPending(null); inputRef.current?.focus(); }} className="font-medium opacity-80 hover:opacity-100">Edit first</button>
        </div>
      )}

      <form
        onSubmit={(e) => { e.preventDefault(); submit(Boolean(pending)); }}
        onDragOver={(e) => { if (e.dataTransfer?.types?.includes('Files')) { e.preventDefault(); setDragging(true); } }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => { e.preventDefault(); setDragging(false); attach(e.dataTransfer.files?.[0]); }}
        className={`flex items-end gap-2 p-2 transition-colors ${compact ? 'rounded-3xl' : 'rounded-4xl'} ${dragging ? 'ring-2 ring-accent' : ''} ${
          recording ? 'bg-danger-light' : compact ? 'bg-app-secondary' : 'bg-app-surface'} focus-within:ring-2 ${recording ? 'ring-2 ring-danger/30' : 'focus-within:ring-accent/30'}`}
      >
        <input ref={fileRef} type="file" accept=".pdf,.txt,.md,.json,.csv,application/pdf,text/plain" className="hidden"
          onChange={(e) => { attach(e.target.files?.[0]); e.target.value = ''; }} />
        {!recording && !transcribing && (
          <button
            type="button"
            onClick={() => fileRef.current?.click()}
            disabled={reading || disabled}
            aria-label="Attach a PDF or text file"
            title="Attach a PDF or text file"
            className={`inline-flex items-center justify-center rounded-full shrink-0 text-text-secondary hover:text-text-main hover:bg-app-secondary disabled:opacity-30 ${size}`}
          >
            {reading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Paperclip className="w-4 h-4" strokeWidth={1.5} />}
          </button>
        )}
        {recording || transcribing ? (
          <div className={`flex-1 flex items-center gap-3 px-3 ${compact ? 'min-h-9' : 'min-h-11'} text-sm ${recording ? 'text-danger-dark' : 'text-text-secondary'}`} role="status" aria-live="polite">
            {recording ? (
              <>
                <span className="relative flex w-2.5 h-2.5 shrink-0">
                  <span className="absolute inset-0 rounded-full bg-danger animate-ping opacity-60" />
                  <span className="relative w-2.5 h-2.5 rounded-full bg-danger" />
                </span>
                <span className="font-mono text-xs tabular-nums">{clock(voice.elapsed)}</span>
                <span className="min-w-0 truncate">Listening… tap the mic to send{compact ? '' : ', Esc to stop and edit'}</span>
              </>
            ) : (
              <><Loader2 className="w-4 h-4 animate-spin shrink-0" /> Transcribing…</>
            )}
          </div>
        ) : (
          <textarea
            ref={inputRef}
            value={draft}
            onChange={(e) => { setDraft(e.target.value); if (pending) setPending(null); }}
            onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) { e.preventDefault(); submit(Boolean(pending)); } }}
            rows={1}
            disabled={disabled}
            placeholder={files.length ? 'Ask about this document, or say whose chart it belongs on' : (placeholder || 'Ask about a patient, or tell me what to do')}
            aria-label="Message MAO"
            className={`flex-1 bg-transparent resize-none outline-none text-text-main placeholder:text-text-muted px-3 ${compact ? 'text-sm py-2' : 'text-[15px] py-2.5'}`}
          />
        )}

        {voice.supported && (
          <button
            type="button"
            onClick={voice.toggle}
            disabled={transcribing || disabled}
            aria-pressed={recording}
            aria-label={recording ? 'Stop recording and send' : 'Speak your message'}
            title={recording ? 'Stop and send' : voice.mode === 'server' ? 'Speak (transcribed by the speech model)' : 'Speak (browser dictation)'}
            className={`inline-flex items-center justify-center rounded-full shrink-0 disabled:opacity-30 ${size} ${
              recording ? 'bg-danger text-white hover:bg-danger-dark' : compact ? 'bg-app-surface text-text-main hover:bg-app-bg' : 'bg-app-secondary text-text-main hover:bg-app-bg'}`}
          >
            {recording ? <Square className="w-3.5 h-3.5 fill-current" /> : <Mic className="w-4 h-4" strokeWidth={1.5} />}
          </button>
        )}
        <button
          type="submit"
          disabled={(!draft.trim() && files.length === 0) || busy || disabled || recording || transcribing || reading}
          aria-label="Send"
          className={`inline-flex items-center justify-center rounded-full bg-accent text-white hover:bg-accent-deep disabled:opacity-30 shrink-0 ${size}`}
        >
          {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : <ArrowUp className="w-4 h-4" />}
        </button>
      </form>
    </div>
  );
});
