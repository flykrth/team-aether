/**
 * MDIN Frontend API Client.
 * Connects to FastAPI backend (/health, /api/carestack, /api/fhir, /cds-services).
 */

const API_BASE = import.meta.env.VITE_API_BASE_URL || '';

async function fetchJson(endpoint, options = {}) {
  const url = `${API_BASE}${endpoint}`;
  try {
    const res = await fetch(url, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...options.headers,
      },
    });
    if (!res.ok) {
      const error = new Error(`HTTP ${res.status}: ${res.statusText}`);
      try {
        const body = await res.json();
        if (typeof body?.detail === 'string') error.detail = body.detail;
      } catch { /* non-JSON error body */ }
      throw error;
    }
    return await res.json();
  } catch (err) {
    console.error(`API Error for ${endpoint}:`, err);
    throw err;
  }
}

export const api = {
  // Patient Records (add patients, medical history, import previous records)
  listRecordPatients: () => fetchJson('/api/records/patients'),
  createRecordPatient: (payload) => fetchJson('/api/records/patients', { method: 'POST', body: JSON.stringify(payload) }),
  getPatientRecord: (patientId) => fetchJson(`/api/records/patients/${encodeURIComponent(patientId)}`),
  addHistoryEntries: (patientId, entries, source = 'manual') =>
    fetchJson(`/api/records/patients/${encodeURIComponent(patientId)}/history`, {
      method: 'POST',
      body: JSON.stringify({ entries, source }),
    }),
  extractRecordText: (text) => fetchJson('/api/records/extract', { method: 'POST', body: JSON.stringify({ text }) }),
  importPreviousRecord: (patientId, payload) =>
    fetchJson(`/api/records/patients/${encodeURIComponent(patientId)}/import`, {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  // Dental Coverage Recovery
  getCoverageSources: (region = 'US') => fetchJson(`/api/coverage/sources?region=${region}`),
  refreshCoverageSources: (region = 'US') => fetchJson(`/api/coverage/sources/refresh?region=${region}`, { method: 'POST' }),
  getInsurance: (patientId) => fetchJson(`/api/coverage/patients/${encodeURIComponent(patientId)}/insurance`),
  setInsurance: (patientId, payload) =>
    fetchJson(`/api/coverage/patients/${encodeURIComponent(patientId)}/insurance`, { method: 'PUT', body: JSON.stringify(payload) }),
  uploadPlanDocument: async (patientId, file) => {
    const form = new FormData();
    form.append('file', file, file.name);
    form.append('title', file.name);
    const res = await fetch(`${API_BASE}/api/coverage/patients/${encodeURIComponent(patientId)}/plan-document`, { method: 'POST', body: form });
    const body = await res.json().catch(() => ({}));
    if (!res.ok) {
      const error = new Error(`HTTP ${res.status}`);
      error.detail = typeof body?.detail === 'string' ? body.detail : undefined;
      throw error;
    }
    return body;
  },
  removePlanDocument: (patientId) =>
    fetchJson(`/api/coverage/patients/${encodeURIComponent(patientId)}/plan-document`, { method: 'DELETE' }),
  analyzeCoverage: (payload) => fetchJson('/api/coverage/analyze', { method: 'POST', body: JSON.stringify(payload) }),
  makeCoveragePacket: (patientId, reviewedBy) =>
    fetchJson('/api/coverage/packet', { method: 'POST', body: JSON.stringify({ patient_id: patientId, reviewed_by: reviewedBy }) }),

  // Manual mode: editable chart, file ingestion, risk check
  getPatientChart: (patientId) => fetchJson(`/api/records/patients/${encodeURIComponent(patientId)}/chart`),
  deleteRecordPatient: (patientId) => fetchJson(`/api/records/patients/${encodeURIComponent(patientId)}`, { method: 'DELETE' }),
  updatePatient: (patientId, changes) =>
    fetchJson(`/api/records/patients/${encodeURIComponent(patientId)}`, { method: 'PATCH', body: JSON.stringify(changes) }),
  updateHistoryEntry: (patientId, resourceId, changes) =>
    fetchJson(`/api/records/patients/${encodeURIComponent(patientId)}/history/${encodeURIComponent(resourceId)}`, {
      method: 'PATCH',
      body: JSON.stringify(changes),
    }),
  deleteHistoryEntry: (patientId, resourceId) =>
    fetchJson(`/api/records/patients/${encodeURIComponent(patientId)}/history/${encodeURIComponent(resourceId)}`, { method: 'DELETE' }),
  extractRecordFile: async (file) => {
    const form = new FormData();
    form.append('file', file, file.name);
    const res = await fetch(`${API_BASE}/api/records/extract-file`, { method: 'POST', body: form });
    const body = await res.json().catch(() => ({}));
    if (!res.ok) {
      const error = new Error(`HTTP ${res.status}`);
      error.detail = typeof body?.detail === 'string' ? body.detail : undefined;
      throw error;
    }
    return body;
  },
  riskCheck: (payload) => fetchJson('/api/risk/check', { method: 'POST', body: JSON.stringify(payload) }),
  getRiskProcedures: () => fetchJson('/api/risk/procedures'),
  validateRiskInput: (field, text) => fetchJson('/api/risk/validate-input', { method: 'POST', body: JSON.stringify({ field, text }) }),

  // Speech-to-text for voice control (multipart upload, so no JSON content-type)
  transcribeAudio: async (blob, filename = 'voice.webm') => {
    const form = new FormData();
    form.append('file', blob, filename);
    const res = await fetch(`${API_BASE}/api/assistant/transcribe`, { method: 'POST', body: form });
    const body = await res.json().catch(() => ({}));
    if (!res.ok) {
      const error = new Error(`HTTP ${res.status}`);
      error.detail = typeof body?.detail === 'string' ? body.detail : undefined;
      throw error;
    }
    return body;
  },

  // MAO Assistant (Gemini chat agent)
  getAssistantStatus: () => fetchJson('/api/assistant/status'),
  assistantChat: (messages, patientId, attachments = []) =>
    fetchJson('/api/assistant/chat', {
      method: 'POST',
      body: JSON.stringify({ messages, patient_id: patientId || null, attachments }),
    }),

  // Multi-Agent Orchestrator (MAO)
  getAgentsStatus: () => fetchJson('/api/agents/status'),
  getAgentState: (patientId) => fetchJson(`/api/agents/state/${encodeURIComponent(patientId)}`),
  submitAgentEvent: (payload) =>
    fetchJson('/api/agents/events', { method: 'POST', body: JSON.stringify(payload) }),
  sendClearanceResponse: (patientId, text) =>
    fetchJson(`/api/agents/clearance-response/${encodeURIComponent(patientId)}`, {
      method: 'POST',
      body: JSON.stringify({ text }),
    }),
  checkAgentEscalations: (hours) =>
    fetchJson(`/api/agents/check-escalations${hours ? `?hours_since_dispatch=${hours}` : ''}`, { method: 'POST' }),
  agentStreamUrl: (patientId) => `${API_BASE}/api/agents/stream/${encodeURIComponent(patientId)}`,

  // Health & System
  getHealth: () => fetchJson('/health'),
  getRoot: () => fetchJson('/'),

  // CareStack PMS
  getCareStackStatus: () => fetchJson('/api/carestack/status'),
  getCareStackPatients: (query = '') =>
    fetchJson(`/api/carestack/patients${query ? `?search=${encodeURIComponent(query)}` : ''}`),
  syncCareStack: (patientId, syncDirection = 'bidirectional') =>
    fetchJson('/api/carestack/sync', {
      method: 'POST',
      body: JSON.stringify({
        patient_id: patientId,
        sync_direction: syncDirection,
      }),
    }),

  // FHIR R4 Medical (Connected to HL7 Public Test Server)
  getFhirMetadata: () => fetchJson('/api/fhir/metadata'),
  getFhirServerStatus: () => fetchJson('/api/fhir/server-status'),
  getFhirPatients: () => fetchJson('/api/fhir/Patient'),
  getFhirPatient: (idOrMrn) => fetchJson(`/api/fhir/Patient/${encodeURIComponent(idOrMrn)}`),
  getFhirConditions: (patientId) =>
    fetchJson(`/api/fhir/Condition${patientId ? `?patient=${encodeURIComponent(patientId)}` : ''}`),
  getFhirMedications: (patientId) =>
    fetchJson(`/api/fhir/MedicationRequest${patientId ? `?patient=${encodeURIComponent(patientId)}` : ''}`),
  getFhirObservations: (patientId) =>
    fetchJson(`/api/fhir/Observation${patientId ? `?patient=${encodeURIComponent(patientId)}` : ''}`),
  getFhirAllergies: (patientId) =>
    fetchJson(`/api/fhir/AllergyIntolerance${patientId ? `?patient=${encodeURIComponent(patientId)}` : ''}`),

  // FHIR ConceptMap Semantic Translation
  translateConcept: (system, code, target) =>
    fetchJson('/api/fhir/ConceptMap/$translate', {
      method: 'POST',
      body: JSON.stringify({ system, code, target }),
    }),

  // CDS Hooks
  getCdsServices: () => fetchJson('/cds-services'),
  evaluateRiskHook: (patientId, serviceId = 'med-dental-risk-evaluator') =>
    fetchJson(`/cds-services/${serviceId}`, {
      method: 'POST',
      body: JSON.stringify({
        hook: 'patient-view',
        hookInstance: `ui-${Date.now()}`,
        context: { patientId },
      }),
    }),
  evaluateOrderSelectHook: (patientId, procedureCode) =>
    fetchJson('/cds-services/order-select-contraindication', {
      method: 'POST',
      body: JSON.stringify({
        hook: 'order-select',
        hookInstance: `ui-order-${Date.now()}`,
        context: { patientId, procedureCode, selections: [procedureCode] },
      }),
    }),

  // CareStack Chart Write-Backs & Webhook Sync
  postMedicalAlert: (patientId, alert) =>
    fetchJson(`/api/carestack/patients/${encodeURIComponent(patientId)}/medical-alerts`, {
      method: 'POST',
      body: JSON.stringify(alert),
    }),
  getPatientMedicalAlerts: (patientId) =>
    fetchJson(`/api/carestack/patients/${encodeURIComponent(patientId)}/medical-alerts`),
  simulateWebhookCheckin: (patient) =>
    fetchJson('/api/carestack/webhook', {
      method: 'POST',
      body: JSON.stringify({
        event_type: 'patient.checkin',
        patient: {
          id: patient.id,
          first_name: patient.first_name,
          last_name: patient.last_name,
          birth_date: patient.birth_date,
          gender: patient.gender,
          mrn: patient.mrn,
        },
      }),
    }),

  // Medical Cross-Coding & Claims Billing (Step 8)
  evaluateBillingClaim: (patientId, cdtCode, conditions = null, demographics = null) =>
    fetchJson('/api/billing/evaluate-claim', {
      method: 'POST',
      body: JSON.stringify({
        patient_id: patientId,
        cdt_code: cdtCode,
        ...(conditions ? { conditions } : {}),
        ...(demographics ? { demographics } : {}),
      }),
    }),
  getBillingCrosswalkRules: () => fetchJson('/api/billing/crosswalk-rules'),
  generate837P: (claim) =>
    fetchJson('/api/billing/generate-837p', {
      method: 'POST',
      body: JSON.stringify(claim),
    }),

  // Letter of Medical Necessity (LOMN) & CareStack Document Ingestion (Step 9)
  generateAndAttachLOMN: (patientId, cdtCode) =>
    fetchJson('/api/billing/generate-and-attach-lomn', {
      method: 'POST',
      body: JSON.stringify({
        patient_id: patientId,
        cdt_code: cdtCode,
      }),
    }),
  getCareStackDocuments: (patientId) =>
    fetchJson(`/api/carestack/patients/${encodeURIComponent(patientId)}/documents`),
  attachCareStackDocument: (patientId, docPayload) =>
    fetchJson(`/api/carestack/patients/${encodeURIComponent(patientId)}/documents`, {
      method: 'POST',
      body: JSON.stringify(docPayload),
    }),

  // Medical Clearance Passport & Physician Review Portal (Step 11 & 12)
  dispatchClearance: (patientId, cdtCode = 'D7140', carestackData = null, ehrData = null) =>
    fetchJson('/api/clearance/dispatch', {
      method: 'POST',
      body: JSON.stringify({
        patient_id: patientId,
        cdt_code: cdtCode,
        ...(carestackData ? { carestack_data: carestackData } : {}),
        ...(ehrData ? { ehr_data: ehrData } : {}),
      }),
    }),
  getPatientClearances: (patientId) =>
    fetchJson(`/api/clearance/patient/${encodeURIComponent(patientId)}`),
  getClearanceById: (requestId) =>
    fetchJson(`/api/clearance/${encodeURIComponent(requestId)}`),
  submitClearanceDecision: (requestId, decisionPayload) =>
    fetchJson(`/api/clearance/${encodeURIComponent(requestId)}/decision`, {
      method: 'POST',
      body: JSON.stringify(decisionPayload),
    }),
  getCareStackMedicalClearanceStatus: (patientId) =>
    fetchJson(`/api/carestack/patients/${encodeURIComponent(patientId)}/medical-clearance-status`),
};

