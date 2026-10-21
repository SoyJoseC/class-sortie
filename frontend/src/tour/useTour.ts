import { useCallback, useEffect } from 'react';
import { useDispatch, useSelector } from 'react-redux';
import { useNavigate } from 'react-router-dom';
import { useCurrentTeacherQuery, useUpdateProfileMutation } from '@/api/caricueApi';
import type { TeacherOnboarding } from '@/api/types';
import type { RootState } from '@/store';
import { disableTour, enableTour, startSegment, stopTour, type TourSegment } from './tourSlice';
import { TOUR_STEPS } from './steps';

export function emptyOnboarding(): TeacherOnboarding {
  return { dismissed: false, completed: [] };
}

export function useTour() {
  const dispatch = useDispatch();
  const navigate = useNavigate();
  const teacher = useCurrentTeacherQuery();
  const [updateProfile] = useUpdateProfileMutation();
  const { activeSegment, enabled } = useSelector((state: RootState) => state.tour);
  const onboarding = teacher.data?.onboarding ?? emptyOnboarding();

  const persist = useCallback(
    (next: TeacherOnboarding) => {
      void updateProfile({ onboarding: next })
        .unwrap()
        .catch(() => undefined);
    },
    [updateProfile]
  );

  const start = useCallback(
    (segment: TourSegment) => {
      dispatch(startSegment(segment));
    },
    [dispatch]
  );

  const acceptWelcome = useCallback(() => {
    dispatch(enableTour());
    persist({ ...onboarding, dismissed: false });
    navigate('/app/classes/new');
    dispatch(startSegment('class'));
  }, [dispatch, navigate, onboarding, persist]);

  const dismissWelcome = useCallback(() => {
    persist({ ...onboarding, dismissed: true });
    dispatch(disableTour());
  }, [dispatch, onboarding, persist]);

  const replay = useCallback(() => {
    persist({ dismissed: false, completed: [] });
    dispatch(enableTour());
    navigate('/app/classes/new');
    dispatch(startSegment('class'));
  }, [dispatch, navigate, persist]);

  const markComplete = useCallback(
    (segment: TourSegment) => {
      const completed = onboarding.completed.includes(segment)
        ? onboarding.completed
        : [...onboarding.completed, segment];
      persist({ ...onboarding, completed });
    },
    [onboarding, persist]
  );

  return {
    onboarding,
    enabled,
    activeSegment,
    start,
    acceptWelcome,
    dismissWelcome,
    replay,
    markComplete,
  };
}

/** Mount once in the teacher shell. Drives the highlighted steps. */
export function TourRunner() {
  const dispatch = useDispatch();
  const { activeSegment, markComplete } = useTour();

  useEffect(() => {
    if (!activeSegment) return;
    const steps = TOUR_STEPS[activeSegment].filter((step) =>
      Boolean(document.querySelector(step.element))
    );
    if (steps.length === 0) {
      dispatch(stopTour());
      return;
    }

    let destroyed = false;
    let driverObj: { destroy: () => void; drive: () => void } | null = null;

    void import('driver.js').then(({ driver }) => {
      if (destroyed) return;
      driverObj = driver({
        showProgress: true,
        overlayOpacity: 0.45,
        steps: steps.map((step) => ({
          element: step.element,
          popover: {
            title: step.title,
            description: step.description,
          },
        })),
        onDestroyed: () => {
          markComplete(activeSegment);
          dispatch(stopTour());
        },
      });
      driverObj.drive();
    });

    return () => {
      destroyed = true;
      driverObj?.destroy();
    };
  }, [activeSegment, dispatch, markComplete]);

  return null;
}

/** Starts a segment on mount when the teacher is mid-tour and has not finished it. */
export function useTourSegment(segment: TourSegment) {
  const { enabled, onboarding, activeSegment, start } = useTour();

  useEffect(() => {
    if (!enabled) return;
    if (onboarding.completed.includes(segment)) return;
    if (activeSegment === segment) return;
    start(segment);
  }, [enabled, onboarding.completed, activeSegment, segment, start]);
}
