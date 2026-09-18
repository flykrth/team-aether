import React, { useEffect, useState } from 'react';
import { Stethoscope, FileText, ArrowRightLeft, Pill, AlertTriangle, Loader2, Database } from 'lucide-react';
import { api } from '../services/api';

function getCoding(resource, conceptKey) {
  return (resource?.[conceptKey]?.coding || [])[0] || {};
}

/**
 * Federated Medical EHR panel (Epic/Cerner via TEFCA/FHIR R4).
 * Displays raw FHIR Condition / MedicationRequest / AllergyIntolerance resources
 * with a toggle to inspect the live ConceptMap $translate transformation trace.
 */
export function MedicalEHRViewer({ patient }) {
  const [conditions, setConditions] = useState([]);
  const [medications, setMedications] = useState([]);
  const [allergies, setAllergies] = useState([]);
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

        const [conds, meds, allgs] = await Promise.all([
          api.getFhirConditions(fhirId).catch(() => []),
          api.getFhirMedications(fhirId).catch(() => []),
          api.getFhirAllergies(fhirId).catch(() => []),
        ]);
        if (cancelled) return;
        setConditions(conds);
        setMedications(meds);
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
      <div className="p-6 text-center text-xs text-text-muted bg-app-surface rounded-lg border border-app-border">
        Select a patient to inspect the federated Medical EHR record.
      </div>
    );
  }

  return (
    <div className="bg-app-surface rounded-lg border border-app-border shadow-xs overflow-hidden">
      <div className="flex items-center justify-between px-4 py-3.5 border-b border-app-border bg-app-surface">
        <div className="flex items-center gap-2">
          <Stethoscope className="w-4 h-4 text-teal-500" />
          <div>
            <h3 className="font-bold text-sm text-text-main leading-tight">Federated Medical EHR Record</h3>
            <p className="text-[11px] text-text-secondary">Hospital-of-record clinical data (HL7 FHIR R4)</p>
          </div>
        </div>
        <button
          onClick={() => setShowTrace((v) => !v)}
          className={`inline-flex items-center gap-1.5 text-xs font-semibold px-2.5 py-1.5 rounded border transition-colors ${
            showTrace
              ? 'bg-teal-500 text-white border-teal-500 shadow-xs'
              : 'bg-app-surface text-teal-700 border-teal-300 hover:bg-teal-50'
          }`}
        >
          <ArrowRightLeft className="w-3.5 h-3.5" />
          {showTrace ? 'View Raw FHIR' : 'ConceptMap $translate Trace'}
        </button>
      </div>

      <div className="p-4">
        {loading ? (
          <div className="flex items-center justify-center gap-2 text-xs text-text-muted py-6">
            <Loader2 className="w-4 h-4 animate-spin text-teal-500" />
            Synchronizing federated EHR record via FHIR R4…
          </div>
        ) : showTrace ? (
          <TraceView trace={trace} loading={traceLoading} />
        ) : (
          <RawFhirView conditions={conditions} medications={medications} allergies={allergies} />
        )}
      </div>
    </div>
  );
}

function RawFhirView({ conditions, medications, allergies }) {
  return (
    <div className="space-y-4">
      <ResourceSection
        icon={FileText}
        colorClass="text-info"
        title="Condition (Diagnoses)"
        items={conditions}
        renderItem={(c) => (
          <>
            <div className="font-semibold text-text-main">{c.code?.text}</div>
            <CodingRow coding={getCoding(c, 'code')} />
            <div className="text-[10px] text-text-muted mt-0.5">Onset: {c.onsetDateTime || 'Documented'}</div>
          </>
        )}
      />
      <ResourceSection
        icon={Pill}
        colorClass="text-teal-600"
        title="MedicationRequest (Active Rx)"
        items={medications}
        renderItem={(m) => (
          <>
            <div className="font-semibold text-text-main">{m.medicationCodeableConcept?.text}</div>
            <CodingRow coding={getCoding(m, 'medicationCodeableConcept')} />
            <div className="text-[10px] text-text-muted mt-0.5">Status: <span className="font-medium text-text-main">{m.status}</span></div>
          </>
        )}
      />
      <ResourceSection
        icon={AlertTriangle}
        colorClass="text-danger"
        title="AllergyIntolerance"
        items={allergies}
        renderItem={(a) => (
          <>
            <div className="font-bold text-danger-dark">{a.code?.text}</div>
            <CodingRow coding={getCoding(a, 'code')} />
            <div className="text-[10px] text-danger-dark font-medium mt-0.5 uppercase tracking-wide">
              Criticality: {a.criticality || 'high'}
            </div>
          </>
        )}
      />
    </div>
  );
}

