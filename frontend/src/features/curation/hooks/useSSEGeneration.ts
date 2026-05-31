import { useCallback } from 'react';
import { useCurationStore } from '../stores/curationStore';

/**
 * SSE generation progress hook.
 * Wraps the store's startGeneration with cleanup and cancel support.
 */
export function useSSEGeneration() {
  const {
    generating, generateProgress, generateStatus, generateError,
    generateBookTitle, generateChapters,
    generatePhase, generatePhaseLabel,
    startGeneration, resumeGeneration, cancelGeneration,
  } = useCurationStore();

  const start = useCallback(
    (bookId: string) => {
      startGeneration(bookId);
    },
    [startGeneration],
  );

  const resume = useCallback(
    (bookId: string) => {
      resumeGeneration(bookId);
    },
    [resumeGeneration],
  );

  const cancel = useCallback(
    (bookId: string) => {
      cancelGeneration(bookId);
    },
    [cancelGeneration],
  );

  return {
    generating,
    progress: generateProgress,
    status: generateStatus,
    error: generateError,
    bookTitle: generateBookTitle,
    chapters: generateChapters,
    phase: generatePhase,
    phaseLabel: generatePhaseLabel,
    start,
    resume,
    cancel,
  };
}
