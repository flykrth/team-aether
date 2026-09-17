import React, { useState, useEffect } from 'react';
import { Navbar } from './components/Navbar';
import { InteroperabilityDashboard } from './components/InteroperabilityDashboard';
import { PatientRecordViewer } from './components/PatientRecordViewer';
import { EndpointTester } from './components/EndpointTester';
import { api } from './services/api';

export function App() {
  const [activeTab, setActiveTab] = useState('viewer');
  const [backendOnline, setBackendOnline] = useState(false);
  const [carestackStatus, setCarestackStatus] = useState(null);
  const [patients, setPatients] = useState([]);
  const [syncing, setSyncing] = useState(false);

  const checkConnectivity = async () => {
    try {
      setSyncing(true);
      const [health, status, pts] = await Promise.all([
        api.getHealth().catch(() => null),
        api.getCareStackStatus().catch(() => null),
        api.getCareStackPatients().catch(() => []),
      ]);

      setBackendOnline(health?.status === 'healthy');
      setCarestackStatus(status);
      setPatients(pts);
    } catch (err) {
      console.error('Connection check failed:', err);
      setBackendOnline(false);
    } finally {
      setSyncing(false);
    }
  };

  useEffect(() => {
    checkConnectivity();
    const interval = setInterval(checkConnectivity, 15000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col font-sans">
      <Navbar
        backendOnline={backendOnline}
        activeTab={activeTab}
        setActiveTab={setActiveTab}
      />

      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <InteroperabilityDashboard
          carestackStatus={carestackStatus}
          fhirOnline={backendOnline}
          onRefresh={checkConnectivity}
          syncing={syncing}
        />

        {activeTab === 'viewer' ? (
          <PatientRecordViewer
            patients={patients}
            onSyncSuccess={checkConnectivity}
          />
        ) : (
          <EndpointTester />
        )}
      </main>

      <footer className="bg-white border-t border-slate-200 py-6 mt-12 text-center text-xs text-slate-500">
        <div className="max-w-7xl mx-auto px-4">
          <p className="font-medium text-slate-700">
            Medical-Dental Interoperability Node (MDIN) — CareStack D-Solve Hackathon 2026
          </p>
          <p className="mt-1 text-slate-400">
            DRISHTI · College of Engineering Trivandrum (CET) · Problem 6: Open Problem Statement — Dental Industry
          </p>
        </div>
      </footer>
    </div>
  );
}

export default App;
