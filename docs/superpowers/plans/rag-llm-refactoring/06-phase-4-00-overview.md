# Phase 4: 系统配置页面重构

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 重构系统配置页面，修复现有阻塞性 Bug，实现专家模式（侧边栏 + 手风琴 + 搜索）、向导模式、LLM 健康度诊断、配置导入导出等核心功能，提供双模式配置体验。

**Architecture:** 采用 Zustand 状态管理 + Ant Design 组件库，前后端完全解耦。专家模式与向导模式共享同一份配置数据草稿，切换模式不丢失未保存修改。

**Tech Stack:** React 19, TypeScript 5.3, Zustand 5, Ant Design 6.3.2, FastAPI 0.135.1, MySQL 5.7

**Spec 文档:** [2026-04-15-system-config-redesign.md](../../specs/2026-04-15-system-config-redesign.md)

---

## 🎯 项目背景与目标

### 背景
现有系统配置页面存在以下痛点：
1. **阻塞性 Bug**：恢复出厂设置 404、保存 API 字段不匹配、分类过滤失效
2. **布局问题**：固定 240px 侧边栏，无响应式适配，页面过长无折叠
3. **功能缺失**：无搜索、无修改标记、无撤销、无健康诊断、无导入导出
4. **代码质量**：单文件 861 行职责过重、硬编码重复、死代码未清理

### 核心目标
1. ✅ 修复 3 个阻塞性 Bug（P0）
2. ✅ 实现专家模式：侧边栏 + 手风琴 + 搜索 + 修改标记 + 撤销
3. ✅ 实现向导模式：3 步分步引导配置
4. ✅ 实现 LLM 健康度诊断（自动 + 手动触发）
5. ✅ 实现配置导入/导出功能
6. ✅ 实现响应式布局适配（4 个断点）
7. ✅ 清理技术债务（死代码、冗余状态、硬编码）

---

## 📋 实施原则

1. **Bug 优先**：先修复 3 个 P0 Bug，再实施新功能
2. **增量迭代**：按 P0 → P1 → P2 分阶段实施，每个阶段产出可独立运行的功能
3. **测试驱动**：每个功能模块必须包含单元测试与集成测试
4. **向后兼容**：保持现有配置数据格式兼容，不破坏已有配置版本
5. **组件复用**：提取共享组件（ConfigField、VersionSelector 等），避免重复代码

---

## ✅ 验收标准

### Phase 4.1 验收（Bug 修复）
- 恢复出厂设置功能正常工作，有二次确认与审计日志
- 保存配置功能正常，前后端字段名一致
- Tree 选择任意分类（含子分类）时右侧显示对应配置项

### Phase 4.2 验收（专家模式）
- 侧边栏导航正常，点击平滑滚动到对应区域
- 搜索功能支持 ⌘K 快捷键，响应时间 ≤200ms
- 手风琴折叠/展开正常，避免页面过长
- 修改标记高亮显示，展示"原值→新值"对比
- 单个撤销按钮功能正常
- 响应式布局在 4 个断点下正常显示

### Phase 4.3 验收（高级功能）
- LLM 健康度诊断正常，30 秒防抖触发，缓存 5 分钟
- 向导模式 3 步流程完整，可跳过，可切换专家模式
- 配置导入/导出功能正常，支持 JSON 格式
- 模式切换流畅，draftChanges 不丢失

---

# 项目概览与文件结构变更

## 📋 文件结构变更总览

### 新增文件

