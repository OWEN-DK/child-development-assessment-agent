# RAG 知识库搜索优化实施计划

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 优化 RAG 知识库搜索质量与性能，解决分数语义混乱、年龄适配度粗糙、分数校准不一致、查询权重固定、同义词噪声、去重性能差、重排序慢、边界场景处理不完善等 10 项诊断失败问题。

**Architecture:** 采用分阶段原子变更策略，先解决核心分数语义问题 (Phase A)，再依次优化查询权重 (Phase B)、同义词质量 (Phase C)、性能与边界场景 (Phase D)。

**Tech Stack:** Python 3.13, LlamaIndex 0.14.16, Chroma, FastAPI 0.135.1, React 19.2.4

**需求来源:** [docs/rag_search_optimization_requirements.md](../../rag_search_optimization_requirements.md) (v6.0)

---

## 🎯 项目背景与目标

### 背景
12 项诊断测试中 10 项失败，通过率仅 17%。根因归结为 3 个核心问题：
1. `relevance_score` 混合了检索相关性和年龄适配度，分数语义不清
2. 年龄适配度仅三档固定值 (0.3, 0.7, 1.0)，无法细粒度区分
3. BM25 和向量分数不在同一量级，融合后排序失真

### 核心目标
1. ✅ 分离 `relevance_score` 与 `age_fit_score`，分数语义清晰可调试
2. ✅ 年龄适配度从 3 档改为 ≥10 档连续值 (0-1)
3. ✅ BM25 与向量分数差异 <0.2，融合排序不失真
4. ✅ Precision@5 从 0.53 提升至 ≥0.75
5. ✅ 年龄过滤准确率从 71% 提升至 ≥90%
6. ✅ P50 响应时间从 ~800ms 降至 ≤300ms (预热后)
7. ✅ 去重复杂度从 O(n²) 降至 O(n log n)
8. ✅ 同义词扩展质量验证通过率 ≥95%

---

## 📋 实施原则
1. **原子变更**：Phase A 的分数语义重构必须一次性完成，避免中间状态不可用
2. **向后兼容**：`age_fit_score` 默认值 0.0 保持前端兼容
3. **配置驱动**：所有权重、阈值、回滚开关通过配置管理，禁止硬编码
4. **测试驱动**：每个 Phase 必须以诊断测试通过为验收标准
5. **可回滚**：每个 Phase 提供配置项回滚到旧版逻辑

---

## ✅ 验收标准

### Phase A 验收
- `KnowledgeItem` 新增 `age_fit_score` 字段，与 `relevance_score` 独立
- `relevance_score` 仅反映检索相关性（直接来自 Cross-Encoder）
- `age_fit_score` 输出 ≥10 个不同值（0-1 连续分布）
- 年龄过滤准确率 ≥90%
- BM25 与向量分数最大差异 <0.2
- Precision@5 ≥0.75

### Phase B 验收
- 短查询 (<5 字) 向量权重 ≥0.6
- 专业术语查询 BM25 权重 ≥0.6
- 查询类型分析测试通过

### Phase C 验收
- 同义词扩展质量验证通过率 ≥95%
- LLM 失败时本地兜底成功率 ≥80%

### Phase D 验收
- 去重耗时 ≤50ms (100 条结果)
- 重排序首次延迟 (冷启动) ≤1500ms
- P50 响应时间 (预热后) ≤300ms
- 所有边界场景有合理处理

---

# 项目概览与文件结构变更

## 📋 文件结构变更总览

### 新增文件

| 文件路径 | 职责 | 所属 Phase |
|---------|------|-----------|
| `backend/src/core/rag/age_fit_scorer.py` | 细粒度年龄适配度计算器 | Phase A |
| `backend/src/core/rag/score_calibrator.py` | BM25/向量分数校准器 | Phase A |
| `backend/src/core/rag/dedup_engine.py` | 高效去重引擎 (hash + MinHash) | Phase D |
| `backend/src/core/rag/query_analyzer.py` | 查询类型分析与权重决策器 | Phase B |
| `backend/src/core/rag/synonym_validator.py` | 同义词质量验证器 | Phase C |
| `backend/src/core/rag/local_synonym_expander.py` | 本地同义词扩展器（LLM 失败兜底） | Phase C |
| `backend/src/data/synonym_validation.json` | 验证规则词典（本地降级文件） | Phase C |
| `backend/src/data/local_synonyms.json` | 本地同义词词典（本地降级文件） | Phase C |
| `backend/src/core/rag/boundary_handler.py` | 边界场景处理器 | Phase D |
| `backend/src/core/rag/model_warmer.py` | Cross-Encoder 模型预热器 | Phase D |
| `backend/src/core/rag/age_filter.py` | 年龄过滤逻辑重构（严格/宽松模式） | Phase A |

