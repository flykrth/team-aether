import React, { useEffect, useState } from 'react';
import { Pill, FileText, Activity, AlertTriangle, Loader2, ArrowUpRight, ShieldCheck } from 'lucide-react';
import { api } from '../services/api';

function getCoding(resource, conceptKey) {
  return (resource?.[conceptKey]?.coding || [])[0] || {};
}

function Tile({ icon: Icon, title, subtitle, count, tone = 'default', children }) {
  const disc =
    tone === 'danger'
      ? 'bg-danger-light text-danger'
      : tone === 'accent'
      ? 'bg-accent text-white'
      : 'bg-app-secondary text-ink';
  return (
    <div className="card flex flex-col gap-5 min-h-[15rem]">
      <div className="flex items-center gap-3">
        <span className={`inline-flex items-center justify-center w-12 h-12 rounded-full shrink-0 ${disc}`}>
          <Icon className="w-5 h-5" strokeWidth={1.5} />
        </span>
        <div className="min-w-0 flex-1">
          <div className="font-display text-lg font-medium text-ink leading-tight">{title}</div>
          <div className="text-xs text-text-muted">
            {subtitle} · <span className="font-mono">({count})</span>
          </div>
        </div>
        <span className="icon-btn" aria-hidden="true">
          <ArrowUpRight className="w-[18px] h-[18px]" strokeWidth={1.5} />
        </span>
      </div>
      <div className="space-y-2">{children}</div>
    </div>
  );
}

function Empty({ children }) {
  return <div className="text-sm text-text-muted px-1">{children}</div>;
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
    <section className="mb-2">
      <div className="flex flex-wrap items-end justify-between gap-4 mb-5">
        <div>
          <h2 className="display-lg text-ink">Relevant Medical Context</h2>
          <p className="mt-1 text-sm text-text-muted">Synchronized from Hospital Medical EHR (FHIR R4)</p>
        </div>
        <span className="chip chip-accent">
          <ShieldCheck className="w-3.5 h-3.5" strokeWidth={1.5} />
          Verified EHR Record
        </span>
      </div>

      {loading ? (
        <div className="card flex items-center justify-center gap-2 text-sm text-text-muted py-12">
          <Loader2 className="w-4 h-4 animate-spin text-accent" strokeWidth={1.5} />
          Loading patient medical record…
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-6">
          {/* Pillar 1: Medications */}
          <Tile icon={Pill} title="Medications" subtitle="Active prescriptions" count={medications.length} tone="accent">
            {medications.length > 0 ? (
              medications.map((m) => (
                <div key={m.id} className="well py-3 px-4">
                  <div className="text-sm font-medium text-text-main">{m.medicationCodeableConcept?.text}</div>
                  <div className="text-xs text-text-muted mt-0.5">
                    Status: <span className="text-text-secondary">{m.status}</span>
                  </div>
                </div>
              ))
            ) : (
              <Empty>No active prescriptions recorded.</Empty>
            )}
          </Tile>

          {/* Pillar 2: Conditions */}
          <Tile icon={FileText} title="Diagnoses" subtitle="Care plan" count={conditions.length}>
            {conditions.length > 0 ? (
              conditions.map((c) => (
                <div key={c.id} className="well py-3 px-4">
                  <div className="text-sm font-medium text-text-main">{c.code?.text}</div>
                  <div className="text-xs text-text-muted mt-0.5">Onset: {c.onsetDateTime || 'Documented'}</div>
                </div>
              ))
            ) : (
              <Empty>No chronic diagnoses recorded.</Empty>
            )}
          </Tile>

          {/* Pillar 3: Observations & Labs */}
          <Tile icon={Activity} title="Recent Labs" subtitle="Vital signs" count={observations.length}>
            {observations.length > 0 ? (
              observations.map((o) => (
                <div key={o.id} className="well py-3 px-4 flex items-center justify-between gap-3">
                  <div className="min-w-0">
                    <div className="text-sm font-medium text-text-main">{o.code?.text}</div>
                    <div className="text-xs text-text-muted">{o.effectiveDateTime}</div>
                  </div>
                  {o.valueQuantity && (
                    <span className="font-display text-xl font-medium text-accent whitespace-nowrap">
                      {o.valueQuantity.value}
                      <span className="ml-1 text-xs font-sans text-text-muted">{o.valueQuantity.unit}</span>
                    </span>
                  )}
                </div>
              ))
            ) : (
              <Empty>No recent lab observations.</Empty>
            )}
          </Tile>

          {/* Pillar 4: Allergies */}
          <Tile icon={AlertTriangle} title="Allergies" subtitle="Documented reactions" count={allergies.length} tone="danger">
            {allergies.length > 0 ? (
              allergies.map((a) => (
                <div key={a.id} className="bg-danger-light rounded-3xl py-3 px-4">
                  <div className="text-sm font-medium text-danger-dark">{a.code?.text}</div>
                  <div className="text-xs text-danger-dark/80 mt-0.5">
                    Criticality: {a.criticality || 'High'}
                  </div>
                </div>
              ))
            ) : (
              <Empty>No documented drug allergies.</Empty>
            )}
          </Tile>
        </div>
      )}
    </section>
  );
}
