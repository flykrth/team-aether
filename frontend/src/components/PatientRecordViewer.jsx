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
      <div className="p-8 text-center text-slate-500 bg-white rounded-xl border border-slate-200">
        Loading patients...
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Patient Selector Bar */}
      <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <label htmlFor="patient-select" className="text-xs font-semibold text-slate-600 uppercase tracking-wider">
            Select Interop Patient:
          </label>
          <select
            id="patient-select"
            value={selectedPatientId}
            onChange={(e) => setSelectedPatientId(e.target.value)}
            className="bg-slate-50 border border-slate-300 text-slate-900 text-sm rounded-lg focus:ring-sky-500 focus:border-sky-500 p-2 font-medium"
          >
            {patients.map((p) => (
              <option key={p.id} value={p.id}>
                {p.first_name} {p.last_name} (CareStack: {p.id} | MRN: {p.mrn})
              </option>
            ))}
          </select>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={handleTriggerSync}
            disabled={syncing}
            className="inline-flex items-center gap-2 px-4 py-2 text-xs font-semibold text-white bg-sky-600 hover:bg-sky-700 rounded-lg shadow-sm transition-all disabled:opacity-50"
          >
            <ArrowRightLeft className={`w-3.5 h-3.5 ${syncing ? 'animate-spin' : ''}`} />
            <span>{syncing ? 'Syncing Pipeline...' : 'Trigger Interop Sync'}</span>
          </button>
        </div>
      </div>

      {syncMessage && (
        <div
          className={`p-3 rounded-lg text-xs font-medium border flex items-center justify-between ${
            syncMessage.type === 'success'
              ? 'bg-emerald-50 text-emerald-800 border-emerald-200'
              : 'bg-rose-50 text-rose-800 border-rose-200'
          }`}
        >
          <span>{syncMessage.text}</span>
          <button onClick={() => setSyncMessage(null)} className="text-slate-400 hover:text-slate-600 text-sm ml-4">
            ×
          </button>
        </div>
      )}

      {/* Patient Master Demographics Header */}
      <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-sm">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-4">
            <div className="w-12 h-12 rounded-full bg-slate-100 flex items-center justify-center text-slate-600 border border-slate-200 font-bold text-lg">
              {selectedPatient.first_name[0]}
              {selectedPatient.last_name[0]}
            </div>
            <div>
              <h3 className="text-lg font-bold text-slate-900">
                {selectedPatient.first_name} {selectedPatient.last_name}
              </h3>
              <div className="flex flex-wrap items-center gap-3 text-xs text-slate-500 mt-1">
                <span>DOB: {selectedPatient.birth_date}</span>
                <span>•</span>
                <span>Gender: {selectedPatient.gender}</span>
                <span>•</span>
                <span>CareStack ID: <strong className="text-sky-700">{selectedPatient.id}</strong></span>
                <span>•</span>
                <span>Medical MRN: <strong className="text-teal-700">{selectedPatient.mrn}</strong></span>
              </div>
            </div>
          </div>

          <div className="text-right text-xs">
            <div className="text-slate-500">Assigned Provider</div>
            <div className="font-semibold text-slate-800">{selectedPatient.primary_dentist}</div>
            <div className="text-slate-400 mt-0.5">Next Visit: {selectedPatient.next_appointment}</div>
          </div>
        </div>
      </div>

      {/* CDS Hooks Real-Time Warnings */}
      <div>
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-base font-bold text-slate-900 flex items-center gap-2">
            <AlertOctagon className="w-5 h-5 text-rose-600" />
            <span>CDS Hooks v1.0 — Real-Time Clinical Decision Safety Alerts</span>
          </h3>
          <span className="text-xs text-slate-500">
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
          <div className="p-4 bg-emerald-50 border border-emerald-200 rounded-xl text-xs text-emerald-800 flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4 text-emerald-600" />
            <span>No critical contraindications detected between EHR record and CareStack treatment plan.</span>
          </div>
        )}
      </div>

      {/* Cross-Domain Dual Panels: CareStack Dental vs. Medical EHR */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Left Panel: CareStack Dental PMS Record */}
        <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-sm">
          <div className="flex items-center justify-between pb-3 border-b border-slate-100 mb-4">
            <div className="flex items-center gap-2">
              <FileSpreadsheet className="w-4 h-4 text-sky-600" />
              <h4 className="font-bold text-slate-900 text-sm">CareStack Dental Treatment Plan</h4>
            </div>
            <span className="text-[10px] font-bold uppercase bg-sky-100 text-sky-800 px-2 py-0.5 rounded">
              Dental Chair
            </span>
          </div>

          <p className="text-xs text-slate-500 mb-3">
            Active and proposed CDT procedural items currently queued in CareStack:
          </p>

          <div className="space-y-3">
            {selectedPatient.active_treatment_plan?.map((proc, i) => (
              <div key={i} className="p-3 bg-slate-50 rounded-lg border border-slate-200 text-xs">
                <div className="flex items-start justify-between">
                  <div>
                    <span className="font-mono font-bold text-sky-700 bg-sky-50 px-1.5 py-0.5 rounded border border-sky-200 mr-2">
                      {proc.code}
                    </span>
                    <strong className="text-slate-900">{proc.description}</strong>
                  </div>
                  <span className="text-[10px] font-semibold uppercase px-2 py-0.5 rounded bg-amber-100 text-amber-800">
                    {proc.status}
                  </span>
                </div>
                <div className="mt-2 text-slate-600 flex justify-between text-[11px]">
                  <span>Tooth: {proc.tooth_number || 'General'}</span>
                  {proc.cost && <span>Fee: ${proc.cost.toFixed(2)}</span>}
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Right Panel: Medical EHR (FHIR R4) */}
        <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-sm">
          <div className="flex items-center justify-between pb-3 border-b border-slate-100 mb-4">
            <div className="flex items-center gap-2">
              <Heart className="w-4 h-4 text-teal-600" />
              <h4 className="font-bold text-slate-900 text-sm">Medical EHR Clinical Summary (FHIR R4)</h4>
            </div>
            <span className="text-[10px] font-bold uppercase bg-teal-100 text-teal-800 px-2 py-0.5 rounded">
              Medical Hospital
            </span>
          </div>

          {/* Medical Diagnoses */}
          <div className="mb-4">
            <span className="text-[11px] font-bold uppercase tracking-wider text-slate-500 block mb-2">
              Diagnosed Medical Conditions
            </span>
            <div className="space-y-2">
              {conditions.length > 0 ? (
                conditions.map((c) => (
                  <div key={c.id} className="p-2.5 bg-slate-50 rounded-lg border border-slate-200 text-xs">
                    <div className="font-semibold text-slate-900">{c.code.text}</div>
                    <div className="text-[10px] text-slate-500 mt-0.5">
                      Onset: {c.onsetDateTime || 'Documented'}
                    </div>
                  </div>
                ))
              ) : (
                <div className="text-xs text-slate-400 italic">No chronic medical conditions recorded.</div>
              )}
            </div>
          </div>

          {/* Observations / Lab Values */}
          <div className="mb-4">
            <span className="text-[11px] font-bold uppercase tracking-wider text-slate-500 block mb-2">
              Relevant Medical Observations & Labs
            </span>
            <div className="space-y-2">
              {observations.length > 0 ? (
                observations.map((o) => (
                  <div key={o.id} className="p-2.5 bg-slate-50 rounded-lg border border-slate-200 text-xs flex justify-between items-center">
                    <div>
                      <div className="font-semibold text-slate-900">{o.code.text}</div>
                      <div className="text-[10px] text-slate-500">Date: {o.effectiveDateTime}</div>
                    </div>
                    {o.valueQuantity && (
                      <span className="font-mono font-bold text-teal-700 bg-teal-50 px-2 py-1 rounded border border-teal-200">
                        {o.valueQuantity.value} {o.valueQuantity.unit}
                      </span>
                    )}
                  </div>
                ))
              ) : (
                <div className="text-xs text-slate-400 italic">No recent diagnostic lab values.</div>
              )}
            </div>
          </div>

          {/* Allergies */}
          <div>
            <span className="text-[11px] font-bold uppercase tracking-wider text-slate-500 block mb-2">
              Allergies & Sensitivities
            </span>
            <div className="space-y-2">
              {allergies.length > 0 ? (
                allergies.map((a) => (
                  <div key={a.id} className="p-2.5 bg-rose-50/60 rounded-lg border border-rose-200 text-xs">
                    <div className="font-bold text-rose-900">{a.code.text}</div>
                    <div className="text-[10px] text-rose-700 mt-0.5 uppercase tracking-wide">
                      Criticality: {a.criticality || 'High'}
                    </div>
                  </div>
                ))
              ) : (
                <div className="text-xs text-slate-400 italic">No documented drug or material allergies.</div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
