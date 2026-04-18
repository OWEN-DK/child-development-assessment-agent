/**
 * 推荐面板状态管理
 */

import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { RecommendationMode } from '@/features/rag-eval/components/RecommendationPanel/types';
import type { AdoptedSuggestion } from '@/features/rag-eval/components/ReviewPanel/types';
import type { IgnoredSuggestion } from '@/features/rag-eval/components/IgnoredSuggestionsList/types';

interface RecommendationPanelState {
  // 当前模式
  mode: RecommendationMode;

  // 已采纳的建议ID
  adoptedSuggestions: string[];

  // 已采纳建议详情（用于审查面板）
  adoptedSuggestionsDetails: AdoptedSuggestion[];

  // 已忽略的建议ID
  ignoredSuggestions: string[];

  // 审查面板开关状态
  reviewPanelOpen: boolean;

  // 已忽略列表开关状态
  showIgnoredList: boolean;

  // 已忽略建议详情
  ignoredSuggestionsDetails: IgnoredSuggestion[];

  // Actions
  setMode: (mode: RecommendationMode) => void;
  adoptSuggestion: (suggestionId: string) => void;
  adoptSuggestionDetail: (suggestion: AdoptedSuggestion) => void;
  ignoreSuggestion: (suggestionId: string) => void;
  restoreIgnored: (suggestionId: string) => void;
  resetAdopted: () => void;
  resetIgnored: () => void;

  // 审查面板操作
  openReviewPanel: () => void;
  closeReviewPanel: () => void;
  removeFromAdopted: (id: string) => void;
  updateCustomValue: (id: string, value: unknown) => void;

  // 已忽略列表操作
  toggleIgnoredList: () => void;
  setIgnoredSuggestions: (suggestions: IgnoredSuggestion[]) => void;
}

export const useRecommendationPanelStore = create<RecommendationPanelState>()(
  persist(
    (set) => ({
      // 初始状态
      mode: 'recommendation',
      adoptedSuggestions: [],
      adoptedSuggestionsDetails: [],
      ignoredSuggestions: [],
      reviewPanelOpen: false,
      showIgnoredList: false,
      ignoredSuggestionsDetails: [],

      // 切换模式
      setMode: (mode) => set({ mode }),

      // 采纳建议（仅ID）
      adoptSuggestion: (suggestionId) =>
        set((state) => ({
          adoptedSuggestions: [...state.adoptedSuggestions, suggestionId],
        })),

      // 采纳建议（含详情）
      adoptSuggestionDetail: (suggestion) =>
        set((state) => ({
          adoptedSuggestions: [...state.adoptedSuggestions, suggestion.id],
          adoptedSuggestionsDetails: [...state.adoptedSuggestionsDetails, suggestion],
        })),

      // 忽略建议
      ignoreSuggestion: (suggestionId) =>
        set((state) => ({
          ignoredSuggestions: [...state.ignoredSuggestions, suggestionId],
        })),

      // 恢复被忽略的建议
      restoreIgnored: (suggestionId) =>
        set((state) => ({
          ignoredSuggestions: state.ignoredSuggestions.filter((id) => id !== suggestionId),
        })),

      // 重置已采纳列表
      resetAdopted: () => set({ adoptedSuggestions: [], adoptedSuggestionsDetails: [] }),

      // 重置已忽略列表
      resetIgnored: () => set({ ignoredSuggestions: [] }),

      // 打开审查面板
      openReviewPanel: () => set({ reviewPanelOpen: true }),

      // 关闭审查面板
      closeReviewPanel: () => set({ reviewPanelOpen: false }),

      // 从已采纳中移除
      removeFromAdopted: (id) =>
        set((state) => ({
          adoptedSuggestions: state.adoptedSuggestions.filter((sId) => sId !== id),
          adoptedSuggestionsDetails: state.adoptedSuggestionsDetails.filter((s) => s.id !== id),
        })),

      // 更新自定义值
      updateCustomValue: (id, value) =>
        set((state) => ({
          adoptedSuggestionsDetails: state.adoptedSuggestionsDetails.map((s) =>
            s.id === id ? { ...s, custom_value: value } : s
          ),
        })),

      // 切换已忽略列表显示
      toggleIgnoredList: () =>
        set((state) => ({
          showIgnoredList: !state.showIgnoredList,
        })),

      // 设置已忽略建议详情
      setIgnoredSuggestions: (suggestions) =>
        set({
          ignoredSuggestionsDetails: suggestions,
        }),
    }),
    {
      name: 'recommendation-panel-store',
      partialize: (state) => ({
        mode: state.mode,
        ignoredSuggestions: state.ignoredSuggestions,
        adoptedSuggestionsDetails: state.adoptedSuggestionsDetails,
        showIgnoredList: state.showIgnoredList,
        ignoredSuggestionsDetails: state.ignoredSuggestionsDetails,
      }),
    }
  )
);
