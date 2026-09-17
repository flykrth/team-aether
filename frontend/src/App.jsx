import React, { useEffect, useState, useCallback } from 'react';
import { Activity, RefreshCcw, FileCode, CheckCircle2 } from 'lucide-react';
import { CareStackChart } from './components/CareStackChart';
import { CDSHookCard } from './components/CDSHookCard';
import { MedicalEHRViewer } from './components/MedicalEHRViewer';
import { api } from './services/api';

const DEMO_PATIENT_IDS = ['CS-2001', 'CS-2002', 'CS-1003'];

export function App() {
  const [backendOnline, setBackendOnline] = useState(false);
  const [patients, setPatients] = useState([]);
  const [selectedPatientId, setSelectedPatientId] = useState(null);
  const [cdsCards, setCdsCards] = useState([]);
  const [lastProcedure, setLastProcedure] = useState(null);
  const [alertsVersion, setAlertsVersion] = useState(0);
  const [webhookSyncing, setWebhookSyncing] = useState(false);
  const [webhookMessage, setWebhookMessage] = useState(null);

  const selectedPatient = patients.find((p) => p.id === selectedPatientId) || null;

  useEffect(() => {
    async function loadPatients() {
      try {
        const [health, all] = await Promise.all([
          api.getHealth().catch(() => null),
          api.getCareStackPatients().catch(() => []),
        ]);
        setBackendOnline(health?.status === 'healthy');

        const demo = all.filter((p) => DEMO_PATIENT_IDS.includes(p.id));
        const ordered = DEMO_PATIENT_IDS.map((id) => demo.find((p) => p.id === id)).filter(Boolean);
        const list = ordered.length > 0 ? ordered : all;

        setPatients(list);
        setSelectedPatientId((prev) => prev || list[0]?.id || null);
      } catch (err) {
        console.error('Failed to load CareStack patients', err);
        setBackendOnline(false);
      }
    }
    loadPatients();
  }, []);

  const handleSelectPatient = useCallback((id) => {
    setSelectedPatientId(id);
    setCdsCards([]);
    setLastProcedure(null);
  }, []);

  const handleCardsUpdate = useCallback((cards, proc) => {
    setCdsCards(cards);
    setLastProcedure(proc);
  }, []);

  const handleAppendAlert = useCallback(
    async (card) => {
      if (!selectedPatient) return;
      await api.postMedicalAlert(selectedPatient.id, {
        alert_type: card.indicator,
        category: 'coagulation',
        title: card.summary,
        details: card.detail || card.summary,
        source: card.source?.label || 'MDIN CDS Hooks Engine',
        action_required: card.suggestions?.[0]?.label || null,
      });
      setAlertsVersion((v) => v + 1);
    },
    [selectedPatient]
  );

  const handleRequestConsult = useCallback(
    async (card) => {
      if (!selectedPatient) return;
      await api.postMedicalAlert(selectedPatient.id, {
        alert_type: 'warning',
        category: 'coagulation',
        title: `Pre-Op Coagulation Consult Requested (INR) — re: ${card.summary}`,
        details:
          'Chairside request for pre-operative INR / coagulation panel prior to invasive dental procedure. ' +
          'Awaiting physician sign-off before proceeding.',
        source: 'CareStack Chairside Consult Request',
        action_required: 'Obtain INR within 24-48 hours prior to procedure.',
      });
      setAlertsVersion((v) => v + 1);
    },
    [selectedPatient]
  );

  const handleSimulateWebhookSync = async () => {
    if (!selectedPatient) return;
    setWebhookSyncing(true);
    setWebhookMessage(null);
    try {
      const res = await api.simulateWebhookCheckin(selectedPatient);
      setWebhookMessage({
        type: res.status === 'synchronized' ? 'success' : 'error',
        text: res.message,
      });
      setAlertsVersion((v) => v + 1);
    } catch (err) {
      setWebhookMessage({ type: 'error', text: `Webhook sync failed: ${err.message}` });
    } finally {
      setWebhookSyncing(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col font-sans">
      <header className="bg-white border-b border-slate-200 sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 h-auto sm:h-16 py-3 sm:py-0">
            <div className="flex items-center gap-3">
              <div className="h-10 w-10 rounded-xl bg-gradient-to-tr from-sky-600 to-teal-500 flex items-center justify-center text-white shadow-md shrink-0">
                <Activity className="h-6 w-6" />
              </div>
              <div>
                <h1 className="font-bold text-base sm:text-lg text-slate-900 tracking-tight leading-tight">
                  CareStack MDIN — Medical-Dental Interoperability Node
                </h1>
                <p className="text-xs text-slate-500">CDS Hooks Sub-second Engine</p>
              </div>
            </div>

            <div className="flex items-center gap-3">
              <div className="flex items-center gap-2 text-xs">
                <span className={`h-2.5 w-2.5 rounded-full ${backendOnline ? 'bg-emerald-500 animate-pulse' : 'bg-rose-500'}`} />
                <span className="text-slate-600 font-medium">{backendOnline ? 'Backend Live' : 'Disconnected'}</span>
              </div>
              <button
                onClick={handleSimulateWebhookSync}
                disabled={webhookSyncing || !selectedPatient}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold text-white bg-slate-900 hover:bg-slate-700 rounded-lg shadow-sm transition-colors disabled:opacity-50"
              >
                <RefreshCcw className={`w-3.5 h-3.5 ${webhookSyncing ? 'animate-spin' : ''}`} />
                {webhookSyncing ? 'Syncing…' : 'Simulate Webhook Sync'}
              </button>
              <a
                href="http://localhost:8000/docs"
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center gap-1 text-xs font-medium text-sky-600 hover:text-sky-800 bg-sky-50 px-2.5 py-1.5 rounded-md hover:bg-sky-100 transition-colors"
              >
                <FileCode className="h-3.5 w-3.5" />
                <span className="hidden sm:inline">Swagger Docs</span>
              </a>
            </div>
          </div>
        </div>
      </header>

      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-6">
        {webhookMessage && (
          <div
            className={`mb-4 p-3 rounded-lg text-xs font-medium border flex items-center justify-between ${
              webhookMessage.type === 'success'
                ? 'bg-emerald-50 text-emerald-800 border-emerald-200'
                : 'bg-rose-50 text-rose-800 border-rose-200'
            }`}
          >
            <span>{webhookMessage.text}</span>
            <button onClick={() => setWebhookMessage(null)} className="text-slate-400 hover:text-slate-600 ml-4">
              ×
            </button>
          </div>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 items-start">
          {/* Left Column: CareStack Dental Chart */}
          <div>
            <h2 className="text-xs font-bold uppercase tracking-wider text-slate-500 mb-2">
              CareStack Dental Chart
            </h2>
            <CareStackChart
              patients={patients}
              selectedPatient={selectedPatient}
              onSelectPatient={handleSelectPatient}
              onCardsUpdate={handleCardsUpdate}
              alertsVersion={alertsVersion}
            />
          </div>

          {/* Right Column: Live CDS Decision Overlay & EHR Interoperability Trace */}
          <div className="space-y-6">
            <div>
              <h2 className="text-xs font-bold uppercase tracking-wider text-slate-500 mb-2">
                Live CDS Decision Overlay
                {lastProcedure && (
                  <span className="ml-2 normal-case font-normal text-slate-400">
                    — evaluated for <span className="font-mono">{lastProcedure.code}</span>
                  </span>
                )}
              </h2>
              {cdsCards.length > 0 ? (
                <div>
                  {cdsCards.map((card, idx) => (
                    <CDSHookCard
                      key={card.uuid || idx}
                      card={card}
                      onAppendAlert={handleAppendAlert}
                      onRequestConsult={handleRequestConsult}
                    />
                  ))}
                </div>
              ) : (
                <div className="p-4 bg-emerald-50 border border-emerald-200 rounded-xl text-xs text-emerald-800 flex items-center gap-2">
                  <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                  <span>
                    {lastProcedure
                      ? 'No contraindications detected for the selected procedure.'
                      : 'Select a CDT procedure on the chart to run the order-select CDS Hook.'}
                  </span>
                </div>
              )}
            </div>

            <div>
              <h2 className="text-xs font-bold uppercase tracking-wider text-slate-500 mb-2">
                EHR Interoperability Trace
              </h2>
              <MedicalEHRViewer patient={selectedPatient} />
            </div>
          </div>
        </div>
      </main>

      <footer className="bg-white border-t border-slate-200 py-6 mt-12 text-center text-xs text-slate-500">
        <div className="max-w-7xl mx-auto px-4">
          <p className="font-medium text-slate-700">
            Medical-Dental Interoperability Node (MDIN) — CareStack D-Solve Hackathon 2026
          </p>
          <p className="mt-1 text-slate-400">
            DRISHTI · College of Engineering Trivandrum (CET) · Problem 6: Open Problem Statement — Dental Industry
          </p>
        </div>
      </footer>
    </div>
  );
}

export default App;
