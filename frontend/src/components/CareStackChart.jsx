import React, { useEffect, useState } from 'react';
import {
  FileText,
  CheckCircle2,
  AlertTriangle,
  HeartPulse,
  Stethoscope,
  Loader2,
  User,
  ShieldAlert,
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
export function CareStackChart({ patients, selectedPatient, onSelectPatient, onCardsUpdate, alertsVersion }) {
  const [selectedProcedure, setSelectedProcedure] = useState(null);
  const [hookLoading, setHookLoading] = useState(false);
  const [alerts, setAlerts] = useState([]);
  const [alertsLoading, setAlertsLoading] = useState(false);

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
      const response = await api.evaluateOrderSelectHook(selectedPatient.mrn, proc.code);
      onCardsUpdate?.(response.cards || [], proc);
    } catch (err) {
      console.error('order-select CDS Hook failed:', err);
      onCardsUpdate?.([], proc);
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
            <div className="flex flex-wrap items-center gap-x-3 gap-y-0.5 text-xs text-text-secondary mt-1">
              <span>DOB: <strong>{selectedPatient.birth_date}</strong></span>
              <span className="text-text-muted">•</span>
              <span>MRN: <strong className="text-teal-700">{selectedPatient.mrn}</strong></span>
              <span className="text-text-muted">•</span>
              <span>CareStack ID: <strong className="text-text-main">{selectedPatient.id}</strong></span>
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

