import React, { useEffect, useState, useCallback, useRef } from 'react';
import {
  FileText,
  CheckCircle2,
  AlertTriangle,
  HeartPulse,
  Stethoscope,
  Loader2,
  User,
  ShieldAlert,
  FileCheck,
  ShieldCheck,
  Clock,
  X,
  RefreshCw,
  Send,
  Check,
  ChevronDown,
} from 'lucide-react';
import { api } from '../services/api';

const PROCEDURES = [
  { code: 'D0120', label: 'Periodic Oral Evaluation', tier: 'routine', icon: Stethoscope },
  { code: 'D1110', label: 'Prophylaxis (Adult Cleaning)', tier: 'routine', icon: CheckCircle2 },
  { code: 'D4341', label: 'Perio Scaling & Root Planing', tier: 'invasive', icon: AlertTriangle },
  { code: 'D7140', label: 'Extraction, Erupted Tooth', tier: 'high-bleed', icon: AlertTriangle },
  { code: 'D7210', label: 'Surgical Extraction', tier: 'severe', icon: HeartPulse },
];

// Tier is conveyed by the tone of the icon disc; tiles themselves stay calm.
const TIER_STYLES = {
  routine: 'bg-success-light text-success-dark',
  invasive: 'bg-warning-light text-warning-dark',
  'high-bleed': 'bg-danger-light text-danger-dark',
  severe: 'bg-danger text-white',
};

const TIER_LABELS = {
  routine: 'Routine',
  invasive: 'Invasive',
  'high-bleed': 'High bleed',
  severe: 'Severe',
};

const ALERT_BANNER_STYLES = {
  critical: { disc: 'bg-danger text-white', icon: ShieldAlert },
  warning: { disc: 'bg-warning text-white', icon: AlertTriangle },
  info: { disc: 'bg-accent text-white', icon: ShieldAlert },
};

/**
 * CareStack Dental PMS chairside workspace component:
 * Compact demographic header, CDT procedure toolbar, and live medical alerts banner
 * synchronized from federated Medical EHR.
 */
