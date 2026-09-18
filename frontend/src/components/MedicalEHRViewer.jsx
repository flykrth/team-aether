import React, { useEffect, useState } from 'react';
import { Stethoscope, FileText, ArrowRightLeft, Pill, AlertTriangle, FlaskConical, Loader2 } from 'lucide-react';
import { api } from '../services/api';

function getCoding(resource, conceptKey) {
  return (resource?.[conceptKey]?.coding || [])[0] || {};
}

/**
 * Right-hand federated Medical EHR panel (Epic/Cerner via TEFCA/FHIR).
 * Shows the raw FHIR Condition / MedicationRequest / AllergyIntolerance / Observation
 * resources for the selected patient, with a toggle to visualize the live ConceptMap
 * $translate transformation trace for each coded concept.
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
        // Resolve the FHIR-native patient id from the CareStack MRN first — the
        // Condition/MedicationRequest/AllergyIntolerance search endpoints filter by
        // FHIR resource id, not by MRN identifier.
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
      <div className="p-6 text-center text-sm text-slate-500 bg-white rounded-xl border border-slate-200">
        Select a patient to view the federated Medical EHR record.
      </div>
    );
  }

  return (
    <div className="bg-white rounded-xl border border-slate-200 shadow-sm">
      <div className="flex items-center justify-between px-5 py-4 border-b border-slate-100">
        <div className="flex items-center gap-2">
          <Stethoscope className="w-4 h-4 text-teal-600" />
          <div>
            <h3 className="font-bold text-sm text-slate-900">Federated Medical EHR (Epic/Cerner · TEFCA/FHIR)</h3>
            <p className="text-[11px] text-slate-500">Hospital-of-record clinical data for {patient.first_name} {patient.last_name}</p>
          </div>
        </div>
        <button
          onClick={() => setShowTrace((v) => !v)}
          className={`inline-flex items-center gap-1.5 text-[11px] font-semibold px-2.5 py-1.5 rounded-lg border transition-colors ${
            showTrace
              ? 'bg-indigo-600 text-white border-indigo-600'
              : 'bg-white text-indigo-700 border-indigo-300 hover:bg-indigo-50'
          }`}
        >
          <ArrowRightLeft className="w-3.5 h-3.5" />
          {showTrace ? 'Show Raw FHIR' : 'Show $translate Trace'}
        </button>
      </div>

      <div className="p-5">
        {loading ? (
          <div className="flex items-center justify-center gap-2 text-xs text-slate-500 py-8">
            <Loader2 className="w-4 h-4 animate-spin" />
            Loading federated EHR record…
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

function RawFhirView({ conditions, medications, allergies, observations }) {
  return (
    <div className="space-y-5">
      <ResourceSection
        icon={FileText}
        colorClass="text-sky-600"
        title="Condition"
        items={conditions}
        renderItem={(c) => (
          <>
            <div className="font-semibold text-slate-900">{c.code?.text}</div>
            <CodingRow coding={getCoding(c, 'code')} />
            <div className="text-[10px] text-slate-500 mt-1">Onset: {c.onsetDateTime || 'Documented'}</div>
          </>
        )}
      />
      <ResourceSection
        icon={Pill}
        colorClass="text-violet-600"
        title="MedicationRequest"
        items={medications}
        renderItem={(m) => (
          <>
            <div className="font-semibold text-slate-900">{m.medicationCodeableConcept?.text}</div>
            <CodingRow coding={getCoding(m, 'medicationCodeableConcept')} />
            <div className="text-[10px] text-slate-500 mt-1">Status: {m.status}</div>
          </>
        )}
      />
      <ResourceSection
        icon={AlertTriangle}
        colorClass="text-rose-600"
        title="AllergyIntolerance"
        items={allergies}
        renderItem={(a) => (
          <>
            <div className="font-bold text-rose-900">{a.code?.text}</div>
            <CodingRow coding={getCoding(a, 'code')} />
            <div className="text-[10px] text-rose-700 mt-1 uppercase tracking-wide">Criticality: {a.criticality || 'high'}</div>
          </>
        )}
      />
      <ResourceSection
        icon={FlaskConical}
        colorClass="text-amber-600"
        title="Observation"
        items={observations}
        renderItem={(o) => (
          <>
            <div className="flex items-start justify-between gap-2">
              <div className="font-semibold text-slate-900">{o.code?.text}</div>
              {o.valueQuantity && (
                <span className="shrink-0 font-mono font-bold text-amber-800 bg-amber-50 px-2 py-0.5 rounded border border-amber-200">
                  {o.valueQuantity.value} {o.valueQuantity.unit}
                </span>
              )}
            </div>
            <CodingRow coding={getCoding(o, 'code')} />
            <div className="text-[10px] text-slate-500 mt-1">Resulted: {o.effectiveDateTime || 'Undated'}</div>
          </>
        )}
      />
    </div>
  );
}

function ResourceSection({ icon: Icon, colorClass, title, items, renderItem }) {
  return (
    <div>
      <div className="flex items-center gap-1.5 mb-2">
        <Icon className={`w-3.5 h-3.5 ${colorClass}`} />
        <span className="text-[11px] font-bold uppercase tracking-wider text-slate-500">{title}</span>
        <span className="text-[10px] text-slate-400">({items.length})</span>
      </div>
      <div className="space-y-2">
        {items.length > 0 ? (
          items.map((item) => (
            <div key={item.id} className="p-2.5 bg-slate-50 rounded-lg border border-slate-200 text-xs">
              {renderItem(item)}
            </div>
          ))
        ) : (
          <div className="text-xs text-slate-400 italic">No {title} resources recorded.</div>
        )}
      </div>
    </div>
  );
}

function CodingRow({ coding }) {
  if (!coding?.code) return null;
  return (
    <div className="mt-1 font-mono text-[10px] text-slate-500 break-all">
      {coding.system} <span className="font-bold text-slate-700">|</span> {coding.code}
    </div>
  );
}

function TraceView({ trace, loading }) {
  if (loading) {
    return (
      <div className="flex items-center justify-center gap-2 text-xs text-slate-500 py-8">
        <Loader2 className="w-4 h-4 animate-spin" />
        Running ConceptMap $translate operation…
      </div>
    );
  }

  if (trace.length === 0) {
    return <div className="text-xs text-slate-400 italic py-4">No coded concepts available to translate.</div>;
  }

  return (
    <div className="space-y-2">
      <p className="text-[11px] text-slate-500 mb-3">
        Live FHIR ConceptMap <code className="font-mono bg-slate-100 px-1 rounded">$translate</code> trace — each
        source medical code below is resolved against{' '}
        <code className="font-mono bg-slate-100 px-1 rounded">medical-to-dental-contraindications</code>.
      </p>
      {trace.map((row, i) => {
        const matched = row.outcome?.result;
        const match = row.outcome?.match?.[0];
        return (
          <div
            key={i}
            className={`flex items-center gap-3 p-3 rounded-lg border text-xs ${
              matched ? 'border-indigo-200 bg-indigo-50/60' : 'border-slate-200 bg-slate-50'
            }`}
          >
            <div className="flex-1 min-w-0">
              <div className="font-mono text-[10px] text-slate-500 truncate">{row.system}</div>
              <div className="font-bold text-slate-900">{row.display || row.code}</div>
              <div className="font-mono text-[10px] text-slate-600">{row.code}</div>
            </div>
            <ArrowRightLeft className={`w-4 h-4 shrink-0 ${matched ? 'text-indigo-600' : 'text-slate-300'}`} />
            <div className="flex-1 min-w-0 text-right">
              {matched ? (
                <>
                  <div className="font-mono text-[10px] text-indigo-500">{match.equivalence}</div>
                  <div className="font-bold text-indigo-900">{match.concept.code}</div>
                  <div className="text-[10px] text-indigo-700">{match.concept.display}</div>
                </>
              ) : (
                <span className="text-slate-400 italic">No mapping</span>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}
