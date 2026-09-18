import { useCallback, useEffect, useRef, useState } from 'react';
import { api } from '../../services/api';

// Voice capture with two paths:
//   server  : MediaRecorder -> POST /api/assistant/transcribe (Groq Whisper, or a self-hosted NVIDIA Speech NIM
//             when NVIDIA_STT_URL is set; NVIDIA's hosted Nemotron ASR is gRPC-only and is not wired)
//   browser : window.SpeechRecognition (Web Speech API), used when the server has no speech provider
//             or the upload fails.
// While recording for the server path the browser recognizer also listens when it exists, so a failed
// upload (503, network) still yields a transcript instead of making the user repeat themselves.

const MIME_CANDIDATES = ['audio/webm;codecs=opus', 'audio/webm', 'audio/mp4', 'audio/ogg;codecs=opus', 'audio/ogg'];
const EXTENSIONS = { webm: 'webm', mp4: 'mp4', ogg: 'ogg', wav: 'wav' };
const MAX_RECORDING_MS = 60_000;

const getRecognitionClass = () =>
  (typeof window === 'undefined' ? null : window.SpeechRecognition || window.webkitSpeechRecognition || null);

const canRecord = () =>
  typeof window !== 'undefined' && typeof window.MediaRecorder !== 'undefined' && Boolean(navigator.mediaDevices?.getUserMedia);

const pickMimeType = () =>
  MIME_CANDIDATES.find((t) => window.MediaRecorder.isTypeSupported?.(t)) || '';

const isPermissionError = (err) => err?.name === 'NotAllowedError' || err?.name === 'SecurityError' || err === 'not-allowed';

const micErrorMessage = (err) =>
  (isPermissionError(err)
    ? 'Microphone access was blocked. Allow it in the browser to use voice.'
    : 'Could not start the microphone.');

/**
 * useVoiceInput({ serverSpeech, onTranscript })
 *   serverSpeech  false when /status says no speech provider is configured (skips the upload path)
 *   onTranscript  (text, { provider, model, send }) ; send is false when the user pressed Esc
 * Returns { supported, mode, state, elapsed, error, start, stop, toggle, clearError }.
 *   state: 'idle' | 'recording' | 'transcribing'
 */
