import React, { useState } from 'react';
import {
  AlertTriangle,
  ShieldCheck,
  Info,
  HeartPulse,
  CheckCircle2,
  Stethoscope,
  ArrowRight,
  TrendingUp,
  FileSpreadsheet,
  Link2,
  Sparkles,
  Send,
  Loader2,
  Clock,
} from 'lucide-react';
import { api } from '../services/api';

const INDICATOR_STYLES = {
  critical: {
    wrapper: 'border-danger/30 bg-danger-light text-danger-dark',
    badge: 'bg-danger text-white font-bold',
    icon: AlertTriangle,
    iconColor: 'text-danger',
    label: 'CRITICAL CLINICAL HAZARD',
  },
  warning: {
    wrapper: 'border-warning/40 bg-warning-light text-warning-dark',
    badge: 'bg-warning text-white font-bold',
    icon: HeartPulse,
    iconColor: 'text-warning-dark',
    label: 'CLINICAL REVIEW REQUIRED',
  },
  info: {
    wrapper: 'border-info/30 bg-info-light text-info-dark',
    badge: 'bg-info text-white font-bold',
    icon: Info,
    iconColor: 'text-info',
    label: 'CLINICAL INFORMATIONAL',
  },
};

/**
 * Very small markdown renderer for CDS detail text (supports bolding, bullet points, and line breaks).
 */
function renderDetailMarkdown(detail, textColor = 'text-text-main') {
  if (!detail) return null;
  const lines = detail.split('\n');
  return lines.map((line, i) => {
    const trimmed = line.trim();
    const isBullet = trimmed.startsWith('- ') || trimmed.startsWith('* ');
    const content = isBullet ? trimmed.slice(2) : trimmed;
    const parts = content.split(/(\*\*[^*]+\*\*)/g).map((chunk, j) =>
      chunk.startsWith('**') && chunk.endsWith('**') ? (
        <strong key={j} className={`font-semibold ${textColor}`}>
          {chunk.slice(2, -2)}
        </strong>
      ) : (
        <React.Fragment key={j}>{chunk}</React.Fragment>
      )
    );

    if (!trimmed) return <div key={i} className="h-1.5" />;

    return isBullet ? (
      <div key={i} className={`flex gap-2 pl-1 text-xs ${textColor} leading-relaxed`}>
        <span aria-hidden="true" className="opacity-60">•</span>
        <span>{parts}</span>
      </div>
    ) : (
      <p key={i} className={`text-xs ${textColor} leading-relaxed`}>{parts}</p>
    );
  });
}

/**
 * Enterprise CareStack CDS Hooks v1.0 & Step 10 Dual Decision Card Component:
 * - Card Type A: Clinical Safety Card (Red/Amber/Blue for contraindications & clinical hazards).
 * - Card Type B: Administrative Opportunity Card (Emerald/Green theme for medical cross-coding & financial optimization).
 */
