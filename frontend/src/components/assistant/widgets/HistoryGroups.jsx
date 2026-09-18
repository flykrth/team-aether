import React from 'react';
import { Group, ConceptChips, asList, toConcept } from './parts';

const TYPE_LABELS = { condition: 'Conditions', medication: 'Medications', allergy: 'Allergies', observation: 'Labs and vitals' };
const TYPE_TONE = { condition: 'neutral', medication: 'accent', allergy: 'danger', observation: 'success' };

// Observation entries carry their reading: show it with the label.
const withValue = (entry) => {
  if (!entry || typeof entry !== 'object' || entry.value == null) return entry;
  const concept = toConcept(entry);
  return { code: concept.code, display: `${concept.label}: ${entry.value}${entry.unit ? ` ${entry.unit}` : ''}` };
};

// Excluded entries say why they were left off the chart.
const withReason = (entry) => {
  if (!entry || typeof entry !== 'object' || !entry.reason) return entry;
  const concept = toConcept(entry);
  return { code: concept.code, display: `${concept.label} (${entry.reason})` };
};

/**
 * The outcome of a history write ({added, skipped_duplicates, unrecognized, excluded, verification, ...}):
 * shared by the history_updated widget and the patient_created widget (history given in the same prompt).
 */
export function HistoryGroups({ data }) {
  const added = asList(data?.added);
  const duplicates = asList(data?.skipped_duplicates);
  const unrecognized = asList(data?.unrecognized);
  const excluded = asList(data?.excluded);
  const codesIgnored = asList(data?.codes_ignored);
  const datesDropped = asList(data?.onset_dropped);
  const byType = added.reduce((groups, entry) => {
    const type = (entry && typeof entry === 'object' && entry.type) || 'other';
    return { ...groups, [type]: [...(groups[type] || []), entry] };
  }, {});

  return (
    <>
      {added.length === 0 && <p className="text-[13px] text-text-secondary">Nothing new was written to the record.</p>}

      {added.length > 0 && data?.verification === 'unconfirmed' && (
        <p className="rounded-2xl bg-warning-light text-warning-dark px-3 py-2 text-[12px]">
          Extracted automatically and charted as unconfirmed. Review these in the Previous records panel.
        </p>
      )}

      {Object.entries(byType).map(([type, entries]) => (
        <Group key={type} label={TYPE_LABELS[type] || 'Other'} count={entries.length}>
          <ConceptChips items={entries.map(withValue)} tone={TYPE_TONE[type] || 'neutral'} />
        </Group>
      ))}

      {duplicates.length > 0 && (
        <Group label="Already on record, skipped" count={duplicates.length}>
          <ConceptChips items={duplicates} tone="muted" />
        </Group>
      )}

      {unrecognized.length > 0 && (
        <Group label="Stored uncoded, needs review" count={unrecognized.length}>
          <ConceptChips items={unrecognized} tone="warning" />
          <p className="text-[11px] text-text-muted mt-1.5">These did not match the ICD-10 / RxNorm lexicon. They were kept as free text and will not drive risk rules until coded.</p>
        </Group>
      )}

      {excluded.length > 0 && (
        <Group label="Found but not charted" count={excluded.length}>
          <ConceptChips items={excluded.map(withReason)} tone="muted" />
          <p className="text-[11px] text-text-muted mt-1.5">Negated, family-history or discontinued statements are never added as active findings.</p>
        </Group>
      )}

      {(codesIgnored.length > 0 || datesDropped.length > 0) && (
        <p className="text-[11px] text-text-muted">
          {codesIgnored.length > 0 && `Codes not typed by you were ignored (${codesIgnored.join(', ')}); the lexicon coded the text instead. `}
          {datesDropped.length > 0 && 'Dates that were not exact (YYYY-MM-DD) were left off.'}
        </p>
      )}
    </>
  );
}
