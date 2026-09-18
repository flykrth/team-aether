import React from 'react';
import { UserPlus, UserCheck, FolderPlus, MessageSquareText } from 'lucide-react';
import { WidgetShell, Group, Badge, ConceptChips, Fact, Notice, failureMessage, asList, pretty } from './parts';
import { HistoryGroups } from './HistoryGroups';

export function PatientCreatedWidget({ data, title, onAsk, onOpenIntake }) {
  const failure = failureMessage(data);
  if (failure) return <Notice Icon={UserPlus} title={title || 'Patient'} message={failure} />;

  const existed = Boolean(data.already_existed);
  const history = data.history && typeof data.history === 'object' ? data.history : null;
  const historyFailure = history && history.ok === false ? (history.message || 'The backend rejected it.') : null;
  // planned procedures come back as {code, description, tooth_number} or as "CODE description" strings
  const procedures = asList(data.planned_procedures).map((p) =>
    (typeof p === 'string' ? p : { code: p.code, display: [p.description, p.tooth_number && `tooth ${p.tooth_number}`].filter(Boolean).join(' · ') || p.code }));

  return (
    <WidgetShell
      Icon={existed ? UserCheck : UserPlus}
      title={data.name || title || 'New patient'}
      subtitle={existed ? 'Already on file: no duplicate was created' : 'Added to CareStack and the medical record'}
      badge={<Badge cls={existed ? 'bg-warning-light text-warning-dark' : 'bg-success-light text-success-dark'}>{existed ? 'Existing patient' : 'Patient created'}</Badge>}
    >
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <Fact label="Patient ID" value={data.patient_id} mono />
        <Fact label="MRN" value={data.mrn} mono />
        <Fact label="Date of birth" value={data.birth_date} />
        <Fact label="Gender" value={data.gender && pretty(data.gender)} />
      </div>

      {procedures.length > 0 && (
        <Group label="Planned procedures" count={procedures.length}><ConceptChips items={procedures} tone="accent" /></Group>
      )}

      {/* History given in the same prompt is written by the same tool call and comes back nested here */}
      {history && (
        <div className="space-y-3 pt-1">
          <div className="eyebrow">Medical history from this message</div>
          {historyFailure
            ? <p className="rounded-2xl bg-danger-light text-danger-dark px-3 py-2 text-[12px]">The patient was created, but the history was not saved: {historyFailure}</p>
            : <HistoryGroups data={history} />}
        </div>
      )}

      <div className="flex flex-wrap gap-1.5">
        {onAsk && data.patient_id && (
          <button type="button" className="chip chip-accent cursor-pointer hover:bg-accent-soft/70"
            onClick={() => onAsk(`Add medical history for ${data.name || data.patient_id} (${data.patient_id}): `)}>
            <MessageSquareText className="w-3.5 h-3.5" strokeWidth={1.5} /> Describe their history
          </button>
        )}
        {onOpenIntake && (
          <button type="button" className="chip cursor-pointer hover:bg-app-bg" onClick={() => onOpenIntake(data.patient_id)}>
            <FolderPlus className="w-3.5 h-3.5" strokeWidth={1.5} /> Open records panel
          </button>
        )}
      </div>
    </WidgetShell>
  );
}
