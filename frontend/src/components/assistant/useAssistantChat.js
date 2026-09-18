import { useCallback, useEffect, useRef, useSyncExternalStore } from 'react';
import { api } from '../../services/api';

// One conversation shared by the full-page workspace and the floating "Ask MAO" panel. It lives in a
// module-level store (not component state) so both surfaces stay in sync, and is mirrored to
// sessionStorage so switching tabs or a hot reload does not lose it.
const STORAGE_KEY = 'mao.assistant.conversation.v1';
const MAX_STORED_MESSAGES = 60;
const MAX_STORED_ATTACHMENT_CHARS = 60000; // sessionStorage is ~5 MB: keep long documents from evicting the conversation

// Widgets that mean the patient registry changed and the rest of the app should refetch.
const REGISTRY_WIDGETS = new Set(['patient_created', 'history_updated']);
// Tools that changed an existing chart (their widget is a plain patient_summary, so the widget alone does not say so).
const CHART_EDIT_TOOLS = new Set(['update_patient_details', 'update_history_item', 'remove_history_item']);
// Widgets whose data names the patient the conversation is now about.
const FOCUS_WIDGETS = new Set(['patient_created', 'patient_summary', 'history_updated', 'agent_workflow']);

const load = () => {
  try {
    const saved = JSON.parse(sessionStorage.getItem(STORAGE_KEY) || 'null');
    if (saved && Array.isArray(saved.messages)) return { messages: saved.messages, focus: saved.focus || null };
  } catch { /* storage blocked or corrupt: start clean */ }
  return { messages: [], focus: null };
};

let state = { ...load(), thinking: false, status: null };
const listeners = new Set();

const persist = () => {
  try {
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify({
      messages: state.messages.slice(-MAX_STORED_MESSAGES).map((m) => (m.attachments?.length
        ? { ...m, attachments: m.attachments.map((a) => ({ ...a, text: a.text.slice(0, MAX_STORED_ATTACHMENT_CHARS) })) }
        : m)),
      focus: state.focus,
    }));
  } catch { /* quota or private mode: the conversation simply is not restored */ }
};

const setState = (patch) => {
  state = { ...state, ...(typeof patch === 'function' ? patch(state) : patch) };
  persist();
  listeners.forEach((l) => l());
};

const subscribe = (listener) => { listeners.add(listener); return () => listeners.delete(listener); };
const getSnapshot = () => state;

let nextId = Date.now();
const newId = () => `m${(nextId += 1)}`;

let statusRequest = null;
const loadStatus = (force = false) => {
  if (statusRequest && !force) return statusRequest;
  statusRequest = api.getAssistantStatus()
    .then((status) => setState({ status }))
    .catch(() => { setState({ status: { configured: false, offline: true } }); statusRequest = null; });
  return statusRequest;
};

// Names seen anywhere in the turn (a patient_list or patient_summary widget), keyed by every id they go by.
const namesFromWidgets = (widgets) => {
  const names = {};
  const note = (row) => {
    const name = row?.name || row?.patient_name;
    if (!name) return;
    [row.patient_id, row.mrn].filter(Boolean).forEach((id) => { names[String(id).toUpperCase()] = { id: row.patient_id, name }; });
  };
  widgets.forEach(({ data }) => {
    note(data);
    if (Array.isArray(data?.patients)) data.patients.forEach(note);
  });
  return names;
};

// agent_workflow echoes whatever alias the model passed ("MRN-10001"), and history_updated has no name: resolve
// both against the turn's other widgets, then against the previous focus, before falling back to the bare id.
const focusFromWidgets = (widgets, previous) => {
  const names = namesFromWidgets(widgets);
  for (let i = widgets.length - 1; i >= 0; i -= 1) {
    const { type, data } = widgets[i];
    if (FOCUS_WIDGETS.has(type) && data?.patient_id) {
      const known = names[String(data.patient_id).toUpperCase()];
      const id = known?.id || data.patient_id;
      const samePatient = previous && String(previous.id).toUpperCase() === String(id).toUpperCase();
      return { id, name: data.name || data.patient_name || known?.name || (samePatient ? previous.name : id) };
    }
  }
  return null;
};

