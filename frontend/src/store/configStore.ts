import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { configApi } from '../api/config';
import {
  ConfigFieldMetadata,
  ConfigVersion,
  ConfigResetRequest,
} from '../api/config/types';

// 类型定义
export interface DiagnosticSuggestion {
  priority: 'high' | 'medium' | 'low';
  issue: string;
  suggestion: string;
  config_path: string;
  current_value: string;
  recommended_value: string;
}

export interface DiagnosticResult {
  score: number;
  score_basis: string;
  suggestions: DiagnosticSuggestion[];
  cached_at?: string;
}

export type ModePreference = 'expert' | 'wizard';

interface ConfigStore {
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

  // Actions
  loadConfig: () => Promise<void>;
  loadVersions: () => Promise<void>;
  updateDraft: (key: string, value: any) => void;
  undoChange: (key: string) => void;
  saveConfig: (description: string) => Promise<void>;
  resetDraft: () => void;
  rollbackToVersion: (versionId: string) => Promise<void>;
  resetToFactory: () => Promise<void>;
  setRunning: (running: boolean) => void;
  setLastResult: (result: any) => void;

  // 新增 Actions
  switchMode: (mode: ModePreference) => void;
  runHealthDiagnostic: () => Promise<void>;
  setSearchQuery: (query: string) => void;
  setStatusFilter: (filter: ConfigStore['statusFilter']) => void;
  toggleFavorite: (key: string) => void;
  toggleAccordion: (keys: string[]) => void;
}

// 辅助函数：本地规则评分（降级备用）
function calculateLocalScore(config: Record<string, any>): DiagnosticResult {
  let score = 0;

  // LLM 凭证 (30%)
  const llmProviders = config.llm_providers || {};
  if (Object.keys(llmProviders).length > 0) score += 30;

  // 核心场景模型 (25%)
  const sceneConfigs = config.llm_scene_configs || {};
  const recommendedModels = ['qwen-max', 'qwen-plus'];
  const hasRecommendedModel = Object.values(sceneConfigs).some(
    (sc: any) => recommendedModels.includes(sc?.model)
  );
  if (hasRecommendedModel) score += 25;

  // RAG 配置 (20%)
  const ragRetrieval = config.rag_retrieval || {};
  if (ragRetrieval.strategy && ragRetrieval.chunk_size) score += 20;

  // 业务规则 (15%)
  const rules = config.rules || {};
  if (Object.keys(rules).length > 0) score += 15;

  // 系统设置 (10%)
  const system = config.system || {};
  if (system.logging && system.paths) score += 10;

  return {
    score,
    score_basis: '基于本地规则评分（降级模式）',
    suggestions: []
  };
}

// 防抖定时器
let healthDiagnosticTimer: NodeJS.Timeout | null = null;

