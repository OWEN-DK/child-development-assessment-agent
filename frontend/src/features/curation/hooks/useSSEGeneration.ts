import { useCallback, useRef } from 'react';
import { useCurationStore } from '../stores/curationStore';

/**
 * SSE generation progress hook.
 * Wraps the store's startGeneration with cleanup support.
 */
export function useSSEGeneration() {
  const eventSourceRef = useRef<EventSource | null>(null);
  const {
    generating, generateProgress, generateStatus, generateError,
    generateBookTitle, generateChapters,
    startGeneration,
  } = useCurationStore();

  const start = useCallback(
    (bookId: string) => {
      // Close previous if any
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
        eventSourceRef.current = null;
      }
      startGeneration(bookId);
    },
    [startGeneration],
  );

  const cancel = useCallback(() => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }
  }, []);

  return {
    generating,
    progress: generateProgress,
    status: generateStatus,
    error: generateError,
    bookTitle: generateBookTitle,
    chapters: generateChapters,
    start,
    cancel,
  };
}
