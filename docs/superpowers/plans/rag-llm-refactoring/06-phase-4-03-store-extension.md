# Phase 4.3: ConfigStore 扩展与状态管理

> **优先级:** P1
> **预估工作量:** 3-4 小时

---

## 🎯 目标

扩展 Zustand ConfigStore，支持：
1. 新增状态字段（modePreference、healthDiagnostic、searchQuery、favorites 等）
2. 新增 Actions（undoChange、switchMode、runHealthDiagnostic 等）
3. originalValues 追踪（用于修改对比）
4. localStorage 持久化（用户偏好）

---

## 📦 状态定义

**文件:** `frontend/src/store/configStore.ts`

```typescript
import { create } from 'zustand';
import { persist } from 'zustand/middleware';

// 类型定义
export interface ConfigFieldMetadata {
  key: string;
  label: string;
  description?: string;
  category: string;
  type: 'bool' | 'int' | 'float' | 'str' | 'list' | 'dict' | 'select';
  defaultValue: any;
  min?: number;
  max?: number;
  options?: { label: string; value: any }[];
  sensitive?: boolean;
}

export interface DiagnosticResult {
  score: number;
  score_basis: string;
  suggestions: DiagnosticSuggestion[];
  cached_at?: string;
}

export interface DiagnosticSuggestion {
  priority: 'high' | 'medium' | 'low';
  issue: string;
  suggestion: string;
  config_path: string;
  current_value: string;
  recommended_value: string;
}

export type ModePreference = 'expert' | 'wizard';

// Store 接口
interface ConfigStore {
  // 配置数据
  configFields: ConfigFieldMetadata[];
  draftChanges: Record<string, any>;
  originalValues: Record<string, any>;  // 新增：原始值追踪
  activeVersion: string | null;
  versions: ConfigVersion[];
  
  // 模式与偏好
  modePreference: ModePreference;  // 新增
  expandedKeys: string[];          // 新增：手风琴展开状态
  
  // 搜索与筛选
  searchQuery: string;             // 新增
  statusFilter: 'all' | 'active' | 'needs_restart' | 'error';  // 新增
  
  // 健康诊断
  healthDiagnostic: DiagnosticResult | null;  // 新增
  isDiagnosing: boolean;                      // 新增
  
  // 收藏
  favorites: string[];             // 新增
  
  // 加载状态
  isLoading: boolean;
  isSaving: boolean;
  
  // Actions
  loadConfig: () => Promise<void>;
  loadVersions: () => Promise<void>;
  updateDraft: (key: string, value: any) => void;
  undoChange: (key: string) => void;  // 新增
  saveConfig: (description: string) => Promise<void>;
  resetDraft: () => void;
  rollbackToVersion: (versionId: string) => Promise<void>;
  resetToFactory: () => Promise<void>;
  
  // 新增 Actions
  switchMode: (mode: ModePreference) => void;
  runHealthDiagnostic: () => Promise<void>;
  setSearchQuery: (query: string) => void;
  setStatusFilter: (filter: ConfigStore['statusFilter']) => void;
  toggleFavorite: (key: string) => void;
  toggleAccordion: (keys: string[]) => void;
}

// 创建 Store
export const useConfigStore = create<ConfigStore>()(
  persist(
    (set, get) => {
      // 防抖定时器
      let healthDiagnosticTimer: NodeJS.Timeout | null = null;
      
      return {
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
      
      // 加载配置
      loadConfig: async () => {
        set({ isLoading: true });
        try {
          const response = await configApi.getConfig();
          const { config_snapshot, version_id } = response;
          
          // 提取配置字段元数据（保留嵌套结构）
          const fields = extractConfigFields(config_snapshot);
          
          set({
            configFields: fields,
            draftChanges: {},
            originalValues: config_snapshot,  // 保留完整嵌套结构
            activeVersion: version_id,
            isLoading: false
          });
        } catch (error) {
          set({ isLoading: false });
          throw error;
        }
      },
      
      // 更新草稿（触发防抖健康诊断）
      updateDraft: (key: string, value: any) => {
        set((state) => ({
          draftChanges: {
            ...state.draftChanges,
            [key]: value
          }
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
        
        set({ isSaving: true });
        try {
          // 合并草稿与原始值
          const mergedConfig = {
            ...originalValues,
            ...draftChanges
          };
          
          // 适配后端字段名
          await configApi.saveConfig({
            config_snapshot: mergedConfig,
            description
          });
          
          // 清空草稿，更新原始值
          set({
            draftChanges: {},
            originalValues: mergedConfig,
            isSaving: false
          });
        } catch (error) {
          set({ isSaving: false });
          throw error;
        }
      },
      
      // 切换模式
      switchMode: (mode: ModePreference) => {
        set({ modePreference: mode });
        // 同步到 localStorage
        localStorage.setItem('configModePreference', mode);
      },
      
      // 运行健康诊断
      runHealthDiagnostic: async () => {
        const { draftChanges, originalValues, healthDiagnostic } = get();
        
        // 检查缓存（5 分钟有效期）
        if (healthDiagnostic && healthDiagnostic.cached_at) {
          const cachedTime = new Date(healthDiagnostic.cached_at).getTime();
          const now = Date.now();
          if (now - cachedTime < 5 * 60 * 1000) {
            // 缓存未过期，跳过
            return;
          }
        }
        
        set({ isDiagnosing: true });
        try {
          // 合并当前配置
          const currentConfig = {
            ...originalValues,
            ...draftChanges
          };
          
          const result = await configApi.runHealthDiagnostic({
            config: currentConfig
          });
          
          set({
            healthDiagnostic: {
              ...result,
              cached_at: new Date().toISOString()
            },
            isDiagnosing: false
          });
        } catch (error) {
          // 降级到本地规则评分
          const localScore = calculateLocalScore(originalValues, draftChanges);
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
      
      // 设置状态筛选
      setStatusFilter: (filter: ConfigStore['statusFilter']) => {
        set({ statusFilter: filter });
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
      
      // ... 其他已有方法
      };
    },
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
```