/**
 * useAssistantChat({ patient, onPatientsChanged })
 *   patient            the patient selected in the app (fallback focus for the conversation)
 *   onPatientsChanged  called with a patient id when a turn created a patient or added history
 */
export function useAssistantChat({ patient, onPatientsChanged } = {}) {
  const snapshot = useSyncExternalStore(subscribe, getSnapshot);
  const changedRef = useRef(onPatientsChanged);
  changedRef.current = onPatientsChanged;

  useEffect(() => { loadStatus(); }, []);

  // Selecting a different patient in the app is an explicit act: it drops the focus the chat had picked up,
  // so "this patient" can never silently mean the previous one. (Skipped on mount and when nothing is selected.)
  const appPatientId = patient?.id || null;
  const lastAppPatientId = useRef(appPatientId);
  useEffect(() => {
    if (appPatientId && lastAppPatientId.current && appPatientId !== lastAppPatientId.current && state.focus) {
      setState({ focus: null });
    }
    if (appPatientId) lastAppPatientId.current = appPatientId;
  }, [appPatientId]);

  // Until then (or until it is cleared by hand) the conversation's own focus, set by widgets, wins.
  const appFocus = patient ? { id: patient.id, name: `${patient.first_name} ${patient.last_name}` } : null;
  const focus = snapshot.focus || appFocus;
  const focusId = focus?.id || null;

  const send = useCallback(async (text, { viaVoice = false, attachments = [] } = {}) => {
    const content = (text || '').trim();
    if (!content || state.thinking) return;
    const attached = attachments.map(({ filename, text: t, method, pages, found }) => ({ filename, text: t, method, pages, found }));
    const turns = [...state.messages.filter((m) => !m.error), { role: 'user', content, attachments: attached }];
    const history = turns.map(({ role, content: c }) => ({ role, content: c }));
    // Every document attached in this conversation rides along (latest 3, by filename), so "add it to Chen's chart"
    // still works a few turns after the upload.
    const documents = Object.values(Object.fromEntries(
      turns.flatMap((m) => m.attachments || []).map((a) => [a.filename, { filename: a.filename, text: a.text }]),
    )).slice(-3);
    setState((s) => ({ messages: [...s.messages, { id: newId(), role: 'user', content, viaVoice, attachments: attached }], thinking: true }));
    try {
      const res = await api.assistantChat(history, focusId, documents);
      const widgets = Array.isArray(res.widgets) ? res.widgets.filter((w) => w && w.type) : [];
      const reply = {
        id: newId(),
        role: 'assistant',
        content: res.reply || '',
        actions: Array.isArray(res.actions) ? res.actions : [],
        widgets,
        specialists: Array.isArray(res.specialists) ? res.specialists : [],
        provider: res.provider || null,
        model: res.model || null,
      };
      setState((s) => {
        const widgetFocus = focusFromWidgets(widgets, s.focus);
        return { messages: [...s.messages, reply], thinking: false, ...(widgetFocus ? { focus: widgetFocus } : {}) };
      });
      const edited = (res.actions || []).filter((a) => a.ok && CHART_EDIT_TOOLS.has(a.tool)).map((a) => a.args?.patient_id || null);
      const changed = [...new Set([...widgets.filter((w) => REGISTRY_WIDGETS.has(w.type)).map((w) => w.data?.patient_id || null), ...edited])];
      changed.forEach((patientId) => changedRef.current?.(patientId));
    } catch (err) {
      const message = err.detail || (err.message === 'Failed to fetch' ? 'The backend is not reachable.' : err.message) || 'Something went wrong.';
      setState((s) => ({ messages: [...s.messages, { id: newId(), role: 'assistant', content: message, error: true }], thinking: false }));
    }
  }, [focusId]);

  const reset = useCallback(() => setState({ messages: [], focus: null }), []);
  const clearFocus = useCallback(() => setState({ focus: null }), []);
  const refreshStatus = useCallback(() => loadStatus(true), []);

  return {
    status: snapshot.status,
    messages: snapshot.messages,
    thinking: snapshot.thinking,
    focus,
    focusIsFromChat: Boolean(snapshot.focus),
    send,
    reset,
    clearFocus,
    refreshStatus,
  };
}