### 修改文件

| 文件路径 | 变更内容 | 所属 Phase |
|---------|----------|-----------|
| `backend/src/service/retrieval_service.py` | 分数语义重构、年龄过滤前置、分数校准统一 | Phase A |
| `backend/src/core/hybrid_retrieval.py` | 动态权重决策集成、分数校准接入 | Phase A/B |
| `backend/src/core/reranker.py` | 模型预热、动态 initial_k | Phase D |
| `backend/src/core/age_filter.py` | 年龄过滤逻辑重构（严格/宽松模式） | Phase A |
| `backend/src/core/result_fusion.py` | `age_fit_score` 分离展示 | Phase A |
| `backend/src/models/rag_models.py` | `KnowledgeItem` 新增 `age_fit_score` 字段 | Phase A |
| `backend/src/config/settings.py` | 新增优化相关配置项与回滚开关 | Phase A/B/C/D |
| `backend/src/core/prompts_fallback.py` | 优化 `SYNONYM_EXPANSION_PROMPT`（新增领域约束和负面示例） | Phase C |
| `backend/src/controller/rag_controller.py` | 边界场景处理接入 | Phase D |
| `frontend/src/api/rag.ts` | 响应类型更新（新增 `age_fit_score`） | Phase A |
| `frontend/src/components/rag/SearchResults.tsx` | 分数展示适配 | Phase A |
| `backend/tests/diagnose_rag_comprehensive_v2.py` | 诊断测试更新与验收 | Phase A/B/C/D |
| `pyproject.toml` | 新增 MinHash 等依赖 | Phase D |

---

## 🏗️ 架构说明

### 分数语义重构架构 (Phase A)

```
┌─────────────────────────────────────────────────────────┐
│                    检索流水线                              │
│                                                          │
│  查询输入 → 查询重写 → BM25检索 + 向量检索                  │
│                           ↓                              │
│              ┌─────────────────────┐                     │
│              │  ScoreCalibrator    │  ← 统一校准策略       │
│              │  (BM25/向量同量级)    │                     │
│              └─────────┬───────────┘                     │
│                        ↓                                 │
│              ┌─────────────────────┐                     │
│              │  HybridRetrieval    │  ← 动态权重融合       │
│              │  (融合分数)          │                     │
│              └─────────┬───────────┘                     │
│                        ↓                                 │
│              ┌─────────────────────┐                     │
│              │  Cross-Encoder      │  ← 重排序            │
│              │  (relevance_score)  │                     │
│              └─────────┬───────────┘                     │
│                        ↓                                 │
│              ┌─────────────────────┐                     │
│              │  AgeFilter          │  ← 前置过滤          │
│              │  (严格/宽松模式)     │                     │
│              └─────────┬───────────┘                     │
│                        ↓                                 │
│              ┌─────────────────────┐                     │
│              │  AgeFitScorer       │  ← 细粒度计算        │
│              │  (age_fit_score)    │                     │
│              └─────────┬───────────┘                     │
│                        ↓                                 │
│              ┌─────────────────────┐                     │
│              │  KnowledgeItem      │                     │
│              │  relevance_score    │  ← 仅检索相关性       │
│              │  age_fit_score      │  ← 独立年龄适配度     │
│              └─────────────────────┘                     │
└─────────────────────────────────────────────────────────┘
```

### 年龄适配度计算逻辑 (Phase A)

```
输入: 内容块 (content, metadata, target_age_min, target_age_max)
      用户年龄 (user_age)

计算维度:
├── 1. 年龄范围匹配度 (0-0.4)
│    ├── 完全在范围内 → 0.4
│    ├── 差 1 岁 → 0.3
│    ├── 差 2 岁 → 0.2
│    └── 差 3 岁以上 → 0.0
│
├── 2. 内容特征适配度 (0-0.3)
│    ├── 内容长度适配（句子数、字数）
│    ├── 专业术语密度适配
│    └── 句子复杂度适配
│
└── 3. 领域匹配度 (0-0.3)
     ├── 内容涉及的发展领域与年龄段匹配
     └── 训练类型与年龄段匹配

输出: age_fit_score = 维度1 + 维度2 + 维度3 (0-1 连续值)
```

