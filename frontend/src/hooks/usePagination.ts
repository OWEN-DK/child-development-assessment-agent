import { useState, useCallback } from 'react';
import { DEFAULT_PAGE_SIZE } from '@shared/lib/constants';

interface UsePaginationOptions {
  initialPage?: number;
  initialPageSize?: number;
}

interface UsePaginationReturn {
  currentPage: number;
  pageSize: number;
  total: number;
  setCurrentPage: (page: number) => void;
  setPageSize: (size: number) => void;
  setTotal: (total: number) => void;
  reset: () => void;
  offset: number;
}

export function usePagination(options: UsePaginationOptions = {}): UsePaginationReturn {
  const { initialPage = 1, initialPageSize = DEFAULT_PAGE_SIZE } = options;
  
  const [currentPage, setCurrentPage] = useState(initialPage);
  const [pageSize, setPageSize] = useState(initialPageSize);
  const [total, setTotal] = useState(0);

  const reset = useCallback(() => {
    setCurrentPage(initialPage);
    setPageSize(initialPageSize);
    setTotal(0);
  }, [initialPage, initialPageSize]);

  const offset = (currentPage - 1) * pageSize;

  return {
    currentPage,
    pageSize,
    total,
    setCurrentPage,
    setPageSize: useCallback((size: number) => {
      setPageSize(size);
      setCurrentPage(1);
    }, []),
    setTotal,
    reset,
    offset,
  };
}
