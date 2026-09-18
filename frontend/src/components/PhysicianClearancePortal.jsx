import React, { useState, useEffect, useCallback } from 'react';
import {
  HeartPulse,
  Activity,
  ShieldCheck,
  AlertTriangle,
  CheckCircle2,
  Clock,
  FileText,
  Send,
  Lock,
  Hospital,
  User,
  Check,
  RefreshCw,
  Hash,
  FileCheck,
  ArrowRight,
  ExternalLink,
  AlertCircle,
  Stethoscope,
  ChevronRight,
} from 'lucide-react';
import { api } from '../services/api';

export function PhysicianClearancePortal({
  patient,
  onClearanceUpdated,
  onSwitchToDentalView,
}) {
  const [requests, setRequests] = useState([]);
  const [selectedRequestId, setSelectedRequestId] = useState(null);
  const [loading, setLoading] = useState(false);
  const [dispatching, setDispatching] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [confirmationBadge, setConfirmationBadge] = useState(null);
  const [errorMsg, setErrorMsg] = useState(null);

  // Decision Form State
  const [decisionType, setDecisionType] = useState('APPROVED_WITH_CONDITIONS');
  const [targetInr, setTargetInr] = useState('2.0 - 2.5');
  const [holdMedication, setHoldMedication] = useState(false);
  const [physicianNotes, setPhysicianNotes] = useState(
    'Verify INR within 24h prior to extraction (target 2.0-2.5). Do NOT discontinue Warfarin; maintain uninterrupted dosage. Apply local hemostatic measures (absorbable gelatin sponge + sutures + 4.8% tranexamic acid mouthwash).'
  );
  const [signerName, setSignerName] = useState('Dr. Kenneth Vance, MD (Cardiology)');

  const selectedRequest = requests.find((r) => String(r.request_id) === String(selectedRequestId)) || requests[0] || null;

  const loadClearanceRequests = useCallback(async () => {
    if (!patient) return;
    setLoading(true);
    setErrorMsg(null);
    try {
      // Fetch clearances by patient ID or alias
      const list = await api.getPatientClearances(patient.id || patient.mrn).catch(() => []);
      setRequests(Array.isArray(list) ? list : []);
      if (list && list.length > 0) {
        setSelectedRequestId((prev) => prev || list[0].request_id);
      }
    } catch (err) {
      console.error('Failed to load clearance requests:', err);
      setErrorMsg('Unable to retrieve clearance queue.');
    } finally {
      setLoading(false);
    }
  }, [patient]);

  useEffect(() => {
    loadClearanceRequests();
  }, [loadClearanceRequests]);

  // Dispatch a new clearance request if none exist
  const handleAutoDispatch = async () => {
    if (!patient) return;
    setDispatching(true);
    setErrorMsg(null);
    try {
      const newPassport = await api.dispatchClearance(patient.id, 'D7140');
      setRequests((prev) => [newPassport, ...prev]);
      setSelectedRequestId(newPassport.request_id);
      setConfirmationBadge(null);
    } catch (err) {
      console.error('Failed to dispatch clearance passport:', err);
      setErrorMsg(`Failed to initiate clearance request: ${err.message}`);
    } finally {
      setDispatching(false);
    }
  };

  // Submit physician decision
  const handleSubmitDecision = async (e) => {
    e.preventDefault();
    if (!selectedRequest) return;
    setSubmitting(true);
    setErrorMsg(null);

    const coagParams = {
      target_inr_range: decisionType === 'APPROVED_WITH_CONDITIONS' ? targetInr : decisionType === 'APPROVED' ? '2.0-3.0' : 'N/A',
      hold_medication: holdMedication,
      hold_hours: holdMedication ? 24 : 0,
    };

    const decisionPayload = {
      request_id: String(selectedRequest.request_id),
      decision: decisionType,
      physician_notes: physicianNotes,
      coagulation_parameters: coagParams,
      signed_by: signerName,
      timestamp: new Date().toISOString(),
    };

    try {
      const updatedPassport = await api.submitClearanceDecision(selectedRequest.request_id, decisionPayload);

      // Create synthetic cryptographic audit hash
      const rawString = `${selectedRequest.request_id}-${decisionType}-${signerName}-${Date.now()}`;
      let hashNum = 0;
      for (let i = 0; i < rawString.length; i++) {
        hashNum = (hashNum << 5) - hashNum + rawString.charCodeAt(i);
        hashNum |= 0;
      }
      const signatureHash = `SHA256:0x${Math.abs(hashNum).toString(16).padStart(12, '0')}e91b4a`;

      setConfirmationBadge({
        decision: decisionType,
        signed_by: signerName,
        timestamp: new Date().toLocaleTimeString(),
        signatureHash,
        targetInr: coagParams.target_inr_range,
        notes: physicianNotes,
        holdMedication,
      });

      // Refresh list
      setRequests((prev) =>
        prev.map((r) => (r.request_id === selectedRequest.request_id ? updatedPassport : r))
      );

      // Notify parent app to update CareStack status and badges
      if (onClearanceUpdated) {
        onClearanceUpdated(updatedPassport);
      }
    } catch (err) {
      console.error('Failed to submit clearance decision:', err);
      setErrorMsg(`Sign-off transmission failed: ${err.message}`);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="bg-slate-900 text-slate-100 rounded-xl shadow-2xl border border-slate-700 overflow-hidden font-sans animate-fade-in">
      {/* Hospital EHR Top Branding Header (Epic InBasket / Cerner Message Center Simulator) */}
      <div className="bg-gradient-to-r from-blue-900 via-indigo-950 to-slate-900 border-b border-slate-700/80 px-6 py-4 flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="h-11 w-11 rounded-lg bg-blue-600/90 border border-blue-400/40 flex items-center justify-center text-white shadow-md shrink-0">
            <Hospital className="w-6 h-6" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-base sm:text-lg font-bold tracking-tight text-white flex items-center gap-2">
                <span>Metropolitan Heart Center</span>
                <span className="text-xs px-2 py-0.5 rounded bg-blue-500/20 text-blue-300 border border-blue-400/30 font-medium">
                  Provider Portal · InBasket Tasks
                </span>
              </h1>
            </div>
            <p className="text-xs text-blue-200/80 flex items-center gap-2 mt-0.5">
              <span>HL7 FHIR R4 Interoperability Gateway</span>
              <span>•</span>
              <span>CareStack PMS Inbound Bridge</span>
            </p>
          </div>
        </div>

        {/* Attending Physician Profile Card */}
        <div className="flex items-center gap-3 bg-slate-800/80 border border-slate-700 px-3.5 py-2 rounded-lg text-xs shadow-inner">
          <div className="h-8 w-8 rounded-full bg-blue-500/20 border border-blue-400/40 flex items-center justify-center text-blue-300 font-bold">
            <User className="w-4 h-4" />
          </div>
          <div>
            <div className="font-semibold text-slate-100 flex items-center gap-1.5">
              <span>Dr. Kenneth Vance, MD</span>
              <span className="text-[10px] px-1.5 py-0.2 bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 rounded font-mono font-bold">
                ACTIVE
              </span>
            </div>
            <div className="text-[11px] text-slate-400">
              Chief of Cardiology · NPI: <span className="font-mono text-slate-300">1982341120</span>
            </div>
          </div>
        </div>
      </div>

      {/* Hospital Sub-bar / Navigation Banner */}
      <div className="bg-slate-800/70 border-b border-slate-700/60 px-6 py-2.5 flex flex-wrap items-center justify-between text-xs gap-3">
        <div className="flex items-center gap-3">
          <span className="text-slate-400 font-medium">Queue:</span>
          <span className="px-2 py-0.5 rounded bg-blue-500/20 text-blue-300 font-semibold flex items-center gap-1">
            <Activity className="w-3.5 h-3.5" />
            <span>Pre-Operative Dental Clearance Requests ({requests.length})</span>
          </span>
          {patient && (
            <span className="text-slate-300">
              Active Patient:{' '}
              <strong className="text-white">
                {patient.first_name} {patient.last_name}
              </strong>{' '}
              ({patient.mrn || patient.id})
            </span>
          )}
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={loadClearanceRequests}
            disabled={loading}
            className="px-2.5 py-1 bg-slate-700 hover:bg-slate-600 text-slate-200 rounded border border-slate-600 transition-colors flex items-center gap-1 cursor-pointer"
            title="Refresh InBasket Queue"
          >
            <RefreshCw className={`w-3 h-3 ${loading ? 'animate-spin' : ''}`} />
            <span>Refresh</span>
          </button>
          {requests.length === 0 && (
            <button
              onClick={handleAutoDispatch}
              disabled={dispatching}
              className="px-3 py-1 bg-blue-600 hover:bg-blue-500 text-white font-semibold rounded shadow-xs transition-colors flex items-center gap-1.5 cursor-pointer"
            >
              <Send className="w-3 h-3" />
              <span>{dispatching ? 'Dispatching...' : 'Dispatch D7140 Clearance'}</span>
            </button>
          )}
        </div>
      </div>

      {/* Main Split Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-12 min-h-[560px]">
        {/* Left: InBasket Task List (lg:col-span-4) */}
        <div className="lg:col-span-4 border-b lg:border-b-0 lg:border-r border-slate-700/70 bg-slate-900/60 p-4 space-y-3">
          <div className="flex items-center justify-between text-xs font-bold text-slate-400 uppercase tracking-wider mb-1">
            <span>Incoming Tasks</span>
            <span className="text-[11px] font-mono text-blue-400">{requests.length} pending / reviewed</span>
          </div>

          {requests.length === 0 ? (
            <div className="text-center py-12 px-4 bg-slate-800/40 rounded-lg border border-slate-700/60 text-slate-400">
              <HeartPulse className="w-9 h-9 mx-auto text-blue-400/60 mb-2 animate-pulse" />
              <p className="text-sm font-semibold text-slate-200">No Active Clearance Inbound Tasks</p>
              <p className="text-xs text-slate-400 mt-1">
                Dispatch an automated clearance passport from CareStack operatory or click below to simulate incoming extraction request.
              </p>
              <button
                onClick={handleAutoDispatch}
                disabled={dispatching}
                className="mt-4 px-4 py-1.5 bg-blue-600 hover:bg-blue-500 text-white font-semibold rounded text-xs transition-all shadow-md inline-flex items-center gap-1.5 cursor-pointer"
              >
                <Send className="w-3.5 h-3.5" />
                <span>{dispatching ? 'Synthesizing...' : 'Simulate Inbound Clearance (D7140)'}</span>
              </button>
            </div>
          ) : (
            <div className="space-y-2">
              {requests.map((req) => {
                const isSelected = String(req.request_id) === String(selectedRequest?.request_id);
                const status = req.status || 'TRANSMITTED_TO_INBOX';
                const isApproved = status.includes('APPROVED');
                const isRejected = status === 'REJECTED';

                return (
                  <div
                    key={req.request_id}
                    onClick={() => {
                      setSelectedRequestId(req.request_id);
                      setConfirmationBadge(null);
                    }}
                    className={`p-3.5 rounded-lg border text-left cursor-pointer transition-all ${
                      isSelected
                        ? 'bg-blue-950/70 border-blue-500/80 shadow-md ring-1 ring-blue-400/30'
                        : 'bg-slate-800/60 border-slate-700/80 hover:bg-slate-800 hover:border-slate-600'
                    }`}
                  >
                    <div className="flex items-start justify-between gap-2 mb-1.5">
                      <div className="font-semibold text-sm text-white flex items-center gap-1.5">
                        <HeartPulse className="w-4 h-4 text-rose-400 shrink-0" />
                        <span>{req.patient_demographics?.name || 'Patient'}</span>
                      </div>
                      <span
                        className={`text-[10px] font-bold px-2 py-0.5 rounded-full border tracking-wide uppercase ${
                          isApproved
                            ? 'bg-emerald-950/80 text-emerald-300 border-emerald-500/40'
                            : isRejected
                            ? 'bg-rose-950/80 text-rose-300 border-rose-500/40'
                            : 'bg-amber-950/80 text-amber-300 border-amber-500/40 animate-pulse'
                        }`}
                      >
                        {status.replace(/_/g, ' ')}
                      </span>
                    </div>

                    <div className="text-xs text-slate-300 mb-1 flex items-center justify-between">
                      <span>Procedure: CDT <strong className="text-blue-300 font-mono">D7140</strong></span>
                      <span className="text-slate-400 text-[11px] font-mono">{req.patient_demographics?.mrn || 'MRN-10001'}</span>
                    </div>

                    <div className="text-[11px] text-slate-400 line-clamp-2 italic">
                      "{req.clinical_justification || 'High bleeding hazard; Warfarin anticoagulation therapy review required.'}"
                    </div>

                    <div className="mt-2.5 pt-2 border-t border-slate-700/60 flex items-center justify-between text-[10px] text-slate-400 font-mono">
                      <span>Task: task-clearance-{String(req.request_id).slice(0, 8)}</span>
                      <span className="text-blue-400 flex items-center gap-0.5">
                        <span>Review</span>
                        <ChevronRight className="w-3 h-3" />
                      </span>
                    </div>
                  </div>
                );
              })}
            </div>
          )}

          {/* Quick Info Box */}
          <div className="p-3 bg-slate-800/40 rounded-lg border border-slate-700/60 text-slate-400 text-xs">
            <div className="font-semibold text-slate-300 flex items-center gap-1.5 mb-1">
              <Lock className="w-3.5 h-3.5 text-blue-400" />
              <span>Direct FHIR Clinical Endpoint</span>
            </div>
            <p className="text-[11px] leading-relaxed">
              Clearance requests arrive via HL7 FHIR R4 <code className="text-blue-300">CommunicationRequest</code> and <code className="text-blue-300">Task</code> payloads dispatched by the MDIN ConceptMap rule engine.
            </p>
          </div>
        </div>

        {/* Right: Clearance Request Review Card & Interactive Decision Form (lg:col-span-8) */}
        <div className="lg:col-span-8 p-5 sm:p-6 bg-slate-900 flex flex-col justify-between space-y-6">
          {errorMsg && (
            <div className="p-3 rounded-lg bg-rose-950/80 border border-rose-600/50 text-rose-200 text-xs flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 text-rose-400 shrink-0" />
              <span>{errorMsg}</span>
            </div>
          )}

          {selectedRequest ? (
            <div className="space-y-6">
              {/* Clearance Request Review Card */}
              <div className="bg-slate-800/90 rounded-xl border border-slate-700 p-5 shadow-lg space-y-4">
                {/* Header Row */}
                <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-3 border-b border-slate-700/80 gap-2">
                  <div>
                    <span className="text-[10px] uppercase font-bold tracking-wider text-blue-400 font-mono">
                      INBOUND CLEARANCE PASSPORT #{String(selectedRequest.request_id).slice(0, 8)}
                    </span>
                    <h2 className="text-lg font-bold text-white flex items-center gap-2 mt-0.5">
                      <span>{selectedRequest.patient_demographics?.name || 'Patient'}</span>
                      <span className="text-xs font-normal text-slate-400">
                        (DOB: {selectedRequest.patient_demographics?.dob || '1968-04-12'} · MRN: {selectedRequest.patient_demographics?.mrn || 'MRN-10001'})
                      </span>
                    </h2>
                  </div>
                  <div className="text-right">
                    <span className="text-xs text-slate-400 block">CareStack Requesting Facility:</span>
                    <span className="text-xs font-semibold text-slate-200">
                      {selectedRequest.carestack_provider?.practice_name || 'CareStack Center for Advanced Dentistry'}
                    </span>
                  </div>
                </div>

                {/* Procedure & Requesting Clinician Details */}
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs bg-slate-900/60 p-3 rounded-lg border border-slate-700/60">
                  <div>
                    <span className="text-slate-400 block text-[11px]">Proposed Surgical Procedure:</span>
                    <span className="font-semibold text-blue-300 text-sm flex items-center gap-1.5 mt-0.5">
                      <Stethoscope className="w-4 h-4 text-blue-400" />
                      <span>CDT D7140 — Surgical Extraction (Tooth #30)</span>
                    </span>
                    <span className="text-[11px] text-slate-400 block mt-0.5">
                      Scheduled: 2026-09-22 09:30 AM · Operatory 1 (Surgical)
                    </span>
                  </div>
                  <div>
                    <span className="text-slate-400 block text-[11px]">Requesting Dental Surgeon:</span>
                    <span className="font-semibold text-slate-200 block mt-0.5">
                      {selectedRequest.carestack_provider?.dentist_name || 'Dr. Sarah Jenkins, DDS'}
                    </span>
                    <span className="text-[11px] text-slate-400 block font-mono">
                      NPI: {selectedRequest.carestack_provider?.npi || '1982736450'} · Phone: {selectedRequest.carestack_provider?.phone || '(555) 019-2830'}
                    </span>
                  </div>
                </div>

                {/* Clinical Rationale Banner (Active Warfarin & AFib) */}
                <div className="p-4 rounded-lg bg-gradient-to-r from-amber-950/40 via-slate-800 to-amber-950/20 border border-amber-500/40 space-y-2">
                  <div className="flex items-center gap-2 text-amber-300 text-xs font-bold uppercase tracking-wider">
                    <AlertTriangle className="w-4 h-4 text-amber-400" />
                    <span>ConceptMap Clinical Risk Rationale — Coagulation & Bleeding Hazard</span>
                  </div>
                  <p className="text-xs text-slate-200 leading-relaxed">
                    {selectedRequest.clinical_justification || (
                      <>
                        Patient is on active <strong>Warfarin Sodium 5 MG Daily</strong> (RxNorm: 855332) for confirmed{' '}
                        <strong>Atrial Fibrillation</strong> (ICD-10: I48.91). Scheduled surgical dental extraction carries a high
                        hemorrhage hazard. Attending cardiologist clearance required to specify pre-operative target INR thresholds
                        and anticoagulant maintenance protocol.
                      </>
                    )}
                  </p>
                  <div className="flex flex-wrap gap-2 pt-1 text-[11px]">
                    <span className="px-2 py-0.5 rounded bg-amber-500/20 text-amber-200 border border-amber-500/30 font-semibold">
                      Rx: Warfarin Sodium 5mg PO
                    </span>
                    <span className="px-2 py-0.5 rounded bg-blue-500/20 text-blue-200 border border-blue-500/30 font-semibold">
                      Dx: Atrial Fibrillation (I48.91)
                    </span>
                    <span className="px-2 py-0.5 rounded bg-rose-500/20 text-rose-200 border border-rose-500/30 font-semibold">
                      Risk: Critical Hemorrhage Hazard
                    </span>
                  </div>
                </div>

                {/* Requested Actions from Dentist */}
                <div className="text-xs space-y-1.5">
                  <span className="font-semibold text-slate-300 block">Requested Physician Actions:</span>
                  <ul className="grid grid-cols-1 sm:grid-cols-2 gap-1.5 text-slate-300 text-[11px]">
                    {(selectedRequest.requested_actions || [
                      'Review coagulation protocol',
                      'Specify target INR threshold',
                      'Authorize temporary cessation of anticoagulant if applicable',
                      'Confirm safe pre-procedural hemodynamic tolerance',
                    ]).map((action, idx) => (
                      <li key={idx} className="flex items-center gap-1.5 bg-slate-900/40 px-2 py-1 rounded border border-slate-700/50">
                        <Check className="w-3.5 h-3.5 text-blue-400 shrink-0" />
                        <span>{action}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              </div>

              {/* Interactive Decision Form */}
              <form onSubmit={handleSubmitDecision} className="bg-slate-800/90 rounded-xl border border-slate-700 p-5 shadow-lg space-y-4">
                <div className="flex items-center justify-between pb-2 border-b border-slate-700/80">
                  <h3 className="text-sm font-bold text-white flex items-center gap-2">
                    <FileCheck className="w-4 h-4 text-emerald-400" />
                    <span>Attending Cardiologist Sign-Off Directives</span>
                  </h3>
                  <span className="text-[11px] text-slate-400">Epic/Cerner Attestation</span>
                </div>

                {/* 3 Decision Radio Options */}
                <div className="space-y-2">
                  <label className="text-xs font-semibold text-slate-300 block">Clinical Sign-Off Determination:</label>
                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 text-xs">
                    {/* 1. Approve Standard */}
                    <label
                      className={`p-3 rounded-lg border cursor-pointer transition-all flex flex-col justify-between ${
                        decisionType === 'APPROVED'
                          ? 'bg-emerald-950/70 border-emerald-500 text-emerald-200 ring-1 ring-emerald-400/30'
                          : 'bg-slate-900/60 border-slate-700 text-slate-300 hover:bg-slate-800'
                      }`}
                    >
                      <div className="flex items-center gap-2 font-semibold">
                        <input
                          type="radio"
                          name="clearanceDecision"
                          value="APPROVED"
                          checked={decisionType === 'APPROVED'}
                          onChange={() => setDecisionType('APPROVED')}
                          className="text-emerald-500 focus:ring-emerald-400"
                        />
                        <span>Approve Clearance</span>
                      </div>
                      <span className="text-[11px] text-slate-400 mt-1">Standard Protocol (Hemodynamically Stable)</span>
                    </label>

                    {/* 2. Approve with Conditions */}
                    <label
                      className={`p-3 rounded-lg border cursor-pointer transition-all flex flex-col justify-between ${
                        decisionType === 'APPROVED_WITH_CONDITIONS'
                          ? 'bg-blue-950/70 border-blue-500 text-blue-200 ring-1 ring-blue-400/30'
                          : 'bg-slate-900/60 border-slate-700 text-slate-300 hover:bg-slate-800'
                      }`}
                    >
                      <div className="flex items-center gap-2 font-semibold">
                        <input
                          type="radio"
                          name="clearanceDecision"
                          value="APPROVED_WITH_CONDITIONS"
                          checked={decisionType === 'APPROVED_WITH_CONDITIONS'}
                          onChange={() => setDecisionType('APPROVED_WITH_CONDITIONS')}
                          className="text-blue-500 focus:ring-blue-400"
                        />
                        <span>Approve with Conditions</span>
                      </div>
                      <span className="text-[11px] text-blue-300/80 mt-1">Specific INR / Hemostatic Protocol (Recommended)</span>
                    </label>

                    {/* 3. Deny Clearance */}
                    <label
                      className={`p-3 rounded-lg border cursor-pointer transition-all flex flex-col justify-between ${
                        decisionType === 'REJECTED'
                          ? 'bg-rose-950/70 border-rose-500 text-rose-200 ring-1 ring-rose-400/30'
                          : 'bg-slate-900/60 border-slate-700 text-slate-300 hover:bg-slate-800'
                      }`}
                    >
                      <div className="flex items-center gap-2 font-semibold">
                        <input
                          type="radio"
                          name="clearanceDecision"
                          value="REJECTED"
                          checked={decisionType === 'REJECTED'}
                          onChange={() => setDecisionType('REJECTED')}
                          className="text-rose-500 focus:ring-rose-400"
                        />
                        <span>Deny Clearance</span>
                      </div>
                      <span className="text-[11px] text-slate-400 mt-1">High Risk - Reschedule Post-Stabilization</span>
                    </label>
                  </div>
                </div>

                {/* Dynamic Inputs when Approve with Conditions is selected */}
                {decisionType === 'APPROVED_WITH_CONDITIONS' && (
                  <div className="p-4 rounded-lg bg-blue-950/30 border border-blue-500/40 space-y-3 animate-fade-in text-xs">
                    <div className="flex items-center justify-between font-semibold text-blue-300">
                      <span>Conditional Parameters &amp; Hemostasis Directives</span>
                      <span className="text-[10px] uppercase tracking-wider text-blue-400 font-mono">ADA / AHA Aligned</span>
                    </div>

                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 items-center">
                      <div>
                        <label className="block text-slate-300 font-medium mb-1">Target Pre-Operative INR Range:</label>
                        <input
                          type="text"
                          value={targetInr}
                          onChange={(e) => setTargetInr(e.target.value)}
                          placeholder="2.0 - 2.5"
                          className="w-full bg-slate-900 border border-slate-600 rounded px-3 py-1.5 text-white font-mono focus:border-blue-400 focus:outline-none"
                        />
                        <span className="text-[10px] text-slate-400 block mt-0.5">
                          Standard safe extraction threshold: 2.0 – 2.5
                        </span>
                      </div>

                      {/* Hold Medication Toggle */}
                      <div className="p-2.5 bg-slate-900/80 rounded border border-slate-700">
                        <label className="flex items-start gap-2 cursor-pointer">
                          <input
                            type="checkbox"
                            checked={!holdMedication}
                            onChange={(e) => setHoldMedication(!e.target.checked)}
                            className="mt-0.5 text-blue-500 focus:ring-blue-400"
                          />
                          <span className="text-[11px] text-slate-200 leading-snug">
                            <strong>Do NOT discontinue Warfarin;</strong> maintain local hemostatic measures (Gelfoam + Tranexamic acid rinse).
                          </span>
                        </label>
                      </div>
                    </div>
                  </div>
                )}

                {/* Clinical Notes Textarea */}
                <div>
                  <label className="block text-xs font-semibold text-slate-300 mb-1">
                    Physician Clinical Notes &amp; Operatory Directives:
                  </label>
                  <textarea
                    rows={3}
                    value={physicianNotes}
                    onChange={(e) => setPhysicianNotes(e.target.value)}
                    className="w-full bg-slate-900 border border-slate-600 rounded-lg p-2.5 text-xs text-white placeholder-slate-500 focus:border-blue-400 focus:outline-none leading-relaxed"
                    placeholder="Enter instructions for dental surgery team..."
                  />
                </div>

                {/* Signature Attestation Field */}
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 items-end pt-2 border-t border-slate-700/80">
                  <div>
                    <label className="block text-[11px] text-slate-400 mb-1">Electronically Attested By:</label>
                    <input
                      type="text"
                      value={signerName}
                      onChange={(e) => setSignerName(e.target.value)}
                      className="w-full bg-slate-900 border border-slate-600 rounded px-3 py-1.5 text-xs text-slate-200 font-semibold focus:border-blue-400 focus:outline-none"
                    />
                  </div>

                  {/* Submission Button */}
                  <div className="text-right">
                    <button
                      type="submit"
                      disabled={submitting}
                      className="w-full sm:w-auto px-5 py-2.5 bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 text-white font-bold rounded-lg shadow-lg text-xs flex items-center justify-center gap-2 cursor-pointer transition-all disabled:opacity-50"
                    >
                      <Lock className="w-3.5 h-3.5" />
                      <span>{submitting ? 'Transmitting Sign-Off...' : 'Electronically Sign & Transmit to CareStack'}</span>
                    </button>
                  </div>
                </div>
              </form>

              {/* Real-time Confirmation Badge (Displayed on submission) */}
              {confirmationBadge && (
                <div className="p-4 bg-emerald-950/70 border border-emerald-500/60 rounded-xl shadow-lg space-y-2 animate-fade-in">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2 text-emerald-300 font-bold text-sm">
                      <CheckCircle2 className="w-5 h-5 text-emerald-400" />
                      <span>Medical Clearance Successfully Transmitted &amp; Acknowledged!</span>
                    </div>
                    <span className="text-[11px] font-mono text-emerald-400 bg-emerald-900/60 px-2 py-0.5 rounded border border-emerald-700/40">
                      HTTP 200 Acknowledged
                    </span>
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 text-xs text-slate-300 pt-1">
                    <div>
                      <span className="text-slate-400 block text-[11px]">Decision:</span>
                      <strong className="text-white">{confirmationBadge.decision.replace(/_/g, ' ')}</strong>
                    </div>
                    <div>
                      <span className="text-slate-400 block text-[11px]">Signed By:</span>
                      <strong className="text-white">{confirmationBadge.signed_by}</strong>
                    </div>
                    <div>
                      <span className="text-slate-400 block text-[11px]">Delivered At:</span>
                      <span className="font-mono text-slate-200">{confirmationBadge.timestamp}</span>
                    </div>
                  </div>

                  <div className="p-2.5 bg-slate-900/80 rounded border border-emerald-600/30 text-[11px] font-mono text-slate-300 space-y-1">
                    <div className="flex items-center justify-between">
                      <span className="text-slate-400">CareStack Webhook Target:</span>
                      <span className="text-blue-300">POST /api/carestack/patients/{patient?.id}/medical-clearance-status</span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-slate-400">Cryptographic Attestation Hash:</span>
                      <span className="text-emerald-400 font-bold">{confirmationBadge.signatureHash}</span>
                    </div>
                  </div>

                  <div className="flex items-center justify-between pt-1">
                    <p className="text-[11px] text-emerald-300/90">
                      CareStack chart alert appended: <em>"Cardiology Clearance Received: Target INR {confirmationBadge.targetInr}. Approved by Dr. Vance."</em>
                    </p>
                    {onSwitchToDentalView && (
                      <button
                        onClick={onSwitchToDentalView}
                        className="text-xs text-white font-bold bg-emerald-600 hover:bg-emerald-500 px-3 py-1 rounded transition-colors flex items-center gap-1 cursor-pointer"
                      >
                        <span>View in Dental Operatory</span>
                        <ArrowRight className="w-3.5 h-3.5" />
                      </button>
                    )}
                  </div>
                </div>
              )}
            </div>
          ) : (
            <div className="text-center py-20 text-slate-400">
              <p>Select a clearance task from the left queue to evaluate.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