export function CDSHookCard({
  card,
  patient,
  procedure,
  onAppendAlert,
  onRequestConsult,
  onClearanceDispatched,
  onViewEvidence,
  onOpenFinancialDashboard,
}) {
  const [appending, setAppending] = useState(false);
  const [appended, setAppended] = useState(false);
  const [requestingConsult, setRequestingConsult] = useState(false);
  const [consultRequested, setConsultRequested] = useState(false);
  const [dispatchingClearance, setDispatchingClearance] = useState(false);
  const [clearanceDispatched, setClearanceDispatched] = useState(false);

  // Determine if this is an Administrative Billing Opportunity Card (Card Type B)
  const isOpportunity =
    card.cardType === 'administrative' ||
    card.type === 'administrative' ||
    card.indicator === 'opportunity' ||
    card.isBillingOpportunity ||
    Boolean(card.opportunity);

  // ---------------------------------------------------------------------------
  // CARD TYPE B: Administrative Opportunity Card (Emerald Theme)
  // ---------------------------------------------------------------------------
  if (isOpportunity) {
    const opportunity = card.opportunity || {};
    const cdtCode = card.cdt_code || opportunity.cdt_code || 'D4341';
    const cptCode = card.cpt_code || opportunity.suggested_cpt || '41874';
    const icd10List = card.icd10_codes || opportunity.justifying_icd10 || ['E11.9'];
    const icd10Primary = card.icd10 || icd10List[0] || 'E11.9';
    const summaryText =
      card.summary ||
      (opportunity.estimated_coverage
        ? `Est. Medical Coverage: $${opportunity.estimated_coverage.toFixed(2)}`
        : 'Est. Medical Coverage: $400 - $800');

    return (
      <div className="rounded-lg border border-emerald-500 bg-emerald-50 text-emerald-900 p-4 mb-3 shadow-xs transition-all hover:shadow-md">
        {/* Opportunity Card Header */}
        <div className="flex items-start justify-between gap-3">
          <div className="flex items-start gap-2.5">
            <div className="mt-0.5 shrink-0 p-1 rounded-md bg-emerald-100 text-emerald-700 border border-emerald-300">
              <TrendingUp className="w-4 h-4" />
            </div>
            <div>
              <div className="flex items-center gap-1.5 mb-1">
                <span className="inline-flex items-center gap-1 text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded bg-emerald-600 text-white shadow-xs">
                  <Sparkles className="w-3 h-3" />
                  Financial Optimization
                </span>
                <span className="text-[10px] font-semibold text-emerald-700 bg-emerald-100/80 px-1.5 py-0.5 rounded border border-emerald-200">
                  Medical Cross-Coding
                </span>
              </div>
              <h3 className="font-bold text-sm text-emerald-950 leading-snug">
                Medical Cross-Coding Opportunity Identified
              </h3>
            </div>
          </div>
        </div>

        {/* Reimbursement Summary Banner */}
        <div className="mt-3 px-3 py-2 rounded-md bg-white border border-emerald-200 shadow-xs flex items-center justify-between">
          <div>
            <span className="text-[10px] font-bold uppercase tracking-wider text-emerald-700 block">
              Estimated Medical Reimbursement
            </span>
            <span className="text-sm font-extrabold text-emerald-900 font-mono">
              {summaryText}
            </span>
          </div>
          <span className="text-[11px] font-medium text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded border border-emerald-200">
            Primary Medical Payer
          </span>
        </div>

        {/* Code Cross-Walk Pill Badges */}
        <div className="mt-2.5 pt-2.5 border-t border-emerald-200/80">
          <div className="text-[10px] font-bold uppercase tracking-wider text-emerald-800 mb-1.5 flex items-center gap-1">
            <Link2 className="w-3 h-3 text-emerald-600" />
            <span>Code Cross-Walk Pathway</span>
          </div>
          <div className="flex flex-wrap items-center gap-1.5 text-xs">
            <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-md font-mono font-bold bg-white text-slate-800 border border-emerald-300 shadow-xs">
              <span className="text-[10px] font-sans font-semibold text-text-muted">CDT</span>
              <span>{cdtCode}</span>
            </span>

            <ArrowRight className="w-3.5 h-3.5 text-emerald-600 shrink-0" />

            <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-md font-mono font-bold bg-emerald-600 text-white shadow-xs">
              <span className="text-[10px] font-sans font-semibold text-emerald-100">CPT</span>
              <span>{cptCode}</span>
            </span>

            <span className="text-emerald-700 text-[11px] font-medium px-1">linked via</span>

            <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-md font-mono font-semibold bg-emerald-100 text-emerald-900 border border-emerald-300">
              <span className="text-[10px] font-sans font-semibold text-emerald-700">ICD-10</span>
              <span className="font-bold">{icd10Primary}</span>
            </span>
          </div>
        </div>

        {/* Narrative Clinical Justification */}
        {card.detail && (
          <div className="mt-2.5 pt-2 border-t border-emerald-200/60 text-xs text-emerald-900/90 leading-relaxed">
            {renderDetailMarkdown(card.detail, 'text-emerald-950')}
          </div>
        )}

        {/* Verified Source Attribution */}
        <div className="mt-3 flex items-center justify-between text-[11px] text-emerald-800 bg-white/70 px-2.5 py-1.5 rounded border border-emerald-200">
          <span className="flex items-center gap-1.5 font-medium">
            <ShieldCheck className="w-3.5 h-3.5 text-emerald-600 shrink-0" />
            <span>
              Source:{' '}
              <strong className="text-emerald-950 font-semibold">
                {card.source?.label || 'CareStack Administrative Cross-Coding Engine'}
              </strong>
            </span>
          </span>
          <span className="text-[10px] text-emerald-700 font-mono">ConceptMap CDT to CPT</span>
        </div>

        {/* Action Button: Launch Financial Optimization Dashboard */}
        <div className="mt-3 pt-2.5 border-t border-emerald-300/80 flex items-center justify-between">
          <span className="text-[11px] text-emerald-700 italic">
            Ready for CMS-1500 generation & 837P EDI
          </span>
          <button
            onClick={() => onOpenFinancialDashboard?.(card)}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded bg-emerald-600 text-white hover:bg-emerald-700 transition-colors shadow-xs cursor-pointer active:scale-98"
          >
            <FileSpreadsheet className="w-3.5 h-3.5" />
            <span>Open Financial Optimization Dashboard</span>
            <ArrowRight className="w-3.5 h-3.5 ml-0.5" />
          </button>
        </div>
      </div>
    );
  }

  // ---------------------------------------------------------------------------
  // CARD TYPE A: Clinical Safety Card (Red/Amber Theme)
  // ---------------------------------------------------------------------------
  const style = INDICATOR_STYLES[card.indicator] || INDICATOR_STYLES.info;
  const Icon = style.icon;

  const handleAppendAlert = async () => {
    if (!onAppendAlert || appending) return;
    setAppending(true);
    try {
      await onAppendAlert(card);
      setAppended(true);
    } finally {
      setAppending(false);
    }
  };

  const handleRequestConsult = async () => {
    if (!onRequestConsult || requestingConsult) return;
    setRequestingConsult(true);
    try {
      await onRequestConsult(card);
      setConsultRequested(true);
    } finally {
      setRequestingConsult(false);
    }
  };

  const isCriticalClearanceCard =
    card.indicator === 'critical' ||
    (card.summary && /warfarin|bleeding|anticoagulant|hemorrhage|clearance|inr/i.test(card.summary)) ||
    (card.detail && /warfarin|hemorrhage|coagulation/i.test(card.detail));

  const handleDispatchClearance = async () => {
    if (dispatchingClearance || clearanceDispatched) return;
    setDispatchingClearance(true);
    try {
      const patientId = patient?.id || patient?.mrn || 'CS-2001';
      const cdtCode = procedure?.code || card.cdt_code || 'D7140';
      const res = await api.dispatchClearance(patientId, cdtCode);
      setClearanceDispatched(true);
      onClearanceDispatched?.(res);
    } catch (err) {
      console.error('Failed to dispatch digital clearance passport:', err);
    } finally {
      setDispatchingClearance(false);
    }
  };

  return (
    <div className={`rounded-lg border p-4 mb-3 bg-app-surface shadow-xs transition-all ${style.wrapper}`}>
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-start gap-2.5">
          <div className="mt-0.5 shrink-0">
            <Icon className={`w-4 h-4 ${style.iconColor}`} />
          </div>
          <div>
            <span className={`inline-block text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded mb-1 ${style.badge}`}>
              {style.label}
            </span>
            <h3 className="font-semibold text-sm text-text-main leading-snug">{card.summary}</h3>
          </div>
        </div>
      </div>

      {card.detail && (
        <div className="mt-2.5 pt-2.5 border-t border-app-border/60 space-y-1">
          {renderDetailMarkdown(card.detail)}
        </div>
      )}

      {/* Verified Source Attribution */}
      {card.source && (
        <div className="mt-3 flex items-center justify-between text-[11px] text-text-secondary bg-app-bg px-2.5 py-1.5 rounded border border-app-border">
          <span className="flex items-center gap-1.5 font-medium">
            <ShieldCheck className="w-3.5 h-3.5 text-teal-500 shrink-0" />
            <span>Source: <strong className="text-text-main font-semibold">{card.source.label}</strong></span>
          </span>
          <span className="text-[10px] text-text-muted font-mono">HL7 FHIR R4 Engine</span>
        </div>
      )}

      {/* Step 13: Dedicated Digital Clearance Passport Action Block for Critical Contradictions */}
      {isCriticalClearanceCard && (
        <div className="mt-3.5 pt-3 border-t border-danger/30 bg-slate-900/40 p-3 rounded-lg border border-slate-700/60 flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs">
          <div>
            <div className="flex items-center gap-1.5 font-bold text-slate-100">
              <Send className="w-3.5 h-3.5 text-indigo-400" />
              <span>Automated Pre-Screening Clearance Gateway</span>
            </div>
            <p className="text-[11px] text-slate-300 mt-0.5">
              {clearanceDispatched
                ? 'Passport Dispatched to Dr. Kenneth Vance (Metropolitan Heart Center) via FHIR Task'
                : 'Bridge to Attending Cardiologist via HL7 FHIR R4 Task & CommunicationRequest'}
            </p>
          </div>

          <div className="flex items-center gap-2">
            {clearanceDispatched ? (
              <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-bold bg-amber-100 text-amber-900 border border-amber-300 animate-pulse shadow-xs">
                <Clock className="w-3.5 h-3.5 text-amber-700" />
                <span>Awaiting Physician Clearance</span>
              </span>
            ) : (
              <button
                type="button"
                onClick={handleDispatchClearance}
                disabled={dispatchingClearance}
                className="inline-flex items-center gap-2 px-3.5 py-1.5 text-xs font-bold rounded-lg bg-gradient-to-r from-indigo-600 to-blue-600 hover:from-indigo-500 hover:to-blue-500 text-white shadow-md transition-all cursor-pointer disabled:opacity-50 active:scale-98"
              >
                {dispatchingClearance ? (
                  <>
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    <span>Transmitting FHIR Task…</span>
                  </>
                ) : (
                  <>
                    <Send className="w-3.5 h-3.5 text-indigo-200" />
                    <span>Dispatch Digital Clearance Passport</span>
                  </>
                )}
              </button>
            )}
          </div>
        </div>
      )}

      {/* Clinical Workflow Action Buttons */}
      <div className="mt-3 pt-2.5 border-t border-app-border flex flex-wrap items-center gap-2">
        {onViewEvidence && (
          <button
            onClick={() => onViewEvidence(card)}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded bg-app-bg text-text-main border border-app-border hover:bg-app-secondary transition-colors"
          >
            <ShieldCheck className="w-3.5 h-3.5 text-teal-600" />
            <span>View Evidence</span>
          </button>
        )}
        <button
          onClick={handleAppendAlert}
          disabled={appending || appended || !onAppendAlert}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded bg-teal-500 text-white hover:bg-teal-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors shadow-xs"
        >
          {appended ? <CheckCircle2 className="w-3.5 h-3.5" /> : null}
          {appended ? 'Medical Alert Appended to Chart' : appending ? 'Appending…' : 'Post Medical Alert to CareStack Chart'}
        </button>
        <button
          onClick={handleRequestConsult}
          disabled={requestingConsult || consultRequested || !onRequestConsult}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded bg-white text-text-main border border-app-border hover:bg-app-secondary disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          {consultRequested ? <CheckCircle2 className="w-3.5 h-3.5 text-success" /> : <Stethoscope className="w-3.5 h-3.5 text-info" />}
          {consultRequested
            ? 'Physician Consult Requested'
            : requestingConsult
            ? 'Requesting…'
            : 'Request Physician Consult (INR)'}
        </button>
      </div>
    </div>
  );
}


