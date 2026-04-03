import apiClient from '../client';
import type { SearchResultItem } from './types';

export const searchKnowledge = async (
  query: string, 
  limit: number = 20
): Promise<{ 
  status: string; 
  total: number; 
  results: SearchResultItem[] 
}> => {
  const response = await apiClient.get('/rag/search', {
    params: { query, limit }
  });
  return response.data;
};
