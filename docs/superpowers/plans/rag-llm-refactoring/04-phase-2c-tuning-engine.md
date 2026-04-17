# Phase 2C: 智能调参建议引擎 Implementation Plan

> **⚠️ 本文档已拆分**: 本文件已拆分为 6 个独立子文档 + 1 个 Overview，请使用下方索引访问。
> **状态:** 📋 方案构建完成，待实施

## 文档索引

| # | 文档 | 内容 | 行数 |
|---|------|------|------|
| 0 | [Overview](./04-phase-2c-00-overview.md) | 架构总览、实施顺序、验收标准、回滚计划、风险登记册 | ~140 |
| 1 | [规则引擎](./04-phase-2c-01-rule-engine.md) | 规则配置化 (MySQL) + 核心实现 + 冲突检测 | ~200 |
| 2 | [历史对比分析](./04-phase-2c-02-history-analyzer.md) | 数据关联链路 + 相似匹配 + 效果追踪 | ~160 |
| 3 | [LLM 诊断](./04-phase-2c-03-llm-diagnoser.md) | Prompt 设计 + Bad Case 聚合 + json-repair 输出解析 | ~160 |
| 4 | [统一引擎 + API](./04-phase-2c-04-engine-api.md) | 引擎入口 + 3 个 API 接口 + DI 注册 | ~140 |
| 5 | [前端集成 (MVP)](./04-phase-2c-05-frontend-mvp.md) | 建议面板 + 一键优化组件 + API 客户端 | ~160 |
| 6 | [TDD 测试策略](./04-phase-2c-06-testing.md) | 测试文件清单 + 红绿重构步骤 + Fixture 定义 | ~120 |

## 快速导航

- **开始实施**: 先阅读 [Overview](./04-phase-2c-00-overview.md) 了解整体架构
- **规则引擎**: 查看 [01-rule-engine](./04-phase-2c-01-rule-engine.md)
- **历史对比**: 查看 [02-history-analyzer](./04-phase-2c-02-history-analyzer.md)
- **LLM 诊断**: 查看 [03-llm-diagnoser](./04-phase-2c-03-llm-diagnoser.md)
- **引擎 + API**: 查看 [04-engine-api](./04-phase-2c-04-engine-api.md)
- **前端 MVP**: 查看 [05-frontend-mvp](./04-phase-2c-05-frontend-mvp.md)
- **测试策略**: 查看 [06-testing](./04-phase-2c-06-testing.md)

## 实施顺序

1. 规则配置化 (01-Task 2C.1.1) → 2. 规则引擎核心 (01-Task 2C.1.2) → 3. 冲突检测 (01-Task 2C.1.3) → 4. 历史对比分析 (02) → 5. LLM 诊断 (03) → 6. 统一引擎 (04-Task 2C.4.1) → 7. API 实现 (04-Task 2C.4.2) → 8. 前端集成 (05) → 9. TDD 测试 (06，与开发并行)

> **⚠️ 注意**: TDD 测试 (06) 应与开发并行推进，每个模块实施前先生成测试确认失败 (Red)，再实现代码 (Green)，最后重构。
