# RAG 系统评估需求方案

**文档版本**: v1.0  
**创建日期**: 2026-04-07  
**需求来源**: [`docs/rag 评估方法.md`](/Users/owen/project/ai/child-development-assessment-agent/docs/rag 评估方法.md)  
**适用对象**: 产品经理、后端开发、算法工程师、测试工程师  
**状态**: 已评审

---

## 1. 需求背景与目标

### 1.1 业务背景

儿童发展评估 Agent 的 RAG 系统已具备检索 + 生成能力，但缺少系统化评估体系：

- 检索质量依赖经验判断，无法量化优化效果
- 生成质量缺少自动化评估，依赖人工检查
- 版本迭代缺少对比基准，无法保证质量不退化
- 上线前缺少标准化验收流程

### 1.2 需求目标

基于 RAG 评估方法论，构建**分阶段、可量化、自动化**的评估体系：

| 目标 | 说明 | 优先级 |
|------|------|--------|
| **检索质量可量化** | Recall@k、MRR、NDCG 等指标监控 | P0 |
| **生成质量可评估** | 忠实度、相关性、完整性自动打分 | P0 |
| **版本迭代可对比** | 每次优化前后指标对比 | P1 |
| **问题定位可追溯** | 失败案例归因（检索/生成/都差） | P1 |
| **上线质量有保障** | 人工评估 + 自动化评估双重验证 | P1 |

### 1.3 评估原则

1. **先评估检索，再评估生成** - 检索不行，生成再好也没用
2. **离线评估 + 线上 AB 实验 + 人工抽检** 三层闭环
3. **指标必须可自动化计算**，不能只靠人主观打分

---

## 2. 现状分析

### 2.1 已有能力

| 模块 | 文件 | 状态 |
|------|------|------|
| 检索评估器 | [`backend/src/core/rag_evaluator.py`](/Users/owen/project/ai/child-development-assessment-agent/backend/src/core/rag_evaluator.py) | 已有基础实现 |
| 测试管理 | [`backend/src/service/rag_test_manager.py`](/Users/owen/project/ai/child-development-assessment-agent/backend/src/service/rag_test_manager.py) | 已有基础实现 |
| 测试控制器 | [`backend/src/controller/rag_test_controller.py`](/Users/owen/project/ai/child-development-assessment-agent/backend/src/controller/rag_test_controller.py) | 已有基础实现 |
| 测试数据模型 | [`backend/src/model/rag_test.py`](/Users/owen/project/ai/child-development-assessment-agent/backend/src/model/rag_test.py) | 已有基础实现 |

### 2.2 能力差距

| 需求 | 现状 | 差距 |
|------|------|------|
| Recall@1/3/5/10 | 仅支持固定 k 值 | 需支持多 k 值评估 |
| Precision@3 | 有基础实现 | 需对接业务标准 |
| MRR | 有基础实现 | 需集成到测试流程 |
| 上下文相关性 | 无 | 需新建 LLM 评估模块 |
| 忠实度评估 | 无 | 需新建 LLM 评估模块 |
| 回答相关性 | 无 | 需新建 LLM 评估模块 |
| 完整性评估 | 无 | 需新建 LLM 评估模块 |
| 测试集管理 | 有基础结构 | 需扩展标注字段 |
| 评估报告 | 无 | 需新建报告生成模块 |
| 线上监控 | 无 | 需新建埋点系统 |

---

## 3. 功能需求

### 3.1 检索模块评估

#### 3.1.1 召回率 Recall@k

**需求描述**: 计算知识库中真正相关的 chunk 被检索出来的比例

**功能要求**:
- 支持 Recall@1/3/5/10 多粒度评估
- 基于标注好的问答对（问题 → 应该命中哪些 chunk）
- 自动化计算，输出可视化报告

**验收标准**:
- Recall@3 ≥ 85% 为合格
- 支持批量评估 200+ 测试用例
- 输出漏召回案例清单

