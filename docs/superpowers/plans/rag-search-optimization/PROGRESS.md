# RAG 搜索优化进度追踪

## 总体进度

| Phase | 状态 | 进度 | 预计完成 |
|-------|------|------|----------|
| Phase A: 分数语义重构 | ✅ 已完成 | 100% | 2026-04-16 |
| Phase B: 查询权重调优 | ✅ 已完成 | 100% | 2026-04-16 |
| Phase C: 同义词扩展质量优化 | ✅ 已完成 | 100% | 2026-04-16 |
| Phase D: 性能优化 | ✅ 已完成 | 100% | 2026-04-16 |

## Phase A: 分数语义重构 (P0) 🔄

- [x] **A-1: 分数分离与数据模型变更** ✅
  - ✅ 修改 `KnowledgeItem` 新增 `age_fit_score` 字段
  - ✅ 修改 `_convert_to_knowledge_items` 移除分数混合逻辑
  - ✅ 修改 `_process_search_results` 新增 `age_fit_score` 字段
  - ✅ 创建单元测试 `test_score_separation.py` (6 个测试全部通过)
  
- [x] **A-2: 年龄适配度细粒度计算器** ✅
  - ✅ 创建 `AgeFitScorer` 类 (`src/core/rag/age_fit_scorer.py`)
  - ✅ 实现三维度计算模型(年龄范围匹配、内容特征适配、领域匹配)
  - ✅ 使用 `@lru_cache` 优化性能
  - ✅ 创建单元测试 `test_age_fit_scorer.py` (14 个测试全部通过)
  - ✅ 验证输出 ≥10 个不同值(细粒度连续分布)
  
- [x] **A-3: BM25/向量分数校准统一** ✅
  - ✅ 创建 `ScoreCalibrator` 类 (`src/core/rag/score_calibrator.py`)
  - ✅ 实现 Min-Max 归一化 + 统一 Sigmoid 校准
  - ✅ 创建单元测试 `test_score_calibrator.py` (26 个测试全部通过)
  - ✅ 验证 BM25 与向量分数最大差异 <0.2
  
- [x] **A-4: 年龄过滤逻辑重构** ✅
  - ✅ 创建 `AgeFilter` 类和 `AgeFilterMode` 枚举
  - ✅ 实现严格模式（user_age 必须在 [target_min, target_max] 内）
  - ✅ 实现宽松模式（tolerance=2 for range, 1 for single age）
  - ✅ 修改 `_build_age_filters` 使用新 `AgeFilter`
  - ✅ 新增配置项 `rag_age_filter_mode`、`rag_age_filter_tolerance_strict`、`rag_age_filter_tolerance_loose`
  - ✅ 创建单元测试 `test_age_filter.py` (14 个测试全部通过)
  - ✅ 验证严格模式准确率 100% (7/7)
  
- [x] **A-5: 过滤流水线集成** ✅
  - ✅ 在 `_execute_retrieval` 后添加精确年龄过滤（二次过滤）
  - ✅ 确保 `relevance_score` 仅反映检索相关性
  - ✅ 确保 `age_fit_score` 独立计算
  
- [x] **A-6: 前端分数展示适配** ✅
  - ✅ `SearchResultItem` 接口新增 `age_fit_score?: number` 字段
  - ✅ `SearchResultList.tsx` 展示双分数（检索相关度 + 年龄适配度）
  - ✅ `ResultDetailModal.tsx` 详情弹窗展示双分数
  - ✅ 添加 Tooltip 说明分数含义
  - ✅ 分数颜色辅助函数（≥0.8 绿色，≥0.6 蓝色，≥0.4 橙色，<0.4 红色）
  - ✅ 向后兼容：`age_fit_score` 缺失时不展示

**Phase A 核心验收标准**:
- ✅ `KnowledgeItem` 包含 `age_fit_score` 字段，与 `relevance_score` 独立
- ✅ `age_fit_score` 输出 ≥10 个不同值（0-1 连续分布）
- ✅ BM25 与向量分数最大差异 <0.2
- ✅ 年龄过滤准确率 100% (7/7 标准测试用例)
- ✅ 60 个单元测试全部通过 (A-1: 6, A-2: 14, A-3: 26, A-4: 14)

## Phase B: 查询权重调优 (P1) ✅

- [x] **B-1: 查询类型分析器** ✅
  - ✅ 实现查询特征提取（长度、关键词密度、专业术语）
  - ✅ 中文场景适配
  - ✅ 创建 `QueryAnalyzer` 类 (`src/core/rag/query_analyzer.py`)
  - ✅ 创建专业术语词典 (`src/data/terminology.json`)
  - ✅ 创建单元测试 `test_query_analyzer.py` (18 个测试全部通过)
  
