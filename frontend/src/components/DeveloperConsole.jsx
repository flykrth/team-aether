import React from 'react';
import { Terminal, FileCode, Network, Server, X } from 'lucide-react';
import { EndpointTester } from './EndpointTester';
import { InteroperabilityDashboard } from './InteroperabilityDashboard';

export function DeveloperConsole({ carestackStatus, backendOnline, onRefresh, onClose }) {
  return (
    <div className="card p-8 space-y-8 animate-fade-in">
      {/* Console Header */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-4">
          <span className="inline-flex items-center justify-center w-12 h-12 rounded-full bg-ink text-white shrink-0">
            <Terminal className="w-5 h-5" strokeWidth={1.5} />
          </span>
          <div>
            <h2 className="display-lg text-ink">Developer &amp; Integration Console</h2>
            <p className="mt-1 text-sm text-text-muted">System diagnostics, OpenAPI Swagger specs, and FHIR endpoint testing</p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <a
            href="http://localhost:8000/docs"
            target="_blank"
            rel="noreferrer"
            className="btn-ghost"
          >
            <FileCode className="w-4 h-4" strokeWidth={1.5} />
            <span>OpenAPI / Swagger Specs</span>
          </a>
          {onClose && (
            <button onClick={onClose} className="icon-btn" aria-label="Close developer console">
              <X className="w-[18px] h-[18px]" strokeWidth={1.5} />
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
