import React, { useState } from 'react';
import { Play, Code, CheckCircle, Clock } from 'lucide-react';
import { api } from '../services/api';

const ENDPOINTS = [
  { id: 'health', name: 'System Health', method: 'GET', path: '/health', fn: () => api.getHealth() },
  { id: 'carestack-status', name: 'CareStack Status', method: 'GET', path: '/api/carestack/status', fn: () => api.getCareStackStatus() },
  { id: 'carestack-patients', name: 'CareStack Patients', method: 'GET', path: '/api/carestack/patients', fn: () => api.getCareStackPatients() },
  { id: 'fhir-metadata', name: 'FHIR Capability', method: 'GET', path: '/api/fhir/metadata', fn: () => api.getFhirMetadata() },
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
    <div className="bg-app-surface rounded-lg border border-app-border p-5 shadow-xs">
      <div className="pb-4 border-b border-app-border mb-4">
        <h3 className="text-base font-bold text-text-main tracking-tight flex items-center gap-2">
          <Code className="w-4 h-4 text-teal-500" />
          <span>Interactive Interoperability Endpoint Tester</span>
        </h3>
        <p className="text-xs text-text-secondary mt-0.5">
          Execute live requests against the FastAPI backend endpoints (/api/carestack, /api/fhir, /cds-services).
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
        {/* Endpoint Selector List */}
        <div className="lg:col-span-4 space-y-1.5">
          {ENDPOINTS.map((ep) => {
            const isSelected = selectedEndpoint.id === ep.id;
            return (
              <button
                key={ep.id}
                onClick={() => {
                  setSelectedEndpoint(ep);
                  handleRun(ep);
                }}
                className={`w-full text-left p-2.5 rounded border transition-all text-xs flex items-center justify-between ${
                  isSelected
                    ? 'border-teal-500 bg-teal-50/50 shadow-xs'
                    : 'border-app-border hover:border-text-muted bg-app-surface'
                }`}
              >
                <div>
                  <div className="font-semibold text-text-main">{ep.name}</div>
                  <div className="text-[10px] font-mono text-text-secondary mt-0.5">{ep.path}</div>
                </div>
                <span
                  className={`px-1.5 py-0.5 text-[9px] font-mono font-bold rounded ${
                    ep.method === 'GET'
                      ? 'bg-teal-100 text-teal-800'
                      : 'bg-info-light text-info-dark'
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
          <div className="bg-text-main rounded-lg overflow-hidden shadow-inner flex flex-col h-full min-h-[400px]">
            {/* Header bar */}
            <div className="bg-slate-900 px-4 py-2.5 flex items-center justify-between border-b border-slate-800">
              <div className="flex items-center gap-2.5">
                <span className="font-mono text-xs font-bold text-teal-400">
                  {selectedEndpoint.method}
                </span>
                <span className="font-mono text-xs text-slate-300">
                  {selectedEndpoint.path}
                </span>
              </div>

              <div className="flex items-center gap-2.5">
                {duration !== null && (
                  <span className="flex items-center gap-1 text-[10px] text-slate-400 font-mono">
                    <Clock className="w-3 h-3 text-teal-400" />
                    {duration}ms
                  </span>
                )}
                <button
                  onClick={() => handleRun()}
                  disabled={loading}
                  className="inline-flex items-center gap-1.5 px-2.5 py-1 bg-teal-500 hover:bg-teal-700 text-white rounded text-xs font-semibold transition-colors disabled:opacity-50"
                >
                  <Play className={`w-3 h-3 ${loading ? 'animate-spin' : ''}`} />
                  <span>Execute</span>
                </button>
              </div>
            </div>

            {/* Code Output */}
            <div className="p-3.5 flex-1 overflow-auto font-mono text-xs text-slate-200">
              {loading && (
                <div className="h-full flex items-center justify-center text-slate-400 text-xs">
                  Connecting to MDIN FastAPI node...
                </div>
              )}

              {error && (
                <div className="text-danger-dark bg-danger-light p-3 rounded border border-danger/30">
                  Error: {error}
                </div>
              )}

              {result && !loading && (
                <pre className="whitespace-pre-wrap leading-relaxed text-[11px] text-teal-300">
                  {JSON.stringify(result, null, 2)}
                </pre>
              )}

              {!result && !loading && !error && (
                <div className="h-full flex items-center justify-center text-slate-400 text-xs">
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

