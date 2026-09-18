import React from 'react';
import { PatientSummaryWidget } from './PatientSummaryWidget';
import { PatientListWidget } from './PatientListWidget';
import { RiskAssessmentWidget } from './RiskAssessmentWidget';
import { AgentWorkflowWidget } from './AgentWorkflowWidget';
import { PatientCreatedWidget } from './PatientCreatedWidget';
import { HistoryUpdatedWidget } from './HistoryUpdatedWidget';
import { SpecialistPanelWidget } from './SpecialistPanelWidget';
import { ChartAlertWidget } from './ChartAlertWidget';
import { CoverageResultWidget } from './CoverageResultWidget';
import { VisitStatusWidget } from './VisitStatusWidget';
import { FallbackWidget } from './FallbackWidget';
import { WidgetTone } from './parts';

export { WidgetTone };

// widget type (from POST /api/assistant/chat) -> component
export const WIDGET_REGISTRY = {
  patient_summary: PatientSummaryWidget,
  patient_list: PatientListWidget,
  risk_assessment: RiskAssessmentWidget,
  agent_workflow: AgentWorkflowWidget,
  patient_created: PatientCreatedWidget,
  history_updated: HistoryUpdatedWidget,
  specialist_panel: SpecialistPanelWidget,
  chart_alert: ChartAlertWidget,
  coverage_result: CoverageResultWidget,
  visit_status: VisitStatusWidget,
};

// Which tool produced each widget, to recover the call arguments from the turn's actions.
const WIDGET_TOOLS = { chart_alert: ['post_chart_alert'] };

// A malformed payload must never take the conversation down with it.
class WidgetBoundary extends React.Component {
  constructor(props) { super(props); this.state = { failed: false }; }
  static getDerivedStateFromError() { return { failed: true }; }
  render() { return this.state.failed ? <FallbackWidget {...this.props.widget} /> : this.props.children; }
}

/**
 * Renders one {type, title, data} widget. onAsk(text) prefills the composer; onOpenIntake(patientId) opens the records panel.
 * index = this widget's position among the turn's widgets of the same type: the i-th chart_alert widget belongs to
 * the i-th successful post_chart_alert action, never simply "the last one".
 */
export function AssistantWidget({ widget, actions, index = 0, onAsk, onOpenIntake }) {
  const Component = WIDGET_REGISTRY[widget?.type] || FallbackWidget;
  const tools = WIDGET_TOOLS[widget?.type] || [];
  const matching = (actions || []).filter((a) => tools.includes(a.tool) && a.ok !== false);
  const args = (matching[index] || matching[matching.length - 1])?.args;
  return (
    <WidgetBoundary widget={widget}>
      <Component type={widget.type} title={widget.title} data={widget.data} args={args} onAsk={onAsk} onOpenIntake={onOpenIntake} />
    </WidgetBoundary>
  );
}
