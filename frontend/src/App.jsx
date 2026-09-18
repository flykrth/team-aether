import React, { useEffect, useState, useCallback, useMemo } from 'react';
import { Activity, RefreshCcw, FileCode, CheckCircle2, ShieldAlert, TrendingUp, Sparkles, FileSpreadsheet } from 'lucide-react';
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
import { FinancialOptimizationModal } from './components/FinancialOptimizationModal';
import { api } from './services/api';

const DEMO_PATIENT_IDS = ['CS-2001', 'CS-2002', 'CS-1003'];

export function App() {
  const [activeTab, setActiveTab] = useState('chairside');
  const [backendOnline, setBackendOnline] = useState(false);
  const [carestackStatus, setCarestackStatus] = useState(null);
  const [patients, setPatients] = useState([]);
  const [selectedPatientId, setSelectedPatientId] = useState(null);
  const [cdsCards, setCdsCards] = useState([]);
  const [billingOpportunity, setBillingOpportunity] = useState(null);
  const [activeFilter, setActiveFilter] = useState('all'); // 'all' | 'safety' | 'billing'
  const [documentsCount, setDocumentsCount] = useState(0);
  const [isFinancialModalOpen, setIsFinancialModalOpen] = useState(false);
  const [lastProcedure, setLastProcedure] = useState({ code: 'D7140', label: 'Extraction, Erupted Tooth' });
  const [alertsVersion, setAlertsVersion] = useState(0);
  const [webhookSyncing, setWebhookSyncing] = useState(false);
  const [webhookMessage, setWebhookMessage] = useState(null);
  const [claimToast, setClaimToast] = useState(null);
  const [selectedEvidenceCard, setSelectedEvidenceCard] = useState(null);
  const [showDeveloperConsole, setShowDeveloperConsole] = useState(false);

  const selectedPatient = patients.find((p) => p.id === selectedPatientId) || null;

  const loadDocuments = useCallback(async (patientId) => {
    if (!patientId) return;
    try {
      const res = await api.getCareStackDocuments(patientId).catch(() => []);
      const count = Array.isArray(res) ? res.length : (res?.documents?.length || res?.document_count || 0);
      setDocumentsCount(count);
    } catch (err) {
      console.error('Failed to load patient documents:', err);
    }
  }, []);

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

  // Load CareStack documents count when patient changes
  useEffect(() => {
    if (selectedPatient) {
      loadDocuments(selectedPatient.id);
    }
  }, [selectedPatient, loadDocuments]);

  // Pre-evaluate default procedure D7140 (and D4341 for CS-1003) on initial patient load
  useEffect(() => {
    if (!selectedPatient) return;
    let cancelled = false;
    async function initialRiskEval() {
      try {
        const procCode = lastProcedure?.code || 'D7140';
        const [response, billingRes] = await Promise.all([
          api.evaluateOrderSelectHook(selectedPatient.mrn, procCode).catch(() => ({ cards: [] })),
          api.evaluateBillingClaim(selectedPatient.id || selectedPatient.mrn, procCode).catch(() => null),
        ]);
        if (!cancelled) {
          setCdsCards(response.cards || []);
          setBillingOpportunity(billingRes);
        }
      } catch (err) {
        console.error('Initial risk evaluation failed', err);
      }
    }
    initialRiskEval();
    return () => {
      cancelled = true;
    };
  }, [selectedPatientId, selectedPatient]);

  const handleSelectPatient = useCallback((id) => {
    setSelectedPatientId(id);
    setCdsCards([]);
    setBillingOpportunity(null);
    setLastProcedure({ code: 'D7140', label: 'Extraction, Erupted Tooth' });
    setSelectedEvidenceCard(null);
    setIsFinancialModalOpen(false);
  }, []);

  const handleCardsUpdate = useCallback((cards, proc, billingRes) => {
    setCdsCards(cards);
    setLastProcedure(proc);
    setBillingOpportunity(billingRes);
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
      loadDocuments(selectedPatient.id);
    } catch (err) {
      setWebhookMessage({ type: 'error', text: `Webhook sync failed: ${err.message}` });
    } finally {
      setWebhookSyncing(false);
    }
  };

  // Synthesize Card Type B: Administrative Opportunity Card if eligible
  const administrativeCard = useMemo(() => {
    if (!billingOpportunity || !billingOpportunity.is_eligible) return null;
    return {
      cardType: 'administrative',
      indicator: 'opportunity',
      uuid: `admin-crosswalk-${lastProcedure?.code || 'proc'}-${selectedPatient?.id}`,
      header: 'Medical Cross-Coding Opportunity Identified',
      summary: billingOpportunity.estimated_coverage
        ? `Est. Medical Coverage: $${billingOpportunity.estimated_coverage.toFixed(2)}`
        : 'Est. Medical Coverage: $400 - $800',
      detail:
        billingOpportunity.narrative_justification ||
        'Dental procedure qualifies for primary medical insurance cross-coding under medical necessity guidelines.',
      cdt_code: billingOpportunity.cdt_code || lastProcedure?.code || 'D4341',
      cpt_code: billingOpportunity.suggested_cpt || '41874',
      icd10_codes: billingOpportunity.justifying_icd10 || ['E11.9'],
      icd10: billingOpportunity.justifying_icd10?.[0] || 'E11.9',
      opportunity: billingOpportunity,
      source: {
        label: 'CareStack Administrative Cross-Coding Engine',
      },
    };
  }, [billingOpportunity, lastProcedure, selectedPatient]);

  // Combined and filtered CDS cards list
  const filteredCards = useMemo(() => {
    const clinical = cdsCards || [];
    const admin = administrativeCard ? [administrativeCard] : [];
    if (activeFilter === 'safety') return clinical;
    if (activeFilter === 'billing') return admin;
    // 'all': Clinical safety cards first, followed by administrative opportunity cards stacked cleanly
    return [...clinical, ...admin];
  }, [cdsCards, administrativeCard, activeFilter]);

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

        {/* Claim Submission Success Toast */}
        {claimToast && (
          <div className="mb-4 p-3 rounded text-xs font-semibold border bg-emerald-50 text-emerald-900 border-emerald-300 flex items-center justify-between shadow-xs animate-fade-in">
            <div className="flex items-center gap-2">
              <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
              <span>{claimToast}</span>
            </div>
            <button onClick={() => setClaimToast(null)} className="text-emerald-700 hover:text-emerald-950 font-bold text-sm ml-4">
              ×
            </button>
          </div>
        )}

        {/* Patient Demographic Banner with CareStack Documents Counter */}
        <PatientHeader
          patients={patients}
          selectedPatient={selectedPatient}
          onSelectPatient={handleSelectPatient}
          activeProcedure={lastProcedure}
          documentsCount={documentsCount}
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
                  documentsCount={documentsCount}
                />
              </div>

              {/* Right: Clinical Review Cards & Financial Optimization */}
              <div>
                <div className="flex items-center justify-between mb-2">
                  <h2 className="text-xs font-bold uppercase tracking-wider text-text-secondary flex items-center gap-1">
                    <span>Clinical Review &amp; Optimization Alerts</span>
                    {lastProcedure && (
                      <span className="normal-case font-normal text-teal-700">
                        — CDT <code className="font-mono font-bold bg-teal-50 px-1 py-0.5 rounded border border-teal-200">{lastProcedure.code}</code>
                      </span>
                    )}
                  </h2>
                  <span className="text-[10px] font-bold text-teal-700 bg-teal-50 px-2 py-0.5 rounded border border-teal-200">
                    MDIN Multi-Card Engine
                  </span>
                </div>

                {/* Quick-Filter Tabs */}
                <div className="flex items-center gap-1.5 mb-3 p-1 bg-app-secondary/60 rounded-lg border border-app-border text-xs">
                  <button
                    onClick={() => setActiveFilter('all')}
                    className={`flex-1 flex items-center justify-center gap-1.5 py-1.5 px-2 rounded-md font-semibold transition-all cursor-pointer ${
                      activeFilter === 'all'
                        ? 'bg-app-surface text-text-main shadow-xs border border-app-border font-bold'
                        : 'text-text-secondary hover:text-text-main'
                    }`}
                  >
                    <span>All Alerts</span>
                    <span className="text-[10px] px-1.5 py-0.2 rounded-full bg-teal-100 text-teal-800 font-mono font-bold">
                      {cdsCards.length + (billingOpportunity?.is_eligible ? 1 : 0)}
                    </span>
                  </button>
                  <button
                    onClick={() => setActiveFilter('safety')}
                    className={`flex-1 flex items-center justify-center gap-1.5 py-1.5 px-2 rounded-md font-semibold transition-all cursor-pointer ${
                      activeFilter === 'safety'
                        ? 'bg-app-surface text-danger-dark shadow-xs border border-app-border font-bold'
                        : 'text-text-secondary hover:text-text-main'
                    }`}
                  >
                    <span>Clinical Safety</span>
                    <span className="text-[10px] px-1.5 py-0.2 rounded-full bg-danger-light text-danger-dark font-mono font-bold">
                      {cdsCards.length}
                    </span>
                  </button>
                  <button
                    onClick={() => setActiveFilter('billing')}
                    className={`flex-1 flex items-center justify-center gap-1.5 py-1.5 px-2 rounded-md font-semibold transition-all cursor-pointer ${
                      activeFilter === 'billing'
                        ? 'bg-app-surface text-emerald-800 shadow-xs border border-app-border font-bold'
                        : 'text-text-secondary hover:text-text-main'
                    }`}
                  >
                    <span>Billing &amp; Revenue</span>
                    <span className="text-[10px] px-1.5 py-0.2 rounded-full bg-emerald-100 text-emerald-800 font-mono font-bold">
                      {billingOpportunity?.is_eligible ? 1 : 0}
                    </span>
                  </button>
                </div>

                {/* Stact of CDS Cards */}
                {filteredCards.length > 0 ? (
                  <div>
                    {filteredCards.map((card, idx) => (
                      <CDSHookCard
                        key={card.uuid || idx}
                        card={card}
                        onAppendAlert={handleAppendAlert}
                        onRequestConsult={handleRequestConsult}
                        onViewEvidence={(c) => setSelectedEvidenceCard(c)}
                        onOpenFinancialDashboard={() => setIsFinancialModalOpen(true)}
                      />
                    ))}
                  </div>
                ) : (
                  <div className="p-3.5 bg-success-light border border-success/30 rounded text-xs text-success-dark flex items-center gap-2">
                    <CheckCircle2 className="w-4 h-4 text-success shrink-0" />
                    <span>
                      {activeFilter === 'safety'
                        ? `No clinical safety contraindications detected for CDT ${lastProcedure?.code || 'D7140'}.`
                        : activeFilter === 'billing'
                        ? `No primary medical billing cross-coding opportunities for CDT ${lastProcedure?.code || 'D7140'}.`
                        : `No clinical alerts or cross-coding opportunities detected for CDT ${lastProcedure?.code || 'D7140'}.`}
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

      {/* Financial Optimization & CMS-1500 Modal Overlay */}
      {isFinancialModalOpen && (
        <FinancialOptimizationModal
          isOpen={isFinancialModalOpen}
          onClose={() => setIsFinancialModalOpen(false)}
          opportunity={billingOpportunity}
          patient={selectedPatient}
          procedure={lastProcedure}
          onDocumentSynced={() => {
            if (selectedPatient) loadDocuments(selectedPatient.id);
            setClaimToast('Letter of Medical Necessity & CMS-1500 Claim successfully synced to CareStack Documents API.');
          }}
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



