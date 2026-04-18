# Phase 6-5: 消除通知重复

> **需求来源**: spec 文档 `unified-api-response-and-error-handling.md` 中 `7.5.4` 节
> **所属 Phase**: Phase 6

## 需求定义

提取 95+ 处重复的 `message.success/error` 调用至统一工具函数，消除重复的通知处理代码。

## 验收标准

- [ ] `shared/lib/notification.ts` 创建完成
- [ ] 95+ 处 `message.*` 调用替换为工具函数
- [ ] 功能回归测试通过

## 涉及文件

| 文件路径 | 操作 | 说明 |
|---------|------|------|
| `frontend/src/shared/lib/notification.ts` | 新增 | 通知工具函数 |
| 所有 Page/Feature 组件 | 修改 | 替换通知调用 |

## 实现方案

### shared/lib/notification.ts

```typescript
/**
 * 通知工具模块
 * 
 * 统一成功/错误/警告通知，消除重复的 message.* 调用。
 */

import { message } from 'antd';

/**
 * 执行 API 调用并自动处理通知
 * 
 * 使用方式：
 *   await handleApiCall(() => deleteTestRun(id), {
 *     successMsg: '删除成功',
 *     errorMsg: '删除失败',
 *   });
 */
export async function handleApiCall<T>(
  fn: () => Promise<T>,
  options?: {
    successMsg?: string;
    errorMsg?: string;
    onSuccess?: (data: T) => void;
    silent?: boolean;
  }
): Promise<T | null> {
  try {
    const data = await fn();
    if (options?.successMsg && !options?.silent) {
      message.success(options.successMsg);
    }
    options?.onSuccess?.(data);
    return data;
  } catch (error) {
    if (options?.errorMsg && !options?.silent) {
      message.error(options.errorMsg);
    }
    return null;
  }
}

/**
 * 成功通知
 */
export function success(msg: string, duration?: number) {
  message.success(msg, duration);
}

/**
 * 错误通知
 */
export function error(msg: string, duration?: number) {
  message.error(msg, duration);
}

/**
 * 警告通知
 */
export function warning(msg: string, duration?: number) {
  message.warning(msg, duration);
}

/**
 * 信息通知
 */
export function info(msg: string, duration?: number) {
  message.info(msg, duration);
}
```

### 替换对照

**替换前**（5 行）：
```tsx
try {
  await deleteTestRun(id);
  message.success('删除成功');
} catch {
  message.error('删除失败');
}
```

**替换后**（1 行）：
```tsx
import { handleApiCall } from '@shared/lib/notification';

await handleApiCall(() => deleteTestRun(id), {
  successMsg: '删除成功',
  errorMsg: '删除失败',
});
```

## 测试方案

1. `handleApiCall` 成功时显示成功通知
2. `handleApiCall` 失败时显示错误通知
3. `silent: true` 时不显示通知
4. `onSuccess` 回调正确执行

## 注意事项

- `silent` 选项用于不需要全局提示的场景（如表单校验失败）
- `onSuccess` 回调用于需要额外处理的场景（如刷新列表）
- 保持与后端统一响应格式的拦截器配合使用
