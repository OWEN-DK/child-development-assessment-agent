import { useState, useCallback } from 'react';
import { searchKnowledge } from '../../../api/knowledge';
import type { SearchResultItem } from '../../../api/knowledge/types';

interface UseKnowledgeSearchReturn {
  query: string;
  results: SearchResultItem[];
  loading: boolean;
  total: number;
  handleSearch: (query: string, limit?: number, offset?: number) => Promise<void>;
  clearSearch: () => void;
}

export const useKnowledgeSearch = (): UseKnowledgeSearchReturn => {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<SearchResultItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [total, setTotal] = useState(0);

  const handleSearch = useCallback(async (searchQuery: string, limit: number = 10, offset: number = 0) => {
    setQuery(searchQuery);
    
    if (!searchQuery.trim()) {
      setResults([]);
      setTotal(0);
      return;
    }

    try {
      setLoading(true);
      const response = await searchKnowledge(searchQuery, limit, offset);
      setResults(response.results);
      setTotal(response.total);
    } catch (e: any) {
      console.error('Search failed:', e);
      setResults([]);
      setTotal(0);
      throw e;
    } finally {
      setLoading(false);
    }
  }, []);

  const clearSearch = useCallback(() => {
    setQuery('');
    setResults([]);
    setTotal(0);
  }, []);

  return {
    query,
    results,
    loading,
    total,
    handleSearch,
    clearSearch,
  };
};