| 文件路径 | 职责 | 所属阶段 |
|---------|------|----------|
| `frontend/src/store/configStore.ts` (扩展) | 新增 modePreference、healthDiagnostic、searchQuery、favorites 状态 | Phase 4.3 |
| `frontend/src/components/config/ExpertMode.tsx` | 专家模式容器组件 | Phase 4.2 |
| `frontend/src/components/config/WizardMode.tsx` | 向导模式容器组件 | Phase 4.3 |
| `frontend/src/components/config/Sidebar.tsx` | 侧边栏导航组件 | Phase 4.2 |
| `frontend/src/components/config/TopToolbar.tsx` | 顶部工具栏（搜索 + 筛选 + 操作） | Phase 4.2 |
| `frontend/src/components/config/AccordionPanel.tsx` | 手风琴面板组件 | Phase 4.2 |
| `frontend/src/components/config/ConfigCard.tsx` | 配置卡片组件 | Phase 4.2 |
| `frontend/src/components/config/ConfigField.tsx` | 配置字段编辑器（共享） | Phase 4.2 |
| `frontend/src/components/config/ChangeIndicator.tsx` | 修改标记组件 | Phase 4.2 |
| `frontend/src/components/config/HealthScoreCard.tsx` | 健康度卡片组件 | Phase 4.3 |
| `frontend/src/components/config/ModeSwitcher.tsx` | 模式切换组件 | Phase 4.3 |
| `frontend/src/components/config/StepNavigator.tsx` | 步骤导航器组件 | Phase 4.3 |
| `frontend/src/components/config/SearchBox.tsx` | 搜索框组件（支持 ⌘K） | Phase 4.2 |
| `frontend/src/components/config/ImportExportDialog.tsx` | 导入导出对话框 | Phase 4.3 |
| `frontend/src/components/config/MobileNav.tsx` | 移动端底部导航 | Phase 4.2 |
| `frontend/src/components/config/ConfigErrorBoundary.tsx` | 错误边界组件 | Phase 4.2 |
| `frontend/src/components/config/constants.ts` | 配置分类常量、场景映射 | Phase 4.2 |
| `backend/src/controller/config_health_controller.py` | LLM 健康诊断 API | Phase 4.3 |
| `backend/src/service/config_health_service.py` | 健康诊断服务（LLM + 本地规则） | Phase 4.3 |
| `backend/src/service/config_export_service.py` | 配置导入导出服务 | Phase 4.3 |
| `backend/src/schemas/config_health.py` | 健康诊断 Pydantic 模型 | Phase 4.3 |
| `backend/tests/api/test_config_health.py` | 健康诊断 API 测试 | Phase 4.3 |
| `backend/tests/api/test_config_export.py` | 导入导出 API 测试 | Phase 4.3 |
| `backend/tests/service/test_config_health_service.py` | 健康诊断服务测试 | Phase 4.3 |

### 修改文件

| 文件路径 | 变更内容 | 所属阶段 |
|---------|----------|----------|
| `frontend/src/pages/SystemConfigPage.tsx` | 重构为容器组件，集成 ExpertMode/WizardMode/ModeSwitcher | Phase 4.2 |
| `frontend/src/pages/SystemConfigPage.module.scss` | 重写样式，支持响应式布局（4 断点） | Phase 4.2 |
| `frontend/src/components/config/DynamicConfigForm.tsx` | 拆分为多组件，修复分类过滤逻辑 | Phase 4.2 |
| `frontend/src/components/config/DynamicConfigForm.module.scss` | 拆分样式文件 | Phase 4.2 |
| `frontend/src/components/config/ConfigVersionSelector.tsx` | 保持兼容，集成到新布局 | Phase 4.2 |
| `frontend/src/components/config/ConfigDiffView.tsx` | 集成到专家模式（P2） | Phase 4.3 |
| `backend/src/controller/config_controller.py` | 新增 /reset、/validate、/export、/import 路由 | Phase 4.1/4.3 |
| `backend/src/schemas/config.py` | 新增 ResetConfigRequest、ValidateConfigRequest 等 | Phase 4.1 |
| `backend/src/config/core/manager.py` | 新增 reset_to_factory() 方法 | Phase 4.1 |
| `backend/src/repository/config_repository.py` | 新增 reset 相关审计日志记录 | Phase 4.1 |

### 删除文件

| 文件路径 | 原因 | 所属阶段 |
|---------|------|----------|
| `frontend/src/features/system-config/` (整个目录) | 死代码，无任何模块引用 | Phase 4.1 |

---

## 🏗️ 架构说明

### 专家模式布局

