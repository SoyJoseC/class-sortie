import { createSlice, type PayloadAction } from '@reduxjs/toolkit';

export type TourSegment = 'class' | 'activity' | 'reflection';

export interface TourState {
  /** The segment currently driving, if any. */
  activeSegment: TourSegment | null;
  /** The teacher accepted the tour (or hit replay) this session. */
  enabled: boolean;
}

const initialState: TourState = {
  activeSegment: null,
  enabled: false,
};

export const tourSlice = createSlice({
  name: 'tour',
  initialState,
  reducers: {
    enableTour(state) {
      state.enabled = true;
    },
    startSegment(state, action: PayloadAction<TourSegment>) {
      state.enabled = true;
      state.activeSegment = action.payload;
    },
    stopTour(state) {
      state.activeSegment = null;
    },
    disableTour(state) {
      state.enabled = false;
      state.activeSegment = null;
    },
  },
});

export const { enableTour, startSegment, stopTour, disableTour } = tourSlice.actions;
