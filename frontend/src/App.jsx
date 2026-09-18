import React, { useEffect, useState, useCallback } from 'react';
import { Activity, RefreshCcw, FileCode, CheckCircle2, ShieldAlert } from 'lucide-react';
import { Navbar } from './components/Navbar';
import { PatientHeader } from './components/PatientHeader';
import { ClinicalContext } from './components/ClinicalContext';
import { CareStackChart } from './components/CareStackChart';
import { CDSHookCard } from './components/CDSHookCard';
import { MedicalEHRViewer } from './components/MedicalEHRViewer';
import { EvidenceDrawer } from './components/EvidenceDrawer';
import { PatientTimeline } from './components/PatientTimeline';
import { DeveloperConsole } from './components/DeveloperConsole';
import { PatientRecordViewer } from './components/PatientRecordViewer';
import { api } from './services/api';

const DEMO_PATIENT_IDS = ['CS-2001', 'CS-2002', 'CS-1003'];

export function App() {
  const [activeTab, setActiveTab] = useState('chairside');
  const [backendOnline, setBackendOnline] = useState(false);
  const [carestackStatus, setCarestackStatus] = useState(null);
  const [patients, setPatients] = useState([]);
  const [selectedPatientId, setSelectedPatientId] = useState(null);
  const [cdsCards, setCdsCards] = useState([]);
  const [lastProcedure, setLastProcedure] = useState({ code: 'D7140', label: 'Extraction, Erupted Tooth' });
  const [alertsVersion, setAlertsVersion] = useState(0);
  const [webhookSyncing, setWebhookSyncing] = useState(false);
  const [webhookMessage, setWebhookMessage] = useState(null);
  const [selectedEvidenceCard, setSelectedEvidenceCard] = useState(null);
  const [showDeveloperConsole, setShowDeveloperConsole] = useState(false);

  const selectedPatient = patients.find((p) => p.id === selectedPatientId) || null;

  const loadStatusAndPatients = useCallback(async () => {
    try {
      const [health, status, all] = await Promise.all([
        api.getHealth().catch(() => null),
        api.getCareStackStatus().catch(() => null),
        api.getCareStackPatients().catch(() => []),
      ]);
      setBackendOnline(health?.status === 'healthy');
      setCarestackStatus(status);

      const demo = all.filter((p) => DEMO_PATIENT_IDS.includes(p.id));
      const ordered = DEMO_PATIENT_IDS.map((id) => demo.find((p) => p.id === id)).filter(Boolean);
      const list = ordered.length > 0 ? ordered : all;

      setPatients(list);
      setSelectedPatientId((prev) => prev || list[0]?.id || null);
    } catch (err) {
      console.error('Failed to load CareStack data', err);
      setBackendOnline(false);
    }
  }, []);

  useEffect(() => {
    loadStatusAndPatients();
  }, [loadStatusAndPatients]);

  // Pre-evaluate default procedure D7140 on initial patient load
  useEffect(() => {
    if (!selectedPatient) return;
    async function initialRiskEval() {
      try {
        const response = await api.evaluateOrderSelectHook(selectedPatient.mrn, 'D7140').catch(() => ({ cards: [] }));
        setCdsCards(response.cards || []);
      } catch (err) {
        console.error('Initial risk evaluation failed', err);
      }
    }
    initialRiskEval();
  }, [selectedPatientId, selectedPatient]);

  const handleSelectPatient = useCallback((id) => {
    setSelectedPatientId(id);
    setCdsCards([]);
    setLastProcedure({ code: 'D7140', label: 'Extraction, Erupted Tooth' });
    setSelectedEvidenceCard(null);
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
    <div className="min-h-screen bg-app-bg text-text-main flex flex-col font-sans">
      <Navbar
        backendOnline={backendOnline}
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        onSimulateWebhook={handleSimulateWebhookSync}
        webhookSyncing={webhookSyncing}
        selectedPatient={selectedPatient}
        onToggleDeveloperConsole={() => setShowDeveloperConsole((v) => !v)}
        showDeveloperConsole={showDeveloperConsole}
      />

      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-5">
        {/* Isolated Developer Console Container */}
        {showDeveloperConsole && (
          <div className="mb-5">
            <DeveloperConsole
              carestackStatus={carestackStatus}
              backendOnline={backendOnline}
              onRefresh={loadStatusAndPatients}
              onClose={() => setShowDeveloperConsole(false)}
            />
          </div>
        )}

        {/* Sync Feedback Message */}
        {webhookMessage && (
          <div
            className={`mb-4 p-3 rounded text-xs font-medium border flex items-center justify-between shadow-xs ${
              webhookMessage.type === 'success'
                ? 'bg-success-light text-success-dark border-success/30'
                : 'bg-danger-light text-danger-dark border-danger/30'
            }`}
          >
            <span className="flex items-center gap-1.5">
              <CheckCircle2 className="w-4 h-4 text-success shrink-0" />
              <span>{webhookMessage.text}</span>
            </span>
            <button onClick={() => setWebhookMessage(null)} className="text-text-muted hover:text-text-main font-bold text-sm ml-4">
              ×
            </button>
          </div>
        )}

        {/* Patient Demographic Banner */}
        <PatientHeader
          patients={patients}
          selectedPatient={selectedPatient}
          onSelectPatient={handleSelectPatient}
          activeProcedure={lastProcedure}
        />

        {/* Doctor View 1: Patient Workspace */}
        {activeTab === 'chairside' && (
          <div className="space-y-4">
            {/* Relevant Medical Context Component */}
            <ClinicalContext patient={selectedPatient} />

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-5 items-start">
              {/* Left: Dental Procedure Toolbar */}
              <div>
                <div className="flex items-center justify-between mb-2">
                  <h2 className="text-xs font-bold uppercase tracking-wider text-text-secondary">
                    Procedure Selection Toolbar
                  </h2>
                  <span className="text-[11px] text-text-muted">Triggers Order-Select Decision Engine</span>
                </div>
                <CareStackChart
                  patients={patients}
                  selectedPatient={selectedPatient}
                  onSelectPatient={handleSelectPatient}
                  onCardsUpdate={handleCardsUpdate}
                  alertsVersion={alertsVersion}
                />
              </div>

              {/* Right: Clinical Review Cards */}
              <div>
                <div className="flex items-center justify-between mb-2">
                  <h2 className="text-xs font-bold uppercase tracking-wider text-text-secondary flex items-center gap-1">
                    <span>Clinical Review & Safety Alerts</span>
                    {lastProcedure && (
                      <span className="normal-case font-normal text-teal-700">
                        — CDT <code className="font-mono font-bold bg-teal-50 px-1 py-0.5 rounded border border-teal-200">{lastProcedure.code}</code>
                      </span>
                    )}
                  </h2>
                  <span className="text-[10px] font-bold text-teal-700 bg-teal-50 px-2 py-0.5 rounded border border-teal-200">
                    Real-Time Safety Engine
                  </span>
                </div>

                {cdsCards.length > 0 ? (
                  <div>
                    {cdsCards.map((card, idx) => (
                      <CDSHookCard
                        key={card.uuid || idx}
                        card={card}
                        onAppendAlert={handleAppendAlert}
                        onRequestConsult={handleRequestConsult}
                        onViewEvidence={(c) => setSelectedEvidenceCard(c)}
                      />
                    ))}
                  </div>
                ) : (
                  <div className="p-3.5 bg-success-light border border-success/30 rounded text-xs text-success-dark flex items-center gap-2">
                    <CheckCircle2 className="w-4 h-4 text-success shrink-0" />
                    <span>
                      No contraindications detected for procedure CDT {lastProcedure?.code || 'D7140'}.
                    </span>
                  </div>
                )}
              </div>
            </div>
          </div>
        )}

        {/* Doctor View 2: Clinical Risk Reviews */}
        {activeTab === 'reconciliation' && (
          <div>
            <PatientRecordViewer patients={patients} onSyncSuccess={loadStatusAndPatients} />
          </div>
        )}

        {/* Doctor View 3: Patient History & EHR */}
        {activeTab === 'history' && (
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 items-start">
            <div className="lg:col-span-5">
              <PatientTimeline patient={selectedPatient} alertsCount={cdsCards.length} />
            </div>
            <div className="lg:col-span-7">
              <MedicalEHRViewer patient={selectedPatient} />
            </div>
          </div>
        )}
      </main>

      {/* Slide-out Evidence Drawer */}
      {selectedEvidenceCard && (
        <EvidenceDrawer
          card={selectedEvidenceCard}
          procedure={lastProcedure}
          patient={selectedPatient}
          onClose={() => setSelectedEvidenceCard(null)}
        />
      )}

      {/* Footer */}
      <footer className="bg-app-surface border-t border-app-border py-4 mt-8 text-center text-xs text-text-secondary">
        <div className="max-w-7xl mx-auto px-4 flex flex-col sm:flex-row items-center justify-between gap-2">
          <p className="font-medium text-text-main">
            CareStack MDIN — Medical-Dental Interoperability Node
          </p>
          <p className="text-[11px] text-text-muted">
            CareStack Practice Integration · DSOLVE 2026
          </p>
        </div>
      </footer>
    </div>
  );
}

export default App;