### 动态权重决策逻辑 (Phase B)

```
输入: 查询文本 (query)

特征提取:
├── 查询长度 (字数)
├── 关键词密度 (jieba 分词)
├── 专业术语匹配度（领域词库）
└── 查询类型分类

权重决策:
├── 短查询 (<5 字) → BM25=0.3, Vector=0.7
├── 专业术语 → BM25=0.7, Vector=0.3
├── 描述性查询 (5-15 字) → BM25=0.4, Vector=0.6
└── 复杂查询 (>15 字) → BM25=0.5, Vector=0.5 + 查询重写
```

### 去重引擎架构 (Phase D)

```
输入: 候选结果列表 (n 条)

去重流程:
├── 1. content_hash 精确去重 (O(n))
│    └── 使用 dict/set 快速过滤完全相同内容
│
├── 2. MinHash 近似去重 (O(n log n))
│    ├── 计算每条内容的 MinHash 签名
│    ├── LSH (Locality Sensitive Hashing) 分桶
│    └── 仅桶内比较，避免 O(n²)
│
└── 3. 保留最高 relevance_score 的代表项

输出: 去重后结果列表
```

---

## 📦 依赖管理

### Phase D 新增依赖

```toml
# MinHash 近似去重
datasketch = "^1.6.0"

# jieba 中文分词（查询分析）
jieba = "^0.42.1"
```

---

## 🔧 配置管理

### 新增配置项

```python
# Phase A: 分数语义重构
rag_score_method: str = "separated"  # "separated" | "legacy"
rag_age_filter_mode: str = "strict"  # "strict" | "loose"
rag_age_fit_score_enabled: bool = True

# Phase B: 查询权重
rag_weight_strategy: str = "dynamic"  # "dynamic" | "fixed"
rag_weight_bm25_short_query: float = 0.3
rag_weight_vector_short_query: float = 0.7
rag_weight_bm25_term_query: float = 0.7
rag_weight_vector_term_query: float = 0.3

# Phase C: 同义词扩展
rag_query_rewrite_method: str = "validated"  # "validated" | "legacy"
rag_synonym_quality_threshold: float = 0.8
rag_synonym_validation_rules: dict = {}  # 从 system_configs 加载
rag_local_synonyms_dict: dict = {}  # 从 system_configs 加载
rag_synonym_expansion_timeout: int = 10  # LLM 超时（秒）
rag_synonym_log_rejected: bool = True  # 记录被拒词

# Phase D: 性能优化
rag_performance_optimizations: bool = True
rag_dedup_method: str = "minhash"  # "minhash" | "hash" | "sequence"
rag_reranker_warmup: bool = True
rag_reranker_dynamic_initial_k: bool = True
```

---

## 📖 下一步

继续查看各个 Phase 的详细实施方案：

1. [Phase A: 分数语义重构](./01-phase-a-00-overview.md)
   - [A-1: 分数分离与数据模型变更](./01-phase-a-01-score-separation.md)
   - [A-2: 年龄适配度细粒度计算器](./01-phase-a-02-age-fit-scorer.md)
   - [A-3: BM25/向量分数校准统一](./01-phase-a-03-score-calibration.md)
   - [A-4: 年龄过滤逻辑重构](./01-phase-a-04-age-filter-refactor.md)
   - [A-5: 过滤流水线集成](./01-phase-a-05-filter-pipeline-integration.md)
   - [A-6: 前端分数展示适配](./01-phase-a-06-frontend-adaptation.md)
2. [Phase B: 查询权重调优](./02-phase-b-00-overview.md)
3. [Phase C: 同义词扩展质量优化](./03-phase-c-00-overview.md)
4. [Phase D: 性能优化](./04-phase-d-00-overview.md)
   - [D-1: content_hash 精确去重](./04-phase-d-01-hash-dedup.md)
   - [D-2: MinHash 近似去重](./04-phase-d-02-minhash-dedup.md)
   - [D-3: Cross-Encoder 模型预热](./04-phase-d-03-reranker-warmup.md)
   - [D-4: 动态 initial_k 规则](./04-phase-d-04-dynamic-initial-k.md)
   - [D-5: 输入校验与预处理](./04-phase-d-05-input-validation.md)
   - [D-6: 边界年龄映射与降级策略](./04-phase-d-06-boundary-age-fallback.md)

---

**返回索引：** [README.md](./README.md)
