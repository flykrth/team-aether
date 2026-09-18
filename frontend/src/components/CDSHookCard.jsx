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
  ArrowUpRight,
} from 'lucide-react';
import { api } from '../services/api';

const INDICATOR_STYLES = {
  critical: {
    dark: true,
    wrapper: 'card-dark',
    badge: 'bg-white/10 text-white/80',
    disc: 'bg-danger text-white',
    icon: AlertTriangle,
    label: 'Critical clinical hazard',
  },
  warning: {
    dark: false,
    wrapper: 'card',
    badge: 'bg-warning-light text-warning-dark',
    disc: 'bg-warning text-white',
    icon: HeartPulse,
    label: 'Clinical review required',
  },
  info: {
    dark: false,
    wrapper: 'card',
    badge: 'bg-accent-soft text-accent-deep',
    disc: 'bg-accent text-white',
    icon: Info,
    label: 'Clinical informational',
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
      <div key={i} className={`flex gap-2.5 pl-1 text-sm ${textColor} leading-relaxed`}>
        <span aria-hidden="true" className="opacity-60">•</span>
        <span>{parts}</span>
      </div>
    ) : (
      <p key={i} className={`text-sm ${textColor} leading-relaxed`}>{parts}</p>
    );
  });
}

/**
 * Enterprise CareStack CDS Hooks v1.0 & Step 10 Dual Decision Card Component:
 * - Card Type A: Clinical Safety Card (Red/Amber/Blue for contraindications & clinical hazards).
 * - Card Type B: Administrative Opportunity Card (electric-blue accent theme for medical cross-coding & financial optimization).
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
  // CARD TYPE B: Administrative Opportunity Card (Accent Theme)
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
      <div className="card-accent p-7 mb-4 last:mb-0 animate-fade-in">
        {/* Opportunity Card Header */}
        <div className="flex items-start justify-between gap-4">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2 mb-4">
              <span className="inline-flex items-center gap-1.5 h-7 px-3 rounded-full bg-white text-accent-deep text-xs font-medium">
                <Sparkles className="w-3.5 h-3.5" strokeWidth={1.5} />
                Financial Optimization
              </span>
              <span className="inline-flex items-center h-7 px-3 rounded-full bg-white/15 text-white/90 text-xs font-medium">
                Medical Cross-Coding
              </span>
            </div>
            <h3 className="font-display text-2xl font-medium leading-tight tracking-tight text-white">
              Medical Cross-Coding Opportunity Identified
            </h3>
          </div>
          <span className="icon-btn-white text-accent">
            <TrendingUp className="w-5 h-5" strokeWidth={1.5} />
          </span>
        </div>

        {/* Reimbursement Summary Banner */}
        <div className="mt-6 flex flex-wrap items-end justify-between gap-3">
          <div>
            <span className="text-sm text-white/70 block mb-1">Estimated Medical Reimbursement</span>
            <span className="font-display text-4xl font-medium tracking-tight text-white leading-none">
              {summaryText}
            </span>
          </div>
          <span className="inline-flex items-center h-7 px-3 rounded-full bg-white/15 text-white text-xs font-medium">
            Primary Medical Payer
          </span>
        </div>

        {/* Code Cross-Walk Pill Badges */}
        <div className="mt-6 rounded-3xl bg-white/10 p-4">
          <div className="text-sm text-white/70 mb-3 flex items-center gap-1.5">
            <Link2 className="w-4 h-4" strokeWidth={1.5} />
            <span>Code Cross-Walk Pathway</span>
          </div>
          <div className="flex flex-wrap items-center gap-2 text-sm">
            <span className="inline-flex items-center gap-1.5 h-9 px-4 rounded-full bg-white/15 text-white font-mono">
              <span className="text-[11px] font-sans text-white/60">CDT</span>
              <span>{cdtCode}</span>
            </span>

            <ArrowRight className="w-4 h-4 text-white/60 shrink-0" strokeWidth={1.5} />

            <span className="inline-flex items-center gap-1.5 h-9 px-4 rounded-full bg-white text-accent-deep font-mono">
              <span className="text-[11px] font-sans text-accent/70">CPT</span>
              <span>{cptCode}</span>
            </span>

            <span className="text-white/60 text-xs px-1">linked via</span>

            <span className="inline-flex items-center gap-1.5 h-9 px-4 rounded-full bg-white/15 text-white font-mono">
              <span className="text-[11px] font-sans text-white/60">ICD-10</span>
              <span>{icd10Primary}</span>
            </span>
          </div>
        </div>

        {/* Narrative Clinical Justification */}
        {card.detail && (
          <div className="mt-5 space-y-1">
            {renderDetailMarkdown(card.detail, 'text-white/85')}
          </div>
        )}

        {/* Verified Source Attribution */}
        <div className="mt-5 flex flex-wrap items-center justify-between gap-2 text-xs text-white/70">
          <span className="flex items-center gap-1.5">
            <ShieldCheck className="w-4 h-4 shrink-0" strokeWidth={1.5} />
            <span>
              Source:{' '}
              <span className="text-white font-medium">
                {card.source?.label || 'CareStack Administrative Cross-Coding Engine'}
              </span>
            </span>
          </span>
          <span className="font-mono text-white/50">ConceptMap CDT to CPT</span>
        </div>

        {/* Action Button: Launch Financial Optimization Dashboard */}
        <div className="mt-6 flex flex-wrap items-center justify-between gap-3">
          <span className="text-xs text-white/70">
            Ready for CMS-1500 generation & 837P EDI
          </span>
          <button
            onClick={() => onOpenFinancialDashboard?.(card)}
            className="group inline-flex items-center gap-3 h-12 pl-5 pr-1.5 rounded-full bg-white text-ink font-display font-semibold text-[15px] hover:bg-app-secondary cursor-pointer"
          >
            <FileSpreadsheet className="w-4 h-4 text-accent" strokeWidth={1.5} />
            <span>Open Financial Optimization Dashboard</span>
            <span className="inline-flex items-center justify-center w-9 h-9 rounded-full bg-ink text-white">
              <ArrowUpRight className="w-4 h-4" strokeWidth={1.5} />
            </span>
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

  const isDark = style.dark;

  return (
    <div className={`${style.wrapper} p-7 mb-4 last:mb-0 animate-fade-in`}>
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <span className={`inline-flex items-center h-7 px-3 rounded-full text-xs font-medium mb-4 ${style.badge}`}>
            {style.label}
          </span>
          <h3 className={`font-display text-2xl font-medium leading-tight tracking-tight ${isDark ? 'text-white' : 'text-text-main'}`}>
            {card.summary}
          </h3>
        </div>
        <span className={`inline-flex items-center justify-center w-12 h-12 rounded-full shrink-0 ${style.disc}`}>
          <Icon className="w-5 h-5" strokeWidth={1.5} />
        </span>
      </div>

      {card.detail && (
        <div className="mt-5 space-y-1">
          {renderDetailMarkdown(card.detail, isDark ? 'text-white/80' : 'text-text-secondary')}
        </div>
      )}

      {/* Verified Source Attribution */}
      {card.source && (
        <div
          className={`mt-5 flex flex-wrap items-center justify-between gap-2 rounded-2xl px-4 py-3 text-xs ${
            isDark ? 'bg-white/5 text-white/60' : 'bg-app-secondary text-text-secondary'
          }`}
        >
          <span className="flex items-center gap-1.5">
            <ShieldCheck className={`w-4 h-4 shrink-0 ${isDark ? 'text-white/70' : 'text-accent'}`} strokeWidth={1.5} />
            <span>
              Source: <span className={`font-medium ${isDark ? 'text-white' : 'text-text-main'}`}>{card.source.label}</span>
            </span>
          </span>
          <span className={`font-mono ${isDark ? 'text-white/40' : 'text-text-muted'}`}>HL7 FHIR R4 Engine</span>
        </div>
      )}

      {/* Step 13: Dedicated Digital Clearance Passport Action Block for Critical Contradictions */}
      {isCriticalClearanceCard && (
        <div
          className={`mt-4 rounded-3xl p-5 flex flex-col sm:flex-row sm:items-center justify-between gap-4 ${
            isDark ? 'bg-white/5' : 'bg-app-secondary'
          }`}
        >
          <div className="flex items-start gap-3 min-w-0">
            <span
              className={`inline-flex items-center justify-center w-10 h-10 rounded-full shrink-0 ${
                isDark ? 'bg-white/10 text-white' : 'bg-accent-soft text-accent-deep'
              }`}
            >
              <Send className="w-4 h-4" strokeWidth={1.5} />
            </span>
            <div className="min-w-0">
              <div className={`font-display font-semibold text-[15px] ${isDark ? 'text-white' : 'text-text-main'}`}>
                Automated Pre-Screening Clearance Gateway
              </div>
              <p className={`text-xs mt-1 leading-relaxed ${isDark ? 'text-white/60' : 'text-text-secondary'}`}>
                {clearanceDispatched
                  ? 'Passport Dispatched to Dr. Kenneth Vance (Metropolitan Heart Center) via FHIR Task'
                  : 'Bridge to Attending Cardiologist via HL7 FHIR R4 Task & CommunicationRequest'}
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2 shrink-0">
            {clearanceDispatched ? (
              <span className="inline-flex items-center gap-1.5 h-9 px-4 rounded-full text-xs font-medium bg-warning-light text-warning-dark animate-pulse">
                <Clock className="w-4 h-4" strokeWidth={1.5} />
                <span>Awaiting Physician Clearance</span>
              </span>
            ) : (
              <button
                type="button"
                onClick={handleDispatchClearance}
                disabled={dispatchingClearance}
                className={`inline-flex items-center gap-2 h-11 px-5 rounded-full font-display font-semibold text-sm cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed ${
                  isDark ? 'bg-accent text-white hover:bg-accent-deep' : 'bg-ink text-white hover:bg-ink-soft'
                }`}
              >
                {dispatchingClearance ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" strokeWidth={1.5} />
                    <span>Transmitting FHIR Task…</span>
                  </>
                ) : (
                  <>
                    <Send className="w-4 h-4" strokeWidth={1.5} />
                    <span>Dispatch Digital Clearance Passport</span>
                  </>
                )}
              </button>
            )}
          </div>
        </div>
      )}

      {/* Clinical Workflow Action Buttons */}
      <div className="mt-6 flex flex-wrap items-center gap-2">
        {onViewEvidence && (
          <button
            onClick={() => onViewEvidence(card)}
            className={`inline-flex items-center gap-2 h-11 pl-5 pr-1.5 rounded-full font-display font-medium text-[15px] ${
              isDark ? 'bg-white/10 text-white hover:bg-white/15' : 'bg-app-secondary text-text-main hover:bg-app-bg'
            }`}
          >
            <span>View Evidence</span>
            <span className={`inline-flex items-center justify-center w-8 h-8 rounded-full ${isDark ? 'bg-white text-ink' : 'bg-ink text-white'}`}>
              <ArrowUpRight className="w-4 h-4" strokeWidth={1.5} />
            </span>
          </button>
        )}
        <button
          onClick={handleAppendAlert}
          disabled={appending || appended || !onAppendAlert}
          className={`inline-flex items-center justify-center gap-2 h-11 px-5 rounded-full font-display font-semibold text-[15px] disabled:opacity-50 disabled:cursor-not-allowed ${
            isDark ? 'bg-white text-ink hover:bg-app-secondary' : 'bg-accent text-white hover:bg-accent-deep'
          }`}
        >
          {appended ? <CheckCircle2 className="w-4 h-4" strokeWidth={1.5} /> : null}
          {appended ? 'Medical Alert Appended to Chart' : appending ? 'Appending…' : 'Post Medical Alert to CareStack Chart'}
        </button>
        <button
          onClick={handleRequestConsult}
          disabled={requestingConsult || consultRequested || !onRequestConsult}
          className={`inline-flex items-center justify-center gap-2 h-11 px-5 rounded-full font-display font-medium text-[15px] disabled:opacity-50 disabled:cursor-not-allowed ${
            isDark ? 'bg-white/10 text-white hover:bg-white/15' : 'bg-app-secondary text-text-main hover:bg-app-bg'
          }`}
        >
          {consultRequested ? (
            <CheckCircle2 className="w-4 h-4 text-success" strokeWidth={1.5} />
          ) : (
            <Stethoscope className={`w-4 h-4 ${isDark ? 'text-white/70' : 'text-accent'}`} strokeWidth={1.5} />
          )}
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