export function useVoiceInput({ serverSpeech, onTranscript }) {
  const [state, setState] = useState('idle');
  const [elapsed, setElapsed] = useState(0);
  const [error, setError] = useState(null);
  const [serverFailed, setServerFailed] = useState(false);

  const onTranscriptRef = useRef(onTranscript);
  onTranscriptRef.current = onTranscript;
  const mounted = useRef(true); // the permission prompt can outlive the component
  const starting = useRef(false); // guards the await on getUserMedia against a double press
  const session = useRef(null); // { recorder, stream, chunks, recognition, browserText, send, timer, limit }

  const hasBrowser = Boolean(getRecognitionClass());
  const useServer = canRecord() && serverSpeech !== false && !serverFailed;
  const mode = useServer ? 'server' : hasBrowser ? 'browser' : null;

  const cleanup = useCallback(() => {
    const s = session.current;
    if (!s) return;
    clearInterval(s.timer);
    clearTimeout(s.limit);
    s.stream?.getTracks().forEach((t) => t.stop());
    session.current = null;
  }, []);

  const deliver = useCallback((text, meta, send) => {
    const clean = (text || '').trim();
    if (clean) onTranscriptRef.current?.(clean, { ...meta, send });
    else setError('No speech was detected. Try again a little closer to the microphone.');
  }, []);

  const startRecognition = (s, { primary }) => {
    const Recognition = getRecognitionClass();
    if (!Recognition) return null;
    try {
      const recognition = new Recognition();
      recognition.lang = 'en-US';
      recognition.continuous = true;
      recognition.interimResults = false;
      recognition.onresult = (event) => {
        for (let i = event.resultIndex; i < event.results.length; i += 1) {
          if (event.results[i].isFinal) s.browserText = `${s.browserText} ${event.results[i][0].transcript}`.trim();
        }
      };
      if (primary) {
        recognition.onerror = (event) => {
          if (event.error === 'no-speech' || event.error === 'aborted') return;
          s.failed = true;
          setError(event.error === 'not-allowed' || event.error === 'service-not-allowed'
            ? micErrorMessage('not-allowed') : 'Browser speech recognition failed.');
        };
        recognition.onend = () => {
          if (session.current !== s) return;
          cleanup();
          setState('idle');
          if (!s.failed) deliver(s.browserText, { provider: 'browser', model: 'Web Speech API' }, s.send);
        };
      } else {
        recognition.onerror = () => {}; // backup listener only: never surfaces errors
      }
      recognition.start();
      return recognition;
    } catch {
      return null;
    }
  };

  const start = useCallback(async () => {
    if (session.current || starting.current || state !== 'idle' || !mode) return;
    setError(null);
    const s = { chunks: [], browserText: '', send: true, failed: false };
    const startedAt = Date.now();

    if (mode === 'browser') {
      s.recognition = startRecognition(s, { primary: true });
      if (!s.recognition) { setError('Browser speech recognition is not available.'); return; }
    } else {
      starting.current = true;
      try {
        s.stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      } catch (err) {
        if (!mounted.current) return;
        // No usable capture device for MediaRecorder (NotFoundError, NotReadableError): the browser recognizer
        // manages its own audio, so use it from now on instead of failing the same way on every press.
        if (!isPermissionError(err) && hasBrowser) {
          setServerFailed(true);
          setError('Could not record audio for the server. Switched to browser dictation: press the mic and try again.');
        } else {
          setError(micErrorMessage(err));
        }
        return;
      } finally {
        starting.current = false;
      }
      if (!mounted.current) {
        // Unmounted while the permission prompt was up: release the mic or the recording indicator stays on.
        s.stream.getTracks().forEach((t) => t.stop());
        return;
      }
      const mimeType = pickMimeType();
      s.recorder = new window.MediaRecorder(s.stream, mimeType ? { mimeType } : undefined);
      s.recorder.ondataavailable = (event) => { if (event.data?.size) s.chunks.push(event.data); };
      s.recorder.onstop = async () => {
        const type = (s.recorder.mimeType || mimeType || 'audio/webm').split(';')[0];
        try { s.recognition?.stop(); } catch { /* already stopped */ }
        cleanup();
        const blob = new Blob(s.chunks, { type });
        if (!blob.size) { setState('idle'); deliver('', {}, s.send); return; }
        setState('transcribing');
        try {
          const ext = EXTENSIONS[type.split('/')[1]] || 'webm';
          const res = await api.transcribeAudio(blob, `voice.${ext}`);
          deliver(res.text, { provider: res.provider, model: res.model }, s.send);
        } catch (err) {
          // Server speech is unavailable: stay on the browser recognizer from now on.
          if (hasBrowser) setServerFailed(true);
          if (s.browserText) deliver(s.browserText, { provider: 'browser', model: 'Web Speech API' }, s.send);
          else if (hasBrowser) setError('Server transcription is unavailable. Switched to browser dictation: press the mic and try again.');
          else setError(err.detail || 'Transcription failed.');
        } finally {
          setState('idle');
        }
      };
      s.recorder.start();
      s.recognition = startRecognition(s, { primary: false });
    }

    s.timer = setInterval(() => setElapsed(Math.floor((Date.now() - startedAt) / 1000)), 250);
    s.limit = setTimeout(() => stopRef.current?.(true), MAX_RECORDING_MS);
    session.current = s;
    setElapsed(0);
    setState('recording');
  }, [state, mode, hasBrowser, cleanup, deliver]); // eslint-disable-line react-hooks/exhaustive-deps

  // stop(true): transcribe and let the caller auto-send. stop(false) (Esc): transcribe into the input only.
  const stop = useCallback((send = true) => {
    const s = session.current;
    if (!s) return;
    s.send = send;
    clearInterval(s.timer);
    clearTimeout(s.limit);
    if (s.recorder) {
      if (s.recorder.state !== 'inactive') s.recorder.stop();
    } else {
      try { s.recognition?.stop(); } catch { cleanup(); setState('idle'); }
    }
  }, [cleanup]);
  const stopRef = useRef(stop);
  stopRef.current = stop;

  const toggle = useCallback(() => (session.current ? stop(true) : start()), [start, stop]);

  // Release the microphone if the component unmounts mid-recording.
  useEffect(() => {
    mounted.current = true; // StrictMode runs effects twice: re-arm on every mount
    return () => { mounted.current = false; };
  }, []);
  useEffect(() => () => {
    const s = session.current;
    if (!s) return;
    if (s.recorder) s.recorder.onstop = null;
    if (s.recognition) s.recognition.onend = null;
    try { s.recorder?.state !== 'inactive' && s.recorder?.stop(); } catch { /* ignore */ }
    try { s.recognition?.abort(); } catch { /* ignore */ }
    cleanup();
  }, [cleanup]);

  return { supported: Boolean(mode), mode, state, elapsed, error, start, stop, toggle, clearError: () => setError(null) };
}
