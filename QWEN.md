# Qwen Code 项目指南

## Superpowers 技能集成

本项目已安装 [Superpowers](https://github.com/obra/superpowers) 技能库，位于 `.agent/superpowers/` 目录。

### 核心工作流

在任何任务开始时，**必须**遵循以下流程：

1. **brainstorming** - 在编写代码前激活。通过提问优化设计，展示设计方案供确认。
2. **using-git-worktrees** - 设计确认后激活。创建隔离工作空间。
3. **writing-plans** - 将工作分解为小任务（每个2-5分钟），包含确切文件路径、完整代码、验证步骤。
4. **subagent-driven-development** - 通过子代理执行每个任务，进行两阶段审查（规范合规性、代码质量）。
5. **test-driven-development** - 强制执行 RED-GREEN-REFACTOR 循环。
6. **requesting-code-review** - 任务间进行代码审查。
7. **finishing-a-development-branch** - 任务完成时验证测试、清理工作树。

### 技能位置

所有技能定义在 `.agent/superpowers/skills/` 目录下：

| 技能 | 用途 |
|------|------|
| `brainstorming` | 设计讨论与方案优化 |
| `writing-plans` | 编写详细实施计划 |
| `executing-plans` | 批量执行计划 |
| `subagent-driven-development` | 子代理驱动开发 |
| `test-driven-development` | TDD 红绿重构 |
| `systematic-debugging` | 系统化调试 |
| `requesting-code-review` | 代码审查请求 |
| `receiving-code-review` | 接收代码审查反馈 |
| `using-git-worktrees` | Git 工作树使用 |
| `finishing-a-development-branch` | 分支完成工作流 |
| `dispatching-parallel-agents` | 并行代理调度 |
| `verification-before-completion` | 完成前验证 |
| `writing-skills` | 编写新技能 |
| `using-superpowers` | 技能系统介绍 |

### 使用方式

由于 Qwen Code 没有原生的 Skill 工具，在任务开始时：

1. **主动读取相关技能**：使用 `read_file` 工具读取 `.agent/superpowers/skills/<skill-name>/SKILL.md`
2. **遵循技能指导**：严格按照技能内容执行
3. **创建任务清单**：使用 `todo_write` 工具跟踪技能要求的检查项

### 红旗警告

以下想法意味着你必须停下来检查技能：

| 想法 | 现实 |
|------|------|
| "这只是个简单问题" | 问题也是任务，检查技能 |
| "我需要先了解更多上下文" | 技能检查在澄清问题之前 |
| "让我先探索代码库" | 技能告诉你如何探索 |
| "我记得这个技能" | 技能会更新，读取当前版本 |
| "这不需要正式技能" | 如果技能存在，就使用它 |

### 技能优先级

当多个技能可能适用时，按以下顺序使用：

1. **流程技能优先**（brainstorming、debugging）- 决定如何接近任务
2. **实施技能其次**（具体领域技能）- 指导执行

### 注意事项

- **用户指令优先**：CLAUDE.md 中的指令优先级最高
- **技能是强制的**：如果有 1% 的可能性技能适用，就必须使用
- **不要跳过流程**：即使在看似简单的任务中
