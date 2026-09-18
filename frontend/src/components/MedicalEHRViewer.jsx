import React, { useEffect, useState } from 'react';
import { Stethoscope, FileText, ArrowRightLeft, Pill, AlertTriangle, FlaskConical, Loader2 } from 'lucide-react';
import { api } from '../services/api';

function getCoding(resource, conceptKey) {
  return (resource?.[conceptKey]?.coding || [])[0] || {};
}

/**
 * Federated Medical EHR panel (Epic/Cerner via TEFCA/FHIR R4).
 * Displays raw FHIR Condition / MedicationRequest / AllergyIntolerance / Observation resources
 * with a toggle to inspect the live ConceptMap $translate transformation trace.
 */
export function MedicalEHRViewer({ patient }) {
  const [conditions, setConditions] = useState([]);
  const [medications, setMedications] = useState([]);
  const [allergies, setAllergies] = useState([]);
  const [observations, setObservations] = useState([]);
  const [loading, setLoading] = useState(false);
  const [showTrace, setShowTrace] = useState(false);
  const [trace, setTrace] = useState([]);
  const [traceLoading, setTraceLoading] = useState(false);

  useEffect(() => {
    if (!patient?.mrn) return;
    let cancelled = false;

    async function loadRecords() {
      setLoading(true);
      try {
        const fhirPatient = await api.getFhirPatient(patient.mrn).catch(() => null);
        const fhirId = fhirPatient?.id || patient.mrn;

        const [conds, meds, allgs, obs] = await Promise.all([
          api.getFhirConditions(fhirId).catch(() => []),
          api.getFhirMedications(fhirId).catch(() => []),
          api.getFhirAllergies(fhirId).catch(() => []),
          api.getFhirObservations(fhirId).catch(() => []),
        ]);
        if (cancelled) return;
        setConditions(conds);
        setMedications(meds);
        setAllergies(allgs);
        setObservations(obs);
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    loadRecords();
    return () => {
      cancelled = true;
    };
  }, [patient?.mrn]);

  useEffect(() => {
    if (!showTrace) return;
    let cancelled = false;

    async function buildTrace() {
      setTraceLoading(true);
      const sources = [
        ...conditions.map((c) => ({ resourceType: 'Condition', ...getCoding(c, 'code') })),
        ...medications.map((m) => ({ resourceType: 'MedicationRequest', ...getCoding(m, 'medicationCodeableConcept') })),
        ...allergies.map((a) => ({ resourceType: 'AllergyIntolerance', ...getCoding(a, 'code') })),
      ].filter((s) => s.system && s.code);

      const results = await Promise.all(
        sources.map(async (s) => {
          const outcome = await api.translateConcept(s.system, s.code).catch(() => null);
          return { ...s, outcome };
        })
      );
      if (!cancelled) setTrace(results);
      setTraceLoading(false);
    }

    buildTrace();
    return () => {
      cancelled = true;
    };
  }, [showTrace, conditions, medications, allergies]);

  if (!patient) {
    return (
      <div className="card text-center text-sm text-text-muted py-10">
        Select a patient to inspect the federated Medical EHR record.
      </div>
    );
  }

  return (
    <div className="card p-7">
      <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-4 mb-6">
        <div className="flex items-center gap-4">
          <div className="icon-disc">
            <Stethoscope className="w-5 h-5" strokeWidth={1.5} />
          </div>
          <div>
            <h3 className="font-display text-2xl font-medium text-text-main leading-tight">Federated Medical EHR Record</h3>
            <p className="text-[13px] text-text-muted mt-0.5">Hospital-of-record clinical data (HL7 FHIR R4)</p>
          </div>
        </div>
        <button
          onClick={() => setShowTrace((v) => !v)}
          className={`pill shrink-0 ${showTrace ? 'pill-active' : 'bg-app-secondary'}`}
        >
          <ArrowRightLeft className="w-4 h-4" strokeWidth={1.5} />
          {showTrace ? 'View Raw FHIR' : 'ConceptMap $translate Trace'}
        </button>
      </div>

      <div>
        {loading ? (
          <div className="well flex items-center justify-center gap-2.5 text-sm text-text-muted py-10">
            <Loader2 className="w-4 h-4 animate-spin text-accent" strokeWidth={1.5} />
            Synchronizing federated EHR record via FHIR R4…
          </div>
        ) : showTrace ? (
          <TraceView trace={trace} loading={traceLoading} />
        ) : (
          <RawFhirView
            conditions={conditions}
            medications={medications}
            allergies={allergies}
            observations={observations}
          />
        )}
      </div>
    </div>
  );
}

const RESOURCE_FILTERS = [
  { key: 'all', label: 'All' },
  { key: 'conditions', label: 'Conditions' },
  { key: 'medications', label: 'Medications' },
  { key: 'allergies', label: 'Allergies' },
  { key: 'labs', label: 'Labs' },
];

function RawFhirView({ conditions, medications, allergies, observations }) {
  const [filter, setFilter] = useState('all');
  const show = (key) => filter === 'all' || filter === key;

  return (
    <div>
      <div className="flex flex-wrap gap-2 mb-6">
        {RESOURCE_FILTERS.map((f) => (
          <button
            key={f.key}
            type="button"
            onClick={() => setFilter(f.key)}
            className={`pill h-10 px-4 text-sm ${filter === f.key ? 'pill-active' : 'bg-app-secondary'}`}
          >
            {f.label}
          </button>
        ))}
      </div>

      <div className="space-y-7">
        {show('conditions') && (
          <ResourceSection
            icon={FileText}
            title="Condition (Diagnoses)"
            items={conditions}
            renderItem={(c) => (
              <>
                <div className="font-display text-base font-semibold text-text-main leading-snug">{c.code?.text}</div>
                <CodingRow coding={getCoding(c, 'code')} />
                <div className="text-xs text-text-muted mt-2 tabular-nums">Onset: {c.onsetDateTime || 'Documented'}</div>
              </>
            )}
          />
        )}
        {show('medications') && (
          <ResourceSection
            icon={Pill}
            title="MedicationRequest (Active Rx)"
            items={medications}
            renderItem={(m) => (
              <>
                <div className="font-display text-base font-semibold text-text-main leading-snug">{m.medicationCodeableConcept?.text}</div>
                <CodingRow coding={getCoding(m, 'medicationCodeableConcept')} />
                <div className="mt-2">
                  <span className="chip bg-white">Status: <span className="text-text-main">{m.status}</span></span>
                </div>
              </>
            )}
          />
        )}
        {show('allergies') && (
          <ResourceSection
            icon={AlertTriangle}
            discClass="bg-danger"
            tileClass="bg-danger-light"
            title="AllergyIntolerance"
            items={allergies}
            renderItem={(a) => (
              <>
                <div className="font-display text-base font-semibold text-danger-dark leading-snug">{a.code?.text}</div>
                <CodingRow coding={getCoding(a, 'code')} />
                <div className="mt-2">
                  <span className="chip bg-white text-danger-dark">Criticality: {a.criticality || 'high'}</span>
                </div>
              </>
            )}
          />
        )}
        {show('labs') && (
          <ResourceSection
            icon={FlaskConical}
            title="Observation (Labs)"
            items={observations}
            renderItem={(o) => (
              <div className="flex items-end justify-between gap-4">
                <div className="min-w-0">
                  <div className="font-display text-base font-semibold text-text-main leading-snug">{o.code?.text}</div>
                  <CodingRow coding={getCoding(o, 'code')} />
                  <div className="text-xs text-text-muted mt-2 tabular-nums">Resulted: {o.effectiveDateTime || 'Undated'}</div>
                </div>
                {o.valueQuantity && (
                  <div className="shrink-0 text-right leading-none">
                    <span className="font-display text-4xl font-medium text-text-main tracking-tight tabular-nums">
                      {o.valueQuantity.value}
                    </span>{' '}
                    <span className="text-xs text-text-muted">{o.valueQuantity.unit}</span>
                  </div>
                )}
              </div>
            )}
          />
        )}
      </div>
    </div>
  );
}

function ResourceSection({ icon: Icon, discClass = '', tileClass = 'bg-app-secondary', title, items, renderItem }) {
  return (
    <div>
      <div className="flex items-center gap-2 mb-3">
        <span className="font-display text-[15px] font-medium text-text-main">{title}</span>
        <span className="text-xs text-text-muted tabular-nums">({items.length})</span>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        {items.length > 0 ? (
          items.map((item) => (
            <div key={item.id} className={`flex items-start gap-4 rounded-3xl p-4 text-sm ${tileClass}`}>
              <div className={`icon-disc w-10 h-10 ${discClass}`}>
                <Icon className="w-[18px] h-[18px]" strokeWidth={1.5} />
              </div>
              <div className="min-w-0 flex-1 pt-0.5">{renderItem(item)}</div>
            </div>
          ))
        ) : (
          <div className="well text-sm text-text-muted md:col-span-2">
            No {title} resources recorded in federated EHR.
          </div>
        )}
      </div>
    </div>
  );
}

function CodingRow({ coding }) {
  if (!coding?.code) return null;
  return (
    <div className="mt-1 font-mono text-[11px] text-text-muted break-all">
      {coding.system} <span className="text-text-muted">|</span> <strong className="text-text-main font-medium">{coding.code}</strong>
    </div>
  );
}

function TraceView({ trace, loading }) {
  if (loading) {
    return (
      <div className="well flex items-center justify-center gap-2.5 text-sm text-text-muted py-10">
        <Loader2 className="w-4 h-4 animate-spin text-accent" strokeWidth={1.5} />
        Running ConceptMap $translate operation against medical-to-dental-contraindications...
      </div>
    );
  }

  if (trace.length === 0) {
    return <div className="well text-sm text-text-muted">No coded concepts available for semantic translation.</div>;
  }

  return (
    <div className="space-y-2.5">
      <p className="text-[13px] text-text-secondary mb-4">
        Live FHIR ConceptMap <code className="font-mono text-xs bg-app-secondary px-2 py-0.5 rounded-full text-text-main">$translate</code> trace — cross-specialty mapping:
      </p>
      {trace.map((row, i) => {
        const matched = row.outcome?.result;
        const match = row.outcome?.match?.[0];
        return (
          <div
            key={i}
            className={`flex items-center gap-4 rounded-3xl p-4 text-sm ${
              matched ? 'bg-accent-soft' : 'bg-app-secondary'
            }`}
          >
            <div className="flex-1 min-w-0">
              <div className="font-mono text-[10px] text-text-muted truncate">{row.system}</div>
              <div className="font-display font-semibold text-text-main truncate mt-0.5">{row.display || row.code}</div>
              <div className="font-mono text-[11px] text-text-secondary">{row.code}</div>
            </div>
            <div className={`inline-flex items-center justify-center w-9 h-9 rounded-full shrink-0 ${matched ? 'bg-accent text-white' : 'bg-white text-text-muted'}`}>
              <ArrowRightLeft className="w-4 h-4" strokeWidth={1.5} />
            </div>
            <div className="flex-1 min-w-0 text-right">
              {matched ? (
                <>
                  <div className="font-mono text-[10px] text-accent-deep">{match.equivalence}</div>
                  <div className="font-mono font-semibold text-accent-deep mt-0.5">{match.concept.code}</div>
                  <div className="text-[11px] text-accent-deep/80 truncate">{match.concept.display}</div>
                </>
              ) : (
                <span className="text-text-muted text-xs">No mapping rule</span>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}
