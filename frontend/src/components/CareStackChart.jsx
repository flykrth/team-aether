import React, { useEffect, useState } from 'react';
import {
  FileText,
  CheckCircle2,
  AlertTriangle,
  HeartPulse,
  Stethoscope,
  Loader2,
  User,
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
  routine: 'border-emerald-300 bg-emerald-50 text-emerald-800 hover:bg-emerald-100',
  invasive: 'border-amber-300 bg-amber-50 text-amber-800 hover:bg-amber-100',
  'high-bleed': 'border-red-300 bg-red-50 text-red-800 hover:bg-red-100',
  severe: 'border-red-400 bg-red-100 text-red-900 hover:bg-red-200',
};

const ALERT_BANNER_STYLES = {
  critical: 'border-red-300 bg-red-50 text-red-900',
  warning: 'border-amber-300 bg-amber-50 text-amber-900',
  info: 'border-blue-300 bg-blue-50 text-blue-900',
};

/**
 * Simulated CareStack Dental PMS chairside workspace: patient selector, demographic
 * header, CDT procedure toolbar (odontogram stand-in), and a live medical alerts banner
 * synchronized from the federated Medical EHR. Selecting a procedure fires the
 * `order-select` CDS Hook against the MDIN backend in real time.
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
      <div className="p-6 text-center text-sm text-slate-500 bg-white rounded-xl border border-slate-200">
        Loading CareStack patients…
      </div>
    );
  }

  return (
    <div className="bg-white rounded-xl border border-slate-200 shadow-sm">
      {/* Patient Selector */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 px-5 py-4 border-b border-slate-100">
        <div className="flex items-center gap-2">
          <User className="w-4 h-4 text-sky-600" />
          <label htmlFor="carestack-patient-select" className="text-xs font-semibold text-slate-600 uppercase tracking-wider">
            Patient:
          </label>
        </div>
        <select
          id="carestack-patient-select"
          value={selectedPatient.id}
          onChange={(e) => onSelectPatient(e.target.value)}
          className="bg-slate-50 border border-slate-300 text-slate-900 text-sm rounded-lg focus:ring-sky-500 focus:border-sky-500 p-2 font-medium flex-1 sm:flex-none"
        >
          {patients.map((p) => (
            <option key={p.id} value={p.id}>
              {p.first_name} {p.last_name} — {p.id}
            </option>
          ))}
        </select>
      </div>

      {/* Demographic Header */}
      <div className="px-5 py-4 bg-slate-50/70 border-b border-slate-100">
        <div className="flex items-center gap-4">
          <div className="w-12 h-12 rounded-full bg-white flex items-center justify-center text-slate-600 border border-slate-200 font-bold text-lg shrink-0">
            {selectedPatient.first_name[0]}
            {selectedPatient.last_name[0]}
          </div>
          <div>
            <h3 className="text-lg font-bold text-slate-900">
              {selectedPatient.first_name} {selectedPatient.last_name}
            </h3>
            <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-slate-500 mt-1">
              <span>DOB: {selectedPatient.birth_date}</span>
              <span>•</span>
              <span>
                MRN: <strong className="text-teal-700">{selectedPatient.mrn}</strong>
              </span>
              <span>•</span>
              <span>
                CareStack Account #: <strong className="text-sky-700">{selectedPatient.id}</strong>
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Live Medical Alerts Banner */}
      <div className="px-5 py-4 border-b border-slate-100">
        <span className="text-[11px] font-bold uppercase tracking-wider text-slate-500 block mb-2">
          Live Medical Alerts (Synced from External EHR)
        </span>
        {alertsLoading ? (
          <div className="flex items-center gap-2 text-xs text-slate-400">
            <Loader2 className="w-3.5 h-3.5 animate-spin" /> Checking chart…
          </div>
        ) : alerts.length > 0 ? (
          <div className="space-y-2">
            {alerts.map((a) => (
              <div
                key={a.alert_id}
                className={`text-xs px-3 py-2 rounded-lg border font-medium ${
                  ALERT_BANNER_STYLES[a.alert_type] || ALERT_BANNER_STYLES.info
                }`}
              >
                {a.title}
              </div>
            ))}
          </div>
        ) : (
          <div className="text-xs text-slate-400 italic flex items-center gap-1.5">
            <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500" />
            No medical alerts posted to this chart yet.
          </div>
        )}
      </div>

      {/* Procedure Selection Toolbar */}
      <div className="px-5 py-4">
        <div className="flex items-center gap-2 mb-3">
          <FileText className="w-4 h-4 text-slate-600" />
          <span className="text-[11px] font-bold uppercase tracking-wider text-slate-500">
            Odontogram · CDT Procedure Selection
          </span>
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
                className={`flex items-center gap-2 px-3 py-2.5 rounded-lg border text-left text-xs font-medium transition-all disabled:opacity-60 ${
                  TIER_STYLES[proc.tier]
                } ${isActive ? 'ring-2 ring-offset-1 ring-slate-900' : ''}`}
              >
                <Icon className="w-4 h-4 shrink-0" />
                <span>
                  <span className="font-mono font-bold">{proc.code}</span> — {proc.label}
                </span>
                {isActive && hookLoading && <Loader2 className="w-3.5 h-3.5 animate-spin ml-auto" />}
              </button>
            );
          })}
        </div>
        <p className="text-[10px] text-slate-400 mt-2">
          Selecting a procedure fires the <code className="font-mono">order-select</code> CDS Hook against the MDIN
          engine in real time.
        </p>
      </div>
    </div>
  );
}