function ResourceSection({ icon: Icon, colorClass, title, items, renderItem }) {
  return (
    <div>
      <div className="flex items-center gap-1.5 mb-1.5">
        <Icon className={`w-3.5 h-3.5 ${colorClass}`} />
        <span className="text-[11px] font-bold uppercase tracking-wider text-text-secondary">{title}</span>
        <span className="text-[10px] text-text-muted font-mono">({items.length})</span>
      </div>
      <div className="space-y-1.5">
        {items.length > 0 ? (
          items.map((item) => (
            <div key={item.id} className="p-2.5 bg-app-bg rounded border border-app-border text-xs">
              {renderItem(item)}
            </div>
          ))
        ) : (
          <div className="text-xs text-text-muted italic bg-app-surface p-2 rounded border border-app-border/50">
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
    <div className="mt-0.5 font-mono text-[10px] text-text-muted break-all">
      {coding.system} <span className="font-bold text-text-secondary">|</span> <strong className="text-text-main font-semibold">{coding.code}</strong>
    </div>
  );
}

function TraceView({ trace, loading }) {
  if (loading) {
    return (
      <div className="flex items-center justify-center gap-2 text-xs text-text-muted py-6">
        <Loader2 className="w-4 h-4 animate-spin text-teal-500" />
        Running ConceptMap $translate operation against medical-to-dental-contraindications...
      </div>
    );
  }

  if (trace.length === 0) {
    return <div className="text-xs text-text-muted italic py-3">No coded concepts available for semantic translation.</div>;
  }

  return (
    <div className="space-y-2">
      <p className="text-[11px] text-text-secondary mb-2">
        Live FHIR ConceptMap <code className="font-mono bg-app-secondary px-1 py-0.5 rounded border border-app-border text-text-main">$translate</code> trace — cross-specialty mapping:
      </p>
      {trace.map((row, i) => {
        const matched = row.outcome?.result;
        const match = row.outcome?.match?.[0];
        return (
          <div
            key={i}
            className={`flex items-center gap-2.5 p-2.5 rounded border text-xs ${
              matched ? 'border-teal-300 bg-teal-50/60' : 'border-app-border bg-app-bg'
            }`}
          >
            <div className="flex-1 min-w-0">
              <div className="font-mono text-[9px] text-text-muted truncate">{row.system}</div>
              <div className="font-semibold text-text-main truncate">{row.display || row.code}</div>
              <div className="font-mono text-[10px] text-text-secondary">{row.code}</div>
            </div>
            <ArrowRightLeft className={`w-3.5 h-3.5 shrink-0 ${matched ? 'text-teal-600' : 'text-text-muted'}`} />
            <div className="flex-1 min-w-0 text-right">
              {matched ? (
                <>
                  <div className="font-mono text-[9px] text-teal-700 uppercase font-bold">{match.equivalence}</div>
                  <div className="font-mono font-bold text-teal-800">{match.concept.code}</div>
                  <div className="text-[10px] text-teal-700 truncate">{match.concept.display}</div>
                </>
              ) : (
                <span className="text-text-muted italic text-[11px]">No mapping rule</span>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}

