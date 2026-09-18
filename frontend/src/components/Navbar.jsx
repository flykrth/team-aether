import React from 'react';
import { Activity, ShieldCheck, Database, Stethoscope, RefreshCcw, Network, Clock, Terminal, User } from 'lucide-react';

export function Navbar({ backendOnline, activeTab, setActiveTab, onSimulateWebhook, webhookSyncing, selectedPatient, onToggleDeveloperConsole, showDeveloperConsole }) {
  return (
    <header className="bg-app-surface border-b border-app-border sticky top-0 z-40 shadow-xs">
      {/* Top Header Bar */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-14">
          {/* Brand Identity */}
          <div className="flex items-center space-x-3">
            <div className="h-8 w-8 rounded bg-teal-500 flex items-center justify-center text-white shadow-xs shrink-0 font-bold">
              <Activity className="h-5 w-5" />
            </div>
            <div>
              <div className="flex items-center space-x-2">
                <span className="font-bold text-sm text-text-main tracking-tight">CareStack MDIN</span>
                <span className="px-2 py-0.5 text-[10px] font-bold rounded bg-teal-50 text-teal-700 border border-teal-200 uppercase">
                  Clinical Node
                </span>
              </div>
              <p className="text-[10px] text-text-secondary">Medical-Dental Interoperability Node · Practice Integration</p>
            </div>
          </div>

          {/* Right Status Controls */}
          <div className="flex items-center space-x-3">
            {/* Live Practice Location Context */}
            <div className="hidden lg:flex items-center gap-1.5 text-xs text-text-secondary bg-app-bg px-2.5 py-1 rounded border border-app-border">
              <span className="w-2 h-2 rounded-full bg-teal-500"></span>
              <span className="font-medium text-text-main">Main Practice · Operatory 3</span>
            </div>

            {/* Live EHR Connection Status */}
            <div className="flex items-center space-x-1.5 px-2.5 py-1 rounded bg-app-bg border border-app-border text-xs">
              <span
                className={`h-2 w-2 rounded-full ${
                  backendOnline ? 'bg-success animate-pulse' : 'bg-danger'
                }`}
              />
              <span className="text-text-main font-medium text-[11px]">
                {backendOnline ? 'Medical EHR Connected' : 'EHR Disconnected'}
              </span>
            </div>

            {/* Simulate EHR Sync Button */}
            {onSimulateWebhook && (
              <button
                onClick={onSimulateWebhook}
                disabled={webhookSyncing || !selectedPatient}
                className="hidden sm:inline-flex items-center gap-1.5 px-2.5 py-1 text-xs font-semibold text-white bg-teal-500 hover:bg-teal-700 rounded transition-colors disabled:opacity-50 shadow-xs"
              >
                <RefreshCcw className={`w-3 h-3 ${webhookSyncing ? 'animate-spin' : ''}`} />
                <span>{webhookSyncing ? 'Syncing...' : 'Simulate EHR Sync'}</span>
              </button>
            )}

            {/* Discrete Developer Console Toggle */}
            <button
              onClick={onToggleDeveloperConsole}
              className={`inline-flex items-center gap-1 px-2.5 py-1 rounded text-xs font-semibold border transition-colors ${
                showDeveloperConsole
                  ? 'bg-text-main text-white border-text-main shadow-xs'
                  : 'bg-app-bg text-text-secondary border-app-border hover:bg-app-secondary'
              }`}
              title="Developer & API Testing Tools"
            >
              <Terminal className="w-3.5 h-3.5 text-teal-500" />
              <span className="hidden sm:inline">Developer Tools</span>
            </button>
          </div>
        </div>

        {/* Doctor-Facing Clinical Navigation Sub-Bar */}
        <div className="flex items-center space-x-1 border-t border-app-border/60 py-1.5 overflow-x-auto scrollbar-none">
          <button
            onClick={() => setActiveTab('chairside')}
            className={`px-3 py-1 text-xs font-semibold rounded transition-colors flex items-center gap-1.5 whitespace-nowrap ${
              activeTab === 'chairside'
                ? 'bg-teal-500 text-white shadow-xs'
                : 'text-text-secondary hover:text-text-main hover:bg-app-secondary'
            }`}
          >
            <Stethoscope className="w-3.5 h-3.5" />
            <span>Patient Workspace</span>
          </button>

          <button
            onClick={() => setActiveTab('reconciliation')}
            className={`px-3 py-1 text-xs font-semibold rounded transition-colors flex items-center gap-1.5 whitespace-nowrap ${
              activeTab === 'reconciliation'
                ? 'bg-teal-500 text-white shadow-xs'
                : 'text-text-secondary hover:text-text-main hover:bg-app-secondary'
            }`}
          >
            <ShieldCheck className="w-3.5 h-3.5" />
            <span>Clinical Risk Reviews</span>
          </button>

          <button
            onClick={() => setActiveTab('history')}
            className={`px-3 py-1 text-xs font-semibold rounded transition-colors flex items-center gap-1.5 whitespace-nowrap ${
              activeTab === 'history'
                ? 'bg-teal-500 text-white shadow-xs'
                : 'text-text-secondary hover:text-text-main hover:bg-app-secondary'
            }`}
          >
            <Clock className="w-3.5 h-3.5" />
            <span>Patient History & EHR</span>
          </button>
        </div>
      </div>
    </header>
  );
}


