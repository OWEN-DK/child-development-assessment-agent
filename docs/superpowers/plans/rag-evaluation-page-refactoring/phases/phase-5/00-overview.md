# Phase 5: 推荐模式面板 + 配置/提示词编辑 — 总览

> **需求来源**: spec 文档 `04-frontend-pages.md` 4.2-4.3 节
> **需求点数量**: 11 个
> **优先级**: P2

## 目标

实现推荐模式面板（三种模式）、采纳→审查→保存三步分离、配置/提示词原子保存与热重载。

## 需求点清单

### 前端面板 (5 个) - P0 核心流程

| # | 需求点 | 实施文件 | 优先级 | 说明 |
|---|--------|---------|--------|------|
| 1 | 推荐模式面板（三种模式） | `01-recommendation-panel-three-modes.md` | P0 | 推荐/向导/专家三种模式切换 |
| 2 | 审查面板（抽屉式） | `02-review-panel-drawer.md` | P0 | 点击"审查已采纳项"展开，抽屉式覆盖 |
| 5 | 采纳→审查→保存三步流程 | `05-adopt-review-save-flow.md` | P0 | 三步分离，不合并为一步 |
| 3 | 配置对比视图 | `03-comparison-view-config.md` | P1 | 展示配置修改前后 diff + 历史参考 |
| 4 | 提示词对比视图 | `04-comparison-view-prompt.md` | P1 | 展示提示词内容 diff + 变更摘要 |

### 后端服务 (3 个) - P0 核心功能

| # | 需求点 | 实施文件 | 优先级 | 说明 |
|---|--------|---------|--------|------|
| 6 | 原子保存事务 | `06-atomic-save-transaction.md` | P0 | ConfigChangeSet 事务，配置+提示词整体保存 |
| 7 | 配置热重载 | `07-config-hot-reload.md` | P0 | Redis Pub/Sub 发布 config_changed 事件 |
| 8 | ConfigCache 单例 | `08-config-cache-singleton.md` | P0 | 配置缓存，订阅事件后刷新 |

### 忽略列表 (2 个) - P1 次要功能

| # | 需求点 | 实施文件 | 优先级 | 说明 |
|---|--------|---------|--------|------|
| 9 | 已忽略建议列表 | `09-ignored-suggestions-list.md` | P1 | 展示忽略记录，支持 report/test_set 级别 |
| 10 | 恢复忽略建议 | `10-restore-ignored-suggestion.md` | P1 | 恢复后重新加入推荐列表 |

### 布局适配 (1 个) - P2 优化

| # | 需求点 | 实施文件 | 优先级 | 说明 |
|---|--------|---------|--------|------|
| 11 | 面板布局适配 | `11-panel-layout-adaptation.md` | P2 | 固定分栏 (380px) / Drawer 抽屉式 (< 1440px) |

## 验收标准

- [ ] 推荐模式面板三种模式切换正常（推荐/向导/专家）
- [ ] 采纳→审查→保存三步分离
- [ ] 配置/提示词原子保存（ConfigChangeSet 事务）
- [ ] 热重载机制工作正常（Redis Pub/Sub + ConfigCache）
- [ ] 对比视图展示 diff（配置值 diff、提示词内容 diff）
- [ ] 已忽略列表功能正常（恢复操作）
- [ ] 面板布局适配（固定分栏 / Drawer 抽屉式）

## 核心原则

- 推荐只是参考，不替用户做决策
- 每个推荐必须回答：为什么改？改了有什么影响？前后对比是什么？
- 禁止"一键应用"式设计，用户需要审查后再保存

---

**文档索引**: 
- 上一节: [Phase 4 总览](../phase-4/00-overview.md)
- 下一节: [01-recommendation-panel-three-modes.md](./01-recommendation-panel-three-modes.md) — 需求点 1
