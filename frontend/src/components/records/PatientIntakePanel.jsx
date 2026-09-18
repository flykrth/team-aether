import React, { useEffect, useMemo, useRef, useState } from 'react';
import { X, UserPlus, ClipboardPlus, FileUp, FolderHeart } from 'lucide-react';
import { api } from '../../services/api';
import { normalizePatient } from './shared';
import { NewPatientSection } from './NewPatientSection';
import { MedicalHistorySection, usePatientRecord } from './MedicalHistorySection';
import { PreviousRecordsSection } from './PreviousRecordsSection';

const TABS = [
  { id: 'new', label: 'New patient', icon: UserPlus },
  { id: 'history', label: 'Medical history', icon: ClipboardPlus },
  { id: 'records', label: 'Previous records', icon: FileUp },
];
// Callers (navbar, chat "open intake") may name the section loosely.
const TAB_ALIASES = {
  new: 'new', 'new-patient': 'new', patient: 'new', create: 'new',
  history: 'history', 'medical-history': 'history',
  records: 'records', 'previous-records': 'records', previous: 'records', import: 'records',
};
const resolveTab = (tab, hasPatient) => TAB_ALIASES[String(tab || '').toLowerCase()] || (hasPatient ? 'history' : 'new');

const FOCUSABLE = 'a[href], button:not([disabled]), input:not([disabled]):not([type="hidden"]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

/**
 * Patient records slide-over: register a patient, add coded medical history, import previous records.
 * Sections stay mounted while the panel is open so a half-written form survives switching tabs.
 */
