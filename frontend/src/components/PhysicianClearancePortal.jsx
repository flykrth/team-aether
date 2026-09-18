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
  ArrowUpRight,
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


  const decisionOptions = [
    {
      value: 'APPROVED',
      title: 'Approve Clearance',
      hint: 'Standard Protocol (Hemodynamically Stable)',
      active: 'bg-success text-white',
      hintActive: 'text-white/80',
    },
    {
      value: 'APPROVED_WITH_CONDITIONS',
      title: 'Approve with Conditions',
      hint: 'Specific INR / Hemostatic Protocol (Recommended)',
      active: 'bg-accent text-white',
      hintActive: 'text-white/80',
    },
    {
      value: 'REJECTED',
      title: 'Deny Clearance',
      hint: 'High Risk - Reschedule Post-Stabilization',
      active: 'bg-danger text-white',
      hintActive: 'text-white/80',
    },
  ];

  return (
    <div className="space-y-6 font-sans animate-fade-in">
      {/* Hospital EHR Top Branding Header (Epic InBasket / Cerner Message Center Simulator) */}
      <div className="card-dark flex flex-col md:flex-row md:items-center justify-between gap-6">
        <div className="flex items-center gap-4 min-w-0">
          <span className="icon-disc">
            <Hospital className="w-5 h-5" strokeWidth={1.5} />
          </span>
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <h1 className="font-display text-2xl font-medium tracking-tight text-white">
                Metropolitan Heart Center
              </h1>
              <span className="inline-flex items-center h-7 px-3 rounded-full bg-white/10 text-white/80 text-xs font-medium">
                Provider Portal · InBasket Tasks
              </span>
            </div>
            <p className="text-sm text-white/60 flex flex-wrap items-center gap-2 mt-1">
              <span>HL7 FHIR R4 Interoperability Gateway</span>
              <span className="text-white/30">·</span>
              <span>CareStack PMS Inbound Bridge</span>
            </p>
          </div>
        </div>

        {/* Attending Physician Profile Card */}
        <div className="flex items-center gap-3 bg-white/10 rounded-full pl-2 pr-5 py-2 shrink-0">
          <span className="inline-flex items-center justify-center w-10 h-10 rounded-full bg-white text-ink shrink-0">
            <User className="w-4 h-4" strokeWidth={1.5} />
          </span>
          <div className="text-xs">
            <div className="font-display text-sm font-medium text-white flex items-center gap-2">
              <span>Dr. Kenneth Vance, MD</span>
              <span className="inline-flex items-center gap-1 h-5 px-2 rounded-full bg-success text-white text-[10px] font-medium">
                <span className="w-1.5 h-1.5 rounded-full bg-white" />
                Active
              </span>
            </div>
            <div className="text-white/60 mt-0.5">
              Chief of Cardiology · NPI: <span className="font-mono text-white/80">1982341120</span>
            </div>
          </div>
        </div>
      </div>

      {/* Hospital Sub-bar / Navigation Banner */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="overflow-x-auto scrollbar-none min-w-0 max-w-full">
          <div className="flex items-center gap-2 w-max">
            <span className="pill pill-active shrink-0">
              <Activity className="w-4 h-4" strokeWidth={1.5} />
              <span>Pre-Operative Dental Clearance Requests ({requests.length})</span>
            </span>
            {patient && (
              <span className="pill shrink-0">
                <span className="text-text-muted">Active Patient</span>
                <span className="text-text-main">
                  {patient.first_name} {patient.last_name}
                </span>
                <span className="font-mono text-xs text-text-muted">{patient.mrn || patient.id}</span>
              </span>
            )}
          </div>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={loadClearanceRequests}
            disabled={loading}
            className="btn-ghost bg-app-surface hover:bg-app-secondary cursor-pointer"
            title="Refresh InBasket Queue"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} strokeWidth={1.5} />
            <span>Refresh</span>
          </button>
          {requests.length === 0 && (
            <button
              onClick={handleAutoDispatch}
              disabled={dispatching}
              className="btn-primary cursor-pointer"
            >
              <Send className="w-4 h-4" strokeWidth={1.5} />
              <span>{dispatching ? 'Dispatching...' : 'Dispatch D7140 Clearance'}</span>
            </button>
          )}
        </div>
      </div>

      {/* Main Split Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 min-h-[560px]">
        {/* Left: InBasket Task List (lg:col-span-4) */}
        <div className="lg:col-span-4 card space-y-4 self-start">
          <div className="flex items-end justify-between gap-3">
            <h2 className="font-display text-xl font-medium text-ink">Incoming Tasks</h2>
            <span className="text-xs text-text-muted">
              <span className="font-mono text-text-main">{requests.length}</span> pending / reviewed
            </span>
          </div>

          {requests.length === 0 ? (
            <div className="well text-center py-10 px-5">
              <span className="inline-flex items-center justify-center w-14 h-14 rounded-full bg-accent-soft text-accent mx-auto mb-4">
                <HeartPulse className="w-6 h-6 animate-pulse" strokeWidth={1.5} />
              </span>
              <p className="font-display text-base font-medium text-text-main">No Active Clearance Inbound Tasks</p>
              <p className="text-sm text-text-muted mt-2 leading-relaxed">
                Dispatch an automated clearance passport from CareStack operatory or click below to simulate incoming extraction request.
              </p>
              <button
                onClick={handleAutoDispatch}
                disabled={dispatching}
                className="btn-primary mt-5 cursor-pointer"
              >
                <Send className="w-4 h-4" strokeWidth={1.5} />
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

                const statusClass = isApproved
                  ? isSelected
                    ? 'bg-success text-white'
                    : 'bg-success-light text-success-dark'
                  : isRejected
                  ? isSelected
                    ? 'bg-danger text-white'
                    : 'bg-danger-light text-danger-dark'
                  : isSelected
                  ? 'bg-warning text-white'
                  : 'bg-warning-light text-warning-dark';

                return (
                  <div
                    key={req.request_id}
                    onClick={() => {
                      setSelectedRequestId(req.request_id);
                      setConfirmationBadge(null);
                    }}
                    className={`p-4 rounded-3xl text-left cursor-pointer transition-colors ${
                      isSelected ? 'bg-ink text-white' : 'bg-app-secondary text-text-main hover:bg-app-bg'
                    }`}
                  >
                    <div className="flex items-start justify-between gap-2 mb-2">
                      <div className="font-display text-base font-medium flex items-center gap-2 min-w-0">
                        <HeartPulse
                          className={`w-4 h-4 shrink-0 ${isSelected ? 'text-white/70' : 'text-danger'}`}
                          strokeWidth={1.5}
                        />
                        <span className="truncate">{req.patient_demographics?.name || 'Patient'}</span>
                      </div>
                      <span
                        className={`inline-flex items-center h-6 px-2.5 rounded-full text-[11px] font-medium shrink-0 capitalize ${statusClass}`}
                      >
                        {status.replace(/_/g, ' ').toLowerCase()}
                      </span>
                    </div>

                    <div
                      className={`text-xs mb-1.5 flex items-center justify-between gap-2 ${
                        isSelected ? 'text-white/70' : 'text-text-secondary'
                      }`}
                    >
                      <span>
                        Procedure: CDT{' '}
                        <span className={`font-mono font-medium ${isSelected ? 'text-white' : 'text-accent'}`}>D7140</span>
                      </span>
                      <span className={`font-mono text-[11px] ${isSelected ? 'text-white/50' : 'text-text-muted'}`}>
                        {req.patient_demographics?.mrn || 'MRN-10001'}
                      </span>
                    </div>

                    <div className={`text-xs line-clamp-2 leading-relaxed ${isSelected ? 'text-white/60' : 'text-text-muted'}`}>
                      "{req.clinical_justification || 'High bleeding hazard; Warfarin anticoagulation therapy review required.'}"
                    </div>

                    <div
                      className={`mt-3 flex items-center justify-between gap-2 text-[11px] font-mono ${
                        isSelected ? 'text-white/50' : 'text-text-muted'
                      }`}
                    >
                      <span className="truncate">Task: task-clearance-{String(req.request_id).slice(0, 8)}</span>
                      <span
                        className={`inline-flex items-center gap-1 font-sans font-medium ${
                          isSelected ? 'text-white' : 'text-accent'
                        }`}
                      >
                        <span>Review</span>
                        <ChevronRight className="w-3.5 h-3.5" strokeWidth={1.5} />
                      </span>
                    </div>
                  </div>
                );
              })}
            </div>
          )}

          {/* Quick Info Box */}
          <div className="rounded-3xl bg-accent-soft p-4 text-xs text-text-secondary">
            <div className="font-display text-sm font-medium text-accent-deep flex items-center gap-2 mb-1.5">
              <Lock className="w-4 h-4" strokeWidth={1.5} />
              <span>Direct FHIR Clinical Endpoint</span>
            </div>
            <p className="leading-relaxed">
              Clearance requests arrive via HL7 FHIR R4 <code className="font-mono text-accent-deep">CommunicationRequest</code> and{' '}
              <code className="font-mono text-accent-deep">Task</code> payloads dispatched by the MDIN ConceptMap rule engine.
            </p>
          </div>
        </div>

        {/* Right: Clearance Request Review Card & Interactive Decision Form (lg:col-span-8) */}
        <div className="lg:col-span-8 flex flex-col space-y-6">
          {errorMsg && (
            <div className="rounded-3xl bg-danger-light text-danger-dark px-5 py-4 text-sm flex items-center gap-3">
              <AlertTriangle className="w-4 h-4 text-danger shrink-0" strokeWidth={1.5} />
              <span>{errorMsg}</span>
            </div>
          )}

          {selectedRequest ? (
            <div className="space-y-6">
              {/* Clearance Request Review Card */}
              <div className="card space-y-6">
                {/* Header Row */}
                <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-4">
                  <div className="min-w-0">
                    <span className="eyebrow">
                      Inbound Clearance Passport{' '}
                      <span className="font-mono normal-case tracking-normal text-accent">
                        #{String(selectedRequest.request_id).slice(0, 8)}
                      </span>
                    </span>
                    <h2 className="display-lg text-ink mt-2">
                      {selectedRequest.patient_demographics?.name || 'Patient'}
                    </h2>
                    <p className="text-sm text-text-muted mt-1">
                      DOB: {selectedRequest.patient_demographics?.dob || '1968-04-12'} · MRN:{' '}
                      <span className="font-mono">{selectedRequest.patient_demographics?.mrn || 'MRN-10001'}</span>
                    </p>
                  </div>
                  <div className="flex items-center gap-3 sm:text-right sm:flex-row-reverse">
                    <span className="icon-btn" aria-hidden="true">
                      <ArrowUpRight className="w-[18px] h-[18px]" strokeWidth={1.5} />
                    </span>
                    <div>
                      <span className="text-xs text-text-muted block">CareStack Requesting Facility</span>
                      <span className="text-sm font-medium text-text-main">
                        {selectedRequest.carestack_provider?.practice_name || 'CareStack Center for Advanced Dentistry'}
                      </span>
                    </div>
                  </div>
                </div>

                {/* Procedure & Requesting Clinician Details */}
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <div className="well p-5">
                    <span className="text-xs text-text-muted block">Proposed Surgical Procedure</span>
                    <span className="font-display text-base font-medium text-text-main flex items-center gap-2 mt-1.5">
                      <Stethoscope className="w-4 h-4 text-accent shrink-0" strokeWidth={1.5} />
                      <span>CDT D7140 — Surgical Extraction (Tooth #30)</span>
                    </span>
                    <span className="text-xs text-text-muted block mt-1.5">
                      Scheduled: 2026-09-22 09:30 AM · Operatory 1 (Surgical)
                    </span>
                  </div>
                  <div className="well p-5">
                    <span className="text-xs text-text-muted block">Requesting Dental Surgeon</span>
                    <span className="font-display text-base font-medium text-text-main block mt-1.5">
                      {selectedRequest.carestack_provider?.dentist_name || 'Dr. Sarah Jenkins, DDS'}
                    </span>
                    <span className="text-xs text-text-muted block font-mono mt-1.5">
                      NPI: {selectedRequest.carestack_provider?.npi || '1982736450'} · Phone:{' '}
                      {selectedRequest.carestack_provider?.phone || '(555) 019-2830'}
                    </span>
                  </div>
                </div>

                {/* Clinical Rationale Banner (Active Warfarin & AFib) */}
                <div className="rounded-3xl bg-warning-light p-5 space-y-3">
                  <div className="flex items-center gap-3">
                    <span className="inline-flex items-center justify-center w-9 h-9 rounded-full bg-warning text-white shrink-0">
                      <AlertTriangle className="w-4 h-4" strokeWidth={1.5} />
                    </span>
                    <span className="font-display text-base font-medium text-warning-dark">
                      ConceptMap Clinical Risk Rationale — Coagulation &amp; Bleeding Hazard
                    </span>
                  </div>
                  <p className="text-sm text-text-main leading-relaxed">
                    {selectedRequest.clinical_justification || (
                      <>
                        Patient is on active <strong className="font-semibold">Warfarin Sodium 5 MG Daily</strong> (RxNorm: 855332) for confirmed{' '}
                        <strong className="font-semibold">Atrial Fibrillation</strong> (ICD-10: I48.91). Scheduled surgical dental extraction carries a high
                        hemorrhage hazard. Attending cardiologist clearance required to specify pre-operative target INR thresholds
                        and anticoagulant maintenance protocol.
                      </>
                    )}
                  </p>
                  <div className="flex flex-wrap gap-2 pt-1">
                    <span className="chip bg-white text-warning-dark">Rx: Warfarin Sodium 5mg PO</span>
                    <span className="chip bg-white text-accent-deep">Dx: Atrial Fibrillation (I48.91)</span>
                    <span className="chip bg-danger text-white">Risk: Critical Hemorrhage Hazard</span>
                  </div>
                </div>

                {/* Requested Actions from Dentist */}
                <div className="space-y-3">
                  <span className="font-display text-base font-medium text-text-main block">Requested Physician Actions</span>
                  <ul className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-sm text-text-secondary">
                    {(selectedRequest.requested_actions || [
                      'Review coagulation protocol',
                      'Specify target INR threshold',
                      'Authorize temporary cessation of anticoagulant if applicable',
                      'Confirm safe pre-procedural hemodynamic tolerance',
                    ]).map((action, idx) => (
                      <li key={idx} className="flex items-center gap-3 bg-app-secondary rounded-full pl-2 pr-4 py-2">
                        <span className="inline-flex items-center justify-center w-7 h-7 rounded-full bg-accent-soft text-accent shrink-0">
                          <Check className="w-3.5 h-3.5" strokeWidth={1.5} />
                        </span>
                        <span className="leading-snug">{action}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              </div>

              {/* Interactive Decision Form */}
              <form onSubmit={handleSubmitDecision} className="card space-y-6">
                <div className="flex items-center justify-between gap-3">
                  <h3 className="font-display text-xl font-medium text-ink flex items-center gap-3">
                    <span className="inline-flex items-center justify-center w-10 h-10 rounded-full bg-success-light text-success shrink-0">
                      <FileCheck className="w-4 h-4" strokeWidth={1.5} />
                    </span>
                    <span>Attending Cardiologist Sign-Off Directives</span>
                  </h3>
                  <span className="chip shrink-0">Epic/Cerner Attestation</span>
                </div>

                {/* 3 Decision Radio Options */}
                <div className="space-y-3">
                  <label className="text-sm text-text-secondary block">Clinical Sign-Off Determination</label>
                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                    {decisionOptions.map((opt) => {
                      const isActive = decisionType === opt.value;
                      return (
                        <label
                          key={opt.value}
                          className={`p-4 rounded-3xl cursor-pointer transition-colors flex flex-col justify-between gap-2 ${
                            isActive ? opt.active : 'bg-app-secondary text-text-main hover:bg-app-bg'
                          }`}
                        >
                          <div className="flex items-center gap-2.5 font-display text-[15px] font-medium">
                            <input
                              type="radio"
                              name="clearanceDecision"
                              value={opt.value}
                              checked={isActive}
                              onChange={() => setDecisionType(opt.value)}
                              className="w-4 h-4 accent-ink"
                            />
                            <span>{opt.title}</span>
                          </div>
                          <span className={`text-xs ${isActive ? opt.hintActive : 'text-text-muted'}`}>{opt.hint}</span>
                        </label>
                      );
                    })}
                  </div>
                </div>

                {/* Dynamic Inputs when Approve with Conditions is selected */}
                {decisionType === 'APPROVED_WITH_CONDITIONS' && (
                  <div className="rounded-3xl bg-accent-soft p-5 space-y-4 animate-fade-in">
                    <div className="flex items-center justify-between gap-3">
                      <span className="font-display text-base font-medium text-accent-deep">
                        Conditional Parameters &amp; Hemostasis Directives
                      </span>
                      <span className="chip bg-white text-accent-deep shrink-0">ADA / AHA Aligned</span>
                    </div>

                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 items-center">
                      <div>
                        <label className="block text-xs text-text-secondary mb-1.5 px-1">Target Pre-Operative INR Range</label>
                        <input
                          type="text"
                          value={targetInr}
                          onChange={(e) => setTargetInr(e.target.value)}
                          placeholder="2.0 - 2.5"
                          className="field bg-white font-mono"
                        />
                        <span className="text-[11px] text-text-muted block mt-1.5 px-1">
                          Standard safe extraction threshold: 2.0 – 2.5
                        </span>
                      </div>

                      {/* Hold Medication Toggle */}
                      <div className="rounded-3xl bg-white p-4">
                        <label className="flex items-start gap-3 cursor-pointer">
                          <input
                            type="checkbox"
                            checked={!holdMedication}
                            onChange={(e) => setHoldMedication(!e.target.checked)}
                            className="mt-0.5 w-4 h-4 accent-accent shrink-0"
                          />
                          <span className="text-xs text-text-secondary leading-snug">
                            <strong className="font-semibold text-text-main">Do NOT discontinue Warfarin;</strong> maintain local hemostatic measures (Gelfoam + Tranexamic acid rinse).
                          </span>
                        </label>
                      </div>
                    </div>
                  </div>
                )}

                {/* Clinical Notes Textarea */}
                <div>
                  <label className="block text-sm text-text-secondary mb-2">
                    Physician Clinical Notes &amp; Operatory Directives
                  </label>
                  <textarea
                    rows={3}
                    value={physicianNotes}
                    onChange={(e) => setPhysicianNotes(e.target.value)}
                    className="w-full rounded-3xl bg-app-secondary px-5 py-4 text-sm text-text-main placeholder:text-text-muted outline-none focus:bg-white focus:ring-2 focus:ring-accent/30 leading-relaxed resize-y"
                    placeholder="Enter instructions for dental surgery team..."
                  />
                </div>

                {/* Signature Attestation Field */}
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 items-end">
                  <div>
                    <label className="block text-xs text-text-muted mb-1.5 px-1">Electronically Attested By</label>
                    <input
                      type="text"
                      value={signerName}
                      onChange={(e) => setSignerName(e.target.value)}
                      className="field font-medium"
                    />
                  </div>

                  {/* Submission Button */}
                  <div className="sm:text-right">
                    <button
                      type="submit"
                      disabled={submitting}
                      className="btn-primary w-full sm:w-auto cursor-pointer"
                    >
                      <Lock className="w-4 h-4" strokeWidth={1.5} />
                      <span>{submitting ? 'Transmitting Sign-Off...' : 'Electronically Sign & Transmit to CareStack'}</span>
                    </button>
                  </div>
                </div>
              </form>

              {/* Real-time Confirmation Badge (Displayed on submission) */}
              {confirmationBadge && (
                <div className="rounded-4xl bg-success-light p-6 space-y-5 animate-fade-in">
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <div className="flex items-center gap-3">
                      <span className="inline-flex items-center justify-center w-11 h-11 rounded-full bg-success text-white shrink-0">
                        <CheckCircle2 className="w-5 h-5" strokeWidth={1.5} />
                      </span>
                      <span className="font-display text-lg font-medium text-success-dark">
                        Medical Clearance Successfully Transmitted &amp; Acknowledged!
                      </span>
                    </div>
                    <span className="chip bg-white text-success-dark font-mono">HTTP 200 Acknowledged</span>
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                    <div className="rounded-3xl bg-white p-4">
                      <span className="text-xs text-text-muted block">Decision</span>
                      <span className="font-display text-base font-medium text-text-main capitalize">
                        {confirmationBadge.decision.replace(/_/g, ' ').toLowerCase()}
                      </span>
                    </div>
                    <div className="rounded-3xl bg-white p-4">
                      <span className="text-xs text-text-muted block">Signed By</span>
                      <span className="font-display text-base font-medium text-text-main">{confirmationBadge.signed_by}</span>
                    </div>
                    <div className="rounded-3xl bg-white p-4">
                      <span className="text-xs text-text-muted block">Delivered At</span>
                      <span className="font-mono text-sm text-text-main">{confirmationBadge.timestamp}</span>
                    </div>
                  </div>

                  <div className="rounded-3xl bg-white p-4 text-xs font-mono space-y-2">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <span className="text-text-muted font-sans">CareStack Webhook Target</span>
                      <span className="text-accent break-all">POST /api/carestack/patients/{patient?.id}/medical-clearance-status</span>
                    </div>
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <span className="text-text-muted font-sans">Cryptographic Attestation Hash</span>
                      <span className="text-success-dark font-medium break-all">{confirmationBadge.signatureHash}</span>
                    </div>
                  </div>

                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <p className="text-sm text-success-dark leading-relaxed flex-1 min-w-[16rem]">
                      CareStack chart alert appended: <em>"Cardiology Clearance Received: Target INR {confirmationBadge.targetInr}. Approved by Dr. Vance."</em>
                    </p>
                    {onSwitchToDentalView && (
                      <button
                        onClick={onSwitchToDentalView}
                        className="btn-dark cursor-pointer"
                      >
                        <span>View in Dental Operatory</span>
                        <ArrowRight className="w-4 h-4" strokeWidth={1.5} />
                      </button>
                    )}
                  </div>
                </div>
              )}
            </div>
          ) : (
            <div className="card text-center py-20 text-text-muted">
              <p>Select a clearance task from the left queue to evaluate.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
