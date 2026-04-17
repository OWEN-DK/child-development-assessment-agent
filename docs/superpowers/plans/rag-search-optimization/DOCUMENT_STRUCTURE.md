# 文档结构说明

## 📁 文件组织

本文档将 RAG 知识库搜索优化方案拆分为多个独立模块，便于管理和维护。

### 核心文档结构

```
rag-search-optimization/
├── README.md                              # 主索引文件（入口）
├── PROGRESS.md                            # 进度追踪
├── 00-overview.md                         # 项目概览与文件结构变更
│
├── # Phase A: 分数语义重构 (P0)
├── 01-phase-a-00-overview.md              # Phase A 总览与目标
├── 01-phase-a-01-score-separation.md      # 分数分离与数据模型变更
├── 01-phase-a-02-age-fit-scorer.md        # 年龄适配度细粒度计算器
├── 01-phase-a-03-score-calibration.md     # BM25/向量分数校准统一
├── 01-phase-a-04-age-filter.md            # 年龄过滤前置与严格模式
├── 01-phase-a-05-frontend-adaptation.md   # 前端分数展示适配
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
├── 04-phase-d-01-dedup-engine.md          # 高效去重引擎
├── 04-phase-d-02-reranker-optimization.md # 重排序性能优化
├── 04-phase-d-03-boundary-handler.md      # 边界场景处理
│
├── appendix-a-test-verification.md        # 诊断测试验收报告
├── appendix-b-risk-control.md             # 风险控制与回滚策略
│
└── DOCUMENT_STRUCTURE.md                  # 本文档
```

### 文档拆分策略

所有 Phase 均采用"总览 + 细分模块"的分层结构，每个模块独立成文件：

#### Phase A: 分数语义重构 (P0)
| 模块 | 拆分后文件 | 说明 |
|------|-----------|------|
| 总览与目标 | `01-phase-a-00-overview.md` | Phase A 整体目标、范围、验收标准 |
| 分数分离 | `01-phase-a-01-score-separation.md` | KnowledgeItem 模型变更、relevance_score 来源切换 |
| 年龄适配度 | `01-phase-a-02-age-fit-scorer.md` | 三维度细粒度计算器实现 |
| 分数校准 | `01-phase-a-03-score-calibration.md` | BM25/向量统一校准策略 |
| 年龄过滤逻辑重构 | `01-phase-a-04-age-filter-refactor.md` | tolerance 修正、严格/宽松模式、年龄范围判断 |
| 过滤流水线集成 | `01-phase-a-05-filter-pipeline-integration.md` | 前置到检索阶段、与分数计算解耦 |
| 前端适配 | `01-phase-a-06-frontend-adaptation.md` | 响应类型更新、分数展示 |

#### Phase B: 查询权重调优 (P1)
| 模块 | 拆分后文件 | 说明 |
|------|-----------|------|
| 总览与目标 | `02-phase-b-00-overview.md` | Phase B 整体目标、验收标准 |
| 查询分析器 | `02-phase-b-01-query-analyzer.md` | 中文场景查询特征提取 |
| 权重决策 | `02-phase-b-02-weight-decision.md` | 动态权重规则与集成 |

#### Phase C: 同义词扩展质量优化 (P1)
| 模块 | 拆分后文件 | 说明 |
|------|-----------|------|
| 总览与目标 | `03-phase-c-00-overview.md` | Phase C 整体目标、验收标准 |
| 质量验证器 | `03-phase-c-01-synonym-validator.md` | 语义相关性验证、阈值配置 |
| 兜底策略 | `03-phase-c-02-fallback-strategy.md` | 本地关键词提取兜底 |

#### Phase D: 性能优化 (P2)
| 模块 | 拆分后文件 | 说明 |
|------|-----------|------|
| 总览与目标 | `04-phase-d-00-overview.md` | Phase D 整体目标、验收标准 |
| Hash 精确去重 | `04-phase-d-01-hash-dedup.md` | content_hash O(n) 快速过滤 |
| MinHash 近似去重 | `04-phase-d-02-minhash-dedup.md` | LSH 分桶 O(n log n) 语义去重 |
| 模型预热 | `04-phase-d-03-reranker-warmup.md` | Cross-Encoder 后台异步加载 |
| 动态 initial_k | `04-phase-d-04-dynamic-initial-k.md` | 根据查询复杂度调整候选数量 |
| 输入校验 | `04-phase-d-05-input-validation.md` | 空查询/超长查询/特殊字符处理 |
| 边界年龄降级 | `04-phase-d-06-boundary-age-fallback.md` | 0/18 岁映射 + 无结果降级策略 |

#### 通用文档
| 文档 | 文件 | 说明 |
|------|------|------|
| 诊断测试验收 | `appendix-a-test-verification.md` | 12 项测试验收标准与验证方法 |
| 风险控制 | `appendix-b-risk-control.md` | 回滚策略、灰度发布、风险评估 |

---

## 📖 使用指南

### 阅读顺序

1. **入口**：从 [`README.md`](./README.md) 开始，了解项目整体
2. **概览**：阅读 [`00-overview.md`](./00-overview.md)，了解文件结构和架构
3. **实施**：按顺序执行各个 Phase：
   - [`Phase A`](./01-phase-a-00-overview.md) - 分数语义重构 (P0)
   - [`Phase B`](./02-phase-b-00-overview.md) - 查询权重调优 (P1)
   - [`Phase C`](./03-phase-c-00-overview.md) - 同义词扩展质量优化 (P1)
   - [`Phase D`](./04-phase-d-00-overview.md) - 性能优化 (P2)
4. **参考**：查阅附录文档获取验收标准和风险控制指南

### 任务追踪

每个 Phase 文档都使用 checkbox (`- [ ]`) 语法，方便追踪进度：

```markdown
- [ ] **Step 1: 任务描述**
```

实施时，将已完成的步骤标记为：

```markdown
- [x] **Step 1: 任务描述**
```

---

## 🔧 文档维护

### 添加新内容

如需补充某个 Phase 的详细任务，可以：

1. 创建新的文件，如 `01-phase-a-01-score-separation.md`
2. 在 `README.md` 中更新链接
3. 在 `PROGRESS.md` 中标记进度

### 更新现有内容

直接编辑对应的 Phase 文件即可。所有修改应：
- 保持代码示例的完整性
- 包含必要的导入语句
- 提供测试步骤和预期结果

---

## 🔗 相关文档

- [需求文档](../../rag_search_optimization_requirements.md) - 12 项诊断测试与根因分析
- [RAG 系统完整文档](../../RAG_SYSTEM_COMPLETE_DOCUMENTATION.md) - RAG 系统技术细节
- [RAG 流水线架构](../../../.ai/rag_pipeline.md) - 核心模块与 API 端点
- [RAG+LLM 重构计划](../rag-llm-refactoring/) - 参考文档结构

---

**最后更新：** 2026-04-15
**文档版本：** 0.1 (初始框架)
**维护者：** AI Assistant