export const useConfigStore = create<ConfigStore>()(
  persist(
    (set, get) => ({
      // 初始状态
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

      // 加载配置
      loadConfig: async () => {
        set({ isLoading: true });
        try {
          const response = await configApi.getConfig();
          const configFields = Array.isArray(response.config) ? response.config : [];

          // 提取原始值
          const originalValues: Record<string, any> = {};
          configFields.forEach((field: ConfigFieldMetadata) => {
            originalValues[field.key] = field.current_value ?? field.default_value;
          });

          set({
            configFields,
            draftChanges: {},
            originalValues,
            activeVersion: response.active_version,
            isLoading: false
          });
        } catch (error) {
          console.error('Failed to load config:', error);
          set({ configFields: [], isLoading: false });
        }
      },

      // 加载版本列表
      loadVersions: async () => {
        try {
          const versions = await configApi.listVersions();
          const state = get();
          set({
            versions: Array.isArray(versions) ? versions : [],
            activeVersion: state.activeVersion || (versions.length > 0 ? versions[0].id : null)
          });
        } catch (error) {
          console.error('Failed to load versions:', error);
          set({ versions: [] });
        }
      },

      // 更新草稿（触发防抖健康诊断）
      updateDraft: (key: string, value: any) => {
        set((state) => ({
          draftChanges: { ...state.draftChanges, [key]: value },
        }));

        // 防抖：配置修改后 30 秒自动触发健康诊断
        if (healthDiagnosticTimer) {
          clearTimeout(healthDiagnosticTimer);
        }
        healthDiagnosticTimer = setTimeout(() => {
          get().runHealthDiagnostic();
        }, 30000); // 30 秒
      },

      // 撤销单个修改
      undoChange: (key: string) => {
        set((state) => {
          const { [key]: _, ...rest } = state.draftChanges;
          return { draftChanges: rest };
        });
      },

      // 保存配置
      saveConfig: async (description: string) => {
        const { draftChanges, originalValues } = get();
        if (Object.keys(draftChanges).length === 0) return;

        set({ isSaving: true });
        try {
          // 合并草稿与原始值
          const mergedConfig = { ...originalValues, ...draftChanges };

          await configApi.updateConfig({
            config_snapshot: mergedConfig,
            description,
            created_by: 'user',
          });

          // 清空草稿，更新原始值
          set({
            draftChanges: {},
            originalValues: mergedConfig,
            isSaving: false
          });

          await get().loadConfig();
          await get().loadVersions();
        } catch (error) {
          console.error('Failed to save config:', error);
          set({ isSaving: false });
          throw error;
        }
      },

      // 重置草稿
      resetDraft: () => {
        set({ draftChanges: {} });
      },

      // 回滚到指定版本
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

      // 恢复出厂设置
      resetToFactory: async () => {
        try {
          const confirmed = window.confirm(
            '确认恢复出厂设置？\n\n此操作将清除所有自定义配置，是否继续？'
          );

          if (!confirmed) return;

          const resetRequest: ConfigResetRequest = {
            confirm: true,
            reason: '用户手动恢复'
          };

          await configApi.resetToFactory(resetRequest);
          await get().loadConfig();
          await get().loadVersions();
        } catch (error) {
          console.error('Failed to reset:', error);
          throw error;
        }
      },

      // 切换模式
      switchMode: (mode: ModePreference) => {
        set({ modePreference: mode });
        // 同步到 localStorage
        localStorage.setItem('configModePreference', mode);
      },

      // 设置状态筛选
      setStatusFilter: (filter: ConfigStore['statusFilter']) => {
        set({ statusFilter: filter });
      },

      // 运行健康诊断
      runHealthDiagnostic: async () => {
        const { draftChanges, originalValues, healthDiagnostic } = get();

        // 检查缓存（5 分钟有效期）
        if (healthDiagnostic && healthDiagnostic.cached_at) {
          const cachedTime = new Date(healthDiagnostic.cached_at).getTime();
          const now = Date.now();
          if (now - cachedTime < 5 * 60 * 1000) {
            return; // 缓存未过期，跳过
          }
        }

        set({ isDiagnosing: true });
        try {
          // 合并当前配置
          const currentConfig = { ...originalValues, ...draftChanges };

          // 调用后端健康诊断 API
          const result = await configApi.runHealthDiagnostic({ config: currentConfig });

          set({
            healthDiagnostic: {
              ...result,
              cached_at: new Date().toISOString()
            },
            isDiagnosing: false
          });
        } catch (error) {
          console.warn('健康诊断 API 调用失败，使用本地规则评分:', error);
          // 降级到本地规则评分
          const currentConfig = { ...originalValues, ...draftChanges };
          const localScore = calculateLocalScore(currentConfig);
          set({
            healthDiagnostic: localScore,
            isDiagnosing: false
          });
        }
      },

      // 设置搜索关键词
      setSearchQuery: (query: string) => {
        set({ searchQuery: query });
      },

      // 切换收藏
      toggleFavorite: (key: string) => {
        set((state) => ({
          favorites: state.favorites.includes(key)
            ? state.favorites.filter(k => k !== key)
            : [...state.favorites, key]
        }));
      },

      // 切换手风琴展开
      toggleAccordion: (keys: string[]) => {
        set({ expandedKeys: keys });
      },

      // 设置运行状态
      setRunning: (running: boolean) => {
        set({ isRunning: running });
      },

      // 设置最后结果
      setLastResult: (result: any) => {
        set({ lastResult: result });
      },
    }),
    {
      name: 'config-store',
      partialize: (state) => ({
        modePreference: state.modePreference,
        favorites: state.favorites,
        expandedKeys: state.expandedKeys
      })
    }
  )
);
