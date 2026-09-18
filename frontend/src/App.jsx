import React, { useCallback, useEffect, useState } from 'react';
import { Sparkles, SlidersHorizontal, Users, Route, Hospital, Terminal } from 'lucide-react';
import { AssistantWorkspace } from './components/assistant/AssistantWorkspace';
import { PatientIntakePanel } from './components/records/PatientIntakePanel';
import { PatientsView } from './components/manual/PatientsView';
import { VisitView } from './components/visit/VisitView';
import { PhysicianClearancePortal } from './components/PhysicianClearancePortal';
import { DeveloperConsole } from './components/DeveloperConsole';
import { api } from './services/api';

const VIEWS = [
  { id: 'patients', label: 'Patients', Icon: Users },
  { id: 'visit', label: 'Visit', Icon: Route },
  { id: 'physician', label: 'Physician portal', Icon: Hospital },
];

const remember = (key, fallback) => { try { return localStorage.getItem(key) || fallback; } catch { return fallback; } };
const store = (key, value) => { try { localStorage.setItem(key, value); } catch { /* private mode */ } };

// One instance for both modes, at one position: the thumb slides instead of the control remounting.
function ModeSwitch({ mode, onChange }) {
  const options = [['agentic', 'Agentic', Sparkles], ['manual', 'Manual', SlidersHorizontal]];
  return (
    <div className="relative grid grid-cols-2 p-1 rounded-full bg-app-surface w-[232px]" role="tablist" aria-label="Mode">
      <span
        aria-hidden="true"
        className="absolute top-1 bottom-1 left-1 w-[calc(50%-4px)] rounded-full bg-ink transition-transform duration-300 ease-[cubic-bezier(.3,.7,.2,1)]"
        style={{ transform: mode === 'manual' ? 'translateX(100%)' : 'translateX(0)' }}
      />
      {options.map(([id, label, Icon]) => (
        <button key={id} role="tab" aria-selected={mode === id} onClick={() => onChange(id)}
          className={`relative z-10 inline-flex items-center justify-center gap-2 h-9 rounded-full text-sm font-display font-medium transition-colors duration-300 ${mode === id ? 'text-white' : 'text-text-secondary hover:text-text-main'}`}>
          <Icon className="w-4 h-4" strokeWidth={1.5} /> {label}
        </button>
      ))}
    </div>
  );
}

const Wordmark = () => (
  <span className="font-display text-[26px] font-medium tracking-tight text-ink leading-none">MDIN<span className="text-accent">.</span></span>
);

