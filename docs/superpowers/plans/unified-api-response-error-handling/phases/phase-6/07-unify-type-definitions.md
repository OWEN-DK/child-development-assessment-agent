# Phase 6-7: 统一类型定义

> **需求来源**: spec 文档 `unified-api-response-and-error-handling.md` 中 `7.5.5` 节
> **所属 Phase**: Phase 6

## 需求定义

统一前端类型定义，消除 `models/` vs `api/*/types.ts` 的重复定义和循环 re-export 链。

## 验收标准

- [ ] API 响应类型定义在 `api/*/types.ts`
- [ ] 业务实体类型定义在 `entities/*/types.ts`
- [ ] 无循环 re-export
- [ ] 功能回归测试通过

## 涉及文件

| 文件路径 | 操作 | 说明 |
|---------|------|------|
| `frontend/src/models/index.ts` | 删除 | 删除循环 re-export 链 |
| `frontend/src/api/assessment/types.ts` | 迁移 → `entities/assessment/types.ts` | |
| `frontend/src/api/rag-test/types.ts` | 迁移 → `entities/test-run/types.ts` + `entities/test-case/types.ts` | |
| `frontend/src/types/sse-events.ts` | 迁移 → `shared/types/sse.ts` | |

## 实现方案

### 迁移映射

| 当前路径 | 新路径 |
|---------|--------|
| `models/index.ts` | 删除，类型移至 `entities/*/types.ts` |
| `api/assessment/types.ts` | `entities/assessment/types.ts` |
| `api/rag-test/types.ts` | `entities/test-run/types.ts` + `entities/test-case/types.ts` |
| `types/sse-events.ts` | `shared/types/sse.ts` |

### entities/test-run/types.ts

```typescript
// entities/test-run/types.ts

export interface TestRun {
  id: string;
  test_set_id: string;
  status: TestRunStatus;
  created_at: string;
  completed_at: string | null;
  total_cases: number;
  completed_cases: number;
  metrics: RunMetrics | null;
}

export enum TestRunStatus {
  PENDING = 'pending',
  RUNNING = 'running',
  COMPLETED = 'completed',
  FAILED = 'failed',
  CANCELLED = 'cancelled',
}

export interface RunMetrics {
  precision_at_5: number;
  recall_at_5: number;
  f1_score: number;
  mrr: number;
}
```

### shared/types/sse.ts

```typescript
// shared/types/sse.ts

export interface SSEEvent {
  event: string;
  data: Record<string, unknown>;
}

export interface RunStartedEvent {
  run_id: string;
  test_set_id: string;
  total_cases: number;
  timestamp: string;
}

export interface ProgressEvent {
  run_id: string;
  completed: number;
  total: number;
  percentage: number;
  timestamp: string;
}

export interface TestCompletedEvent {
  run_id: string;
  metrics: RunMetrics;
  timestamp: string;
}
```

### 导入规则

| 类型 | 定义位置 | 导入方式 |
|------|---------|---------|
| API 响应类型 | `entities/*/types.ts` | `import type { TestRun } from '@entities/test-run/types'` |
| SSE 事件类型 | `shared/types/sse.ts` | `import type { ProgressEvent } from '@shared/types/sse'` |
| 通用类型 | `shared/types/common.ts` | `import type { PaginatedResponse } from '@shared/types/common'` |

## 测试方案

1. 类型导入无错误
2. 无循环 re-export
3. TypeScript 编译通过
4. 功能回归测试通过

## 注意事项

- 使用 `import type` 避免运行时依赖
- 类型定义与后端 API 响应格式严格对齐
- 删除旧的 `models/` 目录，避免混淆
