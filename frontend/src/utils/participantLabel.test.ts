import { describe, expect, it } from 'vitest';
import { joinName, rosterNameIfDifferent } from './participantLabel';

describe('participantLabel', () => {
  it('prefers display_name for join name', () => {
    expect(
      joinName({ display_name: 'STU-001', label: 'Amara Joseph' })
    ).toBe('STU-001');
  });

  it('shows roster name when it differs from join identifier', () => {
    expect(
      rosterNameIfDifferent({
        display_name: 'STU-001',
        label: 'Amara Joseph',
        student: 42,
      })
    ).toBe('Amara Joseph');
  });
});
