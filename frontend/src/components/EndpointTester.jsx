import React, { useState } from 'react';
import { Play, Code, Clock } from 'lucide-react';
import { api } from '../services/api';

const ENDPOINTS = [
  { id: 'health', name: 'System Health', method: 'GET', path: '/health', fn: () => api.getHealth() },
  { id: 'carestack-status', name: 'CareStack Status', method: 'GET', path: '/api/carestack/status', fn: () => api.getCareStackStatus() },
  { id: 'carestack-patients', name: 'CareStack Patients', method: 'GET', path: '/api/carestack/patients', fn: () => api.getCareStackPatients() },
  { id: 'fhir-metadata', name: 'FHIR Capability', method: 'GET', path: '/api/fhir/metadata', fn: () => api.getFhirMetadata() },
  { id: 'fhir-server-status', name: 'FHIR Live Test Server Status', method: 'GET', path: '/api/fhir/server-status', fn: () => api.getFhirServerStatus() },
  { id: 'fhir-patients', name: 'FHIR Patient Resources', method: 'GET', path: '/api/fhir/Patient', fn: () => api.getFhirPatients() },
  { id: 'cds-discovery', name: 'CDS Hooks Discovery', method: 'GET', path: '/cds-services', fn: () => api.getCdsServices() },
  {
    id: 'cds-eval-mronj',
    name: 'CDS Risk Evaluator (MRONJ)',
    method: 'POST',
    path: '/cds-services/med-dental-risk-evaluator',
    fn: () => api.evaluateRiskHook('EHR-88201'),
  },
  {
    id: 'cds-eval-valve',
    name: 'CDS Risk Evaluator (Heart Valve)',
    method: 'POST',
    path: '/cds-services/med-dental-risk-evaluator',
    fn: () => api.evaluateRiskHook('EHR-99342'),
  },
];

export function EndpointTester() {
  const [selectedEndpoint, setSelectedEndpoint] = useState(ENDPOINTS[0]);
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [duration, setDuration] = useState(null);
  const [error, setError] = useState(null);

  const handleRun = async (ep) => {
    const target = ep || selectedEndpoint;
    setLoading(true);
    setError(null);
    setResult(null);
    const start = performance.now();
    try {
      const data = await target.fn();
      setDuration(Math.round(performance.now() - start));
      setResult(data);
    } catch (err) {
      setDuration(Math.round(performance.now() - start));
      setError(err.message || 'Request failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="card p-7">
      <div className="flex items-center gap-4 mb-7">
        <div className="icon-disc">
          <Code className="w-5 h-5" strokeWidth={1.5} />
        </div>
        <div>
          <h3 className="font-display text-2xl font-medium text-text-main tracking-tight leading-tight">
            <span>Interactive Interoperability Endpoint Tester</span>
          </h3>
          <p className="text-[13px] text-text-muted mt-0.5">
            Execute live requests against the FastAPI backend endpoints (/api/carestack, /api/fhir, /cds-services).
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
        {/* Endpoint Selector List */}
        <div className="lg:col-span-4 space-y-2">
          {ENDPOINTS.map((ep) => {
            const isSelected = selectedEndpoint.id === ep.id;
            return (
              <button
                key={ep.id}
                onClick={() => {
                  setSelectedEndpoint(ep);
                  handleRun(ep);
                }}
                className={`w-full text-left px-5 py-3.5 rounded-3xl transition-colors text-sm flex items-center justify-between gap-3 ${
                  isSelected
                    ? 'bg-ink text-white'
                    : 'bg-app-secondary hover:bg-app-bg text-text-main'
                }`}
              >
                <div className="min-w-0">
                  <div className="font-display font-semibold truncate">{ep.name}</div>
                  <div className={`text-[11px] font-mono mt-0.5 truncate ${isSelected ? 'text-white/60' : 'text-text-muted'}`}>{ep.path}</div>
                </div>
                <span
                  className={`shrink-0 px-2.5 py-1 text-[10px] font-mono font-medium rounded-full ${
                    ep.method === 'GET'
                      ? isSelected ? 'bg-white/10 text-white' : 'bg-white text-text-secondary'
                      : 'bg-accent text-white'
                  }`}
                >
                  {ep.method}
                </span>
              </button>
            );
          })}
        </div>

        {/* Live Payload Viewer */}
        <div className="lg:col-span-8">
          <div className="bg-ink rounded-3xl overflow-hidden flex flex-col h-full min-h-[400px]">
            {/* Header bar */}
            <div className="px-5 pt-5 pb-3 flex items-center justify-between gap-3">
              <div className="flex items-center gap-2.5 min-w-0">
                <span className="font-mono text-[11px] font-medium text-white bg-accent px-2.5 py-1 rounded-full shrink-0">
                  {selectedEndpoint.method}
                </span>
                <span className="font-mono text-xs text-white/70 truncate">
                  {selectedEndpoint.path}
                </span>
              </div>

              <div className="flex items-center gap-3 shrink-0">
                {duration !== null && (
                  <span className="flex items-center gap-1.5 text-[11px] text-white/50 font-mono tabular-nums">
                    <Clock className="w-3.5 h-3.5" strokeWidth={1.5} />
                    {duration}ms
                  </span>
                )}
                <button
                  onClick={() => handleRun()}
                  disabled={loading}
                  className="inline-flex items-center gap-1.5 h-9 px-4 bg-white hover:bg-app-secondary text-ink rounded-full text-sm font-display font-semibold disabled:opacity-40"
                >
                  <Play className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} strokeWidth={1.5} />
                  <span>Execute</span>
                </button>
              </div>
            </div>

            {/* Code Output */}
            <div className="mx-2 mb-2 p-4 flex-1 overflow-auto font-mono text-xs text-white/80 bg-white/[0.04] rounded-[20px]">
              {loading && (
                <div className="h-full flex items-center justify-center text-white/50 text-xs">
                  Connecting to MDIN FastAPI node...
                </div>
              )}

              {error && (
                <div className="text-danger-dark bg-danger-light p-4 rounded-2xl">
                  Error: {error}
                </div>
              )}

              {result && !loading && (
                <pre className="whitespace-pre-wrap leading-relaxed text-[11px] text-accent-soft/90">
                  {JSON.stringify(result, null, 2)}
                </pre>
              )}

              {!result && !loading && !error && (
                <div className="h-full flex items-center justify-center text-white/50 text-xs">
                  Click 'Execute' or choose an endpoint on the left to inspect raw payload.
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
