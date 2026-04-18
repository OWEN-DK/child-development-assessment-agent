# Phase 6-3: 拆分 configStore

> **需求来源**: spec 文档 `unified-api-response-and-error-handling.md` 中 `7.5.2` 节
> **所属 Phase**: Phase 6

## 需求定义

将 `configStore.ts`（369 行）拆分为 4 个文件，消除混合状态、业务逻辑、API 调用、定时器的职责。

## 验收标准

- [ ] `configStore.ts` 拆分为 4 个文件
- [ ] 单文件不超过 200 行
- [ ] 模块级可变状态消除
- [ ] 功能回归测试通过

## 涉及文件

| 文件路径 | 操作 | 说明 |
|---------|------|------|
| `frontend/src/store/configStore.ts` | 删除 | 原 369 行文件 |
| `frontend/src/features/config/stores/configStore.ts` | 新增 | 纯状态管理，~100 行 |
| `frontend/src/features/config/services/diagnosticService.ts` | 新增 | 健康诊断逻辑，~150 行 |
| `frontend/src/features/config/services/scoringService.ts` | 新增 | 评分算法，~100 行 |
| `frontend/src/features/config/hooks/useConfig.ts` | 新增 | 配置操作 hooks，~100 行 |

## 拆分方案

### 职责划分

| 文件 | 职责 | 预估行数 |
|------|------|---------|
| `stores/configStore.ts` | 纯状态管理（Zustand store） | ~100 |
| `services/diagnosticService.ts` | 健康诊断逻辑、定时器 | ~150 |
| `services/scoringService.ts` | 评分算法、计算 | ~100 |
| `hooks/useConfig.ts` | 配置操作 hooks、API 调用 | ~100 |

### configStore.ts（拆分后）

```typescript
// features/config/stores/configStore.ts
import { create } from 'zustand';
import { ConfigItem } from '../types';

interface ConfigState {
  configs: ConfigItem[];
  loading: boolean;
  error: string | null;
  
  setConfigs: (configs: ConfigItem[]) => void;
  setLoading: (loading: boolean) => void;
  setError: (error: string | null) => void;
}

export const useConfigStore = create<ConfigState>((set) => ({
  configs: [],
  loading: false,
  error: null,
  
  setConfigs: (configs) => set({ configs }),
  setLoading: (loading) => set({ loading }),
  setError: (error) => set({ error }),
}));
```

### useConfig.ts

```typescript
// features/config/hooks/useConfig.ts
import { useQuery, useMutation } from '@tanstack/react-query';
import { useConfigStore } from '../stores/configStore';
import { getConfigs, updateConfig } from '../api';
import { notification } from '@shared/lib/notification';

export function useConfigs() {
  const { setConfigs, setLoading, setError } = useConfigStore();
  
  return useQuery({
    queryKey: ['configs'],
    queryFn: getConfigs,
    onSuccess: (data) => setConfigs(data),
    onError: (err) => setError(err.message),
  });
}

export function useUpdateConfig() {
  return useMutation({
    mutationFn: updateConfig,
    onSuccess: () => {
      notification.success('配置已更新');
    },
    onError: (err) => {
      notification.error(err.message || '更新失败');
    },
  });
}
```

## 测试方案

1. Store 状态管理正确
2. Service 逻辑独立可测试
3. Hook 调用 API 正确
4. 功能回归测试通过

## 注意事项

- Store 只负责状态，不包含业务逻辑
- Service 处理纯计算和 API 调用
- Hook 组合 Store 和 Service，供组件使用
- 消除模块级可变状态（如 `healthDiagnosticTimer`）