**现有代码**: [`RAGEvaluator._recall_at_k`](/Users/owen/project/ai/child-development-assessment-agent/backend/src/core/rag_evaluator.py#L158-L181)

**需改进**:
- 支持多 k 值同时计算
- 集成到测试运行流程
- 输出详细错误分析

#### 3.1.2 精确率 Precision@k

**需求描述**: 计算返回的 k 条结果中真正相关的比例

**功能要求**:
- 支持 Precision@1/3/5/10 评估
- 结合业务标注数据计算
- 输出错召回案例清单

**验收标准**:
- Precision@3 ≥ 70% 为合格
- 支持按查询类型分组统计

**现有代码**: [`RAGEvaluator._precision_at_k`](/Users/owen/project/ai/child-development-assessment-agent/backend/src/core/rag_evaluator.py#L133-L156)

#### 3.1.3 MRR（平均倒数排名）

**需求描述**: 计算第一个正确答案位置的倒数均值

**功能要求**:
- 自动化计算 MRR
- 支持按查询类型分组统计
- 输出排名靠后案例

**验收标准**:
- MRR ≥ 0.6 为基本可用
- 支持单次和批量评估

**现有代码**: [`RAGEvaluator._mrr`](/Users/owen/project/ai/child-development-assessment-agent/backend/src/core/rag_evaluator.py#L224-L244)

#### 3.1.4 上下文相关性（Context Relevance）

**需求描述**: 评估检索内容中真正能用来回答问题的比例

**功能要求**:
- 使用 LLM 自动打分（1-5 分）
- 批量评估测试集
- 输出低分案例及原因

**验收标准**:
- 平均分 ≥ 4 为合格
- 评估响应时间 < 5s/条
- 支持自定义评估 Prompt

**实现方式**: 新建 LLM 评估模块

---

### 3.2 生成模块评估

#### 3.2.1 忠实度 Faithfulness

**需求描述**: 评估答案中不幻觉、能被上下文支持的陈述占比

**功能要求**:
- LLM 判断每一句话是否被上下文支撑
- 输出忠实度分数（1-5 分）
- 标注编造内容位置

**验收标准**:
- 忠实度 ≥ 90%（或 ≥ 4.5/5 分）才能上线
- 支持批量自动化评估
- 输出幻觉案例清单

**实现方式**: 新建生成评估模块，使用 LLM-as-Judge

**评估 Prompt**:
```
你需要评估回答是否完全基于上下文，没有编造信息。
上下文：{context}
问题：{query}
回答：{answer}
请输出：
1. 忠实度分数（1-5）
2. 编造内容（若无则写无）
```

#### 3.2.2 回答相关性 Answer Relevance

**需求描述**: 评估回答是否切题、不跑偏、不废话

**功能要求**:
- LLM 打分（1-5 分）
- 评估是否覆盖问题所有要点
- 输出跑题案例

**验收标准**:
- 相关性 ≥ 4 分为合格
- 支持批量评估

**评估 Prompt**:
```
问题：{query}
回答：{answer}
评估回答是否切题、是否完整、是否冗余。
输出 1-5 分，并简要说明。
```

#### 3.2.3 完整性 Completeness

**需求描述**: 评估回答是否覆盖问题所有要点

**功能要求**:
- 提取问题关键信息点
- 检查回答是否覆盖所有要点
- 输出缺失要点清单

**验收标准**:
- 完整性 ≥ 85% 要点覆盖
- 适合客服、知识库、法规类场景

---

### 3.3 测试集管理

#### 3.3.1 测试集构建

**需求描述**: 构建标注好的问答对测试集

**功能要求**:
- 支持收集真实用户问题 ≥ 200 条
- 人工标注：问题 → 应该命中哪些 chunk
- 人工标注：问题 → 标准答案要点
- 支持测试集版本管理

**数据格式**:
```json
{
  "query": "查询文本",
  "age": 2,
  "query_type": "事实查询",
  "relevant_chunks": ["chunk_001", "chunk_023"],
  "relevance_scores": {"chunk_001": 3, "chunk_023": 2},
  "ground_truth_key_points": ["要点 1", "要点 2"],
  "keywords": ["关键词 1", "关键词 2"]
}
```

**问题类型覆盖**:

| 类型 | 示例 | 占比 |
|------|------|------|
| 事实查询 | "XX 规则是什么？" | 40% |
| 多条件查询 | "同时满足 A 和 B 的情况" | 20% |
| 摘要类 | "总结某章节内容" | 15% |
| 对比类 | "A 与 B 的区别" | 15% |
| 边缘/噪声 | 无意义提问、错别字 | 10% |

**现有代码**: [`TestCase`](/Users/owen/project/ai/child-development-assessment-agent/backend/src/model/rag_test.py#L6-L18)

**需扩展字段**:
- `query_type`: 问题类型
- `relevant_chunks`: 相关 chunk ID 列表
- `relevance_scores`: 相关性评分
- `ground_truth_key_points`: 标准答案要点

#### 3.3.2 测试执行

**需求描述**: 批量执行测试并收集结果

**功能要求**:
- 支持单个测试用例执行
- 支持批量测试执行
- 记录检索结果和生成结果
- 自动计算各项指标

**现有代码**: [`RagTestManager.run_all_tests`](/Users/owen/project/ai/child-development-assessment-agent/backend/src/service/rag_test_manager.py#L184-L240)

**需改进**:
- 集成生成评估流程
- 支持多 k 值评估
- 输出详细评估报告

---

### 3.4 评估报告

#### 3.4.1 检索评估报告

**需求描述**: 生成检索模块评估报告

**报告内容**:
```
检索评估报告 v1.0
==================
测试集规模：200 queries
检索策略：BM25 + Vector + Rerank

核心指标:
- Recall@1: 72.5%
- Recall@3: 85.0% ✓
- Recall@5: 89.5%
- Precision@3: 75.0% ✓
- MRR: 0.78 ✓
- Context Relevance: 4.1/5.0 ✓

问题 Top 5:
1. Query: "3 岁精细动作训练方法" - Recall@3=0 (漏召回)
2. Query: "感统失调表现" - 首个相关文档排名=8 (排序靠后)
3. Query: "语言发展迟缓" - Context Relevance=2.5 (噪声大)
```

#### 3.4.2 生成评估报告

**需求描述**: 生成生成模块评估报告

**报告内容**:
```
生成评估报告 v1.0
==================
测试集规模：200 queries

核心指标:
- 忠实度：4.6/5.0 ✓ (92%)
- 回答相关性：4.2/5.0 ✓
- 完整性：88% ✓

幻觉案例 Top 3:
1. Query: "XXX" - 编造了 XXX 规则
2. Query: "YYY" - 引用了不存在的数据
3. Query: "ZZZ" - 错误解读了原文

答非所问案例 Top 3:
...
```

#### 3.4.3 综合评估报告

**需求描述**: 生成端到端综合评估报告

**报告内容**:
- 检索 + 生成综合得分
- 各模块指标对比
- 版本迭代对比
- 问题归因分析
- 优化建议

---

### 3.5 问题定位与优化

#### 3.5.1 检索问题定位

**需求描述**: 根据指标自动定位检索问题

**问题定位表**:

| 现象 | 可能原因 | 优化方向 |
|------|---------|---------|
| Recall 低 | 向量模型不行 / chunk 切割不对 / 知识库不全 | 换 embedding 模型 / 调整 chunk 大小 / 补充知识库 |
| Precision 低 | 相似度阈值太低 / 停用词没处理 / 领域泛文本太多 | 调整阈值 / 处理停用词 / 优化 chunk |
| MRR 低 | 重排序模型没加 / 权重不合理 | 加入 Reranker / 调整权重 |
| 关键词场景失效 | 纯向量不行 | 加入混合稀疏检索（BM25） |

**现有代码**: 已有混合检索 [`hybrid_retrieval.py`](/Users/owen/project/ai/child-development-assessment-agent/backend/src/core/hybrid_retrieval.py)、重排序 [`reranker.py`](/Users/owen/project/ai/child-development-assessment-agent/backend/src/core/reranker.py)

#### 3.5.2 生成问题定位

**需求描述**: 根据指标自动生成问题清单

**输出内容**:
- 幻觉案例清单（含编造内容标注）
- 答非所问案例清单
- 不完整回答案例清单
- 每个案例的优化建议

---

### 3.6 线上监控

#### 3.6.1 埋点需求

**需求描述**: 线上服务埋点，收集真实用户反馈

**埋点内容**:

| 埋点项 | 说明 | 用途 |
|--------|------|------|
| 检索召回数量 | 每次检索返回的 chunk 数 | 监控检索稳定性 |
| 用户"不满意"点击 | 用户反馈不满意 | 线上质量监控 |
| 重复提问率 | 同一用户短时间重复提问 | 回答质量间接指标 |
| LLM 生成长度 | 生成文本长度 | 监控生成稳定性 |
| 耗时 | 检索 + 生成总耗时 | 性能监控 |

#### 3.6.2 定期评估

**需求描述**: 定期运行离线评估，防止版本退化

**执行频率**:
- 每周跑一次离线评估
- 每次代码提交后跑快速验证集（50 条）
- 重大版本全量评估（200+ 条）

---

## 4. 验收标准

### 4.1 检索模块验收标准

| 指标 | 合格线 | 优秀线 |
|------|--------|--------|
| Recall@3 | ≥ 85% | ≥ 90% |
| Precision@3 | ≥ 70% | ≥ 80% |
| MRR | ≥ 0.6 | ≥ 0.75 |
| 上下文相关性 | ≥ 4 分 | ≥ 4.5 分 |
| 元数据过滤准确率 | 100% | 100% |

### 4.2 生成模块验收标准

| 指标 | 合格线 | 优秀线 |
|------|--------|--------|
| 忠实度 | ≥ 90% (或 ≥ 4.5/5) | ≥ 95% (或 ≥ 4.8/5) |
| 回答相关性 | ≥ 4 分 | ≥ 4.5 分 |
| 完整性 | ≥ 85% 要点覆盖 | ≥ 95% 要点覆盖 |

### 4.3 整体验收标准

| 指标 | 合格线 |
|------|--------|
| 人工满意度 | ≥ 85% |
| 自动化评估覆盖率 | ≥ 90% 测试用例 |
| 评估报告生成时间 | < 30 分钟（200 条测试集） |

---

## 5. 非功能需求

### 5.1 性能需求

| 指标 | 要求 |
|------|------|
| 单条检索评估时间 | < 1s |
| 单条生成评估时间（LLM） | < 5s |
| 批量评估 200 条时间 | < 30 分钟 |
| 评估报告生成时间 | < 5 分钟 |

### 5.2 可扩展性

- 支持自定义评估指标
- 支持自定义评估 Prompt
- 支持多种 LLM 后端（当前使用 Qwen）
- 支持测试集版本管理

### 5.3 可维护性

- 评估代码单元测试覆盖率 ≥ 80%
- 评估流程可配置化
- 评估结果可追溯

---

## 6. 实施计划

### 6.1 阶段划分

#### 阶段 1: 构建测试集（1 天）

**任务**:
- 收集真实用户问题 ≥ 200 条
- 人工标注：问题 → 应该命中哪些 chunk
- 人工标注：问题 → 标准答案要点
- 扩展测试数据模型，支持标注字段

**交付物**:
- 测试集 v1.0（200+ 条标注数据）
- 扩展后的测试数据模型

#### 阶段 2: 跑检索指标（半天）

**任务**:
- 计算 Recall@1/3/5
- 计算 MRR
- 输出检索错误案例：漏召回 / 错召回
- 集成到现有测试流程

**交付物**:
- 检索评估报告 v1.0
- 检索错误案例清单

#### 阶段 3: 优化检索（1～3 天）

**任务**:
- 根据检索错误案例优化
- 换更好的 embedding 模型（如需要）
- 加入 BM25 + 向量混合检索（已有）
- 加入 Reranker（已有 bge-reranker）
- 调整 chunk 大小、重叠长度

**交付物**:
- 检索优化版本
- 检索评估报告 v2.0（对比 v1.0）

#### 阶段 4: 生成效果自动化评估（2 天）

**任务**:
- 新建生成评估模块
- 批量跑 Faithfulness / Relevance / Completeness
- 统计幻觉率、答非所问率
- 输出 Bad Case 清单

**交付物**:
- 生成评估模块
- 生成评估报告 v1.0
- Bad Case 清单

#### 阶段 5: 线上监控（1 天）

**任务**:
- 实现埋点：检索召回数量、用户不满意点击、重复提问率等
- 实现定期离线评估脚本
- 实现评估报告自动生成

**交付物**:
- 线上监控埋点
- 定期评估脚本
- 自动化评估报告

### 6.2 里程碑

| 里程碑 | 时间 | 交付物 |
|--------|------|--------|
| M1: 测试集完成 | 阶段 1 结束 | 200+ 标注测试集 |
| M2: 检索评估完成 | 阶段 2 结束 | 检索评估报告 |
| M3: 检索优化完成 | 阶段 3 结束 | 优化后的检索模块 |
| M4: 生成评估完成 | 阶段 4 结束 | 生成评估模块 + 报告 |
| M5: 监控上线 | 阶段 5 结束 | 线上监控系统 |

---

## 7. 风险与应对

| 风险 | 影响 | 概率 | 应对措施 |
|------|------|------|---------|
| 测试集构建进度慢 | 高 | 中 | 优先构建 50 条验证集，快速启动评估 |
| LLM 评估成本高 | 中 | 高 | 批量评估、缓存评估结果、使用低成本模型 |
| 指标与业务不一致 | 高 | 中 | 定期校准自动指标，以人工评估为准 |
| 评估流程复杂 | 中 | 低 | 提供一键评估脚本，简化操作流程 |

---

## 8. 附录

### 8.1 相关文件

- [`docs/rag 评估方法.md`](/Users/owen/project/ai/child-development-assessment-agent/docs/rag 评估方法.md) - RAG 评估方法参考
- [`backend/src/core/rag_evaluator.py`](/Users/owen/project/ai/child-development-assessment-agent/backend/src/core/rag_evaluator.py) - 检索评估器
- [`backend/src/service/rag_test_manager.py`](/Users/owen/project/ai/child-development-assessment-agent/backend/src/service/rag_test_manager.py) - 测试管理
- [`backend/src/model/rag_test.py`](/Users/owen/project/ai/child-development-assessment-agent/backend/src/model/rag_test.py) - 测试数据模型
- [`docs/superpowers/specs/2026-04-02-rag-evaluation-system-design.md`](/Users/owen/project/ai/child-development-assessment-agent/docs/superpowers/specs/2026-04-02-rag-evaluation-system-design.md) - 系统设计文档

### 8.2 术语表

| 术语 | 说明 |
|------|------|
| **RAG** | Retrieval-Augmented Generation，检索增强生成 |
| **Recall@k** | TopK 结果中的召回率 |
| **Precision@k** | TopK 结果中的精确率 |
| **MRR** | Mean Reciprocal Rank，平均倒数排名 |
| **NDCG** | Normalized Discounted Cumulative Gain，归一化折损累计增益 |
| **Faithfulness** | 忠实度，生成内容是否基于检索上下文 |
| **LLM-as-Judge** | 使用 LLM 作为评估员进行自动打分 |
| **BM25** | 稀疏检索算法，适合关键词匹配 |
| **Reranker** | 重排序模型，优化检索结果排序 |

---

## 9. 审批

| 角色 | 姓名 | 日期 | 意见 |
|------|------|------|------|
| 产品经理 | | | |
| 技术负责人 | | | |
| 算法工程师 | | | |
| 测试工程师 | | | |

---

**文档结束**