export function PatientIntakePanel({ open, onClose, patients, initialPatientId, initialTab, onChanged }) {
  const [tab, setTab] = useState('new');
  const [patientId, setPatientId] = useState('');
  const [fetched, setFetched] = useState([]);   // fallback / refresh from /api/records/patients
  const [createdHere, setCreatedHere] = useState([]); // visible immediately, before the parent refetches
  const panelRef = useRef(null);
  const closeRef = useRef(null);
  const returnFocusRef = useRef(null);
  const onCloseRef = useRef(onClose);
  onCloseRef.current = onClose;

  const recordState = usePatientRecord(open && tab !== 'new' ? patientId : '');

  const allPatients = useMemo(() => {
    const byId = new Map();
    [...(patients || []), ...fetched, ...createdHere].forEach((p) => {
      const n = normalizePatient(p);
      if (n && !byId.has(n.id)) byId.set(n.id, n);
    });
    return [...byId.values()];
  }, [patients, fetched, createdHere]);

  const refreshPatients = () => api.listRecordPatients().then((list) => setFetched(Array.isArray(list) ? list : [])).catch(() => {});

  // Every open starts where the caller asked. Only the open transition applies it: the parent may
  // re-select a patient in response to onChanged, and that must not yank the user off the success state.
  const initialRef = useRef({});
  initialRef.current = { initialTab, initialPatientId };
  useEffect(() => {
    if (!open) return;
    const initial = initialRef.current;
    setTab(resolveTab(initial.initialTab, Boolean(initial.initialPatientId)));
    setPatientId(initial.initialPatientId || '');
    refreshPatients();
  }, [open]);

  // The chat may hand over an alias ("MRN-10001", "pat-1") instead of the CareStack id the <select> is keyed by:
  // match the MRN locally, otherwise ask the backend for the canonical id.
  useEffect(() => {
    if (!open || !patientId || allPatients.length === 0 || allPatients.some((p) => p.id === patientId)) return undefined;
    const wanted = patientId.toLowerCase();
    const local = allPatients.find((p) => p.id.toLowerCase() === wanted || (p.mrn || '').toLowerCase() === wanted);
    if (local) { setPatientId(local.id); return undefined; }
    let cancelled = false;
    api.getPatientRecord(patientId)
      .then((record) => { if (!cancelled && record?.patient_id && record.patient_id !== patientId) setPatientId(record.patient_id); })
      .catch(() => {});
    return () => { cancelled = true; };
  }, [open, patientId, allPatients]);

  // Esc to close, Tab kept inside the panel, page scroll locked, focus moved in and restored on close.
  useEffect(() => {
    if (!open) return undefined;
    returnFocusRef.current = document.activeElement;
    const focusTimer = setTimeout(() => closeRef.current?.focus(), 0);
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';

    const onKeyDown = (e) => {
      if (e.key === 'Escape') { e.stopPropagation(); onCloseRef.current?.(); return; }
      if (e.key !== 'Tab' || !panelRef.current) return;
      const items = [...panelRef.current.querySelectorAll(FOCUSABLE)].filter((el) => el.offsetParent !== null);
      if (!items.length) return;
      const first = items[0];
      const last = items[items.length - 1];
      if (!panelRef.current.contains(document.activeElement)) { e.preventDefault(); first.focus(); }
      else if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
      else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
    };
    document.addEventListener('keydown', onKeyDown);
    return () => {
      clearTimeout(focusTimer);
      document.removeEventListener('keydown', onKeyDown);
      document.body.style.overflow = previousOverflow;
      if (returnFocusRef.current?.focus) returnFocusRef.current.focus();
    };
  }, [open]);

  if (!open) return null;

  const handleChanged = (id) => { refreshPatients(); onChanged?.(id); };
  const handleCreated = (created) => {
    setCreatedHere((list) => [...list, created]);
    handleChanged(created.patient_id);
  };
  const goTo = (nextTab) => (id) => { setPatientId(id); setTab(nextTab); };

  return (
    <div className="fixed inset-0 z-50">
      <div className="absolute inset-0 bg-ink/40 animate-[intake-fade_.2s_ease-out_both]" onClick={onClose} aria-hidden="true" />
      <style>{'@keyframes intake-fade{from{opacity:0}to{opacity:1}}@keyframes intake-slide{from{transform:translateX(24px);opacity:0}to{transform:none;opacity:1}}'}</style>

      <aside
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="intake-panel-title"
        className="absolute inset-y-0 right-0 w-full sm:w-[560px] max-w-full flex flex-col bg-app-surface sm:rounded-l-4xl overflow-hidden animate-[intake-slide_.3s_cubic-bezier(.2,.7,.2,1)_both]"
      >
        <header className="shrink-0 px-5 sm:px-6 pt-5 pb-4">
          <div className="flex items-center gap-3">
            <span className="icon-disc !w-11 !h-11"><FolderHeart className="w-5 h-5" strokeWidth={1.5} /></span>
            <div className="min-w-0 flex-1">
              <div className="eyebrow">Patient records</div>
              <h2 id="intake-panel-title" className="font-display text-xl font-medium leading-tight truncate">Add patients and history</h2>
            </div>
            <button ref={closeRef} type="button" onClick={onClose} className="icon-btn" aria-label="Close patient records">
              <X className="w-5 h-5" strokeWidth={1.5} />
            </button>
          </div>

          <div role="tablist" aria-label="Patient records sections" className="flex gap-1.5 mt-4 overflow-x-auto scrollbar-none -mx-1 px-1">
            {TABS.map(({ id, label, icon: Icon }) => (
              <button
                key={id}
                type="button"
                role="tab"
                id={`intake-tab-${id}`}
                aria-selected={tab === id}
                aria-controls={`intake-section-${id}`}
                onClick={() => setTab(id)}
                className={`pill !h-10 !px-4 !text-sm whitespace-nowrap shrink-0 ${tab === id ? 'pill-active' : '!bg-app-secondary'}`}
              >
                <Icon className="w-4 h-4" strokeWidth={1.5} /> {label}
              </button>
            ))}
          </div>
        </header>

        <div className="flex-1 overflow-y-auto px-5 sm:px-6 pb-8">
          <div role="tabpanel" id="intake-section-new" aria-labelledby="intake-tab-new" hidden={tab !== 'new'}>
            <NewPatientSection onCreated={handleCreated} onAddHistory={goTo('history')} onImportRecords={goTo('records')} />
          </div>
          <div role="tabpanel" id="intake-section-history" aria-labelledby="intake-tab-history" hidden={tab !== 'history'}>
            <MedicalHistorySection patients={allPatients} patientId={patientId} onPatientChange={setPatientId} onChanged={handleChanged} recordState={recordState} />
          </div>
          <div role="tabpanel" id="intake-section-records" aria-labelledby="intake-tab-records" hidden={tab !== 'records'}>
            <PreviousRecordsSection patients={allPatients} patientId={patientId} onPatientChange={setPatientId} onChanged={handleChanged} recordState={recordState} />
          </div>
        </div>

        <footer className="shrink-0 px-6 py-3 bg-app-secondary">
          <p className="text-[11px] text-text-muted text-center">Synthetic data only. Diagnoses and drugs are coded by deterministic rules, never invented by a language model.</p>
        </footer>
      </aside>
    </div>
  );
}

export default PatientIntakePanel;
