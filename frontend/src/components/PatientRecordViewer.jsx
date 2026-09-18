import React, { useState, useEffect } from 'react';
import {
  User,
  Calendar,
  AlertOctagon,
  FileSpreadsheet,
  CheckCircle2,
  ArrowRightLeft,
  Heart,
  Droplets,
  Syringe,
  Activity,
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
      <div className="p-6 text-center text-xs text-text-muted bg-app-surface rounded-lg border border-app-border">
        Loading patient directory...
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Patient Selector Bar */}
      <div className="bg-app-surface p-3.5 rounded-lg border border-app-border shadow-xs flex flex-col md:flex-row md:items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <label htmlFor="patient-select" className="text-xs font-semibold text-text-secondary uppercase tracking-wider">
            Select Patient:
          </label>
          <select
            id="patient-select"
            value={selectedPatientId}
            onChange={(e) => setSelectedPatientId(e.target.value)}
            className="bg-app-surface border border-app-border text-text-main text-xs rounded p-1.5 font-medium focus:outline-none focus:border-teal-500"
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
            className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold text-white bg-teal-500 hover:bg-teal-700 rounded shadow-xs transition-colors disabled:opacity-50"
          >
            <ArrowRightLeft className={`w-3.5 h-3.5 ${syncing ? 'animate-spin' : ''}`} />
            <span>{syncing ? 'Syncing Record...' : 'Trigger EHR Reconciliation'}</span>
          </button>
        </div>
      </div>

      {syncMessage && (
        <div
          className={`p-2.5 rounded text-xs font-medium border flex items-center justify-between ${
            syncMessage.type === 'success'
              ? 'bg-success-light text-success-dark border-success/30'
              : 'bg-danger-light text-danger-dark border-danger/30'
          }`}
        >
          <span>{syncMessage.text}</span>
          <button onClick={() => setSyncMessage(null)} className="text-text-muted hover:text-text-main text-sm ml-4">
            ×
          </button>
        </div>
      )}

      {/* Patient Master Demographics Header */}
      <div className="bg-app-surface rounded-lg border border-app-border p-4 shadow-xs">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-3.5">
            <div className="w-10 h-10 rounded-full bg-teal-50 text-teal-700 flex items-center justify-center font-bold text-sm shrink-0 border border-teal-200">
              {selectedPatient.first_name[0]}
              {selectedPatient.last_name[0]}
            </div>
            <div>
              <h3 className="text-base font-bold text-text-main leading-tight">
                {selectedPatient.first_name} {selectedPatient.last_name}
              </h3>
              <div className="flex flex-wrap items-center gap-2.5 text-xs text-text-secondary mt-0.5">
                <span>DOB: <strong>{selectedPatient.birth_date}</strong></span>
                <span className="text-text-muted">•</span>
                <span>Gender: {selectedPatient.gender}</span>
                <span className="text-text-muted">•</span>
                <span>CareStack ID: <strong className="text-text-main">{selectedPatient.id}</strong></span>
                <span className="text-text-muted">•</span>
                <span>MRN: <strong className="text-teal-700">{selectedPatient.mrn}</strong></span>
              </div>
            </div>
          </div>

          <div className="text-right text-xs">
            <div className="text-text-muted">Primary Dentist</div>
            <div className="font-semibold text-text-main">{selectedPatient.primary_dentist}</div>
            <div className="text-text-secondary mt-0.5">Next Appointment: {selectedPatient.next_appointment}</div>
          </div>
        </div>
      </div>

      {/* CDS Hooks Real-Time Warnings */}
      <div>
        <div className="flex items-center justify-between mb-2">
          <h3 className="text-sm font-bold text-text-main flex items-center gap-1.5">
            <AlertOctagon className="w-4 h-4 text-danger" />
            <span>CDS Hooks v1.0 — Real-Time Clinical Decision Safety Review</span>
          </h3>
          <span className="text-[11px] text-text-muted">
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
          <div className="p-3 bg-success-light border border-success/30 rounded text-xs text-success-dark flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4 text-success shrink-0" />
            <span>No contraindications detected between Medical EHR record and CareStack treatment plan.</span>
          </div>
        )}
      </div>

      {/* Cross-Domain Dual Panels: CareStack Dental vs. Medical EHR */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Left Panel: CareStack Dental PMS Record */}
        <div className="bg-app-surface rounded-lg border border-app-border p-4 shadow-xs">
          <div className="flex items-center justify-between pb-2.5 border-b border-app-border mb-3">
            <div className="flex items-center gap-1.5">
              <FileSpreadsheet className="w-4 h-4 text-teal-500" />
              <h4 className="font-bold text-text-main text-xs uppercase tracking-wider">CareStack Dental Treatment Plan</h4>
            </div>
            <span className="text-[10px] font-bold uppercase bg-app-bg text-text-secondary px-2 py-0.5 rounded border border-app-border">
              Chairside Plan
            </span>
          </div>

          <div className="space-y-2">
            {selectedPatient.active_treatment_plan?.map((proc, i) => (
              <div key={i} className="p-2.5 bg-app-bg rounded border border-app-border text-xs">
                <div className="flex items-start justify-between">
                  <div>
                    <span className="font-mono font-bold text-teal-800 bg-teal-50 px-1.5 py-0.5 rounded border border-teal-200 mr-1.5">
                      {proc.code}
                    </span>
                    <strong className="text-text-main font-semibold">{proc.description}</strong>
                  </div>
                  <span className="text-[10px] font-semibold uppercase px-2 py-0.5 rounded bg-warning-light text-warning-dark border border-warning/30">
                    {proc.status}
                  </span>
                </div>
                <div className="mt-1.5 text-text-secondary flex justify-between text-[11px]">
                  <span>Tooth Target: {proc.tooth_number || 'General Area'}</span>
                  {proc.cost && <span>Fee: ${proc.cost.toFixed(2)}</span>}
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Right Panel: Medical EHR (FHIR R4) */}
        <div className="bg-app-surface rounded-lg border border-app-border p-4 shadow-xs">
          <div className="flex items-center justify-between pb-2.5 border-b border-app-border mb-3">
            <div className="flex items-center gap-1.5">
              <Heart className="w-4 h-4 text-teal-500" />
              <h4 className="font-bold text-text-main text-xs uppercase tracking-wider">Medical EHR Clinical Summary (FHIR R4)</h4>
            </div>
            <span className="text-[10px] font-bold uppercase bg-teal-50 text-teal-700 px-2 py-0.5 rounded border border-teal-200">
              Hospital Record
            </span>
          </div>

          {/* Medical Diagnoses */}
          <div className="mb-3">
            <span className="text-[10px] font-bold uppercase tracking-wider text-text-secondary block mb-1">
              Diagnosed Medical Conditions
            </span>
            <div className="space-y-1.5">
              {conditions.length > 0 ? (
                conditions.map((c) => (
                  <div key={c.id} className="p-2 bg-app-bg rounded border border-app-border text-xs">
                    <div className="font-semibold text-text-main">{c.code.text}</div>
                    <div className="text-[10px] text-text-muted mt-0.5">
                      Onset: {c.onsetDateTime || 'Documented'}
                    </div>
                  </div>
                ))
              ) : (
                <div className="text-xs text-text-muted italic">No chronic medical conditions recorded.</div>
              )}
            </div>
          </div>

          {/* Observations / Lab Values */}
          <div className="mb-3">
            <span className="text-[10px] font-bold uppercase tracking-wider text-text-secondary block mb-1">
              Relevant Medical Observations & Labs
            </span>
            <div className="space-y-1.5">
              {observations.length > 0 ? (
                observations.map((o) => (
                  <div key={o.id} className="p-2 bg-app-bg rounded border border-app-border text-xs flex justify-between items-center">
                    <div>
                      <div className="font-semibold text-text-main">{o.code.text}</div>
                      <div className="text-[10px] text-text-muted">Date: {o.effectiveDateTime}</div>
                    </div>
                    {o.valueQuantity && (
                      <span className="font-mono font-bold text-teal-800 bg-teal-50 px-2 py-0.5 rounded border border-teal-200">
                        {o.valueQuantity.value} {o.valueQuantity.unit}
                      </span>
                    )}
                  </div>
                ))
              ) : (
                <div className="text-xs text-text-muted italic">No recent diagnostic lab values.</div>
              )}
            </div>
          </div>

          {/* Allergies */}
          <div>
            <span className="text-[10px] font-bold uppercase tracking-wider text-text-secondary block mb-1">
              Allergies & Sensitivities
            </span>
            <div className="space-y-1.5">
              {allergies.length > 0 ? (
                allergies.map((a) => (
                  <div key={a.id} className="p-2 bg-danger-light rounded border border-danger/30 text-xs">
                    <div className="font-bold text-danger-dark">{a.code.text}</div>
                    <div className="text-[10px] text-danger-dark font-medium mt-0.5 uppercase tracking-wide">
                      Criticality: {a.criticality || 'High'}
                    </div>
                  </div>
                ))
              ) : (
                <div className="text-xs text-text-muted italic">No documented drug or material allergies.</div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

