import React, { useEffect, useState, useCallback, useMemo } from 'react';
import { Activity, RefreshCcw, FileCode, CheckCircle2, ShieldAlert, TrendingUp, Sparkles, FileSpreadsheet, Hospital, Stethoscope } from 'lucide-react';
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
import { PhysicianClearancePortal } from './components/PhysicianClearancePortal';
import { AgentOpsDashboard } from './components/AgentOpsDashboard';
import { AssistantPanel } from './components/AssistantPanel';
import { AssistantWorkspace } from './components/assistant/AssistantWorkspace';
import { PatientIntakePanel } from './components/records/PatientIntakePanel';
import { api } from './services/api';

const DEMO_PATIENT_IDS = ['CS-2001', 'CS-2002', 'CS-1003'];
// Seeded personas that belong to other demos (Agent Live Ops, MRONJ). Anything else was added at runtime
// through the records panel or the chat, and is listed after the demo patients.
const OTHER_SEEDED_PATIENT_IDS = ['CS-1001', 'CS-1002', 'CS-2004', 'CS-2005', 'CS-9921'];

export function App() {
  const [mainView, setMainView] = useState('operatory'); // 'operatory' | 'physician'
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
      const added = all.filter((p) => !DEMO_PATIENT_IDS.includes(p.id) && !OTHER_SEEDED_PATIENT_IDS.includes(p.id));
      const list = ordered.length > 0 ? [...ordered, ...added] : all;

      setPatients(list);
      setSelectedPatientId((prev) => prev || list[0]?.id || null);
      return list;
    } catch (err) {
      console.error('Failed to load CareStack data', err);
      setBackendOnline(false);
      return [];
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

  // Patient records slide-over (new patient, medical history, previous records)
  const [intake, setIntake] = useState({ open: false, patientId: null, tab: null });
  const openIntake = useCallback((patientId, tab) => {
    setIntake({ open: true, patientId: patientId || null, tab: tab || (patientId ? 'history' : 'new') });
  }, []);

  // A patient was created or their history changed (records panel or chat): refetch, and open a newly
  // created patient so the rest of the app is looking at the chart that was just written.
  const handlePatientsChanged = useCallback(async (patientId) => {
    const known = new Set(patients.map((p) => p.id));
    const list = await loadStatusAndPatients();
    if (patientId && !known.has(patientId) && list.some((p) => p.id === patientId)) setSelectedPatientId(patientId);
    setAlertsVersion((v) => v + 1);
  }, [patients, loadStatusAndPatients]);

  const handleTabChange = useCallback((id) => {
    setActiveTab(id);
    if (id === 'chat') setMainView('operatory'); // the chat lives in the operatory view
  }, []);
  const chatActive = mainView === 'operatory' && activeTab === 'chat';

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
      try {
        await api.dispatchClearance(selectedPatient.id, lastProcedure?.code || 'D7140');
      } catch (err) {
        console.warn('Clearance dispatch notice:', err);
      }
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
      setClaimToast(`Automated Digital Clearance Passport dispatched to Dr. Kenneth Vance, MD at Metropolitan Heart Center.`);
    },
    [selectedPatient, lastProcedure]
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

  const filterTabs = [
    {
      id: 'all',
      label: 'All Alerts',
      count: cdsCards.length + (billingOpportunity?.is_eligible ? 1 : 0),
      dot: 'bg-accent',
    },
    { id: 'safety', label: 'Clinical Safety', count: cdsCards.length, dot: 'bg-danger' },
    { id: 'billing', label: 'Billing & Revenue', count: billingOpportunity?.is_eligible ? 1 : 0, dot: 'bg-success' },
  ];

  return (
    <div className="min-h-screen bg-app-bg text-text-main flex flex-col font-sans">
      <Navbar
        backendOnline={backendOnline}
        activeTab={activeTab}
        setActiveTab={handleTabChange}
        onOpenRecords={() => openIntake(null, 'new')}
        onSimulateWebhook={handleSimulateWebhookSync}
        webhookSyncing={webhookSyncing}
        selectedPatient={selectedPatient}
        onToggleDeveloperConsole={() => setShowDeveloperConsole((v) => !v)}
        showDeveloperConsole={showDeveloperConsole}
      />

      <main className="flex-1 max-w-[1440px] w-full mx-auto px-4 sm:px-6 lg:px-10 pt-6 pb-10">
        {/* Top-Level View Switcher: Dental Operatory vs External Physician Portal (hidden on the chat page: it stays minimal) */}
        <div className={`flex-col lg:flex-row lg:items-center justify-between gap-4 mb-8 ${chatActive ? 'hidden' : 'flex'}`}>
          <div className="flex flex-wrap items-center gap-3 min-w-0">
            <span className="chip chip-accent shrink-0">
              <span className="w-1.5 h-1.5 rounded-full bg-accent animate-pulse" />
              DSOLVE 2026 Live Pitch Switcher
            </span>
            <span className="text-sm text-text-muted">
              Bidirectional Asynchronous Medical-Dental Clearance Loop
            </span>
          </div>

          <div className="min-w-0 overflow-x-auto scrollbar-none">
            <div className="flex items-center gap-2 w-max mx-auto lg:mr-0 px-1" role="tablist" aria-label="Main view">
              {[
                { id: 'operatory', label: 'CareStack Dental Operatory View', Icon: Stethoscope },
                { id: 'physician', label: 'External Physician Portal (Hospital EHR Simulator)', Icon: Hospital },
              ].map(({ id, label, Icon }) => (
                <button
                  key={id}
                  role="tab"
                  aria-selected={mainView === id}
                  onClick={() => setMainView(id)}
                  className={`pill h-10 shrink-0 whitespace-nowrap cursor-pointer ${mainView === id ? 'pill-active' : ''}`}
                >
                  <Icon className="w-4 h-4" strokeWidth={1.5} />
                  <span>{label}</span>
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Isolated Developer Console Container */}
        {showDeveloperConsole && (
          <div className="mb-8">
            <DeveloperConsole
              carestackStatus={carestackStatus}
              backendOnline={backendOnline}
              onRefresh={loadStatusAndPatients}
              onClose={() => setShowDeveloperConsole(false)}
            />
          </div>
        )}

        {/* Toasts */}
        {(webhookMessage || claimToast) && (
          <div className="flex flex-col items-start gap-2 mb-6">
            {/* Sync Feedback Message */}
            {webhookMessage && (
              <div
                className={`inline-flex items-center gap-3 min-h-11 pl-2 pr-2 py-1.5 rounded-full text-sm animate-fade-in max-w-full ${
                  webhookMessage.type === 'success'
                    ? 'bg-success-light text-success-dark'
                    : 'bg-danger-light text-danger-dark'
                }`}
              >
                <span
                  className={`inline-flex items-center justify-center w-8 h-8 rounded-full text-white shrink-0 ${
                    webhookMessage.type === 'success' ? 'bg-success' : 'bg-danger'
                  }`}
                >
                  <CheckCircle2 className="w-4 h-4" strokeWidth={1.5} />
                </span>
                <span className="min-w-0">{webhookMessage.text}</span>
                <button
                  onClick={() => setWebhookMessage(null)}
                  className="inline-flex items-center justify-center w-8 h-8 rounded-full hover:bg-white/60 text-base shrink-0"
                  aria-label="Dismiss"
                >
                  ×
                </button>
              </div>
            )}

            {/* Claim Submission Success Toast */}
            {claimToast && (
              <div className="inline-flex items-center gap-3 min-h-11 pl-2 pr-2 py-1.5 rounded-full text-sm bg-success-light text-success-dark animate-fade-in max-w-full">
                <span className="inline-flex items-center justify-center w-8 h-8 rounded-full bg-success text-white shrink-0">
                  <CheckCircle2 className="w-4 h-4" strokeWidth={1.5} />
                </span>
                <span className="min-w-0">{claimToast}</span>
                <button
                  onClick={() => setClaimToast(null)}
                  className="inline-flex items-center justify-center w-8 h-8 rounded-full hover:bg-white/60 text-base shrink-0"
                  aria-label="Dismiss"
                >
                  ×
                </button>
              </div>
            )}
          </div>
        )}

        {/* Dual Mode View: External Physician Portal vs CareStack Dental Operatory */}
        {mainView === 'physician' ? (
          <PhysicianClearancePortal
            patient={selectedPatient}
            onClearanceUpdated={(updatedPassport) => {
              loadStatusAndPatients();
              setAlertsVersion((v) => v + 1);
              setClaimToast(
                `Real-time CareStack webhook callback received: Clearance for ${selectedPatient?.first_name} ${selectedPatient?.last_name} updated to "${updatedPassport?.status?.replace(/_/g, ' ')}" by ${updatedPassport?.decision?.signed_by || 'Dr. Vance'}.`
              );
            }}
            onSwitchToDentalView={() => setMainView('operatory')}
          />
        ) : (
          <>
            {/* Multi-Agent Orchestrator: runs its own demo personas, so no patient banner */}
            {activeTab === 'agents' && <AgentOpsDashboard />}

            {/* MAO Assistant: the dedicated chat page (same conversation as the floating panel) */}
            {activeTab === 'chat' && (
              <AssistantWorkspace patient={selectedPatient} onPatientsChanged={handlePatientsChanged} onOpenIntake={openIntake} />
            )}

            {/* Patient Demographic Banner with CareStack Documents Counter */}
            {activeTab !== 'agents' && activeTab !== 'chat' && (
            <PatientHeader
              patients={patients}
              selectedPatient={selectedPatient}
              onSelectPatient={handleSelectPatient}
              activeProcedure={lastProcedure}
              documentsCount={documentsCount}
            />
            )}

        {/* Doctor View 1: Patient Workspace */}
        {activeTab === 'chairside' && (
          <div className="space-y-12">
            {/* Relevant Medical Context Component */}
            <ClinicalContext patient={selectedPatient} />

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 items-start">
              {/* Left: Dental Procedure Toolbar */}
              <div>
                <div className="flex flex-wrap items-end justify-between gap-3 mb-5">
                  <div>
                    <h2 className="display-lg text-ink">Procedure Selection Toolbar</h2>
                    <p className="mt-1 text-sm text-text-muted">Triggers Order-Select Decision Engine</p>
                  </div>
                </div>
                <CareStackChart
                  patients={patients}
                  selectedPatient={selectedPatient}
                  onSelectPatient={handleSelectPatient}
                  onCardsUpdate={handleCardsUpdate}
                  alertsVersion={alertsVersion}
                  documentsCount={documentsCount}
                  onClearanceUpdated={(clearance) => {
                    loadStatusAndPatients();
                    setAlertsVersion((v) => v + 1);
                    const doc = clearance?.decision?.signed_by || clearance?.physician?.name || 'Dr. Kenneth Vance, MD';
                    const cdt = clearance?.proposed_procedures?.[0]?.cdt_code || lastProcedure?.code || 'D7140';
                    const inr = clearance?.decision?.coagulation_parameters?.target_inr_range || '2.0-2.5';
                    const decision = clearance?.status?.replace(/_/g, ' ') || 'APPROVED';
                    setClaimToast(
                      `New InBasket Notification: ${doc} signed clearance (${decision}) for CDT ${cdt} with condition: Target INR ${inr}.`
                    );
                  }}
                />
              </div>

              {/* Right: Clinical Review Cards & Financial Optimization */}
              <div>
                <div className="flex flex-wrap items-end justify-between gap-3 mb-5">
                  <div>
                    <h2 className="display-lg text-ink">Clinical Review &amp; Optimization Alerts</h2>
                    <p className="mt-1 text-sm text-text-muted flex items-center gap-2">
                      {lastProcedure && (
                        <>
                          <span>CDT</span>
                          <code className="font-mono text-xs text-accent-deep bg-accent-soft px-2 py-0.5 rounded-full">
                            {lastProcedure.code}
                          </code>
                          <span>·</span>
                        </>
                      )}
                      <span>MDIN Multi-Card Engine</span>
                    </p>
                  </div>
                </div>

                {/* Quick-Filter Tabs */}
                <div className="flex flex-wrap items-center gap-2 mb-5">
                  {filterTabs.map((t) => {
                    const active = activeFilter === t.id;
                    return (
                      <button
                        key={t.id}
                        onClick={() => setActiveFilter(t.id)}
                        className={`pill h-10 pr-2 cursor-pointer ${active ? 'pill-active' : ''}`}
                      >
                        {!active && <span className={`w-1.5 h-1.5 rounded-full ${t.dot}`} />}
                        <span>{t.label}</span>
                        <span
                          className={`inline-flex items-center justify-center min-w-7 h-7 px-2 rounded-full font-mono text-[11px] ${
                            active ? 'bg-white/15 text-white' : 'bg-app-secondary text-text-secondary'
                          }`}
                        >
                          {t.count}
                        </span>
                      </button>
                    );
                  })}
                </div>

                {/* Stack of CDS Cards */}
                {filteredCards.length > 0 ? (
                  <div>
                    {filteredCards.map((card, idx) => (
                      <CDSHookCard
                        key={card.uuid || idx}
                        card={card}
                        patient={selectedPatient}
                        procedure={lastProcedure}
                        onClearanceDispatched={(res) => {
                          loadStatusAndPatients();
                          setAlertsVersion((v) => v + 1);
                          setClaimToast(
                            `Digital Clearance Passport dispatched to Dr. Kenneth Vance (Metropolitan Heart Center) via FHIR Task for ${selectedPatient?.first_name} ${selectedPatient?.last_name}.`
                          );
                        }}
                        onAppendAlert={handleAppendAlert}
                        onRequestConsult={handleRequestConsult}
                        onViewEvidence={(c) => setSelectedEvidenceCard(c)}
                        onOpenFinancialDashboard={() => setIsFinancialModalOpen(true)}
                      />
                    ))}
                  </div>
                ) : (
                  <div className="card flex items-center gap-4">
                    <span className="inline-flex items-center justify-center w-12 h-12 rounded-full bg-success-light text-success shrink-0">
                      <CheckCircle2 className="w-5 h-5" strokeWidth={1.5} />
                    </span>
                    <span className="text-sm text-text-secondary">
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
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
            <div className="lg:col-span-5">
              <PatientTimeline patient={selectedPatient} alertsCount={cdsCards.length} />
            </div>
            <div className="lg:col-span-7">
              <MedicalEHRViewer patient={selectedPatient} />
            </div>
          </div>
        )}
          </>
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
      <footer className="py-8 text-sm text-text-muted">
        <div className="max-w-[1440px] mx-auto px-4 sm:px-6 lg:px-10 flex flex-col sm:flex-row items-center justify-between gap-2">
          <p>
            <span className="font-display font-medium text-text-secondary">MDIN.</span>{' '}
            CareStack MDIN — Medical-Dental Interoperability Node
          </p>
          <p className="text-xs">CareStack Practice Integration · DSOLVE 2026</p>
        </div>
      </footer>
      {/* MAO Assistant: chat agent available on every view */}
      <AssistantPanel
        patient={selectedPatient}
        hidden={chatActive}
        onExpand={() => handleTabChange('chat')}
        onPatientsChanged={handlePatientsChanged}
        onOpenIntake={openIntake}
      />
      <PatientIntakePanel
        open={intake.open}
        onClose={() => setIntake((v) => ({ ...v, open: false }))}
        patients={patients}
        initialPatientId={intake.patientId}
        initialTab={intake.tab}
        onChanged={handlePatientsChanged}
      />
    </div>
  );
}

export default App;



