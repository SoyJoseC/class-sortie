import type { Participant } from '@/api/types';

/** What the student typed or used to join (stored on the participant row). */
export function joinName(participant: Pick<Participant, 'display_name' | 'label'>): string {
  const entered = participant.display_name?.trim();
  if (entered) return entered;
  return participant.label;
}

/** Roster-linked name when it differs from what they typed to join. */
export function rosterNameIfDifferent(
  participant: Pick<Participant, 'display_name' | 'label' | 'student'>
): string | null {
  if (participant.student == null) return null;
  const entered = participant.display_name?.trim();
  if (!entered || entered.localeCompare(participant.label, undefined, { sensitivity: 'accent' }) === 0) {
    return null;
  }
  return participant.label;
}
