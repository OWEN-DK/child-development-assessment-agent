# Phase 6-1: FSD Lite 目录结构

> **需求来源**: spec 文档 `unified-api-response-and-error-handling.md` 中 `7.3` 节
> **所属 Phase**: Phase 6

## 需求定义

前端采用 FSD Lite（简化版 Feature-Sliced Design）架构，重组目录结构，建立清晰的分层依赖规则。

## 验收标准

- [ ] 前端目录结构符合 FSD Lite 规范
- [ ] 分层依赖规则：pages → widgets → features → entities → shared
- [ ] 无跨层或反向依赖
- [ ] 功能回归测试通过

## 涉及文件

| 文件路径 | 操作 | 说明 |
|---------|------|------|
| `frontend/src/app/` | 新增 | 应用启动层 |
| `frontend/src/pages/` | 重组 | 路由页面层 |
| `frontend/src/widgets/` | 新增 | 复合区块层 |
| `frontend/src/features/` | 重组 | 业务特性层 |
| `frontend/src/entities/` | 新增 | 业务实体层 |
| `frontend/src/shared/` | 重组 | 共享层 |

## 实现方案

### 目标目录结构

```
frontend/src/
├── app/                    # 应用启动层
│   ├── main.tsx            # 入口
│   ├── App.tsx             # 根组件
│   ├── providers/          # 全局 Provider（Router, QueryClient, Store）
│   └── styles/             # 全局样式
│
├── pages/                  # 路由页面层（组合 features/widgets）
│   ├── assessment/
│   │   └── index.tsx       # 评估页面
│   ├── knowledge-base/
│   │   └── index.tsx       # 知识库页面
│   └── system-config/
│       └── index.tsx       # 系统配置页面
│
├── widgets/                # 复合区块层（多 feature 组合）
│   ├── assessment-form-widget/
│   ├── report-viewer-widget/
│   └── sidebar-layout/
│
├── features/               # 业务特性层（自包含模块）
│   ├── assessment/
│   │   ├── components/     # 特性专属组件
│   │   ├── hooks/          # 特性专属 hooks
│   │   ├── stores/         # 特性专属 stores
│   │   ├── types/          # 特性专属类型
│   │   └── index.ts        # 公共导出
│   ├── rag-eval/
│   ├── documents/
│   ├── knowledge/
│   ├── monitoring/
│   ├── prompts/
│   └── config/
│
├── entities/               # 业务实体层（核心数据模型）
│   ├── test-run/
│   │   ├── types.ts        # TestRun 类型定义
│   │   ├── api.ts          # TestRun API 调用
│   │   └── components/     # TestRun 展示组件
│   ├── test-case/
│   ├── document/
│   ├── prompt/
│   └── config/
│
└── shared/                 # 共享层（跨特性复用）
    ├── api/                # API 客户端、拦截器
    │   ├── client.ts
    │   └── interceptors/
    ├── ui/                 # 通用 UI 组件
    │   ├── Button/
    │   ├── Table/
    │   ├── Modal/
    │   ├── EmptyState/
    │   ├── ErrorBoundary/
    │   └── LoadingSpinner/
    ├── hooks/              # 通用 hooks
    │   ├── useModal.ts
    │   ├── usePagination.ts
    │   ├── useDebounce.ts
    │   └── useApiCall.ts
    ├── lib/                # 工具函数、常量
    │   ├── constants.ts
    │   ├── notification.ts
    │   └── formatters.ts
    └── types/              # 通用类型
        └── common.ts
```

### 分层依赖规则

```
pages → widgets → features → entities → shared
  ↓        ↓         ↓          ↓         ↓
  只能依赖下层，禁止跨层或反向依赖
```

| 层级 | 职责 | 禁止 |
|------|------|------|
| `pages/` | 路由组合、页面布局 | 直接写业务逻辑、API 调用 |
| `widgets/` | 多 feature 组合区块 | 直接调用 API |
| `features/` | 完整业务特性 | 依赖其他 feature |
| `entities/` | 核心数据模型+展示 | 包含页面路由逻辑 |
| `shared/` | 跨特性复用工具 | 包含业务逻辑 |

## 迁移策略

1. 创建新目录结构
2. 按 feature 逐步迁移（一个 feature 完成后验证功能）
3. 删除旧目录（`components/` 等）
4. 更新 tsconfig 路径别名

## 测试方案

1. 新目录结构创建完成
2. 各层依赖规则无违反
3. 前端编译通过
4. 功能回归测试通过

## 注意事项

- 迁移按 feature 逐步进行，每迁移一个都需验证功能
- 禁止跨层导入（如 pages 直接导入 entities）
- 路径别名在 `tsconfig.json` 中配置
