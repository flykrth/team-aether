import React from 'react';
import { Mic, Square, Loader2 } from 'lucide-react';
import { useVoiceInput } from '../assistant/useVoiceInput';

/** Tap to dictate, tap again to stop. onText(transcript) receives the words; the caller decides what to do with them. */
export function VoiceButton({ onText, serverSpeech, label = 'Dictate', className = '' }) {
  const voice = useVoiceInput({ serverSpeech, onTranscript: (text) => onText?.(text) });
  if (!voice.supported) return null;
  const recording = voice.state === 'recording';
  const transcribing = voice.state === 'transcribing';
  return (
    <span className={`inline-flex items-center gap-2 ${className}`}>
      {recording && <span className="text-xs text-danger-dark tabular-nums" role="status">Listening… {voice.elapsed}s</span>}
      {voice.error && !recording && <span className="text-xs text-warning-dark max-w-[220px] truncate" title={voice.error}>{voice.error}</span>}
      <button
        type="button"
        onClick={voice.toggle}
        disabled={transcribing}
        aria-pressed={recording}
        aria-label={recording ? 'Stop dictating' : label}
        title={recording ? 'Stop' : `${label} (${voice.mode === 'server' ? 'speech model' : 'browser dictation'})`}
        className={`inline-flex items-center justify-center w-9 h-9 rounded-full shrink-0 disabled:opacity-40 ${recording ? 'bg-danger text-white animate-pulse' : 'bg-white text-text-main hover:bg-app-bg'}`}
      >
        {transcribing ? <Loader2 className="w-4 h-4 animate-spin" /> : recording ? <Square className="w-3 h-3 fill-current" /> : <Mic className="w-4 h-4" strokeWidth={1.5} />}
      </button>
    </span>
  );
}
