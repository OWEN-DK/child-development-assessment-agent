# Phase 6-8: ESLint 与路径别名配置

> **需求来源**: spec 文档 `unified-api-response-and-error-handling.md` 中 `7.6` 节
> **所属 Phase**: Phase 6

## 需求定义

配置 ESLint 规则强制 FSD 分层依赖，配置 TypeScript 路径别名，防止跨层或反向导入。

## 验收标准

- [ ] ESLint `no-restricted-imports` 规则配置完成
- [ ] TypeScript 路径别名配置完成
- [ ] 跨 feature 导入被禁止
- [ ] 功能回归测试通过

## 涉及文件

| 文件路径 | 操作 | 说明 |
|---------|------|------|
| `frontend/.eslintrc.js` 或 `eslint.config.js` | 修改 | 添加路径限制规则 |
| `frontend/tsconfig.json` | 修改 | 添加路径别名 |
| `frontend/vite.config.ts` | 修改 | 添加 Vite 路径别名 |

## 实现方案

### ESLint 规则

```javascript
// eslint.config.js 或 .eslintrc.js
{
  "rules": {
    "no-restricted-imports": [
      "error",
      {
        "patterns": [
          {
            "group": ["**/features/**"],
            "message": "禁止跨 feature 导入，请使用 shared 层或 entities 层"
          },
          {
            "group": ["**/pages/**"],
            "message": "禁止从 pages 导入，pages 层只能由路由使用"
          },
          {
            "group": ["**/widgets/**"],
            "message": "禁止从 widgets 导入，除非当前是 pages 层"
          }
        ]
      }
    ]
  }
}
```

### TypeScript 路径别名

```json
// tsconfig.json
{
  "compilerOptions": {
    "baseUrl": ".",
    "paths": {
      "@/*": ["./src/*"],
      "@app/*": ["./src/app/*"],
      "@pages/*": ["./src/pages/*"],
      "@features/*": ["./src/features/*"],
      "@entities/*": ["./src/entities/*"],
      "@widgets/*": ["./src/widgets/*"],
      "@shared/*": ["./src/shared/*"]
    }
  }
}
```

### Vite 路径别名

```typescript
// vite.config.ts
import { defineConfig } from 'vite';
import path from 'path';

export default defineConfig({
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
      '@app': path.resolve(__dirname, './src/app'),
      '@pages': path.resolve(__dirname, './src/pages'),
      '@features': path.resolve(__dirname, './src/features'),
      '@entities': path.resolve(__dirname, './src/entities'),
      '@widgets': path.resolve(__dirname, './src/widgets'),
      '@shared': path.resolve(__dirname, './src/shared'),
    },
  },
});
```

### 使用示例

```typescript
// 正确导入
import { useRunList } from '@features/rag-eval/hooks/useRunList';
import type { TestRun } from '@entities/test-run/types';
import { handleApiCall } from '@shared/lib/notification';

// 错误导入（ESLint 会报错）
import { useRunList } from '../../features/rag-eval/hooks/useRunList'; // 应使用 @features/
import { SomeComponent } from '../pages/SomePage'; // 禁止从 pages 导入
```

## 测试方案

1. ESLint 检查跨 feature 导入报错
2. TypeScript 编译路径解析正确
3. Vite 开发服务器路径别名生效
4. 功能回归测试通过

## 注意事项

- ESLint 规则在 CI 中强制执行
- 路径别名与 ESLint 规则配合使用
- 迁移期间可逐步启用，避免一次性全部报错
