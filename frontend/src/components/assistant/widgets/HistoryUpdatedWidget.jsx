import React from 'react';
import { FilePlus2, FolderPlus } from 'lucide-react';
import { WidgetShell, Badge, Notice, failureMessage, asList } from './parts';
import { HistoryGroups } from './HistoryGroups';

export function HistoryUpdatedWidget({ data, title, onOpenIntake }) {
  const failure = failureMessage(data);
  if (failure) return <Notice Icon={FilePlus2} title={title || 'Medical history'} message={failure} />;

  const added = asList(data.added);

  return (
    <WidgetShell
      Icon={FilePlus2}
      title={title || 'Medical history updated'}
      subtitle={[data.patient_id, data.document_id && `document ${data.document_id}`].filter(Boolean).join(' · ')}
      badge={<Badge cls={added.length ? 'bg-success-light text-success-dark' : 'bg-app-secondary text-text-secondary'}>{added.length} added</Badge>}
    >
      <HistoryGroups data={data} />

      {onOpenIntake && (
        <button type="button" className="chip cursor-pointer hover:bg-app-bg" onClick={() => onOpenIntake(data.patient_id)}>
          <FolderPlus className="w-3.5 h-3.5" strokeWidth={1.5} /> Review in records panel
        </button>
      )}
    </WidgetShell>
  );
}