export function App() {
  const [mode, setMode] = useState(() => remember('mdin.mode', 'agentic'));
  const [view, setView] = useState(() => { const v = remember('mdin.view', 'patients'); return ['agents', 'risk', 'coverage'].includes(v) ? 'visit' : v; });
  const [riskPatientId, setRiskPatientId] = useState(null);
  const [patients, setPatients] = useState([]);       // CareStack-shaped, for the physician portal + intake panel
  const [refreshKey, setRefreshKey] = useState(0);
  const [intake, setIntake] = useState({ open: false, patientId: null });
  const [showConsole, setShowConsole] = useState(false);

  const changeMode = (next) => { setMode(next); store('mdin.mode', next); };
  const changeView = (next) => { setView(next); store('mdin.view', next); };

  const loadPatients = useCallback(() => {
    api.getCareStackPatients().then((list) => setPatients(Array.isArray(list) ? list : [])).catch(() => setPatients([]));
  }, []);
  useEffect(() => { loadPatients(); }, [loadPatients, refreshKey]);

  const patientsChanged = useCallback(() => setRefreshKey((k) => k + 1), []);

  const intakePanel = (
    <PatientIntakePanel
      open={intake.open}
      onClose={() => setIntake({ open: false, patientId: null })}
      patients={patients}
      initialPatientId={intake.patientId}
      onChanged={patientsChanged}
    />
  );

  const modeSwitch = (
    <div className="absolute top-[22px] right-3 lg:top-[30px] lg:right-5 z-30">
      <ModeSwitch mode={mode} onChange={changeMode} />
    </div>
  );

  if (mode === 'agentic') {
    return (
      <div className="relative min-h-screen bg-app-bg text-text-main p-3 lg:p-5">
        {modeSwitch}
        <header className="flex items-center h-14 mb-2 px-2"><Wordmark /></header>
        <main key="agentic" className="max-w-[1100px] mx-auto animate-fade-in">
          <AssistantWorkspace
            patient={null}
            heightClass="h-[calc(100vh-7rem)]"
            onPatientsChanged={patientsChanged}
            onOpenIntake={(patientId) => setIntake({ open: true, patientId: patientId || null })}
          />
        </main>
        {intakePanel}
      </div>
    );
  }

  return (
    <div className="relative min-h-screen bg-app-bg text-text-main p-3 lg:p-5">
      {modeSwitch}
      <div key="manual" className="flex gap-4 lg:gap-5 animate-fade-in">
        {/* Icon rail */}
        <aside className="w-[60px] lg:w-[72px] shrink-0 sticky top-3 lg:top-5 h-[calc(100vh-1.5rem)] lg:h-[calc(100vh-2.5rem)] rounded-4xl bg-ink flex flex-col items-center py-5 gap-2">
          <span className="inline-flex items-center justify-center w-11 h-11 rounded-2xl bg-accent text-white font-display font-semibold mb-4">M</span>
          {VIEWS.map(({ id, label, Icon }) => (
            <button key={id} onClick={() => changeView(id)} title={label} aria-label={label} aria-current={view === id ? 'page' : undefined}
              className={`inline-flex items-center justify-center w-11 h-11 rounded-2xl transition-colors ${view === id ? 'bg-white text-ink' : 'text-white/50 hover:text-white hover:bg-white/10'}`}>
              <Icon className="w-5 h-5" strokeWidth={1.5} />
            </button>
          ))}
          <div className="flex-1" />
          <button onClick={() => setShowConsole((v) => !v)} title="Developer tools" aria-label="Developer tools"
            className={`inline-flex items-center justify-center w-11 h-11 rounded-2xl transition-colors ${showConsole ? 'bg-white text-ink' : 'text-white/50 hover:text-white hover:bg-white/10'}`}>
            <Terminal className="w-5 h-5" strokeWidth={1.5} />
          </button>
          <button onClick={() => changeMode('agentic')} title="Switch to agentic" aria-label="Switch to agentic"
            className="inline-flex items-center justify-center w-11 h-11 rounded-2xl bg-accent text-white hover:bg-accent-deep">
            <Sparkles className="w-5 h-5" strokeWidth={1.5} />
          </button>
        </aside>

        <div className="flex-1 min-w-0">
          <header className="flex items-center justify-between h-14 mb-4">
            <div className="flex items-baseline gap-3">
              <Wordmark />
              <span className="hidden sm:inline text-sm text-text-muted">{VIEWS.find((v) => v.id === view)?.label}</span>
            </div>
          </header>

          {showConsole && (
            <div className="mb-5"><DeveloperConsole backendOnline onRefresh={patientsChanged} onClose={() => setShowConsole(false)} /></div>
          )}

          <main className="pb-10">
            {view === 'patients' && <PatientsView refreshKey={refreshKey} onCheckRisk={(id) => { setRiskPatientId(id); changeView('visit'); }} />}
            {view === 'visit' && <VisitView initialPatientId={riskPatientId} onEditChart={() => changeView('patients')} onNewPatient={() => changeView('patients')} />}
            {view === 'physician' && (
              <PhysicianClearancePortal patient={patients[0]} onClearanceUpdated={patientsChanged} onSwitchToDentalView={() => changeView('patients')} />
            )}
          </main>
        </div>
      </div>
      {intakePanel}
    </div>
  );
}

export default App;
