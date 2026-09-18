import React, { useState, useEffect } from 'react';
import {
  AlertOctagon,
  FileSpreadsheet,
  CheckCircle2,
  ArrowRightLeft,
  Heart,
} from 'lucide-react';
import { api } from '../services/api';
import { CdsAlertCard } from './CdsAlertCard';

export function PatientRecordViewer({ patients, onSyncSuccess }) {
  const [selectedPatientId, setSelectedPatientId] = useState(patients[0]?.id || 'CS-1001');
  const [conditions, setConditions] = useState([]);
  const [observations, setObservations] = useState([]);
  const [allergies, setAllergies] = useState([]);
  const [cdsCards, setCdsCards] = useState([]);
  const [loadingPatient, setLoadingPatient] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [syncMessage, setSyncMessage] = useState(null);

  const selectedPatient = patients.find((p) => p.id === selectedPatientId) || patients[0];

  useEffect(() => {
    if (!selectedPatient) return;

    async function loadPatientDetails() {
      setLoadingPatient(true);
      try {
        const mrn = selectedPatient.mrn;
        const [conds, obs, allgs, cdsResp] = await Promise.all([
          api.getFhirConditions(mrn).catch(() => []),
          api.getFhirObservations(mrn).catch(() => []),
          api.getFhirAllergies(mrn).catch(() => []),
          api.evaluateRiskHook(mrn).catch(() => ({ cards: [] })),
        ]);

        setConditions(conds);
        setObservations(obs);
        setAllergies(allgs);
        setCdsCards(cdsResp.cards || []);
      } catch (err) {
        console.error('Failed to load patient records', err);
      } finally {
        setLoadingPatient(false);
      }
    }

    loadPatientDetails();
  }, [selectedPatientId, selectedPatient]);

  const handleTriggerSync = async () => {
    if (!selectedPatient) return;
    setSyncing(true);
    setSyncMessage(null);
    try {
      const res = await api.syncCareStack(selectedPatient.id);
      setSyncMessage({
        type: 'success',
        text: `Reconciliation complete: Patient ${selectedPatient.first_name} ${selectedPatient.last_name} (${res.mrn}) synced with CareStack & Medical EHR.`,
      });
      if (onSyncSuccess) onSyncSuccess();
    } catch (err) {
      setSyncMessage({
        type: 'error',
        text: `Sync failed: ${err.message}`,
      });
    } finally {
      setSyncing(false);
    }
  };

  if (!selectedPatient) {
    return (
      <div className="card text-center text-sm text-text-muted py-10">
        Loading patient directory...
      </div>
    );
  }

  return (
    <div className="space-y-5">
      {/* Patient Selector Bar */}
      <div className="card p-4 flex flex-col md:flex-row md:items-center justify-between gap-3">
        <div className="flex flex-col sm:flex-row sm:items-center gap-3 flex-1 min-w-0">
          <label htmlFor="patient-select" className="text-sm text-text-muted pl-2 shrink-0">
            Select Patient:
          </label>
          <select
            id="patient-select"
            value={selectedPatientId}
            onChange={(e) => setSelectedPatientId(e.target.value)}
            className="field md:max-w-md font-medium cursor-pointer"
          >
            {patients.map((p) => (
              <option key={p.id} value={p.id}>
                {p.first_name} {p.last_name} (CareStack: {p.id} | MRN: {p.mrn})
              </option>
            ))}
          </select>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={handleTriggerSync}
            disabled={syncing}
            className="btn-dark"
          >
            <ArrowRightLeft className={`w-4 h-4 ${syncing ? 'animate-spin' : ''}`} strokeWidth={1.5} />
            <span>{syncing ? 'Syncing Record...' : 'Trigger EHR Reconciliation'}</span>
          </button>
        </div>
      </div>

      {syncMessage && (
        <div
          className={`px-5 py-3.5 rounded-3xl text-sm flex items-center justify-between ${
            syncMessage.type === 'success'
              ? 'bg-success-light text-success-dark'
              : 'bg-danger-light text-danger-dark'
          }`}
        >
          <span>{syncMessage.text}</span>
          <button
            onClick={() => setSyncMessage(null)}
            className="inline-flex items-center justify-center w-8 h-8 rounded-full bg-white/70 hover:bg-white text-text-secondary hover:text-text-main text-base ml-4 shrink-0"
          >
            ×
          </button>
        </div>
      )}

      {/* Patient Master Demographics Header */}
      <div className="card p-7">
        <div className="flex flex-wrap items-center justify-between gap-6">
          <div className="flex items-center gap-4">
            <div className="w-14 h-14 rounded-full bg-accent text-white flex items-center justify-center font-display font-semibold text-lg shrink-0">
              {selectedPatient.first_name[0]}
              {selectedPatient.last_name[0]}
            </div>
            <div>
              <h3 className="display-lg text-text-main">
                {selectedPatient.first_name} {selectedPatient.last_name}
              </h3>
              <div className="flex flex-wrap items-center gap-2 text-xs text-text-secondary mt-2">
                <span className="chip">DOB: <strong className="font-medium text-text-main tabular-nums">{selectedPatient.birth_date}</strong></span>
                <span className="chip">Gender: {selectedPatient.gender}</span>
                <span className="chip">CareStack ID: <strong className="font-mono font-medium text-text-main">{selectedPatient.id}</strong></span>
                <span className="chip chip-accent">MRN: <strong className="font-mono font-medium">{selectedPatient.mrn}</strong></span>
              </div>
            </div>
          </div>

          <div className="well px-5 text-sm md:text-right">
            <div className="text-xs text-text-muted">Primary Dentist</div>
            <div className="font-display text-base font-semibold text-text-main mt-0.5">{selectedPatient.primary_dentist}</div>
            <div className="text-xs text-text-secondary mt-1 tabular-nums">Next Appointment: {selectedPatient.next_appointment}</div>
          </div>
        </div>
      </div>

      {/* CDS Hooks Real-Time Warnings */}
      <div className="card p-7">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 mb-5">
          <h3 className="font-display text-xl font-medium text-text-main flex items-center gap-3">
            <span className="inline-flex items-center justify-center w-10 h-10 rounded-full bg-danger-light text-danger shrink-0">
              <AlertOctagon className="w-[18px] h-[18px]" strokeWidth={1.5} />
            </span>
            <span>CDS Hooks v1.0 — Real-Time Clinical Decision Safety Review</span>
          </h3>
          <span className="text-xs text-text-muted">
            Automated Cross-Specialty Risk Analysis
          </span>
        </div>

        {cdsCards.length > 0 ? (
          <div>
            {cdsCards.map((card, idx) => (
              <CdsAlertCard key={idx} card={card} />
            ))}
          </div>
        ) : (
          <div className="px-5 py-4 bg-success-light rounded-3xl text-sm text-success-dark flex items-center gap-3">
            <CheckCircle2 className="w-5 h-5 text-success shrink-0" strokeWidth={1.5} />
            <span>No contraindications detected between Medical EHR record and CareStack treatment plan.</span>
          </div>
        )}
      </div>

      {/* Cross-Domain Dual Panels: CareStack Dental vs. Medical EHR */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        {/* Left Panel: CareStack Dental PMS Record */}
        <div className="card p-7">
          <div className="flex items-start justify-between gap-3 mb-5">
            <div className="flex items-center gap-3">
              <div className="icon-disc w-10 h-10">
                <FileSpreadsheet className="w-[18px] h-[18px]" strokeWidth={1.5} />
              </div>
              <h4 className="font-display text-lg font-medium text-text-main leading-tight">CareStack Dental Treatment Plan</h4>
            </div>
            <span className="chip shrink-0">Chairside Plan</span>
          </div>

          <div className="space-y-2.5">
            {selectedPatient.active_treatment_plan?.map((proc, i) => (
              <div key={i} className="well text-sm">
                <div className="flex items-start justify-between gap-3">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="chip chip-accent font-mono">
                      {proc.code}
                    </span>
                    <strong className="font-display text-[15px] text-text-main font-semibold">{proc.description}</strong>
                  </div>
                  <span className="chip bg-warning-light text-warning-dark shrink-0">
                    {proc.status}
                  </span>
                </div>
                <div className="mt-3 text-text-secondary flex justify-between text-xs">
                  <span>Tooth Target: {proc.tooth_number || 'General Area'}</span>
                  {proc.cost && <span className="tabular-nums">Fee: ${proc.cost.toFixed(2)}</span>}
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Right Panel: Medical EHR (FHIR R4) */}
        <div className="card p-7">
          <div className="flex items-start justify-between gap-3 mb-5">
            <div className="flex items-center gap-3">
              <div className="icon-disc w-10 h-10">
                <Heart className="w-[18px] h-[18px]" strokeWidth={1.5} />
              </div>
              <h4 className="font-display text-lg font-medium text-text-main leading-tight">Medical EHR Clinical Summary (FHIR R4)</h4>
            </div>
            <span className="chip chip-accent shrink-0">Hospital Record</span>
          </div>

          {/* Medical Diagnoses */}
          <div className="mb-6">
            <span className="text-sm text-text-muted block mb-2">
              Diagnosed Medical Conditions
            </span>
            <div className="space-y-2">
              {conditions.length > 0 ? (
                conditions.map((c) => (
                  <div key={c.id} className="well py-3.5 text-sm">
                    <div className="font-display text-[15px] font-semibold text-text-main">{c.code.text}</div>
                    <div className="text-xs text-text-muted mt-1 tabular-nums">
                      Onset: {c.onsetDateTime || 'Documented'}
                    </div>
                  </div>
                ))
              ) : (
                <div className="text-sm text-text-muted">No chronic medical conditions recorded.</div>
              )}
            </div>
          </div>

          {/* Observations / Lab Values */}
          <div className="mb-6">
            <span className="text-sm text-text-muted block mb-2">
              Relevant Medical Observations & Labs
            </span>
            <div className="space-y-2">
              {observations.length > 0 ? (
                observations.map((o) => (
                  <div key={o.id} className="well py-3.5 text-sm flex justify-between items-center gap-4">
                    <div className="min-w-0">
                      <div className="font-display text-[15px] font-semibold text-text-main">{o.code.text}</div>
                      <div className="text-xs text-text-muted mt-1 tabular-nums">Date: {o.effectiveDateTime}</div>
                    </div>
                    {o.valueQuantity && (
                      <span className="shrink-0 text-right leading-none">
                        <span className="font-display text-2xl font-medium text-text-main tabular-nums">{o.valueQuantity.value}</span>{' '}
                        <span className="text-xs text-text-muted">{o.valueQuantity.unit}</span>
                      </span>
                    )}
                  </div>
                ))
              ) : (
                <div className="text-sm text-text-muted">No recent diagnostic lab values.</div>
              )}
            </div>
          </div>

          {/* Allergies */}
          <div>
            <span className="text-sm text-text-muted block mb-2">
              Allergies & Sensitivities
            </span>
            <div className="space-y-2">
              {allergies.length > 0 ? (
                allergies.map((a) => (
                  <div key={a.id} className="flex items-center justify-between gap-3 px-4 py-3.5 bg-danger-light rounded-3xl text-sm">
                    <div className="font-display text-[15px] font-semibold text-danger-dark">{a.code.text}</div>
                    <span className="chip bg-white text-danger-dark shrink-0">
                      Criticality: {a.criticality || 'High'}
                    </span>
                  </div>
                ))
              ) : (
                <div className="text-sm text-text-muted">No documented drug or material allergies.</div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
