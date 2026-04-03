import { useState, useCallback } from 'react';

interface UseModalOptions<T = any> {
  initialData?: T | null;
}

interface UseModalReturn<T> {
  isOpen: boolean;
  data: T | null;
  open: (data?: T) => void;
  close: () => void;
  toggle: () => void;
  reset: () => void;
}

export function useModal<T = any>(options: UseModalOptions<T> = {}): UseModalReturn<T> {
  const { initialData = null } = options;
  
  const [isOpen, setIsOpen] = useState(false);
  const [data, setData] = useState<T | null>(initialData);

  const open = useCallback((newData?: T) => {
    setData(newData ?? null);
    setIsOpen(true);
  }, []);

  const close = useCallback(() => {
    setIsOpen(false);
  }, []);

  const toggle = useCallback(() => {
    setIsOpen(prev => !prev);
  }, []);

  const reset = useCallback(() => {
    setIsOpen(false);
    setData(initialData);
  }, [initialData]);

  return {
    isOpen,
    data,
    open,
    close,
    toggle,
    reset,
  };
}