- [x] **B-2: 动态权重决策逻辑** ✅
  - ✅ 重构 `get_dynamic_weights` 方法
  - ✅ 集成到 `hybrid_retrieval.py`
  - ✅ 配置化权重参数 (`rag_weight_strategy`, `rag_weight_by_query_type`)
  - ✅ 在 `RetrievalService.__init__` 中初始化 `QueryAnalyzer`
  - ✅ 创建单元测试 `test_weight_decision.py` (9 个测试全部通过)

**Phase B 核心验收标准**:
- ✅ 短查询 (<5 字) 向量权重 = 0.7
- ✅ 专业术语查询 BM25 权重 = 0.7
- ✅ 描述性查询向量权重 = 0.6
- ✅ 复杂查询均衡权重 = 0.5/0.5
- ✅ 固定权重回滚功能正常
- ✅ 年龄微调功能正常（低龄用户 BM25 权重降低 5%）
- ✅ 27 个单元测试全部通过 (B-1: 18, B-2: 9)

## Phase C: 同义词扩展质量优化 (P1) ✅

### C-1: 同义词质量验证器 ✅
- [x] **C-1.1: 分析现有 `_validate_expansion` 的不足** ✅
  - ✅ 确认缺失的验证维度：领域相关性、粒度控制、黑名单机制
- [x] **C-1.2: 构建领域验证词典** ✅
  - ✅ 创建 `src/data/synonym_validation.json`
  - ✅ 定义 `domain_terms` / `domain_whitelist` / `domain_blacklist` 结构（覆盖 12 个核心词条）
- [x] **C-1.3: 实现 `SynonymValidator` 类** ✅
  - ✅ 创建 `src/core/rag/synonym_validator.py`
  - ✅ 实现 `ValidationReport` dataclass
  - ✅ 实现三级降级配置加载（数据库 → JSON → 空词典）
  - ✅ 实现 `_check_term` 多维度检查（长度/字符/黑名单/粒度/白名单/语义重叠）
  - ✅ 预编译正则和转换 set 优化性能
- [x] **C-1.4: 集成到 `_expand_synonyms` 流程** ✅
  - ✅ 在 LLM 返回解析后插入验证逻辑
  - ✅ 在 `RetrievalService.__init__` 中初始化
- [x] **C-1.5: 编写单元测试** ✅
  - ✅ 创建 `tests/test_synonym_validator.py`（18 个测试全部通过）
  - ✅ 黑名单过滤测试
  - ✅ 粒度控制测试
  - ✅ 白名单优先通过测试
  - ✅ 语义重叠检查测试
  - ✅ 验证通过率计算测试
  - ✅ 边界情况测试（单字/超长/特殊字符）
  - ✅ 空词典降级测试
  - ✅ 诊断查询验证测试（注意力/感统/精细动作）

### C-2: LLM 失败本地兜底策略 ✅
- [x] **C-2.1: 分析现有 `_local_expand_synonyms` 的不足** ✅
  - ✅ 确认词典规模/语义精确度/匹配策略问题
- [x] **C-2.2: 构建本地同义词词典** ✅
  - ✅ 创建 `src/data/local_synonyms.json`
  - ✅ 按领域分类组织（5 大领域 30+ 词条）
- [x] **C-2.3: 实现 `LocalSynonymExpander` 类** ✅
  - ✅ 创建 `src/core/rag/local_synonym_expander.py`
  - ✅ 实现三级降级配置加载
  - ✅ 实现 `_exact_match` 精确匹配
  - ✅ 实现 `_substring_match` 子串匹配
  - ✅ 实现 `_tokenized_match` 分词匹配（n-gram 提取）
- [x] **C-2.4: 集成到 `_expand_synonyms` 流程** ✅
  - ✅ 替换现有 `_local_expand_synonyms` 实现
  - ✅ 复用 C-1 验证器过滤本地扩展结果
  - ✅ 在 `RetrievalService.__init__` 中初始化
- [x] **C-2.5: 优化 LLM Prompt** ✅
  - ✅ 更新 `src/core/prompts_fallback.py` 中的 `SYNONYM_EXPANSION_PROMPT`
  - ✅ 新增【领域约束】和【负面示例】
