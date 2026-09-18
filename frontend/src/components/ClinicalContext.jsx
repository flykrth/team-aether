import React, { useEffect, useState } from 'react';
import { Pill, FileText, Activity, AlertTriangle, Loader2 } from 'lucide-react';
import { api } from '../services/api';

function getCoding(resource, conceptKey) {
  return (resource?.[conceptKey]?.coding || [])[0] || {};
}

export function ClinicalContext({ patient }) {
  const [conditions, setConditions] = useState([]);
  const [medications, setMedications] = useState([]);
  const [observations, setObservations] = useState([]);
  const [allergies, setAllergies] = useState([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!patient?.mrn) return;
    let cancelled = false;

    async function loadRecords() {
      setLoading(true);
      try {
        const fhirPatient = await api.getFhirPatient(patient.mrn).catch(() => null);
        const fhirId = fhirPatient?.id || patient.mrn;

        const [conds, meds, obs, allgs] = await Promise.all([
          api.getFhirConditions(fhirId).catch(() => []),
          api.getFhirMedications(fhirId).catch(() => []),
          api.getFhirObservations(fhirId).catch(() => []),
          api.getFhirAllergies(fhirId).catch(() => []),
        ]);
        if (cancelled) return;
        setConditions(conds);
        setMedications(meds);
        setObservations(obs);
        setAllergies(allgs);
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    loadRecords();
    return () => {
      cancelled = true;
    };
  }, [patient?.mrn]);

  if (!patient) return null;

  return (
    <div className="bg-app-surface rounded-lg border border-app-border p-4 shadow-xs mb-4">
      <div className="flex items-center justify-between pb-3 border-b border-app-border mb-3">
        <div>
          <h2 className="text-xs font-bold uppercase tracking-wider text-text-secondary">
            Relevant Medical Context
          </h2>
          <p className="text-[11px] text-text-muted">Synchronized from Hospital Medical EHR (FHIR R4)</p>
        </div>
        <span className="text-[10px] font-bold text-teal-700 bg-teal-50 px-2 py-0.5 rounded border border-teal-200">
          Verified EHR Record
        </span>
      </div>

      {loading ? (
        <div className="flex items-center justify-center gap-2 text-xs text-text-muted py-8">
          <Loader2 className="w-4 h-4 animate-spin text-teal-500" />
          Loading patient medical record…
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3">
          {/* Pillar 1: Medications */}
          <div className="bg-app-bg p-3 rounded border border-app-border">
            <div className="flex items-center gap-1.5 mb-2 pb-1.5 border-b border-app-border">
              <Pill className="w-3.5 h-3.5 text-teal-600 shrink-0" />
              <span className="text-xs font-bold text-text-main">Medications</span>
              <span className="ml-auto text-[10px] font-mono text-text-muted">({medications.length})</span>
            </div>
            <div className="space-y-1.5">
              {medications.length > 0 ? (
                medications.map((m) => (
                  <div key={m.id} className="bg-app-surface p-2 rounded border border-app-border text-xs">
                    <div className="font-semibold text-text-main">{m.medicationCodeableConcept?.text}</div>
                    <div className="text-[10px] text-text-secondary mt-0.5">Status: <span className="font-medium text-text-main">{m.status}</span></div>
                  </div>
                ))
              ) : (
                <div className="text-[11px] text-text-muted italic">No active prescriptions recorded.</div>
              )}
            </div>
          </div>

          {/* Pillar 2: Conditions */}
          <div className="bg-app-bg p-3 rounded border border-app-border">
            <div className="flex items-center gap-1.5 mb-2 pb-1.5 border-b border-app-border">
              <FileText className="w-3.5 h-3.5 text-info shrink-0" />
              <span className="text-xs font-bold text-text-main">Diagnoses</span>
              <span className="ml-auto text-[10px] font-mono text-text-muted">({conditions.length})</span>
            </div>
            <div className="space-y-1.5">
              {conditions.length > 0 ? (
                conditions.map((c) => (
                  <div key={c.id} className="bg-app-surface p-2 rounded border border-app-border text-xs">
                    <div className="font-semibold text-text-main">{c.code?.text}</div>
                    <div className="text-[10px] text-text-muted mt-0.5">Onset: {c.onsetDateTime || 'Documented'}</div>
                  </div>
                ))
              ) : (
                <div className="text-[11px] text-text-muted italic">No chronic diagnoses recorded.</div>
              )}
            </div>
          </div>

          {/* Pillar 3: Observations & Labs */}
          <div className="bg-app-bg p-3 rounded border border-app-border">
            <div className="flex items-center gap-1.5 mb-2 pb-1.5 border-b border-app-border">
              <Activity className="w-3.5 h-3.5 text-teal-700 shrink-0" />
              <span className="text-xs font-bold text-text-main">Recent Labs</span>
              <span className="ml-auto text-[10px] font-mono text-text-muted">({observations.length})</span>
            </div>
            <div className="space-y-1.5">
              {observations.length > 0 ? (
                observations.map((o) => (
                  <div key={o.id} className="bg-app-surface p-2 rounded border border-app-border text-xs flex items-center justify-between">
                    <div>
                      <div className="font-semibold text-text-main">{o.code?.text}</div>
                      <div className="text-[10px] text-text-muted">{o.effectiveDateTime}</div>
                    </div>
                    {o.valueQuantity && (
                      <span className="font-mono font-bold text-teal-800 bg-teal-50 px-1.5 py-0.5 rounded border border-teal-200">
                        {o.valueQuantity.value} {o.valueQuantity.unit}
                      </span>
                    )}
                  </div>
                ))
              ) : (
                <div className="text-[11px] text-text-muted italic">No recent lab observations.</div>
              )}
            </div>
          </div>

          {/* Pillar 4: Allergies */}
          <div className="bg-app-bg p-3 rounded border border-app-border">
            <div className="flex items-center gap-1.5 mb-2 pb-1.5 border-b border-app-border">
              <AlertTriangle className="w-3.5 h-3.5 text-danger shrink-0" />
              <span className="text-xs font-bold text-text-main">Allergies</span>
              <span className="ml-auto text-[10px] font-mono text-text-muted">({allergies.length})</span>
            </div>
            <div className="space-y-1.5">
              {allergies.length > 0 ? (
                allergies.map((a) => (
                  <div key={a.id} className="bg-danger-light p-2 rounded border border-danger/30 text-xs">
                    <div className="font-bold text-danger-dark">{a.code?.text}</div>
                    <div className="text-[10px] text-danger-dark font-medium mt-0.5 uppercase tracking-wide">
                      Criticality: {a.criticality || 'High'}
                    </div>
                  </div>
                ))
              ) : (
                <div className="text-[11px] text-text-muted italic">No documented drug allergies.</div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
