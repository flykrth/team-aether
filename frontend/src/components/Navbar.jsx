import React from 'react';
import { Activity, ShieldCheck, Database, FileCode } from 'lucide-react';

export function Navbar({ backendOnline, activeTab, setActiveTab }) {
  return (
    <header className="bg-white border-b border-slate-200 sticky top-0 z-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between h-16 items-center">
          <div className="flex items-center space-x-3">
            <div className="h-10 w-10 rounded-xl bg-gradient-to-tr from-sky-600 to-teal-500 flex items-center justify-center text-white shadow-md">
              <Activity className="h-6 w-6" />
            </div>
            <div>
              <div className="flex items-center space-x-2">
                <span className="font-bold text-lg text-slate-900 tracking-tight">MDIN</span>
                <span className="px-2 py-0.5 text-xs font-semibold rounded-full bg-sky-100 text-sky-800">
                  CareStack D-Solve
                </span>
              </div>
              <p className="text-xs text-slate-500">Medical-Dental Interoperability Node</p>
            </div>
          </div>

          <div className="flex items-center space-x-4">
            <nav className="flex space-x-1 bg-slate-100 p-1 rounded-lg">
              <button
                onClick={() => setActiveTab('viewer')}
                className={`px-3 py-1.5 text-xs font-medium rounded-md transition-colors ${
                  activeTab === 'viewer'
                    ? 'bg-white text-slate-900 shadow-sm'
                    : 'text-slate-600 hover:text-slate-900'
                }`}
              >
                Clinical Interoperability
              </button>
              <button
                onClick={() => setActiveTab('tester')}
                className={`px-3 py-1.5 text-xs font-medium rounded-md transition-colors ${
                  activeTab === 'tester'
                    ? 'bg-white text-slate-900 shadow-sm'
                    : 'text-slate-600 hover:text-slate-900'
                }`}
              >
                API & CDS Hook Tester
              </button>
            </nav>

            <div className="flex items-center space-x-2 pl-2 border-l border-slate-200 text-xs">
              <span
                className={`h-2.5 w-2.5 rounded-full ${
                  backendOnline ? 'bg-emerald-500 animate-pulse' : 'bg-rose-500'
                }`}
              />
              <span className="text-slate-600 font-medium">
                {backendOnline ? 'Backend 8000: Live' : 'Backend: Disconnected'}
              </span>
            </div>

            <a
              href="http://localhost:8000/docs"
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center space-x-1 text-xs font-medium text-sky-600 hover:text-sky-800 bg-sky-50 px-2.5 py-1.5 rounded-md hover:bg-sky-100 transition-colors"
            >
              <FileCode className="h-3.5 w-3.5" />
              <span>Swagger Docs</span>
            </a>
          </div>
        </div>
      </div>
    </header>
  );
}