- [x] **C-2.6: 编写单元测试** ✅
  - ✅ 创建 `tests/test_local_synonym_expander.py`（24 个测试全部通过）
  - ✅ 精确匹配测试
  - ✅ 子串匹配测试
  - ✅ 分词匹配测试
  - ✅ 兜底成功率验证测试（100% > 80%）
  - ✅ 诊断查询验证测试（3 个标注查询）
  - ✅ 数据库降级测试

**Phase C 核心验收标准**:
- ✅ 质量验证通过率 ≥95%（黑名单/粒度控制 100% 拒绝）
- ✅ 兜底成功率 100%（14 个常见查询全部成功扩展 > 80% 目标）
- ✅ 42 个单元测试全部通过 (C-1: 18, C-2: 24)

## Phase D: 性能优化 (P2) ✅

- [x] **D-1: content_hash 精确去重** ✅
  - ✅ 创建 `DedupEngine` 类 (`src/core/rag/dedup_engine.py`)
  - ✅ 实现 `_exact_dedup` 方法 (O(n) 复杂度)
  - ✅ 使用 dict 按 content_hash 去重，保留分数更高的条目
- [x] **D-2: MinHash 近似去重** ✅
  - ✅ 实现 `_minhash_dedup` 方法 (O(n log n) 复杂度)
  - ✅ 使用 LSH 分桶，仅桶内比较
  - ✅ 支持 datasketch 依赖可选加载
- [x] **D-3: Cross-Encoder 模型预热** ✅
  - ✅ 创建 `ModelWarmer` 类 (`src/core/rag/model_warmer.py`)
  - ✅ 实现 `warmup()` 异步方法，后台加载模型
  - ✅ 在 `CrossEncoderReranker` 中集成预热状态检查
  - ✅ 保留懒加载作为降级策略
- [x] **D-4: 动态 initial_k 规则** ✅
  - ✅ 在 `reranker.py` 中实现 `_calculate_initial_k(query)` 方法
  - ✅ 简单查询 (<5 字) → 15，短词 (5-10) → 20，中等 (10-15) → 30，复杂 (>15) → 50
  - ✅ 配置项 `rag_reranker_dynamic_initial_k` 开关
- [x] **D-5: 输入校验与预处理** ✅
  - ✅ 创建 `BoundaryHandler` 类 (`src/core/rag/boundary_handler.py`)
  - ✅ 实现 `validate_and_clean` 方法（空查询/超长查询/特殊字符）
  - ✅ 实现 `extract_intent` 方法（超长查询意图提取）
- [x] **D-6: 边界年龄映射与降级策略** ✅
  - ✅ 实现 `get_development_stage` 年龄到发展阶段映射
  - ✅ 实现 `map_age到_stage_range` 边界年龄映射
  - ✅ 实现 `apply_fallback_strategy` 无结果降级策略（3 级降级）

**Phase D 核心验收标准**:
- ✅ 去重算法复杂度 O(n log n)
- ✅ 22 个单元测试全部通过

## 诊断测试验收追踪

| 测试项 | 当前状态 | 目标状态 | 负责 Phase |
|--------|----------|----------|------------|
| 测试 1: 检索质量指标 | ❌ P@5=0.53 | ✅ P@5≥0.75 | Phase A |
| 测试 2: 分数分布分析 | ❌ 差异=0.80 | ✅ 差异<0.2 | Phase A |
| 测试 3: 年龄适配度细粒度 | ❌ 3 档 | ✅ ≥10 档 | Phase A |
| 测试 4: 查询类型分析 | ❌ 固定权重 | ✅ 动态权重 | Phase B |
| 测试 5: 内容去重效果 | ❌ O(n²) | ✅ O(n log n) | Phase D |
| 测试 6: 重排序效果 | ❌ 固定 initial_k | ✅ 动态 initial_k | Phase D |
| 测试 7: 性能分析 | ❌ P50=800ms | ✅ P50≤300ms | Phase D |
| 测试 8: 稳定性分析 | ✅ | ✅ 保持 | - |
| 测试 9: 相关性一致性 | ✅ | ✅ 保持 | - |
| 测试 10: 边界场景分析 | ❌ 未处理 | ✅ 合理处理 | Phase D |
| 测试 11: 年龄过滤准确性 | ❌ 71% | ✅ ≥90% | Phase A |
| 测试 12: 同义词扩展质量 | ❌ 高噪声 | ✅ ≥95% 通过率 | Phase C |

---

**最后更新:** 2026-04-16 - Phase A 全部完成（6/6 子任务），Phase B 全部完成（2/2 子任务，27 个单元测试全部通过），Phase C 全部完成（2/2 子任务，42 个单元测试全部通过），Phase D 全部完成（6/6 子任务，22 个单元测试全部通过）
