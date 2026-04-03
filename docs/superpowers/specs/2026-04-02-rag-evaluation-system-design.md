# RAG 系统评估方案设计文档

**文档版本**: v1.0  
**创建日期**: 2026-04-02  
**适用对象**: 后端开发人员、测试工程师、算法工程师  
**参考文档**: [`docs/rag 评估方法.md`](/Users/owen/project/ai/child-development-assessment-agent/docs/rag 评估方法.md)

---

## 📑 目录

1. [系统概览](#1-系统概览)
2. [评估架构设计](#2-评估架构设计)
3. [检索模块评估方案](#3-检索模块评估方案)
4. [生成模块评估方案](#4-生成模块评估方案)
5. [端到端综合评估方案](#5-端到端综合评估方案)
6. [自动化评估工具集成](#6-自动化评估工具集成)
7. [评估数据集构建方案](#7-评估数据集构建方案)
8. [人工评估流程](#8-人工评估流程)
9. [全流程执行步骤](#9-全流程执行步骤)
10. [实施计划与时间规划](#10-实施计划与时间规划)

---

## 1. 系统概览

### 1.1 项目背景

儿童发展评估 Agent 的 RAG 系统已具备完整的检索 + 生成能力：

- **检索模块**: BM25 + Vector 混合检索、Cross-Encoder 重排序、年龄过滤
- **生成模块**: LLM 分层内容生成、报告生成、评估生成
- **测试管理**: 测试用例管理、测试运行、快照管理

**当前痛点**:
- 缺少系统化的评估体系，无法量化优化效果
- 检索质量依赖经验判断，缺少客观指标
- 生成质量缺少自动化评估，依赖人工检查
- 版本迭代缺少对比基准

### 1.2 评估目标

基于业界标准 RAG 评估方法（参考 `docs/rag 评估方法.md`），构建**分阶段、可量化、自动化**的评估体系：

| 目标 | 说明 |
|------|------|
| **检索质量可量化** | Recall@k、MRR、NDCG 等指标监控 |
| **生成质量可评估** | 忠实度、相关性、完整性自动打分 |
| **版本迭代可对比** | 每次优化前后指标对比 |
| **问题定位可追溯** | 失败案例归因（检索/生成/都差） |
| **上线质量有保障** | 人工评估 + 自动化评估双重验证 |

### 1.3 评估范围

```
用户 Query → 检索模块 → 召回 Context → LLM 生成 → 最终 Answer
           ↓              ↓              ↓
        检索评估       上下文评估      生成评估
           ↘              ↓              ↙
              端到端综合评估
```

**评估层级**:
- **细粒度单阶段指标**: 定位模块问题（检索/生成）
- **自动化综合指标**: 版本对比、回归测试
- **人工专家评估**: 校准自动指标、保证业务合规
- **线上真实用户反馈**: 验证真实业务效果

---

## 2. 评估架构设计

### 2.1 评估系统架构图

```
┌─────────────────────────────────────────────────────────┐
│                   RAG 评估系统                            │
├─────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐     │
│  │ 检索评估模块 │  │ 生成评估模块 │  │ 端到端评估  │     │
│  │             │  │             │  │             │     │
│  │ • Recall@k │  │ • Faithful  │  │ • 综合得分  │     │
│  │ • MRR      │  │ • Relevant  │  │ • 用户满意度│     │
│  │ • NDCG     │  │ • Complete  │  │ • 业务可用性│     │
│  └─────────────┘  └─────────────┘  └─────────────┘     │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐     │
│  │ 数据集管理  │  │ 工具集成层  │  │ 报告生成    │     │
│  │             │  │             │  │             │     │
│  │ • 测试集   │  │ • RAGAS     │  │ • 指标报告  │     │
│  │ • 标注集   │  │ • TruLens   │  │ • 失败分析  │     │
│  │ • 标注工具 │  │ • 自定义    │  │ • 版本对比  │     │
│  └─────────────┘  └─────────────┘  └─────────────┘     │
└─────────────────────────────────────────────────────────┘
```

### 2.2 核心模块设计

#### 2.2.1 检索评估模块

**文件路径**: `backend/src/core/rag_evaluator.py` (已有基础，需扩展)

**核心指标**:
- **Recall@k**: 召回率（k=1,3,5,10）
- **Precision@k**: 精确率
- **MRR**: 平均倒数排名
- **NDCG@k**: 归一化折损累计增益
- **Context Relevance**: 上下文相关性（LLM 打分）
- **Context Coverage**: 上下文覆盖率（LLM 打分）

**执行流程**:
```python
1. 加载标注数据集（query + 相关 doc_ids + 相关性评分）
2. 批量执行检索，记录 top-k 结果
3. 自动计算 Recall@k, MRR, NDCG@k
4. LLM 打分 Context Relevance/Coverage
5. 输出检索问题 Top 榜单
```

#### 2.2.2 生成评估模块

**文件路径**: `backend/src/core/rag_generator_evaluator.py` (新建)

**核心指标**:
- **Faithfulness (忠实度)**: 是否基于上下文，无幻觉
- **Answer Relevance (相关性)**: 是否直接回答问题
- **Completeness (完整性)**: 是否覆盖所有关键信息点
- **Correctness (正确性)**: 与标准答案一致性
- **Readability (可读性)**: 流畅度、格式规范

**LLM-as-Judge Prompt**:
```
你是 RAG 系统专业评估员，请根据【用户问题】、【检索上下文】、【模型回答】，
按以下维度打分（1-5 分）并给出理由：

1. 忠实度：是否完全基于上下文，无幻觉
2. 相关性：是否精准回答问题
3. 完整性：是否覆盖所有关键信息
4. 可读性：表达是否流畅规范

输出格式：
忠实度：x/5
相关性：x/5
完整性：x/5
可读性：x/5
问题说明：xxx
```

#### 2.2.3 端到端评估模块

**文件路径**: `backend/src/core/rag_end_to_end_evaluator.py` (新建)

**综合评分公式**:
```
综合得分 = 0.4 × 检索得分 + 0.4 × 生成得分 + 0.2 × 业务可用性

检索得分 = 0.4×Recall@3 + 0.3×MRR + 0.2×NDCG@5 + 0.1×Context Relevance
生成得分 = 0.35×Faithfulness + 0.25×Relevance + 0.25×Completeness + 0.15×Readability
```

**质量门槛**:
- **企业通用标准**: 综合得分 ≥ 4.0
- **高合规场景**: 综合得分 ≥ 4.5，幻觉率 = 0
- **检索 Recall@3**: ≥ 90%

---

## 3. 检索模块评估方案

### 3.1 核心指标定义

#### 3.1.1 基础召回与精确率

**Recall@k**:
```python
Recall@k = (TopK 结果中相关文档数) / (总相关文档数)

常用 k 值：1, 3, 5, 10
业务意义：衡量是否"找得到"关键信息，避免漏召回
```

**Precision@k**:
```python
Precision@k = (TopK 结果中相关文档数) / k

业务意义：衡量上下文是否"干净"，减少冗余噪声
```

#### 3.1.2 排序质量指标

**MRR (Mean Reciprocal Rank)**:
```python
MRR = avg(1 / rank_i)
rank_i = 第 i 个 Query 首个相关文档位置

业务意义：优先保证高价值内容排在最前，直接影响 LLM 读取效率
```

**NDCG@k (Normalized Discounted Cumulative Gain)**:
```python
DCG = Σ(2^rel_i - 1) / log2(i + 2)
NDCG = DCG / IDCG (理想 DCG)

支持分级相关性标注：0(无关)、1(弱相关)、2(强相关)
业务意义：更贴合业务，对强相关文档赋予更高权重
```

#### 3.1.3 RAG 专用上下文指标

**Context Relevance (上下文相关性)**:
- 定义：召回片段中**能直接用于回答问题**的有效信息占比
- 判定标准：
  - 5 分：所有内容均为关键信息，无冗余
  - 3 分：部分冗余，但关键信息完整
  - 1 分：大量无关内容，关键信息极少

**Context Coverage (上下文覆盖率)**:
- 定义：检索结果覆盖问题所需**全部知识点**的比例
- 意义：避免多跳问题、复合问题因信息不全导致生成错误

### 3.2 检索评估数据集构建

#### 3.2.1 数据集规模

| 数据集 | 规模 | 用途 |
|--------|------|------|
| **测试集** | ≥ 200 条 Query | 全面评估、版本对比 |
| **校验集** | ≥ 50 条 Query | 快速验证、开发调试 |

#### 3.2.2 标注规范

**数据格式**:
```json
{
  "query": "2 岁儿童前庭觉失调的表现",
  "ground_truth": "前庭觉失调表现为平衡能力差、注意力不集中、情绪不稳定...",
  "relevant_docs": ["doc_001", "doc_023", "doc_045"],
  "relevance_scores": {
    "doc_001": 3,  // 强相关
    "doc_023": 2,  // 弱相关
    "doc_045": 1   // 边缘相关
  },
  "chunk_ids": ["chunk_001_01", "chunk_023_03"],
  "query_type": "事实查询"  // 事实查询/多条件查询/摘要类/对比类/边缘问题
}
```

#### 3.2.3 问题类型覆盖

| 类型 | 示例 | 占比 |
|------|------|------|
| **事实查询** | "XX 规则是什么？" | 40% |
| **多条件查询** | "同时满足 A 和 B 的情况" | 20% |
| **摘要类** | "总结某章节内容" | 15% |
| **对比类** | "A 与 B 的区别" | 15% |
| **边缘/噪声** | 无意义提问、错别字、口语化 | 10% |

### 3.3 检索评估执行步骤

```python
# 步骤 1: 构建离线测试 Query 集与标注文档
# 步骤 2: 批量执行检索，记录 top-k 召回结果
# 步骤 3: 脚本自动计算 Recall@k, MRR, NDCG@k
# 步骤 4: LLM 自动打分 Context Relevance/Coverage
# 步骤 5: 输出检索问题 Top 榜单：漏召回、排序靠后、无关召回
```

**输出报告示例**:
```
检索评估报告 v1.0
==================
测试集规模：200 queries
检索策略：BM25 + Vector + Rerank

核心指标:
- Recall@1: 72.5%
- Recall@3: 85.0%
- Recall@5: 89.5%
- MRR: 0.78
- NDCG@5: 0.82
- Context Relevance: 4.1/5.0
- Context Coverage: 3.8/5.0

问题 Top 5:
1. Query: "3 岁精细动作训练方法" - Recall@3=0 (漏召回)
2. Query: "感统失调表现" - 首个相关文档排名=8 (排序靠后)
3. Query: "语言发展迟缓" - Context Relevance=2.5 (噪声大)
...
```

---

## 4. 生成模块评估方案

### 4.1 生成核心评估指标

#### 4.1.1 忠实度 Faithfulness

**定义**: 生成内容**100% 基于检索上下文**，无编造、无脑补、无外部知识引入

**分级判定**:
- 5 分：完全忠实，无幻觉
- 3 分：轻微偏差，表述略有出入，不影响理解
- 1 分：严重幻觉，编造规则、数据、案例

**检测逻辑**:
```python
1. 提取生成内容中的所有事实陈述
2. 逐一验证是否在检索上下文中存在
3. 计算无事实支撑的陈述比例
```

#### 4.1.2 回答相关性 Answer Relevance

**定义**: 回答是否直接针对用户问题，不跑题、不冗余

**典型负例**:
- 用户问 A，回答大量讲 B
- 回答包含大量无关背景信息
- 回答重复问题描述

#### 4.1.3 回答完整性 Completeness

**定义**: 是否覆盖问题**所有关键信息点**

**示例**:
```
问题：2 岁儿童前庭觉失调的表现和训练方法有哪些？
关键信息点：
1. 前庭觉失调表现 ✓
2. 训练方法 ✓
完整性得分：2/2 = 100%
```

#### 4.1.4 正确性 Correctness

**定义**: 与业务标准答案一致，可用于直接决策

**适用场景**: 合规、金融、法律、政务等高要求场景

**判定逻辑**:
```python
1. 提取标准答案的关键事实点
2. 检查生成答案是否包含所有关键事实
3. 检查是否存在与标准答案矛盾的内容
```

#### 4.1.5 可读性与格式

**评估维度**:
- 流畅度：无病句、无乱码
- 格式规范：符合业务格式（表格/条目/编号）
- 专业性：术语使用准确

### 4.2 LLM-as-Judge 自动评判

**Prompt 模板**:
```python
evaluation_prompt = """
你是 RAG 系统专业评估员，请根据以下材料进行打分：

【用户问题】
{question}

【检索上下文】
{context}

【模型回答】
{answer}

请按以下维度打分（1-5 分）并给出理由：

1. 忠实度：是否完全基于上下文，无幻觉
2. 相关性：是否精准回答问题
3. 完整性：是否覆盖所有关键信息
4. 可读性：表达是否流畅规范

输出格式：
忠实度：x/5 (理由：xxx)
相关性：x/5 (理由：xxx)
完整性：x/5 (理由：xxx)
可读性：x/5 (理由：xxx)
综合评价：xxx
"""
```

**解析逻辑**:
```python
def parse_evaluation_response(response: str) -> Dict:
    """解析 LLM 评估响应"""
    # 使用正则提取各项得分
    faithfulness = extract_score(response, "忠实度")
    relevance = extract_score(response, "相关性")
    completeness = extract_score(response, "完整性")
    readability = extract_score(response, "可读性")
    
    return {
        "faithfulness": faithfulness,
        "relevance": relevance,
        "completeness": completeness,
        "readability": readability,
        "average": np.mean([faithfulness, relevance, completeness, readability])
    }
```

---

## 5. 端到端综合评估方案

### 5.1 综合评分体系

**评分公式**:
```
综合得分 = 0.4 × 检索得分 + 0.4 × 生成得分 + 0.2 × 业务可用性

其中：
检索得分 = 0.4×Recall@3 + 0.3×MRR + 0.2×NDCG@5 + 0.1×Context Relevance
生成得分 = 0.35×Faithfulness + 0.25×Relevance + 0.25×Completeness + 0.15×Readability
业务可用性 = 人工评估得分 (5 分制)
```

**质量门槛标准**:

| 场景 | 综合得分 | 检索 Recall@3 | 幻觉率 |
|------|---------|--------------|--------|
| **企业通用** | ≥ 4.0 | ≥ 85% | ≤ 5% |
| **高合规** | ≥ 4.5 | ≥ 90% | 0% |
| **内部测试** | ≥ 3.5 | ≥ 80% | ≤ 10% |

### 5.2 问题归因分析

**归因规则**:

| 现象 | 对应异常指标 | 优化方向 |
|------|--------------|---------|
| 经常漏关键信息 | Recall@k 低、Context Coverage 低 | 优化向量模型、增大召回数、加入关键词检索 |
| 上下文噪声大 | Context Relevance 低、Precision 低 | 优化 chunk 切分、使用重排模型、过滤低相关片段 |
| 回答经常编造 | Faithfulness 低 | 加强 prompt 约束、增加事实校验、精简上下文 |
| 答非所问 | Answer Relevance 低 | 优化 query 理解、增强检索相关性 |
| 回答不完整 | Completeness 低 | 提升召回数量、补充多文档关联 |

### 5.3 端到端评估流程

```python
async def evaluate_end_to_end(test_cases: List[TestCase]) -> EndToEndReport:
    """端到端评估流程"""
    # 1. 执行检索 + 生成
    results = []
    for test_case in test_cases:
        # 检索
        retrieval_results = await rag_service.retrieve_knowledge(
            query=test_case.query, 
            age=test_case.age, 
            limit=10
        )
        
        # 生成
        answer = await rag_service.generate_answer(
            query=test_case.query,
            context=retrieval_results
        )
        
        # 检索评估
        retrieval_metrics = evaluator.evaluate_retrieval(
            query=test_case.query,
            retrieved_docs=[item.id for item in retrieval_results],
            ground_truth=test_case.relevant_docs
        )
        
        # 生成评估
        generation_metrics = await evaluator.evaluate_generation(
            query=test_case.query,
            context=[item.content for item in retrieval_results],
            answer=answer,
            ground_truth=test_case.ground_truth
        )
        
        results.append({
            "test_case": test_case,
            "retrieval_metrics": retrieval_metrics,
            "generation_metrics": generation_metrics,
            "answer": answer
        })
    
    # 2. 聚合指标
    aggregated = aggregate_metrics(results)
    
    # 3. 生成报告
    report = generate_report(aggregated)
    
    return report
```

---

## 6. 自动化评估工具集成

### 6.1 RAGAS 集成方案

#### 6.1.1 支持指标

**检索指标**:
- Context Precision
- Context Recall
- Context Relevance
- Context Entailment

**生成指标**:
- Faithfulness
- Answer Relevance
- Answer Correctness
- Answer Similarity

#### 6.1.2 集成步骤

**步骤 1: 环境安装**
```bash
cd backend
poetry add ragas langchain chromadb
# 或
pip install ragas langchain chromadb
```

**步骤 2: 构建评估数据集格式**
```python
from datasets import Dataset

dataset = Dataset.from_list([
    {
        "question": "2 岁儿童前庭觉失调的表现",
        "ground_truth": "前庭觉失调表现为平衡能力差...",
        "contexts": ["chunk1", "chunk2"],
        "answer": "LLM 生成结果"
    },
    # ...更多测试样本
])
```

**步骤 3: 执行评估**
```python
from ragas import evaluate
from ragas.metrics import (
    faithfulness,
    answer_relevance,
    context_recall,
    context_precision
)

result = evaluate(
    dataset,
    metrics=[faithfulness, answer_relevance, context_recall, context_precision]
)

print(result.to_pandas())
```

**步骤 4: 结果用途**
- 版本迭代对比
- 构建质量门禁
- 失败样本筛选

### 6.2 TruLens 集成方案

**适用场景**:
- 需要自定义评估规则
- 需要可视化看板
- 需要长期追踪

**核心功能**:
- 支持自定义 Prompt 评判规则
- 内置 Dashboard 查看检索 + 生成链路
- 可记录每一轮调用的 chunk、prompt、得分、耗时

**集成代码示例**:
```python
from trulens_eval import TruChain, Feedback, Select
from trulens_eval.feedback import Groundedness

# 定义反馈函数
groundedness = Groundedness(groundedness_provider=Select.RecordCalls)
relevance = Feedback(relevance_metric).on(Select.RecordCalls.query).on_output()

# 包装 RAG 应用
tru_rag = TruChain(
    rag_chain,
    app_id="child_development_rag",
    feedbacks=[groundedness, relevance]
)

# 运行评估
with tru_rag as recording:
    for test_case in test_cases:
        rag_chain.invoke(test_case.query)

# 查看 Dashboard
tru_rag.get_dashboard()
```

### 6.3 自定义评估器

**文件路径**: `backend/src/core/rag_custom_evaluator.py`

**评估器接口**:
```python
class CustomRAGEvaluator:
    """自定义 RAG 评估器"""
    
    def __init__(self, config: Dict):
        self.config = config
        self.llm = self._initialize_llm()
    
    async def evaluate(self, test_case: TestCase) -> EvaluationResult:
        """执行单次评估"""
        pass
    
    async def evaluate_batch(self, test_cases: List[TestCase]) -> BatchEvaluationResult:
        """批量评估"""
        pass
    
    def generate_report(self, results: List[EvaluationResult]) -> EvaluationReport:
        """生成评估报告"""
        pass
```

---

## 7. 评估数据集构建方案

### 7.1 数据集构建流程

```
1. 梳理业务场景 → 2. 收集高频问题 → 3. 标注标准答案 → 4. 标注相关 chunk → 5. 质量审核
```

### 7.2 数据来源

**来源 1: 历史真实 Query**
- 从线上日志收集真实用户提问
- 覆盖高频、低频、复杂问题
- 包含口语化、错别字等真实场景

**来源 2: 业务专家构造**
- 邀请儿童发展领域专家构造专业问题
- 确保问题覆盖核心知识点
- 标注标准答案和相关文档

**来源 3: 现有测试用例扩展**
- 基于现有 `rag_test_manager.py` 中的测试用例
- 补充标注信息（ground_truth、relevant_docs）
- 扩展到 200+ 条

### 7.3 标注工具设计

**标注界面字段**:
```json
{
  "query": "查询文本",
  "query_type": "问题类型",
  "age_range": "适用年龄范围",
  "ground_truth": "标准答案",
  "relevant_docs": [
    {
      "doc_id": "文档 ID",
      "chunk_id": "片段 ID",
      "relevance_score": 3,  // 0-3 分
      "reason": "标注理由"
    }
  ],
  "keywords": ["关键词 1", "关键词 2"],
  "notes": "标注备注"
}
```

**标注工具实现**:
- 方案 1: Streamlit 快速构建标注界面
- 方案 2: Label Studio 专业标注平台
- 方案 3: 简易 JSON 标注工具（内部开发）

### 7.4 数据集版本管理

**版本命名**: `rag_eval_dataset_v{major}.{minor}.{patch}`

**版本文件结构**:
```
data/rag_evaluation/
├── datasets/
│   ├── v1.0.0/
│   │   ├── test_set.json          # 测试集 (200 条)
│   │   ├── validation_set.json    # 验证集 (50 条)
│   │   └── metadata.json          # 元数据
│   └── v1.1.0/
├── annotations/
│   └── ...
└── scripts/
    ├── build_dataset.py
    └── validate_dataset.py
```

---

## 8. 人工评估流程

### 8.1 人工评估流程

```
1. 抽样规则 → 2. 评估人员 → 3. 打分表 → 4. 仲裁机制 → 5. 结果汇总
```

**抽样规则**:
- 每日自动评估低分样本（自动打分 < 3.5）
- 随机抽样（每日 20-30 条）
- 重大版本全量评估

**评估人员**:
- 业务专家（儿童发展领域）
- 标注人员（经过培训）
- 产品经理（业务可用性评估）

**仲裁机制**:
- 争议答案由业务负责人终审
- 分歧 > 2 分时触发仲裁

### 8.2 人工评估打分表

| 指标 | 权重 | 5 分 | 3 分 | 1 分 |
|------|------|------|------|------|
| **检索相关性** | 20% | 完全相关 | 部分冗余 | 大量无关 |
| **忠实度（无幻觉）** | 30% | 完全无编造 | 轻微偏差 | 严重错误 |
| **回答完整性** | 20% | 信息全覆盖 | 缺次要信息 | 缺关键信息 |
| **可读性与格式** | 15% | 极佳 | 一般 | 混乱 |
| **业务可用性** | 15% | 可直接使用 | 需修改 | 不可用 |

**综合得分计算**:
```
综合得分 = Σ(指标得分 × 权重)
```

**质量门槛**:
- 企业通用标准：综合得分 ≥ 4.0
- 高合规场景：综合得分 ≥ 4.5，幻觉率 = 0
- 检索 Recall@3 ≥ 90%

### 8.3 人工评估工具

**评估界面设计**:
```
┌─────────────────────────────────────────────┐
│ 用户问题：2 岁儿童前庭觉失调的表现           │
├─────────────────────────────────────────────┤
│ 检索上下文：                                 │
│ [1] 文档 A - 片段 3 (相关性：强)             │
│ [2] 文档 B - 片段 1 (相关性：中)             │
│ ...                                         │
├─────────────────────────────────────────────┤
│ 模型回答：                                   │
│ 前庭觉失调主要表现为平衡能力差、注意力不集中... │
├─────────────────────────────────────────────┤
│ 评估打分：                                   │
│ □ 检索相关性：5 4 3 2 1                      │
│ □ 忠实度：    5 4 3 2 1                      │
│ □ 完整性：    5 4 3 2 1                      │
│ □ 可读性：    5 4 3 2 1                      │
│ □ 业务可用性：5 4 3 2 1                      │
├─────────────────────────────────────────────┤
│ 问题说明：[文本框]                           │
│ 提交评估 [按钮]                              │
└─────────────────────────────────────────────┘
```

**工具实现**:
- Streamlit 快速构建
- FastAPI + React 自定义开发
- 集成到现有前端（KnowledgeSearchPage）

---

## 9. 全流程执行步骤

### 阶段 1: 准备工作（1-2 天）

**任务清单**:
1. ✅ 梳理业务场景，确定高频/核心/风险问题
2. ✅ 构建 200+ 测试集，完成标准答案与 chunk 标注
3. ✅ 接入 RAGAS/TruLens 自动化评估环境

**交付物**:
- 评估数据集 v1.0.0
- 标注工具
- RAGAS 环境配置

### 阶段 2: 基线评估（1 天）

**任务清单**:
1. ✅ 跑通当前版本检索 + 生成全链路
2. ✅ 输出 baseline 指标报告
3. ✅ 定位短板：检索差 / 生成差 / 都差

**交付物**:
- Baseline 评估报告
- 问题清单 Top 10

### 阶段 3: 迭代优化（持续）

**检索优化**:
- 优化向量模型
- 优化 chunk 切分
- 优化检索策略（重排/混合检索）

**生成优化**:
- 优化 prompt
- 增加格式约束
- 增强上下文筛选

**执行流程**:
```
每轮优化 → 自动化评估 → 对比指标提升 → 决定是否上线
```

**交付物**:
- 优化版本评估报告
- 版本对比报告

### 阶段 4: 上线验证（1 天）

**任务清单**:
1. ✅ 人工全量复核测试集
2. ✅ 确认无重大幻觉、无业务错误
3. ✅ 设定线上监控指标

**交付物**:
- 人工评估报告
- 上线审批单

### 阶段 5: 线上持续评估

**任务清单**:
1. ✅ 日志埋点：记录 query、召回 chunk、生成 answer、耗时
2. ✅ 定期抽样人工复核
3. ✅ 按月更新测试集，覆盖新业务问题

**交付物**:
- 线上质量监控 Dashboard
- 月度评估报告

---

## 10. 实施计划与时间规划

### 10.1 实施路线图

```
Week 1: 基础评估能力建设
├── Day 1-2: 检索评估模块扩展 (rag_evaluator.py)
├── Day 3-4: 生成评估模块开发 (新建)
└── Day 5: 端到端评估模块集成

Week 2: 数据集构建与工具集成
├── Day 1-2: 评估数据集构建 (200+ 条)
├── Day 3-4: RAGAS 集成与测试
└── Day 5: 基线评估执行

Week 3: 人工评估与流程完善
├── Day 1-2: 人工评估工具开发
├── Day 3: 人工评估执行
└── Day 4-5: 评估报告生成与优化

Week 4: 线上监控与持续改进
├── Day 1-2: 线上监控埋点
├── Day 3-4: 评估 Dashboard 开发
└── Day 5: 项目总结与文档完善
```

### 10.2 关键里程碑

| 里程碑 | 时间 | 交付物 |
|--------|------|--------|
| **M1: 评估系统 MVP** | Week 1 结束 | 检索 + 生成评估模块可用 |
| **M2: 数据集 v1.0** | Week 2 结束 | 200+ 标注测试集 |
| **M3: 基线报告** | Week 2 结束 | Baseline 评估报告 |
| **M4: 人工评估完成** | Week 3 结束 | 人工评估报告 |
| **M5: 线上监控上线** | Week 4 结束 | 监控 Dashboard |

### 10.3 资源需求

**人力资源**:
- 后端开发：1 人（评估模块开发）
- 算法工程师：0.5 人（RAGAS 集成、模型优化）
- 业务专家：0.5 人（数据集标注、人工评估）
- 前端开发：0.5 人（评估 Dashboard）

**技术资源**:
- RAGAS 许可证（开源免费）
- 标注工具（Streamlit / Label Studio）
- 服务器资源（评估任务执行）

### 10.4 风险与应对

| 风险 | 影响 | 应对措施 |
|------|------|---------|
| **数据集构建进度慢** | 高 | 优先构建 50 条验证集，快速启动评估 |
| **RAGAS 集成困难** | 中 | 先使用自定义评估器，RAGAS 作为补充 |
| **人工评估成本高** | 中 | 自动化评估为主，人工评估抽样 |
| **指标与业务不一致** | 高 | 定期校准自动指标，以人工评估为准 |

---

## 附录

### A. 相关文件

- [`docs/rag 评估方法.md`](/Users/owen/project/ai/child-development-assessment-agent/docs/rag 评估方法.md) - RAG 评估方法参考文档
- [`backend/src/core/rag_evaluator.py`](/Users/owen/project/ai/child-development-assessment-agent/backend/src/core/rag_evaluator.py) - 检索评估器
- [`backend/src/service/rag_test_manager.py`](/Users/owen/project/ai/child-development-assessment-agent/backend/src/service/rag_test_manager.py) - 测试管理
- [`backend/src/model/rag_test.py`](/Users/owen/project/ai/child-development-assessment-agent/backend/src/model/rag_test.py) - 测试数据模型

### B. 参考资源

- [RAGAS 官方文档](https://docs.ragas.io/)
- [TruLens 官方文档](https://www.trulens.org/)
- [RAG 评估技术深度解析](https://blog.csdn.net/Androiddddd/article/details/154572744)
- [Vector Search retrieval quality guide](https://learn.microsoft.com/en-us/azure/databricks/vector-search/vector-search-retrieval-quality)

### C. 术语表

| 术语 | 说明 |
|------|------|
| **RAG** | Retrieval-Augmented Generation，检索增强生成 |
| **Recall@k** | TopK 结果中的召回率 |
| **MRR** | Mean Reciprocal Rank，平均倒数排名 |
| **NDCG** | Normalized Discounted Cumulative Gain，归一化折损累计增益 |
| **Faithfulness** | 忠实度，生成内容是否基于检索上下文 |
| **LLM-as-Judge** | 使用 LLM 作为评估员进行自动打分 |

---

## 总结

本方案设计了一套**完整的 RAG 系统评估体系**，覆盖检索、生成、端到端三个层级，结合自动化评估（RAGAS、自定义评估器）和人工评估，可实现：

1. **检索质量可量化**: Recall@k、MRR、NDCG 等客观指标
2. **生成质量可评估**: 忠实度、相关性、完整性自动打分
3. **版本迭代可对比**: 每次优化前后指标对比
4. **问题定位可追溯**: 失败案例归因分析
5. **上线质量有保障**: 人工 + 自动双重验证

**下一步行动**:
1. 创建实施计划文档（`docs/superpowers/plans/`）
2. 按优先级分阶段实施
3. 每周输出评估报告，持续优化