```
┌─────────────────────────────────────────────────────────────┐
│  🔧 系统配置  │  🔍 搜索配置...  │  [状态筛选]  │  [导入][导出][保存]  │
├──────────────┬──────────────────────────────────────────────┤
│              │                                              │
│  📂 配置分类  │  🤖 LLM 配置诊断报告                         │
│  🔑 凭证管理  │  整体配置良好，建议优化以下配置...            │
│  🤖 AI模型   │  ⚠️ RAG检索阈值偏低 → [去修改]               │
│  📚 RAG      │                                              │
│  ⚙️ 业务规则  │  ┌──────────────────────────────────────┐   │
│  📦 系统设置  │  │ 🔑 LLM 凭证管理           ✅ 已配置 ▼ │   │
│              │  ├──────────────────────────────────────┤   │
│  ──────────  │  │  DashScope API Key    [已修改]       │   │
│  ⭐ 我的收藏  │  │  sk-****                  [撤销]     │   │
│  ──────────  │  │                                      │   │
│  📊 健康度   │  │  OpenAI API Key                     │   │
│     85/100   │  │  sk-****                            │   │
│   [重新诊断] │  └──────────────────────────────────────┘   │
│              │                                              │
└──────────────┴──────────────────────────────────────────────┘
```

### 向导模式流程

```
步骤 1/3：基础配置 → 步骤 2/3：高级配置 → 步骤 3/3：系统设置
  ↓                    ↓                    ↓
凭证管理 + 核心模型    RAG + 业务规则       系统设置 + 其他
可跳过                 可跳过               可跳过
```

### 数据流

```
ConfigStore (Zustand)
├── configFields: ConfigFieldMetadata[]     // 配置元数据
├── draftChanges: Record<string, any>       // 未保存修改
├── originalValues: Record<string, any>     // 原始值（用于对比）
├── activeVersion: string | null            // 当前版本
├── modePreference: 'expert' | 'wizard'     // 用户偏好模式
├── healthDiagnostic: DiagnosticResult      // LLM 诊断结果
├── searchQuery: string                     // 搜索关键词
├── favorites: string[]                     // 收藏的配置项
└── expandedKeys: string[]                  // 手风琴展开状态

Actions:
├── loadConfig()                            // 加载配置
├── updateDraft(key, value)                 // 更新草稿
├── saveConfig(description)                 // 保存配置
├── undoChange(key)                         // 撤销单个修改
├── resetToFactory()                        // 恢复出厂设置
├── switchMode(mode)                        // 切换模式
├── runHealthDiagnostic()                   // 运行健康诊断
├── setSearchQuery(query)                   // 设置搜索关键词
├── toggleFavorite(key)                     // 切换收藏
└── toggleAccordion(key)                    // 切换手风琴展开
```

---

## 📦 依赖管理

### 前端新增依赖

```json
// package.json (如有需要)
{
  "dependencies": {
    // 现有依赖已满足需求，无需新增
  }
}
```

### 后端新增依赖

```toml
# pyproject.toml (如有需要)
# 现有依赖已满足需求，无需新增
```

---

## 🔧 配置管理

### 健康诊断 Prompt

通过 PromptManager 管理，prompt_key: `config_health_diagnosis`

### 本地规则评分权重

| 配置类别 | 权重 | 评分规则 |
|----------|------|----------|
| LLM 凭证 | 30% | 至少配置 1 个提供商得满分 |
| 核心场景模型 | 25% | 使用推荐模型得满分 |
| RAG 配置 | 20% | 检索策略、分块大小合理得满分 |
| 业务规则 | 15% | 校验规则、评分规则完整得满分 |
| 系统设置 | 10% | 日志、路径等基础配置正确得满分 |

---

## 📖 下一步

继续查看各个子阶段的详细实施方案：

1. [Phase 4.1: P0 Bug 修复](./06-phase-4-01-bug-fixes.md)
2. [Phase 4.2: 专家模式实施](./06-phase-4-02-expert-mode.md)
3. [Phase 4.3: ConfigStore 扩展与状态管理](./06-phase-4-03-store-extension.md)
4. [Phase 4.4: 后端 API 扩展](./06-phase-4-04-backend-api.md)
5. [Phase 4.5: 向导模式实施](./06-phase-4-05-wizard-mode.md)

---

**返回索引：** [README.md](./README.md)
