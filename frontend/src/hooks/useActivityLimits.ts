import { useMemo } from 'react';
import { useClientConfigQuery } from '@/api/caricueApi';
import { DEFAULT_LIMITS, type ActivityLimits } from '@/utils/activityDraft';

/** The server's builder limits, with safe defaults while `/api/config/` loads. */
export function useActivityLimits(): ActivityLimits {
  const { data } = useClientConfigQuery();
  return useMemo(
    () => ({
      minQuestions: data?.min_questions ?? DEFAULT_LIMITS.minQuestions,
      maxQuestions: data?.max_questions ?? DEFAULT_LIMITS.maxQuestions,
      maxChoices: data?.max_choices ?? DEFAULT_LIMITS.maxChoices,
    }),
    [data?.min_questions, data?.max_questions, data?.max_choices]
  );
}
