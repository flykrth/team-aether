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
      throw new Error(`HTTP ${res.status}: ${res.statusText}`);
    }
    return await res.json();
  } catch (err) {
    console.error(`API Error for ${endpoint}:`, err);
    throw err;
  }
}

export const api = {
  // Health & System
  getHealth: () => fetchJson('/health'),
  getRoot: () => fetchJson('/'),

  // CareStack PMS
  getCareStackStatus: () => fetchJson('/api/carestack/status'),
  getCareStackPatients: (query = '') =>
    fetchJson(`/api/carestack/patients${query ? `?search=${encodeURIComponent(query)}` : ''}`),
  getCareStackPatient: (id) => fetchJson(`/api/carestack/patients/${id}`),
  syncCareStack: (patientId, syncDirection = 'bidirectional') =>
    fetchJson('/api/carestack/sync', {
      method: 'POST',
      body: JSON.stringify({
        patient_id: patientId,
        sync_direction: syncDirection,
      }),
    }),

  // FHIR R4 Medical
  getFhirMetadata: () => fetchJson('/api/fhir/metadata'),
  getFhirPatients: () => fetchJson('/api/fhir/Patient'),
  getFhirConditions: (patientId) =>
    fetchJson(`/api/fhir/Condition${patientId ? `?patient=${encodeURIComponent(patientId)}` : ''}`),
  getFhirObservations: (patientId) =>
    fetchJson(`/api/fhir/Observation${patientId ? `?patient=${encodeURIComponent(patientId)}` : ''}`),
  getFhirAllergies: (patientId) =>
    fetchJson(`/api/fhir/AllergyIntolerance${patientId ? `?patient=${encodeURIComponent(patientId)}` : ''}`),

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
};
