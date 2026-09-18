import React from 'react';
import { ShieldCheck, Stethoscope, RefreshCcw, Clock, Terminal, Bot, Sparkles, UserPlus } from 'lucide-react';

const TABS = [
  { id: 'chairside', label: 'Patient Workspace', Icon: Stethoscope },
  { id: 'reconciliation', label: 'Clinical Risk Reviews', Icon: ShieldCheck },
  { id: 'history', label: 'Patient History & EHR', Icon: Clock },
  { id: 'agents', label: 'Agent Live Ops', Icon: Bot },
  { id: 'chat', label: 'MAO Assistant', Icon: Sparkles },
];

export function Navbar({ backendOnline, activeTab, setActiveTab, onSimulateWebhook, webhookSyncing, selectedPatient, onToggleDeveloperConsole, showDeveloperConsole, onOpenRecords }) {
  return (
    <header className="sticky top-0 z-40 bg-app-bg/80 backdrop-blur-xl">
      <div className="max-w-[1440px] mx-auto px-4 sm:px-6 lg:px-10">
        <div className="flex items-center gap-6 h-20">
          {/* Wordmark */}
          <div className="flex items-baseline gap-3 shrink-0">
            <span className="font-display text-[28px] font-medium tracking-tight text-ink leading-none">
              MDIN<span className="text-accent">.</span>
            </span>
            <span className="hidden xl:inline text-xs text-text-muted leading-none">
              CareStack Clinical Node
            </span>
          </div>

          {/* Pill navigation */}
          <nav className="flex-1 min-w-0 overflow-x-auto scrollbar-none">
            <div className="flex items-center gap-2 w-max mx-auto px-1">
            {TABS.map(({ id, label, Icon }) => (
              <button
                key={id}
                onClick={() => setActiveTab(id)}
                className={`pill shrink-0 whitespace-nowrap ${activeTab === id ? 'pill-active' : ''}`}
              >
                <Icon className="w-4 h-4" strokeWidth={1.5} />
                <span>{label}</span>
              </button>
            ))}
            </div>
          </nav>

          {/* Status + actions */}
          <div className="flex items-center gap-2 shrink-0">
            <span className="hidden 2xl:inline-flex chip bg-app-surface">
              <span className="w-1.5 h-1.5 rounded-full bg-accent" />
              Main Practice · Operatory 3
            </span>

            <span className="hidden md:inline-flex chip bg-app-surface text-text-main">
              <span
                className={`w-1.5 h-1.5 rounded-full ${backendOnline ? 'bg-success animate-pulse' : 'bg-danger'}`}
              />
              {backendOnline ? 'Medical EHR Connected' : 'EHR Disconnected'}
            </span>

            {onOpenRecords && (
              <button onClick={onOpenRecords} className="btn-dark" title="Add a patient, medical history or previous records">
                <UserPlus className="w-4 h-4" strokeWidth={1.5} />
                <span className="hidden lg:inline">Patient records</span>
              </button>
            )}

            {onSimulateWebhook && (
              <button
                onClick={onSimulateWebhook}
                disabled={webhookSyncing || !selectedPatient}
                className="btn-primary hidden sm:inline-flex"
              >
                <RefreshCcw className={`w-4 h-4 ${webhookSyncing ? 'animate-spin' : ''}`} strokeWidth={1.5} />
                <span>{webhookSyncing ? 'Syncing...' : 'Simulate EHR Sync'}</span>
              </button>
            )}

            <button
              onClick={onToggleDeveloperConsole}
              className={showDeveloperConsole ? 'icon-btn bg-ink text-white hover:bg-ink-soft' : 'icon-btn-white'}
              title="Developer & API Testing Tools"
              aria-label="Developer Tools"
            >
              <Terminal className="w-[18px] h-[18px]" strokeWidth={1.5} />
            </button>
          </div>
        </div>
      </div>
    </header>
  );
}
