import { QueryClient } from '@tanstack/react-query';
import { CACHE_TIME } from './constants';

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 1,
      staleTime: CACHE_TIME.MEDIUM,
      gcTime: CACHE_TIME.LONG,
    },
    mutations: {
      retry: 0,
    },
  },
});
