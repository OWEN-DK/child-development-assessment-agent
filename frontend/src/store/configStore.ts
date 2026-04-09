import { create } from 'zustand';
import { configApi } from '../api/config';
import {
  ConfigFieldMetadata,
  ConfigVersion,
} from '../api/config/types';

interface ConfigStore {
  configFields: ConfigFieldMetadata[];
  activeVersion: string | null;
  versions: ConfigVersion[];
  draftChanges: Record<string, any>;
  isLoading: boolean;
  isSaving: boolean;
  isRunning: boolean;
  lastResult: any | null;
  comparisonBaseline: string | null;

  loadConfig: () => Promise<void>;
  loadVersions: () => Promise<void>;
  updateDraft: (key: string, value: any) => void;
  saveConfig: (description: string) => Promise<void>;
  resetDraft: () => void;
  rollbackToVersion: (versionId: string) => Promise<void>;
  resetToFactory: () => Promise<void>;
  setRunning: (running: boolean) => void;
  setLastResult: (result: any) => void;
}

export const useConfigStore = create<ConfigStore>((set, get) => ({
  configFields: [],
  activeVersion: null,
  versions: [],
  draftChanges: {},
  isLoading: false,
  isSaving: false,
  isRunning: false,
  lastResult: null,
  comparisonBaseline: null,

  loadConfig: async () => {
    set({ isLoading: true });
    try {
      const response = await configApi.getConfig();
      set({
        configFields: Array.isArray(response.config) ? response.config : [],
        activeVersion: response.active_version,
      });
    } catch (error) {
      console.error('Failed to load config:', error);
      set({ configFields: [] });
    } finally {
      set({ isLoading: false });
    }
  },

  loadVersions: async () => {
    try {
      const versions = await configApi.listVersions();
      set({ versions: Array.isArray(versions) ? versions : [] });
    } catch (error) {
      console.error('Failed to load versions:', error);
      set({ versions: [] });
    }
  },

  updateDraft: (key: string, value: any) => {
    set((state) => ({
      draftChanges: { ...state.draftChanges, [key]: value },
    }));
  },

  saveConfig: async (description: string) => {
    const { draftChanges } = get();
    if (Object.keys(draftChanges).length === 0) return;

    set({ isSaving: true });
    try {
      await configApi.updateConfig({
        config: draftChanges,
        description,
        created_by: 'user',
      });
      set({ draftChanges: {} });
      await get().loadConfig();
      await get().loadVersions();
    } finally {
      set({ isSaving: false });
    }
  },

  resetDraft: () => {
    set({ draftChanges: {} });
  },

  rollbackToVersion: async (versionId: string) => {
    try {
      await configApi.rollbackToVersion(versionId);
      await get().loadConfig();
      await get().loadVersions();
    } catch (error) {
      console.error('Failed to rollback:', error);
      throw error;
    }
  },

  resetToFactory: async () => {
    try {
      await configApi.resetToFactory();
      await get().loadConfig();
      await get().loadVersions();
    } catch (error) {
      console.error('Failed to reset:', error);
      throw error;
    }
  },

  setRunning: (running: boolean) => {
    set({ isRunning: running });
  },

  setLastResult: (result: any) => {
    set({ lastResult: result });
  },
}));
