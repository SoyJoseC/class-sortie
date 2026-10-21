import { describe, expect, it } from 'vitest';
import { emptyOnboarding } from './useTour';
import { tourSlice, enableTour, startSegment, disableTour } from './tourSlice';

describe('tourSlice', () => {
  it('starts disabled', () => {
    expect(tourSlice.getInitialState()).toEqual({ activeSegment: null, enabled: false });
  });

  it('enables and starts a segment', () => {
    let state = tourSlice.getInitialState();
    state = tourSlice.reducer(state, enableTour());
    state = tourSlice.reducer(state, startSegment('class'));
    expect(state).toEqual({ enabled: true, activeSegment: 'class' });
  });

  it('clears everything on disable', () => {
    let state = tourSlice.reducer(tourSlice.getInitialState(), startSegment('activity'));
    state = tourSlice.reducer(state, disableTour());
    expect(state.enabled).toBe(false);
    expect(state.activeSegment).toBeNull();
  });
});

describe('emptyOnboarding', () => {
  it('starts undismissed with nothing completed', () => {
    expect(emptyOnboarding()).toEqual({ dismissed: false, completed: [] });
  });
});
