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
    <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-sm">
      <div className="pb-5 border-b border-slate-100 mb-5">
        <h3 className="text-lg font-bold text-slate-900 tracking-tight flex items-center gap-2">
          <Code className="w-5 h-5 text-sky-600" />
          <span>Interactive Interoperability Endpoint Tester</span>
        </h3>
        <p className="text-xs text-slate-500 mt-1">
          Execute live requests against the FastAPI backend endpoints (/api/carestack, /api/fhir, /cds-services).
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
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
                className={`w-full text-left p-3 rounded-lg border transition-all text-xs flex items-center justify-between ${
                  isSelected
                    ? 'border-sky-500 bg-sky-50/50 shadow-xs'
                    : 'border-slate-200 hover:border-slate-300 bg-white'
                }`}
              >
                <div>
                  <div className="font-semibold text-slate-900">{ep.name}</div>
                  <div className="text-[11px] font-mono text-slate-500 mt-0.5">{ep.path}</div>
                </div>
                <span
                  className={`px-2 py-0.5 text-[10px] font-mono font-bold rounded ${
                    ep.method === 'GET'
                      ? 'bg-emerald-100 text-emerald-800'
                      : 'bg-indigo-100 text-indigo-800'
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
          <div className="bg-slate-900 rounded-xl overflow-hidden shadow-inner flex flex-col h-full min-h-[420px]">
            {/* Header bar */}
            <div className="bg-slate-950 px-4 py-3 flex items-center justify-between border-b border-slate-800">
              <div className="flex items-center gap-3">
                <span className="font-mono text-xs font-bold text-emerald-400">
                  {selectedEndpoint.method}
                </span>
                <span className="font-mono text-xs text-slate-300">
                  {selectedEndpoint.path}
                </span>
              </div>

              <div className="flex items-center gap-3">
                {duration !== null && (
                  <span className="flex items-center gap-1 text-[11px] text-slate-400 font-mono">
                    <Clock className="w-3 h-3" />
                    {duration}ms
                  </span>
                )}
                <button
                  onClick={() => handleRun()}
                  disabled={loading}
                  className="inline-flex items-center gap-1.5 px-3 py-1 bg-sky-600 hover:bg-sky-500 text-white rounded text-xs font-medium transition-colors disabled:opacity-50"
                >
                  <Play className={`w-3 h-3 ${loading ? 'animate-spin' : ''}`} />
                  <span>Execute</span>
                </button>
              </div>
            </div>

            {/* Code Output */}
            <div className="p-4 flex-1 overflow-auto font-mono text-xs text-slate-200">
              {loading && (
                <div className="h-full flex items-center justify-center text-slate-500">
                  Connecting to MDIN FastAPI node...
                </div>
              )}

              {error && (
                <div className="text-rose-400 bg-rose-950/40 p-4 rounded-lg border border-rose-800">
                  Error: {error}
                </div>
              )}

              {result && !loading && (
                <pre className="whitespace-pre-wrap leading-relaxed">
                  {JSON.stringify(result, null, 2)}
                </pre>
              )}

              {!result && !loading && !error && (
                <div className="h-full flex items-center justify-center text-slate-500">
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
