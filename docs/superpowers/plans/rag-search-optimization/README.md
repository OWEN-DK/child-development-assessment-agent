# RAG 知识库搜索优化

基于 12 项诊断测试结果（通过率 17%），对 RAG 知识库搜索系统进行系统性优化。

## 📁 文档结构

```
rag-search-optimization/
├── README.md                              # 本文件（主索引）
├── PROGRESS.md                            # 进度追踪
├── 00-overview.md                         # 项目概览与文件结构变更
│
├── # Phase A: 分数语义重构 (P0)
├── 01-phase-a-00-overview.md              # Phase A 总览与目标
├── 01-phase-a-01-score-separation.md      # 分数分离与数据模型变更
├── 01-phase-a-02-age-fit-scorer.md        # 年龄适配度细粒度计算器
├── 01-phase-a-03-score-calibration.md     # BM25/向量分数校准统一
├── 01-phase-a-04-age-filter-refactor.md   # 年龄过滤逻辑重构
├── 01-phase-a-05-filter-pipeline-integration.md  # 过滤流水线集成
├── 01-phase-a-06-frontend-adaptation.md   # 前端分数展示适配
│
├── # Phase B: 查询权重调优 (P1)
├── 02-phase-b-00-overview.md              # Phase B 总览与目标
├── 02-phase-b-01-query-analyzer.md        # 查询类型分析器
├── 02-phase-b-02-weight-decision.md       # 动态权重决策逻辑
│
├── # Phase C: 同义词扩展质量优化 (P1)
├── 03-phase-c-00-overview.md              # Phase C 总览与目标
├── 03-phase-c-01-synonym-validator.md     # 同义词质量验证器
├── 03-phase-c-02-fallback-strategy.md     # LLM 失败本地兜底策略
│
├── # Phase D: 性能优化 (P2)
├── 04-phase-d-00-overview.md              # Phase D 总览与目标
├── 04-phase-d-01-hash-dedup.md            # content_hash 精确去重
├── 04-phase-d-02-minhash-dedup.md         # MinHash 近似去重
├── 04-phase-d-03-reranker-warmup.md       # Cross-Encoder 模型预热
├── 04-phase-d-04-dynamic-initial-k.md     # 动态 initial_k 规则
├── 04-phase-d-05-input-validation.md      # 输入校验与预处理
├── 04-phase-d-06-boundary-age-fallback.md # 边界年龄映射与降级策略
│
├── appendix-a-test-verification.md        # 诊断测试验收报告
├── appendix-b-risk-control.md             # 风险控制与回滚策略
│
└── DOCUMENT_STRUCTURE.md                  # 文档结构说明
```

## 🎯 优化目标

| 指标 | 当前值 | 目标值 |
|------|--------|--------|
| Precision@5 | 0.53 | ≥0.75 |
| 年龄适配度不同值数量 | 3 | ≥10 |
| 年龄过滤准确率 | 71% | ≥90% |
| BM25 与向量分数最大差异 | 0.80 | <0.2 |
| 去重算法复杂度 | O(n²) | O(n log n) |
| P50 响应时间 (预热后) | ~800ms | ≤300ms |
| P95 响应时间 (预热后) | ~1500ms | ≤500ms |
| P99 响应时间 (预热后) | ~2000ms | ≤800ms |

## 📋 Phase 划分

| Phase | 内容 | 优先级 | 对应测试项 | 对应需求 |
|-------|------|--------|------------|----------|
| **Phase A** | 分数语义重构 (相关度/年龄适配度/分数校准/年龄过滤) | P0 | 测试 1、2、3、11 | 需求 4.1、4.2、4.3 |
| **Phase B** | 查询权重调优 (关键词密度阈值调整) | P1 | 测试 4 | 需求 4.4 |
| **Phase C** | 同义词扩展质量优化 | P1 | 测试 12 | 需求 4.5 |
| **Phase D** | 性能优化 (去重/重排序/边界场景) | P2 | 测试 5、6、10 | 需求 4.6、4.7、4.8 |

## 🔗 相关文档

- [需求文档](../../rag_search_optimization_requirements.md) - 12 项诊断测试与根因分析
- [RAG 系统完整文档](../../RAG_SYSTEM_COMPLETE_DOCUMENTATION.md) - RAG 系统技术细节
- [RAG 流水线架构](../../../.ai/rag_pipeline.md) - 核心模块与 API 端点

---

**最后更新：** 2026-04-15
**文档版本：** 0.1 (初始框架)
**维护者：** AI Assistant
