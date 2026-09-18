// Human labels for the quiet tool-activity chips shown above an answer.
export const TOOL_LABELS = {
  list_patients: 'Looked up the patient list',
  get_patient_history: 'Read patient history',
  assess_clinical_risk: 'Assessed clinical risk',
  get_agent_state: 'Checked agent workflow',
  run_agent_workflow: 'Ran the four agents',
  submit_physician_reply: 'Filed physician reply',
  check_clearance_escalations: 'Ran escalation sweep',
  post_chart_alert: 'Posted chart alert',
  create_patient: 'Created patient',
  get_patient_chart: 'Opened the chart',
  update_patient_details: 'Updated patient details',
  update_history_item: 'Edited a history item',
  remove_history_item: 'Removed a history item',
  add_medical_history: 'Added medical history',
  import_previous_record: 'Imported previous record',
  consult_specialists: 'Consulted specialists in parallel',
};

export const describeAction = ({ tool, args }) => {
  const name = [args?.first_name, args?.last_name].filter(Boolean).join(' ');
  const subject = [args?.patient_id, args?.cdt_code, name].filter(Boolean).join(' · ');
  return `${TOOL_LABELS[tool] || tool}${subject ? ` (${subject})` : ''}`;
};

export const PROVIDER_LABELS = { gemini: 'MAO AI', groq: 'MAO AI', nvidia: 'MAO AI', browser: 'Browser' };
export const providerLabel = (provider) => PROVIDER_LABELS[provider] || provider || '';
