import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { ConfigFieldMetadata, ConfigVersion } from '@/api/config/types';
import type { DiagnosticResult } from '../services/diagnosticService';

export type ModePreference = 'expert' | 'wizard';

export interface ConfigState {
  // 配置数据
  configFields: ConfigFieldMetadata[];
  draftChanges: Record<string, any>;
  originalValues: Record<string, any>;
  activeVersion: string | null;
  versions: ConfigVersion[];

  // 模式与偏好
  modePreference: ModePreference;
  expandedKeys: string[];

  // 搜索与筛选
  searchQuery: string;
  statusFilter: 'all' | 'active' | 'needs_restart' | 'error';

  // 健康诊断
  healthDiagnostic: DiagnosticResult | null;
  isDiagnosing: boolean;

  // 收藏
  favorites: string[];

  // 加载状态
  isLoading: boolean;
  isSaving: boolean;
  isRunning: boolean;
  lastResult: any | null;

  // Setters
  setConfigFields: (fields: ConfigFieldMetadata[]) => void;
  setOriginalValues: (values: Record<string, any>) => void;
  setDraftChanges: (changes: Record<string, any>) => void;
  updateDraft: (key: string, value: any) => void;
  undoChange: (key: string) => void;
  resetDraft: () => void;
  
  setActiveVersion: (version: string | null) => void;
  setVersions: (versions: ConfigVersion[]) => void;

  setModePreference: (mode: ModePreference) => void;
  setExpandedKeys: (keys: string[]) => void;
  setSearchQuery: (query: string) => void;
  setStatusFilter: (filter: ConfigState['statusFilter']) => void;

  setHealthDiagnostic: (result: DiagnosticResult | null) => void;
  setIsDiagnosing: (isDiagnosing: boolean) => void;

  toggleFavorite: (key: string) => void;

  setIsLoading: (isLoading: boolean) => void;
  setIsSaving: (isSaving: boolean) => void;
  setIsRunning: (isRunning: boolean) => void;
  setLastResult: (result: any) => void;
}

export const useConfigStore = create<ConfigState>()(
  persist(
    (set) => ({
      configFields: [],
      draftChanges: {},
      originalValues: {},
      activeVersion: null,
      versions: [],

      modePreference: 'expert',
      expandedKeys: [],

      searchQuery: '',
      statusFilter: 'all',

      healthDiagnostic: null,
      isDiagnosing: false,

      favorites: [],

      isLoading: false,
      isSaving: false,
      isRunning: false,
      lastResult: null,

      setConfigFields: (fields) => set({ configFields: fields }),
      setOriginalValues: (values) => set({ originalValues: values }),
      setDraftChanges: (changes) => set({ draftChanges: changes }),
      updateDraft: (key, value) => set((state) => ({ draftChanges: { ...state.draftChanges, [key]: value } })),
      undoChange: (key) => set((state) => {
        const { [key]: _, ...rest } = state.draftChanges;
        return { draftChanges: rest };
      }),
      resetDraft: () => set({ draftChanges: {} }),

      setActiveVersion: (version) => set({ activeVersion: version }),
      setVersions: (versions) => set({ versions }),

      setModePreference: (mode) => set({ modePreference: mode }),
      setExpandedKeys: (keys) => set({ expandedKeys: keys }),
      setSearchQuery: (query) => set({ searchQuery: query }),
      setStatusFilter: (filter) => set({ statusFilter: filter }),

      setHealthDiagnostic: (result) => set({ healthDiagnostic: result }),
      setIsDiagnosing: (isDiagnosing) => set({ isDiagnosing }),

      toggleFavorite: (key) => set((state) => ({
        favorites: state.favorites.includes(key)
          ? state.favorites.filter(k => k !== key)
          : [...state.favorites, key]
      })),

      setIsLoading: (isLoading) => set({ isLoading }),
      setIsSaving: (isSaving) => set({ isSaving }),
      setIsRunning: (isRunning) => set({ isRunning }),
      setLastResult: (result) => set({ lastResult: result }),
    }),
    {
      name: 'config-store',
      partialize: (state) => ({
        modePreference: state.modePreference,
        favorites: state.favorites,
        expandedKeys: state.expandedKeys,
      }),
    }
  )
);