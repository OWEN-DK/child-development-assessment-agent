# Skill 与 MCP 使用手册

本文档汇总项目中所有可用的 Skill 和 MCP Server，以及使用原则。
CLAUDE.md 中仅引用本文件，不在此处展开详细内容。

---

## 📋 使用原则

### Skill 强制规则

**每次收到用户消息时，在响应任何内容之前，必须执行以下流程：**

1. **评估是否有 skill 适用** — 即使只有 1% 的可能性，也必须调用 Skill 工具检查
2. **创建型任务**（新功能、新组件、新逻辑）→ 先调用 `brainstorming` 再动手
3. **修复型任务**（bug、测试失败、异常行为）→ 先调用 `systematic-debugging` 再提方案
4. **多步骤任务**（超过 3 步或涉及多个文件）→ 先调用 `writing-plans` 再执行
5. **任务完成前** → 必须调用 `verification-before-completion` 运行验证命令

**禁止跳过 skill 直接执行。** 以下想法都是自我合理化，必须停止：
- "这个问题很简单，不需要 skill"
- "我先快速看一下代码"
- "我知道怎么做，不用那么正式"

### MCP 使用原则

- **CodeGraph** 用于结构性查询（调用关系/符号定义/影响分析），优先于 grep/read
- **Context7** 用于框架/库文档查询，遇到不熟悉的 API 先查 Context7
- **GitHub** 用于 PR/Issue 操作、仓库信息查询
- **Vercel** 用于部署、日志查看、环境变量管理
- **Playwright** 用于浏览器自动化测试和截图验证

---

## 🎯 Skill 完整目录

### 一、Superpowers（18 个）

#### 流程控制类

| Skill | 触发场景 |
|-------|----------|
| `using-superpowers` | 会话启动引导，定义 skill 使用规则 |
| `brainstorming` | 任何创造性工作前（新功能/组件/逻辑/修改行为） |
| `writing-plans` | 有多步骤任务规范，编写实施计划 |
| `executing-plans` | 有书面计划需要执行，带审查检查点 |
| `finishing-a-development-branch` | 实现完成、测试通过，决定如何集成（merge/PR/清理） |
| `verification-before-completion` | 声称工作完成/修复/通过前，运行验证命令 |

#### 开发方法论类

| Skill | 触发场景 |
|-------|----------|
| `test-driven-development` | 实现任何功能或修复前，先写测试 |
| `systematic-debugging` | 遇到 bug/测试失败/异常行为，提出修复方案前 |
| `using-git-worktrees` | 开始需要隔离的 feature 工作或执行实施计划前 |
| `requesting-code-review` | 完成任务、实现大功能、合并前验证 |
| `receiving-code-review` | 收到代码审查反馈，实现建议前 |

#### 并行与子 Agent 类

| Skill | 触发场景 |
|-------|----------|
| `dispatching-parallel-agents` | 面对 2+ 独立任务，无共享状态或顺序依赖 |
| `subagent-driven-development` | 在当前会话中执行带独立任务的实施计划 |

#### 扩展工具类

| Skill | 触发场景 |
|-------|----------|
| `writing-skills` | 创建新 skill、编辑已有 skill、验证 skill 是否工作 |
| `docx` | 创建/读取/编辑 Word 文档（.docx） |
| `frontend-design` | 构建前端界面（组件/页面/样式/React/Vue/HTML） |
| `mcp-builder` | 构建 MCP Server 集成外部 API 或服务 |
| `webapp-testing` | Web 应用测试（Playwright/E2E） |

---

### 二、Qiushi Skill（11 个）

| Skill | 触发场景 |
|-------|----------|
| `arming-thought` | 新对话开始时自动调用，建立方法论总原则 |
| `concentrate-forces` | 多任务争夺资源，需要确定主攻方向时 |
| `contradiction-analysis` | 问题复杂、存在冲突因素、优先级不清、不知先解决什么 |
| `criticism-self-criticism` | 工作完成/阶段验收/收到批评反馈/需要系统纠偏时 |
| `investigation-first` | 下判断/决策/建议前，事实/上下文/一手信息不充分时 |
| `mass-line` | 收集多方意见、整合零散反馈、带回验证时 |
| `overall-planning` | 多个目标/利益方/制约指标间需要动态平衡时 |
| `practice-cognition` | 理论到实践的转化、认知验证 |
| `protracted-strategy` | 长期战略规划、持久战策略 |
| `spark-prairie-fire` | 从小突破扩散到全局的策略 |
| `workflows` | 标准工作流程定义与执行 |

---

### 三、Codex Skills（28 个通用类）

#### 分析与研究

| Skill | 触发场景 |
|-------|----------|
| `analyze` | 深度代码库分析，返回排序综合报告 |
| `autoresearch` | 状态化验证器控制的研究循环 |
| `best-practice-research` | 有界最佳实践研究，优先使用官方/上游证据 |
| `wiki` | 知识库查询与维护 |
| `knowledge-update` | 纠正 LLM 对平台的过时知识 |

#### 代码质量

| Skill | 触发场景 |
|-------|----------|
| `code-review` | 全面代码审查 |
| `code-simplifier` | 简化/重构代码以提高清晰度、一致性、可维护性 |
| `verification` | 代码验证与检查 |
| `react-best-practices` | React 最佳实践指导 |
| `design` | 仓库级 DESIGN.md 工作流，产品/UI/UX 决策源 |
| `design-system` | Token 架构、组件规范、幻灯片生成 |
| `ui-styling` | UI 样式设计与实现 |
| `ui-ux-pro-max` | UI/UX 专业级设计指导 |

#### 项目管理

| Skill | 触发场景 |
|-------|----------|
| `plan` | 战略规划，可选访谈工作流 |
| `pipeline` | 可配置管道编排器，排序阶段 |
| `bootstrap` | 项目引导编排（Vercel 链接资源/数据库/auth/集成） |
| `release` | 发布管理与版本控制 |
| `deployments-cicd` | Vercel 部署和 CI/CD 专家指导 |
| `performance-goal` | 性能优化工作流 |
| `skill` | Skill 创建与管理 |

#### 文档与测试

| Skill | 触发场景 |
|-------|----------|
| `pdf` | PDF 文件读取/创建/审查，布局和渲染相关 |
| `playwright` | Playwright 测试脚本编写 |
| `playwright-interactive` | Playwright 交互式测试 |
| `doctor` | oh-my-codex 安装问题诊断和修复 |
| `team` | 团队协作与子 Agent 管理 |
| `shadcn` | shadcn/ui 组件使用与定制 |
| `workflow` | 自定义工作流定义与执行 |

---

## 🔌 MCP Server 完整列表

| 名称 | 类型 | 用途 |
|------|------|------|
| `codegraph` | stdio | 代码知识图谱（调用关系/符号定义/影响分析） |
| `context7` | stdio | 文档上下文查询（框架/库文档） |
| `playwright` | stdio | 浏览器自动化测试 |
| `vercel` | http | Vercel 部署管理（项目/部署/日志） |
| `github` | http | GitHub API（PR/Issue/仓库信息） |

---

##  Skill 调用方式

在 Qoder 中调用 skill 的方式：
- **Slash 命令**：输入 `/brainstorming`、`/code-review` 等
- **Skill 工具**：通过 Skill 工具直接调用
- **自动触发**：CLAUDE.md 中定义的启动规则会引导自动调用关键 skill
