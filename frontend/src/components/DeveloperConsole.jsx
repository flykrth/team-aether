import React from 'react';
import { Terminal, FileCode, Network, Server, X } from 'lucide-react';
import { EndpointTester } from './EndpointTester';
import { InteroperabilityDashboard } from './InteroperabilityDashboard';

export function DeveloperConsole({ carestackStatus, backendOnline, onRefresh, onClose }) {
  return (
    <div className="bg-app-surface rounded-lg border border-app-border p-5 shadow-xs space-y-5">
      {/* Console Header */}
      <div className="flex items-center justify-between pb-3 border-b border-app-border">
        <div className="flex items-center gap-2">
          <Terminal className="w-4 h-4 text-teal-600" />
          <div>
            <h2 className="text-sm font-bold text-text-main">Developer & Integration Console</h2>
            <p className="text-[11px] text-text-secondary">System diagnostics, OpenAPI Swagger specs, and FHIR endpoint testing</p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <a
            href="http://localhost:8000/docs"
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-1 text-xs font-semibold text-teal-700 bg-teal-50 hover:bg-teal-100 border border-teal-200 px-2.5 py-1 rounded transition-colors"
          >
            <FileCode className="w-3.5 h-3.5" />
            <span>OpenAPI / Swagger Specs</span>
          </a>
          {onClose && (
            <button
              onClick={onClose}
              className="text-text-muted hover:text-text-main p-1 rounded hover:bg-app-secondary"
            >
              <X className="w-4 h-4" />
            </button>
          )}
        </div>
      </div>

      {/* Network Topology */}
      <InteroperabilityDashboard
        carestackStatus={carestackStatus}
        fhirOnline={backendOnline}
        onRefresh={onRefresh}
        syncing={false}
      />

      {/* Endpoint Interactive Tester */}
      <EndpointTester />
    </div>
  );
}
