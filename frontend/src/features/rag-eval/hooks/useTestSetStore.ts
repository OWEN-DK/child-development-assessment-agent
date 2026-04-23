/**
 * 测试集列表页 Zustand Store
 */

import { create } from 'zustand';
import { getTestSets, createTestSet, deleteTestSet, batchDeleteTestSets } from '@/api/rag-test';
import type { TestSet } from '@/api/rag-test';

export type SourceType = 'BOOK_GENERATED' | 'JSON_IMPORTED' | 'MANUAL';

export interface TestSetListItem extends TestSet {
  total_cases: number;
  run_count: number;
  last_run_at: string | null;
}

interface TestSetStore {
  testSets: TestSetListItem[];
  loading: boolean;
  total: number;
  page: number;
  pageSize: number;
  keyword: string;
  sourceType: SourceType | null;

  fetchTestSets: () => Promise<void>;
  createTestSet: (data: { name: string; description?: string; source_type?: SourceType }) => Promise<void>;
  deleteTestSet: (id: string) => Promise<void>;
  batchDeleteTestSets: (ids: string[]) => Promise<void>;
  setPagination: (page: number, pageSize: number) => void;
  setFilters: (keyword: string, sourceType: SourceType | null) => void;
}

export const useTestSetStore = create<TestSetStore>((set, get) => ({
  testSets: [],
  loading: false,
  total: 0,
  page: 1,
  pageSize: 20,
  keyword: '',
  sourceType: null,

  fetchTestSets: async () => {
    set({ loading: true });
    try {
      const sets = await getTestSets();
      const { keyword, sourceType } = get();

      // 前端过滤
      let filtered = sets;
      if (keyword) {
        filtered = filtered.filter(s => s.name.toLowerCase().includes(keyword.toLowerCase()));
      }
      if (sourceType) {
        filtered = filtered.filter(s => s.source_type === sourceType);
      }

      set({
        testSets: filtered.map(s => ({
          ...s,
          total_cases: s.test_case_ids?.length || 0,
          run_count: 0,
          last_run_at: null,
        })) as TestSetListItem[],
        total: filtered.length,
        loading: false,
      });
    } catch (error) {
      console.error('获取测试集列表失败:', error);
      set({ loading: false });
    }
  },

  createTestSet: async (data) => {
    await createTestSet(data);
    await get().fetchTestSets();
  },

  deleteTestSet: async (id: string) => {
    await deleteTestSet(id);
    await get().fetchTestSets();
  },

  batchDeleteTestSets: async (ids: string[]) => {
    await batchDeleteTestSets(ids);
    await get().fetchTestSets();
  },

  setPagination: (page, pageSize) => set({ page, pageSize }),

  setFilters: (keyword, sourceType) => {
    set({ keyword, sourceType });
    get().fetchTestSets();
  },
}));
