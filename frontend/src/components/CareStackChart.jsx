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

const TIER_STYLES = {
  routine: 'border-success/30 bg-success-light text-success-dark hover:bg-success-light/80',
  invasive: 'border-warning/40 bg-warning-light text-warning-dark hover:bg-warning-light/80',
  'high-bleed': 'border-danger/40 bg-danger-light text-danger-dark hover:bg-danger-light/80',
  severe: 'border-danger/60 bg-danger-light text-danger-dark hover:bg-danger/20 font-bold',
};

const ALERT_BANNER_STYLES = {
  critical: 'border-danger/30 bg-danger-light text-danger-dark',
  warning: 'border-warning/30 bg-warning-light text-warning-dark',
  info: 'border-info/30 bg-info-light text-info-dark',
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
      <div className="p-6 text-center text-xs text-text-muted bg-app-surface rounded-lg border border-app-border">
        Loading CareStack patient directory…
      </div>
    );
  }

  const clearanceStatus = clearanceData?.status || clearanceData?.carestack_status || 'NONE';

  return (
    <div className="bg-app-surface rounded-lg border border-app-border shadow-xs overflow-hidden">
      {/* Patient Selector Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2.5 px-4 py-3 bg-app-secondary/50 border-b border-app-border">
        <div className="flex items-center gap-2">
          <User className="w-4 h-4 text-teal-500" />
          <label htmlFor="carestack-patient-select" className="text-xs font-semibold text-text-secondary uppercase tracking-wider">
            Patient Record:
          </label>
        </div>
        <select
          id="carestack-patient-select"
          value={selectedPatient.id}
          onChange={(e) => onSelectPatient(e.target.value)}
          className="bg-app-surface border border-app-border text-text-main text-xs rounded px-2.5 py-1.5 font-medium focus:outline-none focus:border-teal-500 flex-1 sm:flex-none"
        >
          {patients.map((p) => (
            <option key={p.id} value={p.id}>
              {p.first_name} {p.last_name} — Account #{p.id} (MRN: {p.mrn})
            </option>
          ))}
        </select>
      </div>

      {/* Demographic Context Header */}
      <div className="px-4 py-3.5 bg-app-surface border-b border-app-border">
        <div className="flex items-center gap-3.5">
          <div className="w-10 h-10 rounded-full bg-teal-50 text-teal-700 flex items-center justify-center font-bold text-sm shrink-0 border border-teal-200">
            {selectedPatient.first_name[0]}
            {selectedPatient.last_name[0]}
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h3 className="text-base font-bold text-text-main leading-none">
                {selectedPatient.first_name} {selectedPatient.last_name}
              </h3>
              <span className="text-[10px] font-bold px-2 py-0.5 rounded bg-teal-50 text-teal-700 border border-teal-200 uppercase">
                Active Patient
              </span>
            </div>
            <div className="flex flex-wrap items-center gap-x-3 gap-y-1.5 text-xs text-text-secondary mt-1">
              <span>DOB: <strong>{selectedPatient.birth_date}</strong></span>
              <span className="text-text-muted">•</span>
              <span>MRN: <strong className="text-teal-700">{selectedPatient.mrn}</strong></span>
              <span className="text-text-muted">•</span>
              <span>CareStack ID: <strong className="text-text-main">{selectedPatient.id}</strong></span>

              {/* Step 13: Live Medical Clearance Status Pill Badge & Interactive Popover */}
              {clearanceStatus !== 'NONE' && (
                <>
                  <span className="text-text-muted">•</span>
                  <div className="relative inline-block">
                    {clearanceStatus === 'TRANSMITTED_TO_INBOX' || clearanceStatus === 'UNDER_REVIEW' ? (
                      <button
                        type="button"
                        onClick={() => setIsPopoverOpen((prev) => !prev)}
                        className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[11px] font-bold bg-amber-100 text-amber-900 border border-amber-300 animate-pulse hover:bg-amber-200 transition-all cursor-pointer shadow-xs"
                        title="Click to view digital clearance passport details"
                      >
                        <Clock className="w-3.5 h-3.5 text-amber-700 shrink-0" />
                        <span>Clearance Requested (InBasket Dispatched)</span>
                        <ChevronDown className="w-3 h-3 text-amber-700 opacity-70" />
                      </button>
                    ) : clearanceStatus === 'APPROVED' || clearanceStatus === 'APPROVED_WITH_CONDITIONS' ? (
                      <button
                        type="button"
                        onClick={() => setIsPopoverOpen((prev) => !prev)}
                        className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[11px] font-bold bg-emerald-100 text-emerald-900 border border-emerald-300 hover:bg-emerald-200 transition-all cursor-pointer shadow-xs"
                        title="Click to view digital clearance passport details"
                      >
                        <ShieldCheck className="w-3.5 h-3.5 text-emerald-700 shrink-0" />
                        <span>Surgically Cleared by Cardiology</span>
                        <ChevronDown className="w-3 h-3 text-emerald-700 opacity-70" />
                      </button>
                    ) : clearanceStatus === 'REJECTED' ? (
                      <button
                        type="button"
                        onClick={() => setIsPopoverOpen((prev) => !prev)}
                        className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[11px] font-bold bg-rose-100 text-rose-900 border border-rose-300 hover:bg-rose-200 transition-all cursor-pointer shadow-xs"
                        title="Click to view digital clearance passport details"
                      >
                        <X className="w-3.5 h-3.5 text-rose-700 shrink-0" />
                        <span>Clearance Denied — Surgery Contraindicated</span>
                        <ChevronDown className="w-3 h-3 text-rose-700 opacity-70" />
                      </button>
                    ) : null}

                    {/* Popover */}
                    {isPopoverOpen && clearanceData && (
                      <div
                        ref={popoverRef}
                        className="absolute left-0 top-full mt-2 w-80 sm:w-96 bg-white rounded-xl shadow-2xl border border-slate-200 p-4 z-50 text-slate-800 animate-fade-in text-xs font-normal text-left"
                        style={{ minWidth: '340px', maxWidth: '420px' }}
                      >
                        {/* Popover Header */}
                        <div className="flex items-center justify-between pb-2.5 border-b border-slate-100">
                          <div className="flex items-center gap-1.5">
                            <ShieldCheck className="w-4 h-4 text-teal-600" />
                            <span className="font-bold text-slate-900 text-xs tracking-tight">
                              Pre-Op Medical Clearance Passport
                            </span>
                          </div>
                          <button
                            type="button"
                            onClick={() => setIsPopoverOpen(false)}
                            className="text-slate-400 hover:text-slate-600 p-1 rounded-md hover:bg-slate-100 cursor-pointer"
                          >
                            <X className="w-3.5 h-3.5" />
                          </button>
                        </div>

                        {/* Live Status Pill in Popover */}
                        <div className="mt-3 mb-2.5">
                          {clearanceStatus === 'TRANSMITTED_TO_INBOX' || clearanceStatus === 'UNDER_REVIEW' ? (
                            <div className="p-2.5 rounded-lg bg-amber-50 border border-amber-200 text-amber-900">
                              <div className="font-bold flex items-center gap-1.5 text-xs">
                                <Clock className="w-3.5 h-3.5 text-amber-600 animate-pulse" />
                                <span>Awaiting Physician InBasket Review</span>
                              </div>
                              <p className="text-[11px] text-amber-800 mt-1 leading-relaxed">
                                Task dispatched to hospital EHR via HL7 FHIR R4 Task resource. Awaiting cardiologist sign-off.
                              </p>
                            </div>
                          ) : clearanceStatus === 'APPROVED' || clearanceStatus === 'APPROVED_WITH_CONDITIONS' ? (
                            <div className="p-2.5 rounded-lg bg-emerald-50 border border-emerald-200 text-emerald-900">
                              <div className="font-bold flex items-center gap-1.5 text-xs">
                                <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
                                <span>Surgically Cleared by Cardiology</span>
                              </div>
                              <p className="text-[11px] text-emerald-800 mt-1 leading-relaxed">
                                {clearanceData.decision?.physician_notes ||
                                  'Cardiology clearance approved. Safe to proceed under verified hemostasis parameters.'}
                              </p>
                            </div>
                          ) : (
                            <div className="p-2.5 rounded-lg bg-rose-50 border border-rose-200 text-rose-900">
                              <div className="font-bold flex items-center gap-1.5 text-xs">
                                <X className="w-3.5 h-3.5 text-rose-600" />
                                <span>Surgery Contraindicated</span>
                              </div>
                              <p className="text-[11px] text-rose-800 mt-1 leading-relaxed">
                                {clearanceData.decision?.physician_notes ||
                                  'Clearance rejected by attending physician due to elevated hemodynamic or bleeding hazard.'}
                              </p>
                            </div>
                          )}
                        </div>

                        {/* Attending Physician */}
                        <div className="space-y-1.5 py-2 border-t border-slate-100 text-[11px]">
                          <div className="text-[10px] font-bold uppercase tracking-wider text-slate-400">
                            Attending Specialist
                          </div>
                          <div className="bg-slate-50 p-2.5 rounded-lg border border-slate-200/80">
                            <div className="font-bold text-slate-900 text-xs">
                              {clearanceData.physician?.name || 'Dr. Kenneth Vance, MD'}
                            </div>
                            <div className="text-slate-600 text-[11px] mt-0.5">
                              {clearanceData.physician?.specialty || 'Cardiology'} · {clearanceData.physician?.facility_name || 'Metropolitan Heart Center'}
                            </div>
                            <div className="font-mono text-[10px] text-slate-500 mt-1">
                              NPI: {clearanceData.physician?.npi || '1092837465'} · Direct: {clearanceData.physician?.direct_email || 'k.vance@metroheart.org'}
                            </div>
                          </div>
                        </div>

                        {/* Target Coagulation Parameters */}
                        <div className="space-y-1.5 py-2 border-t border-slate-100 text-[11px]">
                          <div className="text-[10px] font-bold uppercase tracking-wider text-slate-400">
                            Target Coagulation Parameters
                          </div>
                          <div className="grid grid-cols-2 gap-2">
                            <div className="bg-slate-50 p-2 rounded-lg border border-slate-200/80">
                              <div className="text-[10px] text-slate-500 font-medium">Target INR Range</div>
                              <div className="font-mono font-bold text-teal-800 text-xs mt-0.5">
                                {clearanceData.decision?.coagulation_parameters?.target_inr_range || '2.0 - 2.5'}
                              </div>
                            </div>
                            <div className="bg-slate-50 p-2 rounded-lg border border-slate-200/80">
                              <div className="text-[10px] text-slate-500 font-medium">Hold Instructions</div>
                              <div className="font-semibold text-slate-800 text-[11px] mt-0.5">
                                {clearanceData.decision?.coagulation_parameters?.hold_medication
                                  ? `Hold for ${clearanceData.decision.coagulation_parameters.hold_hours || 24} hours`
                                  : 'Continue Warfarin; do not hold'}
                              </div>
                            </div>
                          </div>
                        </div>

                        {/* Verification & Timestamp */}
                        <div className="py-2 border-t border-slate-100 text-[10px] text-slate-500 space-y-1">
                          <div className="flex items-center justify-between">
                            <span className="font-medium text-slate-400">Verification ID:</span>
                            <span className="font-mono text-slate-700 font-semibold truncate max-w-[180px]">
                              {clearanceData.request_id || 'CS-2001-CLEARANCE'}
                            </span>
                          </div>
                          <div className="flex items-center justify-between">
                            <span className="font-medium text-slate-400">Digital Timestamp:</span>
                            <span className="font-mono text-slate-700">
                              {clearanceData.decision?.timestamp
                                ? new Date(clearanceData.decision.timestamp).toLocaleString()
                                : clearanceData.updated_at
                                ? new Date(clearanceData.updated_at).toLocaleString()
                                : 'Pending'}
                            </span>
                          </div>
                          {clearanceData.decision?.signed_by && (
                            <div className="flex items-center justify-between">
                              <span className="font-medium text-slate-400">Signed By:</span>
                              <span className="text-emerald-700 font-semibold">
                                {clearanceData.decision.signed_by}
                              </span>
                            </div>
                          )}
                        </div>

                        {/* 1-Click Simulation Button */}
                        <div className="pt-2.5 border-t border-slate-100">
                          <button
                            type="button"
                            onClick={handleSimulateWebhookCallback}
                            disabled={simulatingWebhook}
                            className="w-full flex items-center justify-center gap-1.5 py-2 px-3 rounded-lg text-xs font-bold text-white bg-gradient-to-r from-teal-600 to-emerald-600 hover:from-teal-500 hover:to-emerald-500 transition-all shadow-sm cursor-pointer disabled:opacity-50"
                          >
                            {simulatingWebhook ? (
                              <>
                                <Loader2 className="w-3.5 h-3.5 animate-spin" />
                                <span>Simulating EHR Webhook…</span>
                              </>
                            ) : (
                              <>
                                <RefreshCw className="w-3.5 h-3.5" />
                                <span>Simulate Incoming EHR Webhook Callback</span>
                              </>
                            )}
                          </button>
                          {simulatedSuccess && (
                            <div className="mt-1.5 text-[11px] text-center text-emerald-700 font-semibold flex items-center justify-center gap-1">
                              <Check className="w-3 h-3 text-emerald-600" />
                              <span>Webhook callback received & CareStack updated!</span>
                            </div>
                          )}
                        </div>
                      </div>
                    )}
                  </div>
                </>
              )}

              <span className="text-text-muted">•</span>
              <span className="inline-flex items-center gap-1 font-semibold text-teal-800 bg-teal-50 px-2 py-0.5 rounded border border-teal-200 text-[11px]">
                <FileCheck className="w-3 h-3 text-teal-600" />
                CareStack Docs: <strong>{documentsCount} Synced</strong>
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Live Medical Alerts Banner */}
      <div className="px-4 py-3 border-b border-app-border bg-app-bg">
        <div className="flex items-center justify-between mb-2">
          <span className="text-[11px] font-bold uppercase tracking-wider text-text-secondary flex items-center gap-1.5">
            <ShieldAlert className="w-3.5 h-3.5 text-teal-500" />
            <span>Chart Medical Alerts (EHR Synced)</span>
          </span>
          {alerts.length > 0 && (
            <span className="text-[10px] font-bold text-warning-dark bg-warning-light px-2 py-0.5 rounded border border-warning/30">
              {alerts.length} Alert{alerts.length > 1 ? 's' : ''} Posted
            </span>
          )}
        </div>
        {alertsLoading ? (
          <div className="flex items-center gap-2 text-xs text-text-muted">
            <Loader2 className="w-3.5 h-3.5 animate-spin" /> Verifying patient chart...
          </div>
        ) : alerts.length > 0 ? (
          <div className="space-y-1.5">
            {alerts.map((a) => (
              <div
                key={a.alert_id}
                className={`text-xs px-3 py-2 rounded border font-medium ${
                  ALERT_BANNER_STYLES[a.alert_type] || ALERT_BANNER_STYLES.info
                }`}
              >
                <div className="font-semibold">{a.title}</div>
                {a.details && <div className="text-[11px] opacity-90 mt-0.5">{a.details}</div>}
              </div>
            ))}
          </div>
        ) : (
          <div className="text-xs text-text-muted italic flex items-center gap-1.5 bg-app-surface p-2 rounded border border-app-border">
            <CheckCircle2 className="w-3.5 h-3.5 text-success" />
            No active medical alerts posted to this CareStack chart.
          </div>
        )}
      </div>

      {/* CDT Procedure Selection Toolbar */}
      <div className="px-4 py-3.5 bg-app-surface">
        <div className="flex items-center justify-between mb-2.5">
          <div className="flex items-center gap-1.5">
            <FileText className="w-4 h-4 text-teal-500" />
            <span className="text-xs font-bold uppercase tracking-wider text-text-secondary">
              Odontogram · CDT Procedure Selection
            </span>
          </div>
          <span className="text-[11px] text-text-muted">Triggers Order-Select CDS Hook</span>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
          {PROCEDURES.map((proc) => {
            const Icon = proc.icon;
            const isActive = selectedProcedure === proc.code;
            return (
              <button
                key={proc.code}
                onClick={() => handleProcedureClick(proc)}
                disabled={hookLoading}
                className={`flex items-center gap-2 px-3 py-2 rounded border text-left text-xs font-medium transition-all disabled:opacity-60 ${
                  TIER_STYLES[proc.tier]
                } ${isActive ? 'ring-2 ring-teal-500 ring-offset-1 bg-white shadow-xs' : ''}`}
              >
                <Icon className="w-3.5 h-3.5 shrink-0" />
                <span className="flex-1 truncate">
                  <strong className="font-mono font-bold text-text-main">{proc.code}</strong> — {proc.label}
                </span>
                {isActive && hookLoading && <Loader2 className="w-3.5 h-3.5 animate-spin ml-auto text-teal-500" />}
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
}

