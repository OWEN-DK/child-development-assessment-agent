# Phase 6 - 前端架构重构

> **本文档包含**: Phase 6 总览、需求点清单、验收标准、实施顺序

---

## 目标

前端采用 FSD Lite（简化版 Feature-Sliced Design）架构，实现页面与逻辑分离，统一 API 调用模式，消除重复代码。

---

## 需求点清单

| # | 需求点名称 | 实施文件 | 影响范围 | 预估工作量 |
|---|-----------|---------|---------|-----------|
| 1 | FSD Lite 目录结构 | `01-fsd-lite-directory-structure.md` | 全局 | 中 |
| 2 | 页面与逻辑分离 | `02-page-logic-separation.md` | 所有 Page | 大 |
| 3 | 拆分 configStore | `03-split-config-store.md` | 369 行 | 中 |
| 4 | 统一 API 调用模式 | `04-unify-api-call-pattern.md` | 全局 | 中 |
| 5 | 消除通知重复 | `05-eliminate-notification-dup.md` | 95+ 处 | 中 |
| 6 | 统一 SSE 实现 | `06-unify-sse-implementation.md` | 2 hook + 1 service | 中 |
| 7 | 统一类型定义 | `07-unify-type-definitions.md` | models/ + api/*/types.ts | 中 |
| 8 | ESLint 与路径别名 | `08-eslint-path-alias-config.md` | 全局配置 | 小 |

---

## 验收标准

- [ ] 前端目录结构符合 FSD Lite：pages → widgets → features → entities → shared
- [ ] 页面与逻辑分离（如 RunListPage 217 行 → hook + component + page）
- [ ] `configStore.ts` 拆分为 4 个文件（store, diagnosticService, scoringService, useConfig）
- [ ] 所有 API 调用通过 `entities/*/api.ts` 或 `features/*/hooks/` 封装
- [ ] 95+ 处 `message.*` 调用替换为 `handleApiCall()` 工具
- [ ] SSE 实现统一为单一 hook
- [ ] 类型定义统一，无循环 re-export
- [ ] ESLint 规则与路径别名配置完成

---

## FSD Lite 分层依赖规则

```
pages → widgets → features → entities → shared
  ↓        ↓         ↓          ↓         ↓
  只能依赖下层，禁止跨层或反向依赖
```

---

## 目标目录结构

```
frontend/src/
├── app/                    # 应用启动层
├── pages/                  # 路由页面层
├── widgets/                # 复合区块层
├── features/               # 业务特性层
├── entities/               # 业务实体层
└── shared/                 # 共享层
```

---

## 实施顺序

1. 创建 FSD Lite 目录 → 2. 页面与逻辑分离 → 3. 拆分 configStore → 4. 统一 API 调用 → 5. 消除通知重复 → 6. 统一 SSE → 7. 统一类型 → 8. ESLint 配置

---

**下一步**: [01-fsd-lite-directory-structure.md](./01-fsd-lite-directory-structure.md)