---

## 🔧 辅助函数

### 配置字段提取（保留嵌套结构）

**重要**: 不扁平化配置，保留嵌套结构，使用路径访问（如 `llm_providers.dashscope.api_key`）

```typescript
interface ConfigFieldWithPath {
  path: string;           // 完整路径，如 "llm_providers.dashscope.api_key"
  key: string;            // 字段名，如 "api_key"
  label: string;          // 显示名称
  category: string;       // 顶级分类
  type: ConfigFieldMetadata['type'];
  defaultValue: any;
  description?: string;
  sensitive?: boolean;
}

function extractConfigFields(config: any): ConfigFieldMetadata[] {
  const fields: ConfigFieldWithPath[] = [];
  
  // 递归遍历嵌套对象，保留路径
  function traverse(obj: any, prefix: string = '', category: string = '') {
    for (const [key, value] of Object.entries(obj)) {
      const fullPath = prefix ? `${prefix}.${key}` : key;
      
      if (typeof value === 'object' && value !== null && !Array.isArray(value)) {
        // 递归处理嵌套对象
        traverse(value, fullPath, category || key);
      } else {
        fields.push({
          path: fullPath,
          key,
          label: formatLabel(key),
          category: category || fullPath.split('.')[0],
          type: inferType(value),
          defaultValue: value,
          sensitive: key.includes('key') || key.includes('secret') || key.includes('password')
        });
      }
    }
  }
  
  traverse(config);
  return fields;
}

// 根据路径从嵌套对象中获取值
function getValueByPath(obj: any, path: string): any {
  return path.split('.').reduce((current, key) => current?.[key], obj);
}

// 根据路径设置嵌套对象的值
function setValueByPath(obj: any, path: string, value: any): any {
  const keys = path.split('.');
  const lastKey = keys.pop()!;
  
  const target = keys.reduce((current, key) => {
    if (!(key in current)) current[key] = {};
    return current[key];
  }, obj);
  
  target[lastKey] = value;
  return obj;
}

function formatLabel(key: string): string {
  return key
    .replace(/_/g, ' ')
    .replace(/([A-Z])/g, ' $1')
    .replace(/^./, (s) => s.toUpperCase());
}

function inferType(value: any): ConfigFieldMetadata['type'] {
  if (typeof value === 'boolean') return 'bool';
  if (typeof value === 'number') return Number.isInteger(value) ? 'int' : 'float';
  if (typeof value === 'string') return 'str';
  if (Array.isArray(value)) return 'list';
  return 'dict';
}
```
```

### 本地规则评分（降级备用）

```typescript
function calculateLocalScore(
  originalValues: Record<string, any>,
  draftChanges: Record<string, any>
): DiagnosticResult {
  const config = { ...originalValues, ...draftChanges };
  
  let score = 0;
  
  // LLM 凭证 (30%)
  const llmProviders = config.llm_providers || {};
  if (Object.keys(llmProviders).length > 0) score += 30;
  
  // 核心场景模型 (25%)
  const sceneConfigs = config.llm_scene_configs || {};
  const recommendedModels = ['qwen-max', 'qwen-plus'];
  const hasRecommendedModel = Object.values(sceneConfigs).some(
    (sc: any) => recommendedModels.includes(sc.model)
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
```

---

## ✅ 验收清单

- [ ] **状态扩展**
  - [ ] modePreference 状态正常
  - [ ] healthDiagnostic 状态正常
  - [ ] searchQuery 状态正常
  - [ ] favorites 状态正常
  - [ ] originalValues 追踪正常

- [ ] **Actions**
  - [ ] undoChange 撤销单个修改
  - [ ] switchMode 切换模式
  - [ ] runHealthDiagnostic 运行诊断
  - [ ] setSearchQuery 设置搜索
  - [ ] toggleFavorite 切换收藏
  - [ ] toggleAccordion 切换展开

- [ ] **持久化**
  - [ ] modePreference 保存到 localStorage
  - [ ] favorites 保存到 localStorage
  - [ ] expandedKeys 保存到 localStorage

- [ ] **降级策略**
  - [ ] LLM 诊断失败时使用本地规则评分
  - [ ] 本地规则评分逻辑正确

---

## 📝 实施步骤

1. **Step 1:** 扩展 ConfigStore 接口
   - 新增状态字段
   - 新增 Actions

2. **Step 2:** 实现辅助函数
   - extractConfigFields
   - flattenConfig
   - calculateLocalScore

3. **Step 3:** 实现新增 Actions
   - undoChange
   - switchMode
   - runHealthDiagnostic
   - setSearchQuery
   - toggleFavorite
   - toggleAccordion

4. **Step 4:** 配置持久化
   - persist 中间件配置
   - localStorage 同步

5. **Step 5:** 测试与验证
   - 状态更新测试
   - 持久化测试
   - 降级策略测试

---

**返回总览：** [06-phase-4-00-overview.md](./06-phase-4-00-overview.md)