export function CareStackChart({
  patients,
  selectedPatient,
  onSelectPatient,
  onCardsUpdate,
  alertsVersion,
  documentsCount = 0,
  onClearanceUpdated,
}) {
  const [selectedProcedure, setSelectedProcedure] = useState(null);
  const [hookLoading, setHookLoading] = useState(false);
  const [alerts, setAlerts] = useState([]);
  const [alertsLoading, setAlertsLoading] = useState(false);
  const [clearanceData, setClearanceData] = useState(null);
  const [isPopoverOpen, setIsPopoverOpen] = useState(false);
  const [simulatingWebhook, setSimulatingWebhook] = useState(false);
  const [simulatedSuccess, setSimulatedSuccess] = useState(false);
  const popoverRef = useRef(null);

  // Close popover when clicking outside or pressing Escape
  useEffect(() => {
    function handleClickOutside(event) {
      if (popoverRef.current && !popoverRef.current.contains(event.target)) {
        setIsPopoverOpen(false);
      }
    }
    function handleKeyDown(event) {
      if (event.key === 'Escape') {
        setIsPopoverOpen(false);
      }
    }
    if (isPopoverOpen) {
      document.addEventListener('mousedown', handleClickOutside);
      document.addEventListener('keydown', handleKeyDown);
    }
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, [isPopoverOpen]);

  // Automated 3-second polling for asynchronous medical clearance status & physician sign-off
  const fetchClearance = useCallback(async (silent = false) => {
    if (!selectedPatient?.id) return;
    try {
      const [list, csStatus] = await Promise.all([
        api.getPatientClearances(selectedPatient.id).catch(() => []),
        api.getCareStackMedicalClearanceStatus(selectedPatient.id).catch(() => null),
      ]);

      const latest = Array.isArray(list) && list.length > 0 ? list[list.length - 1] : null;

      let merged = null;
      if (latest) {
        merged = { ...latest };
        if (csStatus && csStatus.status && csStatus.status !== 'NONE') {
          merged.carestack_status = csStatus.status;
          merged.is_cleared_for_surgery = csStatus.is_cleared_for_surgery;
        }
      } else if (csStatus && csStatus.status && csStatus.status !== 'NONE') {
        merged = {
          request_id: csStatus.request_id || 'CS-RECORD',
          status: csStatus.status,
          decision: csStatus.decision
            ? {
                decision: csStatus.decision,
                physician_notes: csStatus.notes,
                coagulation_parameters: csStatus.coagulation_parameters || {
                  target_inr_range: '2.0-2.5',
                  hold_medication: false,
                  hold_hours: 0,
                },
                signed_by: csStatus.signed_by || 'Dr. Kenneth Vance, MD (Cardiology)',
                timestamp: csStatus.signed_at || csStatus.updated_at,
              }
            : null,
          physician: {
            name: csStatus.signed_by || 'Dr. Kenneth Vance, MD',
            specialty: 'Cardiology',
            facility_name: 'Metropolitan Heart Center',
            fhir_endpoint: 'https://fhir.metroheart.org/r4',
            direct_email: 'k.vance@metroheart.org',
          },
          is_cleared_for_surgery: csStatus.is_cleared_for_surgery,
        };
      }

      setClearanceData((prev) => {
        if (prev && merged && prev.status !== merged.status) {
          onClearanceUpdated?.(merged);
        }
        return merged;
      });
    } catch (err) {
      if (!silent) console.error('Failed to load clearance status:', err);
    }
  }, [selectedPatient, onClearanceUpdated]);

  useEffect(() => {
    fetchClearance();
    const interval = setInterval(() => {
      fetchClearance(true);
    }, 3000);
    return () => clearInterval(interval);
  }, [fetchClearance, alertsVersion]);

  // 1-Click Simulation of Incoming EHR Webhook Callback
  const handleSimulateWebhookCallback = async () => {
    if (simulatingWebhook || !selectedPatient) return;
    setSimulatingWebhook(true);
    setSimulatedSuccess(false);
    try {
      let targetReqId = clearanceData?.request_id;
      if (!targetReqId || targetReqId === 'CS-RECORD') {
        const dispatched = await api.dispatchClearance(selectedPatient.id, selectedProcedure || 'D7140');
        targetReqId = dispatched.request_id;
      }

      const decisionPayload = {
        request_id: String(targetReqId),
        decision: 'APPROVED_WITH_CONDITIONS',
        physician_notes:
          'Cardiology pre-operative evaluation completed. Safe for routine/surgical dental extraction under controlled local hemostasis. Continue current oral anticoagulation regimen with verified morning INR 2.0-2.5.',
        coagulation_parameters: {
          target_inr_range: '2.0-2.5',
          hold_medication: false,
          hold_hours: 0,
        },
        signed_by: 'Dr. Kenneth Vance, MD (Cardiology)',
      };

      const updated = await api.submitClearanceDecision(targetReqId, decisionPayload);
      await fetchClearance(true);
      setSimulatedSuccess(true);
      setTimeout(() => setSimulatedSuccess(false), 4000);
      onClearanceUpdated?.(updated);
    } catch (err) {
      console.error('Failed to simulate incoming EHR webhook callback:', err);
    } finally {
      setSimulatingWebhook(false);
    }
  };

  useEffect(() => {
    if (!selectedPatient) return;
    let cancelled = false;

    async function loadAlerts() {
      setAlertsLoading(true);
      try {
        const res = await api.getPatientMedicalAlerts(selectedPatient.id).catch(() => ({ alerts: [] }));
        if (!cancelled) setAlerts(res.alerts || []);
      } finally {
        if (!cancelled) setAlertsLoading(false);
      }
    }

    loadAlerts();
    return () => {
      cancelled = true;
    };
  }, [selectedPatient, alertsVersion]);

  const handleProcedureClick = async (proc) => {
    if (!selectedPatient) return;
    setSelectedProcedure(proc.code);
    setHookLoading(true);
    try {
      // Concurrently query both the clinical safety CDS Hook and administrative cross-coding evaluation
      const [cdsResponse, billingResponse] = await Promise.all([
        api.evaluateOrderSelectHook(selectedPatient.mrn, proc.code).catch((err) => {
          console.error('order-select CDS Hook failed:', err);
          return { cards: [] };
        }),
        api.evaluateBillingClaim(selectedPatient.id || selectedPatient.mrn, proc.code).catch((err) => {
          console.error('evaluate-claim cross-coding failed:', err);
          return null;
        }),
      ]);

      onCardsUpdate?.(cdsResponse.cards || [], proc, billingResponse);
    } catch (err) {
      console.error('Procedure order-select / cross-coding failed:', err);
      onCardsUpdate?.([], proc, null);
    } finally {
      setHookLoading(false);
    }
  };

  if (!selectedPatient) {
    return (
      <div className="card text-center text-sm text-text-muted py-10">
        Loading CareStack patient directory…
      </div>
    );
  }

  const clearanceStatus = clearanceData?.status || clearanceData?.carestack_status || 'NONE';

  return (
    <div className="card p-6 sm:p-8 space-y-6">
      {/* Patient Selector Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div className="flex items-center gap-2 text-text-secondary">
          <User className="w-4 h-4" strokeWidth={1.5} />
          <label htmlFor="carestack-patient-select" className="text-sm">
            Patient Record:
          </label>
        </div>
        <select
          id="carestack-patient-select"
          value={selectedPatient.id}
          onChange={(e) => onSelectPatient(e.target.value)}
          className="field sm:w-auto sm:min-w-[20rem] font-medium cursor-pointer appearance-none"
        >
          {patients.map((p) => (
            <option key={p.id} value={p.id}>
              {p.first_name} {p.last_name} — Account #{p.id} (MRN: {p.mrn})
            </option>
          ))}
        </select>
      </div>

      {/* Demographic Context Header */}
      <div className="flex items-start gap-4">
        <div className="w-14 h-14 rounded-full bg-accent text-white flex items-center justify-center font-display font-semibold text-lg shrink-0">
          {selectedPatient.first_name[0]}
          {selectedPatient.last_name[0]}
        </div>
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-3">
            <h3 className="display-lg text-text-main">
              {selectedPatient.first_name} {selectedPatient.last_name}
            </h3>
            <span className="chip chip-accent">Active Patient</span>
          </div>
          <div className="flex flex-wrap items-center gap-x-4 gap-y-2 text-sm text-text-secondary mt-2">
            <span>DOB <span className="text-text-main font-medium">{selectedPatient.birth_date}</span></span>
            <span>MRN <span className="font-mono text-accent-deep">{selectedPatient.mrn}</span></span>
            <span>CareStack ID <span className="font-mono text-text-main">{selectedPatient.id}</span></span>

            {/* Step 13: Live Medical Clearance Status Pill Badge & Interactive Popover */}
            {clearanceStatus !== 'NONE' && (
              <div className="relative inline-block">
                {clearanceStatus === 'TRANSMITTED_TO_INBOX' || clearanceStatus === 'UNDER_REVIEW' ? (
                  <button
                    type="button"
                    onClick={() => setIsPopoverOpen((prev) => !prev)}
                    className="inline-flex items-center gap-1.5 h-8 pl-3 pr-2.5 rounded-full text-xs font-medium bg-warning-light text-warning-dark animate-pulse hover:bg-warning/20 cursor-pointer"
                    title="Click to view digital clearance passport details"
                  >
                    <Clock className="w-3.5 h-3.5 shrink-0" strokeWidth={1.5} />
                    <span>Clearance Requested (InBasket Dispatched)</span>
                    <ChevronDown className="w-3.5 h-3.5 opacity-70" strokeWidth={1.5} />
                  </button>
                ) : clearanceStatus === 'APPROVED' || clearanceStatus === 'APPROVED_WITH_CONDITIONS' ? (
                  <button
                    type="button"
                    onClick={() => setIsPopoverOpen((prev) => !prev)}
                    className="inline-flex items-center gap-1.5 h-8 pl-3 pr-2.5 rounded-full text-xs font-medium bg-success-light text-success-dark hover:bg-success/20 cursor-pointer"
                    title="Click to view digital clearance passport details"
                  >
                    <ShieldCheck className="w-3.5 h-3.5 shrink-0" strokeWidth={1.5} />
                    <span>Surgically Cleared by Cardiology</span>
                    <ChevronDown className="w-3.5 h-3.5 opacity-70" strokeWidth={1.5} />
                  </button>
                ) : clearanceStatus === 'REJECTED' ? (
                  <button
                    type="button"
                    onClick={() => setIsPopoverOpen((prev) => !prev)}
                    className="inline-flex items-center gap-1.5 h-8 pl-3 pr-2.5 rounded-full text-xs font-medium bg-danger-light text-danger-dark hover:bg-danger/20 cursor-pointer"
                    title="Click to view digital clearance passport details"
                  >
                    <X className="w-3.5 h-3.5 shrink-0" strokeWidth={1.5} />
                    <span>Clearance Denied — Surgery Contraindicated</span>
                    <ChevronDown className="w-3.5 h-3.5 opacity-70" strokeWidth={1.5} />
                  </button>
                ) : null}

                {/* Popover — dark feature card so it separates from the canvas without borders/shadows */}
                {isPopoverOpen && clearanceData && (
                  <div
                    ref={popoverRef}
                    className="absolute left-0 top-full mt-3 w-[22rem] sm:w-[26rem] max-w-[calc(100vw-2rem)] card-dark p-6 z-50 animate-fade-in text-left font-normal space-y-5"
                  >
                    {/* Popover Header */}
                    <div className="flex items-start justify-between gap-3">
                      <div className="flex items-center gap-3">
                        <span className="inline-flex items-center justify-center w-10 h-10 rounded-full bg-accent text-white shrink-0">
                          <ShieldCheck className="w-4 h-4" strokeWidth={1.5} />
                        </span>
                        <div>
                          <div className="text-[11px] font-medium uppercase tracking-[0.14em] text-white/50">
                            Digital Passport
                          </div>
                          <div className="font-display font-medium text-lg leading-tight text-white">
                            Pre-Op Medical Clearance
                          </div>
                        </div>
                      </div>
                      <button
                        type="button"
                        onClick={() => setIsPopoverOpen(false)}
                        className="inline-flex items-center justify-center w-9 h-9 rounded-full bg-white/10 text-white hover:bg-white/15 shrink-0 cursor-pointer"
                        aria-label="Close clearance passport"
                      >
                        <X className="w-4 h-4" strokeWidth={1.5} />
                      </button>
                    </div>

                    {/* Live Status in Popover */}
                    {clearanceStatus === 'TRANSMITTED_TO_INBOX' || clearanceStatus === 'UNDER_REVIEW' ? (
                      <div className="flex items-start gap-3 rounded-3xl bg-white/5 p-4">
                        <span className="inline-flex items-center justify-center w-9 h-9 rounded-full bg-warning text-white shrink-0">
                          <Clock className="w-4 h-4 animate-pulse" strokeWidth={1.5} />
                        </span>
                        <div className="min-w-0">
                          <div className="text-sm font-medium text-white">Awaiting Physician InBasket Review</div>
                          <p className="text-xs text-white/60 mt-1 leading-relaxed">
                            Task dispatched to hospital EHR via HL7 FHIR R4 Task resource. Awaiting cardiologist sign-off.
                          </p>
                        </div>
                      </div>
                    ) : clearanceStatus === 'APPROVED' || clearanceStatus === 'APPROVED_WITH_CONDITIONS' ? (
                      <div className="flex items-start gap-3 rounded-3xl bg-white/5 p-4">
                        <span className="inline-flex items-center justify-center w-9 h-9 rounded-full bg-success text-white shrink-0">
                          <CheckCircle2 className="w-4 h-4" strokeWidth={1.5} />
                        </span>
                        <div className="min-w-0">
                          <div className="text-sm font-medium text-white">Surgically Cleared by Cardiology</div>
                          <p className="text-xs text-white/60 mt-1 leading-relaxed">
                            {clearanceData.decision?.physician_notes ||
                              'Cardiology clearance approved. Safe to proceed under verified hemostasis parameters.'}
                          </p>
                        </div>
                      </div>
                    ) : (
                      <div className="flex items-start gap-3 rounded-3xl bg-white/5 p-4">
                        <span className="inline-flex items-center justify-center w-9 h-9 rounded-full bg-danger text-white shrink-0">
                          <X className="w-4 h-4" strokeWidth={1.5} />
                        </span>
                        <div className="min-w-0">
                          <div className="text-sm font-medium text-white">Surgery Contraindicated</div>
                          <p className="text-xs text-white/60 mt-1 leading-relaxed">
                            {clearanceData.decision?.physician_notes ||
                              'Clearance rejected by attending physician due to elevated hemodynamic or bleeding hazard.'}
                          </p>
                        </div>
                      </div>
                    )}

                    {/* Attending Physician */}
                    <div>
                      <div className="text-[11px] font-medium uppercase tracking-[0.14em] text-white/50 mb-2">
                        Attending Specialist
                      </div>
                      <div className="rounded-3xl bg-white/5 p-4">
                        <div className="font-display font-medium text-[15px] text-white">
                          {clearanceData.physician?.name || 'Dr. Kenneth Vance, MD'}
                        </div>
                        <div className="text-xs text-white/60 mt-0.5">
                          {clearanceData.physician?.specialty || 'Cardiology'} · {clearanceData.physician?.facility_name || 'Metropolitan Heart Center'}
                        </div>
                        <div className="font-mono text-[11px] text-white/40 mt-2 break-all">
                          NPI: {clearanceData.physician?.npi || '1092837465'} · Direct: {clearanceData.physician?.direct_email || 'k.vance@metroheart.org'}
                        </div>
                      </div>
                    </div>

                    {/* Target Coagulation Parameters */}
                    <div>
                      <div className="text-[11px] font-medium uppercase tracking-[0.14em] text-white/50 mb-2">
                        Target Coagulation Parameters
                      </div>
                      <div className="grid grid-cols-2 gap-2">
                        <div className="rounded-3xl bg-accent p-4">
                          <div className="text-xs text-white/70">Target INR Range</div>
                          <div className="font-display font-medium text-2xl tracking-tight text-white mt-1 leading-none">
                            {clearanceData.decision?.coagulation_parameters?.target_inr_range || '2.0 - 2.5'}
                          </div>
                        </div>
                        <div className="rounded-3xl bg-white/5 p-4">
                          <div className="text-xs text-white/60">Hold Instructions</div>
                          <div className="text-sm font-medium text-white mt-1 leading-snug">
                            {clearanceData.decision?.coagulation_parameters?.hold_medication
                              ? `Hold for ${clearanceData.decision.coagulation_parameters.hold_hours || 24} hours`
                              : 'Continue Warfarin; do not hold'}
                          </div>
                        </div>
                      </div>
                    </div>

                    {/* Verification & Timestamp */}
                    <div className="space-y-1.5 text-xs">
                      <div className="flex items-center justify-between gap-3">
                        <span className="text-white/50">Verification ID</span>
                        <span className="font-mono text-white/80 truncate max-w-[200px]">
                          {clearanceData.request_id || 'CS-2001-CLEARANCE'}
                        </span>
                      </div>
                      <div className="flex items-center justify-between gap-3">
                        <span className="text-white/50">Digital Timestamp</span>
                        <span className="font-mono text-white/80">
                          {clearanceData.decision?.timestamp
                            ? new Date(clearanceData.decision.timestamp).toLocaleString()
                            : clearanceData.updated_at
                            ? new Date(clearanceData.updated_at).toLocaleString()
                            : 'Pending'}
                        </span>
                      </div>
                      {clearanceData.decision?.signed_by && (
                        <div className="flex items-center justify-between gap-3">
                          <span className="text-white/50">Signed By</span>
                          <span className="text-white font-medium text-right">{clearanceData.decision.signed_by}</span>
                        </div>
                      )}
                    </div>

                    {/* 1-Click Simulation Button */}
                    <div>
                      <button
                        type="button"
                        onClick={handleSimulateWebhookCallback}
                        disabled={simulatingWebhook}
                        className="w-full inline-flex items-center justify-center gap-2 h-11 px-5 rounded-full bg-white text-ink font-display font-semibold text-sm hover:bg-app-secondary cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
                      >
                        {simulatingWebhook ? (
                          <>
                            <Loader2 className="w-4 h-4 animate-spin" strokeWidth={1.5} />
                            <span>Simulating EHR Webhook…</span>
                          </>
                        ) : (
                          <>
                            <RefreshCw className="w-4 h-4 text-accent" strokeWidth={1.5} />
                            <span>Simulate Incoming EHR Webhook Callback</span>
                          </>
                        )}
                      </button>
                      {simulatedSuccess && (
                        <div className="mt-2 text-xs text-center text-success flex items-center justify-center gap-1.5">
                          <Check className="w-3.5 h-3.5" strokeWidth={1.5} />
                          <span>Webhook callback received & CareStack updated</span>
                        </div>
                      )}
                    </div>
                  </div>
                )}
              </div>
            )}

            <span className="chip">
              <FileCheck className="w-3.5 h-3.5 text-accent" strokeWidth={1.5} />
              CareStack Docs: <span className="text-text-main font-semibold">{documentsCount} Synced</span>
            </span>
          </div>
        </div>
      </div>

      {/* Live Medical Alerts Banner */}
      <div className="well p-5">
        <div className="flex items-center justify-between gap-3 mb-3">
          <span className="font-display font-medium text-[15px] text-text-main flex items-center gap-2">
            <ShieldAlert className="w-4 h-4 text-accent" strokeWidth={1.5} />
            <span>Chart Medical Alerts (EHR Synced)</span>
          </span>
          {alerts.length > 0 && (
            <span className="chip bg-warning-light text-warning-dark">
              {alerts.length} Alert{alerts.length > 1 ? 's' : ''} Posted
            </span>
          )}
        </div>
        {alertsLoading ? (
          <div className="flex items-center gap-2 text-sm text-text-muted">
            <Loader2 className="w-4 h-4 animate-spin" strokeWidth={1.5} /> Verifying patient chart...
          </div>
        ) : alerts.length > 0 ? (
          <div className="space-y-2">
            {alerts.map((a) => {
              const alertStyle = ALERT_BANNER_STYLES[a.alert_type] || ALERT_BANNER_STYLES.info;
              const AlertIcon = alertStyle.icon;
              return (
                <div key={a.alert_id} className="flex items-start gap-3 bg-app-surface rounded-2xl p-3.5">
                  <span className={`inline-flex items-center justify-center w-9 h-9 rounded-full shrink-0 ${alertStyle.disc}`}>
                    <AlertIcon className="w-4 h-4" strokeWidth={1.5} />
                  </span>
                  <div className="min-w-0 pt-0.5">
                    <div className="text-sm font-medium text-text-main">{a.title}</div>
                    {a.details && <div className="text-xs text-text-secondary mt-0.5 leading-relaxed">{a.details}</div>}
                  </div>
                </div>
              );
            })}
          </div>
        ) : (
          <div className="text-sm text-text-secondary flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4 text-success" strokeWidth={1.5} />
            No active medical alerts posted to this CareStack chart.
          </div>
        )}
      </div>

      {/* CDT Procedure Selection Toolbar */}
      <div>
        <div className="flex items-end justify-between gap-3 mb-4">
          <div className="flex items-center gap-2">
            <FileText className="w-4 h-4 text-accent" strokeWidth={1.5} />
            <span className="font-display font-medium text-lg text-text-main">
              Odontogram · CDT Procedure Selection
            </span>
          </div>
          <span className="text-xs text-text-muted">Triggers Order-Select CDS Hook</span>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          {PROCEDURES.map((proc) => {
            const Icon = proc.icon;
            const isActive = selectedProcedure === proc.code;
            return (
              <button
                key={proc.code}
                onClick={() => handleProcedureClick(proc)}
                disabled={hookLoading}
                className={`group flex items-center gap-3 p-2.5 pr-5 rounded-full text-left transition-colors disabled:opacity-60 ${
                  isActive
                    ? 'bg-accent text-white'
                    : 'bg-app-secondary text-text-main hover:bg-app-bg'
                }`}
              >
                <span
                  className={`inline-flex items-center justify-center w-11 h-11 rounded-full shrink-0 ${
                    isActive ? 'bg-white text-accent' : TIER_STYLES[proc.tier]
                  }`}
                >
                  <Icon className="w-[18px] h-[18px]" strokeWidth={1.5} />
                </span>
                <span className="flex-1 min-w-0">
                  <span className={`block font-mono text-xs ${isActive ? 'text-white/70' : 'text-text-muted'}`}>
                    {proc.code} · {TIER_LABELS[proc.tier]}
                  </span>
                  <span className="block font-display font-medium text-[15px] truncate">{proc.label}</span>
                </span>
                {isActive && hookLoading && <Loader2 className="w-4 h-4 animate-spin ml-auto text-white" strokeWidth={1.5} />}
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
}
