# Phase 6-4: 统一 API 调用模式

> **需求来源**: spec 文档 `unified-api-response-and-error-handling.md` 中 `7.5.3` 节
> **所属 Phase**: Phase 6

## 需求定义

统一所有 API 调用模式，页面组件禁止直接调用 `apiClient.get/post`，必须通过 `entities/*/api.ts` 或 `features/*/hooks/` 封装。

## 验收标准

- [ ] 所有 API 调用通过 entities 或 features 封装
- [ ] 页面组件无直接 `apiClient.get/post` 调用
- [ ] 使用 React Query 管理服务端状态
- [ ] 功能回归测试通过

## 涉及文件

| 文件路径 | 操作 | 说明 |
|---------|------|------|
| `entities/*/api.ts` | 新增 | API 调用封装 |
| `features/*/hooks/` | 新增 | React Query hooks |
| 所有 Page 组件 | 修改 | 替换直接 API 调用 |

## 实现方案

### 规则

| 规则 | 说明 |
|------|------|
| API 调用封装 | 放在 `entities/*/api.ts` |
| 状态管理 | 使用 React Query（`useQuery`/`useMutation`） |
| 页面组件 | 只使用 hooks，不调用 API |
| 错误处理 | 通过 hooks 统一处理 |

### entities/test-run/api.ts

```typescript
// entities/test-run/api.ts
import { apiClient } from '@shared/api/client';
import { TestRun } from './types';

export async function getTestRuns(): Promise<TestRun[]> {
  const response = await apiClient.get('/api/runs');
  return response.data;
}

export async function getTestRun(id: string): Promise<TestRun> {
  const response = await apiClient.get(`/api/runs/${id}`);
  return response.data;
}

export async function deleteTestRun(id: string): Promise<void> {
  await apiClient.delete(`/api/runs/${id}`);
}

export async function createTestRun(data: Partial<TestRun>): Promise<TestRun> {
  const response = await apiClient.post('/api/runs', data);
  return response.data;
}
```

### features/rag-eval/hooks/useRunList.ts

```typescript
// features/rag-eval/hooks/useRunList.ts
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { getTestRuns, deleteTestRun } from '@entities/test-run/api';
import { notification } from '@shared/lib/notification';

export function useRunList() {
  const queryClient = useQueryClient();
  
  const { data: runs, isLoading, error } = useQuery({
    queryKey: ['test-runs'],
    queryFn: getTestRuns,
  });
  
  const deleteRun = useMutation({
    mutationFn: deleteTestRun,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['test-runs'] });
      notification.success('删除成功');
    },
    onError: () => {
      notification.error('删除失败');
    },
  });
  
  return { runs, isLoading, error, deleteRun: deleteRun.mutate };
}
```

### pages/rag-eval/run-list.tsx

```typescript
// pages/rag-eval/run-list.tsx
import { useRunList } from '@features/rag-eval/hooks/useRunList';
import { RunListTable } from '@features/rag-eval/components/RunListTable';

export const RunListPage = () => {
  const { runs, isLoading, deleteRun } = useRunList();
  return <RunListTable runs={runs} loading={isLoading} onDelete={deleteRun} />;
};
```

## 测试方案

1. API 封装函数调用正确
2. React Query 缓存和失效正确
3. 页面组件无直接 API 调用
4. 功能回归测试通过

## 注意事项

- `apiClient` 已在拦截器中解包 `data` 字段
- React Query 的 `queryKey` 需保持一致
- `invalidateQueries` 用于缓存失效
