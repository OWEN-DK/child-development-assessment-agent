# Phase 1: LLM 多提供商 + 热配置 Implementation Plan

> **⚠️ 本文档已拆分**: 本文件已拆分为 5 个独立子文档，请使用下方索引访问。
> **状态:** ✅ 方案已审查并修正（评分 9.5/10，已修复 25 个问题）

## 文档索引

| # | 文档 | 内容 | 行数 |
|---|------|------|------|
| 0 | [Overview](./01-phase-1-00-overview.md) | 架构总览、实施顺序、验收标准、回滚计划、性能基准、问题清单 | ~180 |
| 1 | [配置层改造](./01-phase-1-01-config-layer.md) | Task 1.1: LLM/Embedding/RAG 配置模块扩展 | ~170 |
| 2 | [工厂类重构](./01-phase-1-02-factory-refactor.md) | Task 1.2: ProviderRegistry, LLMServiceFactory, EmbeddingFactory, RerankerFactory | ~550 |
| 3 | [热更新机制](./01-phase-1-03-hot-reload.md) | Task 1.3: 配置校验层、零停机热更新测试、EventBus 集成 | ~170 |
| 4 | [调用点改造](./01-phase-1-04-call-sites.md) | Task 1.4: 节点/服务/解析器/评分器调用点替换 | ~120 |
| 5 | [依赖与测试](./01-phase-1-05-dependencies.md) | Task 1.5: pyproject.toml 更新、pytest fixtures、集成测试 | ~150 |

## 快速导航

- **开始实施**: 先阅读 [Overview](./01-phase-1-00-overview.md) 了解整体架构
- **配置改造**: 查看 [01-config-layer](./01-phase-1-01-config-layer.md)
- **工厂重构**: 查看 [02-factory-refactor](./01-phase-1-02-factory-refactor.md)
- **热更新**: 查看 [03-hot-reload](./01-phase-1-03-hot-reload.md)
- **调用点**: 查看 [04-call-sites](./01-phase-1-04-call-sites.md)
- **依赖测试**: 查看 [05-dependencies](./01-phase-1-05-dependencies.md)

## 实施顺序

1. 配置层改造 (01) → 2. 配置校验层 (03-Task1.3.1) → 3. 工厂类重构 (02) → 4. 调用点改造 (04) → 5. 依赖安装 (05) → 6. 热更新测试 (03-Task1.3.2/3)

> **⚠️ 注意**: 配置校验层 (Task 1.3.1) 必须在工厂类重构 (Task 1.2.2) 之前实现，因为工厂依赖校验器。
