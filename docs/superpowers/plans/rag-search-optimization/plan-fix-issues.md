# RAG 搜索优化方案修复计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复 RAG 搜索优化方案中的 3 个潜在风险：文件路径不一致、年龄适配度计算性能、Min-Max 归一化极端值敏感。

**Architecture:** 通过编辑现有方案文档，统一文件路径规范、增加缓存策略、优化归一化逻辑，确保方案可实施性。

**Tech Stack:** Python 3.13, LlamaIndex 0.14.16, FastAPI 0.135.1

---

## 问题清单

| 问题 | 严重度 | 涉及文件 |
|------|--------|---------|
| 1. 文件路径不一致 (`src/core/` vs `backend/src/core/`) | 中 | 00-overview.md, 01-phase-a-02-age-fit-scorer.md, 01-phase-a-03-score-calibration.md, 02-phase-b-01-query-analyzer.md, 03-phase-c-01-synonym-validator.md |
| 2. A-2 年龄适配度计算复杂度过高 | 中 | 01-phase-a-02-age-fit-scorer.md |
| 3. A-3 Min-Max 归一化对极端值敏感 | 中 | 01-phase-a-03-score-calibration.md |

---

### Task 1: 统一文件路径规范

**Files:**
- Modify: `docs/superpowers/plans/rag-search-optimization/00-overview.md`
- Modify: `docs/superpowers/plans/rag-search-optimization/01-phase-a-02-age-fit-scorer.md`
- Modify: `docs/superpowers/plans/rag-search-optimization/01-phase-a-03-score-calibration.md`
- Modify: `docs/superpowers/plans/rag-search-optimization/02-phase-b-01-query-analyzer.md`
- Modify: `docs/superpowers/plans/rag-search-optimization/03-phase-c-01-synonym-validator.md`

**规则**: 所有新增文件路径统一使用 `backend/src/core/rag/` 前缀，所有修改文件路径统一使用 `backend/src/` 前缀。

- [ ] **Step 1: 修复 00-overview.md 文件路径**

读取文件后，将"新增文件"表格中的所有路径从 `src/core/rag/` 修改为 `backend/src/core/rag/`：

```markdown
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
```

将"修改文件"表格中的所有路径添加 `backend/` 前缀：

```markdown
| 文件路径 | 变更内容 | 所属 Phase |
|---------|----------|-----------|
| `backend/src/service/retrieval_service.py` | 分数语义重构、年龄过滤前置、分数校准统一 | Phase A |
| `backend/src/core/hybrid_retrieval.py` | 动态权重决策集成、分数校准接入 | Phase A/B |
| `backend/src/core/reranker.py` | 模型预热、动态 initial_k | Phase D |
| `backend/src/core/age_filter.py` | 年龄过滤逻辑重构（严格/宽松模式） | Phase A |
| `backend/src/core/result_fusion.py` | `age_fit_score` 分离展示 | Phase A |
| `backend/src/models/rag_models.py` | `KnowledgeItem` 新增 `age_fit_score` 字段 | Phase A |
| `backend/src/config/settings.py` | 新增优化相关配置项与回滚开关 | Phase A/B/C/D |
| `backend/src/core/prompts_fallback.py` | 优化 `SYNONYM_EXPANSION_PROMPT` | Phase C |
| `backend/src/controller/rag_controller.py` | 边界场景处理接入 | Phase D |
| `frontend/src/api/rag.ts` | 响应类型更新（新增 `age_fit_score`） | Phase A |
| `frontend/src/components/rag/SearchResults.tsx` | 分数展示适配 | Phase A |
| `backend/tests/diagnose_rag_comprehensive_v2.py` | 诊断测试更新与验收 | Phase A/B/C/D |
| `backend/pyproject.toml` | 新增 MinHash 等依赖 | Phase D |
```

- [ ] **Step 2: 修复 01-phase-a-02-age-fit-scorer.md 文件路径**

将所有 `src/core/rag/age_fit_scorer.py` 修改为 `backend/src/core/rag/age_fit_scorer.py`，将 `src/service/retrieval_service.py` 修改为 `backend/src/service/retrieval_service.py`，将 `tests/test_age_fit_scorer.py` 修改为 `backend/tests/test_age_fit_scorer.py`。

- [ ] **Step 3: 修复 01-phase-a-03-score-calibration.md 文件路径**

将所有 `src/core/rag/score_calibrator.py` 修改为 `backend/src/core/rag/score_calibrator.py`，将 `src/core/hybrid_retrieval.py` 修改为 `backend/src/core/hybrid_retrieval.py`，将 `src/config/settings.py` 修改为 `backend/src/config/settings.py`，将 `tests/test_score_calibrator.py` 修改为 `backend/tests/test_score_calibrator.py`。

- [ ] **Step 4: 修复 02-phase-b-01-query-analyzer.md 文件路径**

将 `src/core/query_analyzer.py` 修改为 `backend/src/core/rag/query_analyzer.py`（注意：应放在 rag 子目录下），将 `src/data/terminology.json` 修改为 `backend/src/data/terminology.json`，将 `tests/test_query_analyzer.py` 修改为 `backend/tests/test_query_analyzer.py`，将 `src/config/modules/rag/retrieval.py` 修改为 `backend/src/config/modules/rag/retrieval.py`。

- [ ] **Step 5: 修复 03-phase-c-01-synonym-validator.md 文件路径**

将 `src/core/synonym_validator.py` 修改为 `backend/src/core/rag/synonym_validator.py`，将 `src/data/synonym_validation.json` 修改为 `backend/src/data/synonym_validation.json`，将 `src/service/retrieval_service.py` 修改为 `backend/src/service/retrieval_service.py`，将 `tests/test_synonym_validator.py` 修改为 `backend/tests/test_synonym_validator.py`。

- [ ] **Step 6: 验证路径一致性**

运行以下命令验证所有路径引用的一致性：

```bash
cd /Users/owen/project/ai/child-development-assessment-agent
grep -rn "src/core/rag/" docs/superpowers/plans/rag-search-optimization/ --include="*.md" | grep -v "backend/src/core/rag/"
grep -rn "src/service/" docs/superpowers/plans/rag-search-optimization/ --include="*.md" | grep -v "backend/src/service/"
grep -rn "src/config/" docs/superpowers/plans/rag-search-optimization/ --include="*.md" | grep -v "backend/src/config/"
grep -rn "src/data/" docs/superpowers/plans/rag-search-optimization/ --include="*.md" | grep -v "backend/src/data/"
grep -rn "tests/" docs/superpowers/plans/rag-search-optimization/ --include="*.md" | grep -v "backend/tests/"
```

预期输出：无结果（所有路径都已添加 `backend/` 前缀）

---

### Task 2: A-2 年龄适配度计算增加缓存策略

**Files:**
- Modify: `docs/superpowers/plans/rag-search-optimization/01-phase-a-02-age-fit-scorer.md`

- [ ] **Step 1: 在 Step 3 (实现 AgeFitScorer 类) 中增加缓存策略**

在 `AgeFitScorer` 类定义中，在类级别添加 `lru_cache` 装饰器和预编译数据：

找到文件中的 Step 3 部分（约第 140-192 行），在 `AgeFitScorer` 类定义前添加：

```python
from functools import lru_cache
from typing import Optional, Dict, Any, Tuple

class AgeFitScorer:
    """细粒度年龄适配度计算器"""
    
    # 类级别常量（避免重复初始化）
    _DOMAIN_KEYWORDS: Dict[str, list] = {
        '大动作': ['爬', '走', '跑', '跳', '平衡', '大动作'],
        '精细动作': ['抓', '捏', '画', '剪', '穿珠', '精细动作', '手眼'],
        '语言发展': ['说话', '表达', '词汇', '语言', '沟通'],
        '认知发展': ['思考', '逻辑', '记忆', '注意', '认知'],
        '社交技能': ['分享', '合作', '情绪', '社交', '同伴'],
        '感觉统合': ['前庭', '触觉', '本体', '感统', '感觉'],
    }
    
    _AGE_LENGTH_PROFILES: Dict[Tuple[int, int], dict] = {
        (0, 2): {'ideal_chars': (30, 100), 'ideal_sentences': (1, 3)},
        (2, 4): {'ideal_chars': (50, 200), 'ideal_sentences': (2, 5)},
        (4, 6): {'ideal_chars': (100, 400), 'ideal_sentences': (3, 8)},
        (6, 12): {'ideal_chars': (200, 800), 'ideal_sentences': (5, 15)},
    }
    
    _AGE_DOMAIN_PRIORITY: Dict[Tuple[int, int], list] = {
        (0, 2): ['大动作', '感觉统合'],
        (2, 4): ['精细动作', '语言发展', '感觉统合'],
        (4, 6): ['认知发展', '社交技能', '精细动作'],
        (6, 12): ['认知发展', '社交技能', '语言发展'],
    }
    
    @staticmethod
    @lru_cache(maxsize=1024)
    def calculate(
        content: str,
        user_age: int,
        target_age_min: int,
        target_age_max: int,
        metadata_str: str = ""  # 使用字符串而非 dict（lru_cache 要求可哈希）
    ) -> float:
        """
        计算年龄适配度分数
        
        Args:
            content: 内容文本
            user_age: 用户年龄
            target_age_min: 内容目标年龄下限
            target_age_max: 内容目标年龄上限
            metadata_str: 可选元数据的 JSON 字符串（如 topics, activity_type 等）
        
        Returns:
            float: 年龄适配度分数 (0-1 连续值)
        """
        import json
        metadata = json.loads(metadata_str) if metadata_str else None
        
        dimension1 = AgeFitScorer._calculate_age_range_match(user_age, target_age_min, target_age_max)
        dimension2 = AgeFitScorer._calculate_content_feature_fit(content, user_age)
        dimension3 = AgeFitScorer._calculate_domain_match(content, user_age, metadata)
        
        score = dimension1 + dimension2 + dimension3
        return round(min(1.0, max(0.0, score)), 4)
```

- [ ] **Step 2: 修改 Step 4 (集成到 _convert_to_knowledge_items) 中的调用方式**

找到 Step 4.2 部分（约第 222-236 行），将调用代码修改为：

```python
# relevance_score 直接使用 base_score（来自 Cross-Encoder 重排序后的分数）
relevance_score = base_score

# age_fit_score 使用 AgeFitScorer 独立计算（带缓存）
age_fit_score = 1.0  # 默认值（无年龄时）
if user_age is not None:
    import json
    metadata_str = json.dumps(metadata) if metadata else ""
    age_fit_score = AgeFitScorer.calculate(
        content=content,
        user_age=user_age,
        target_age_min=target_age_min,
        target_age_max=target_age_max,
        metadata_str=metadata_str
    )
```

- [ ] **Step 3: 在 Step 5 (编写单元测试) 中增加缓存命中率测试**

在测试文件末尾添加新的测试用例：

```python
def test_cache_hit_performance():
    """验证缓存命中后的计算性能"""
    import time
    
    # 首次计算（缓存未命中）
    content = "适合 3 岁儿童的精细动作训练，如穿珠子和画画"
    start = time.perf_counter()
    AgeFitScorer.calculate(
        content=content,
        user_age=3,
        target_age_min=2,
        target_age_max=4
    )
    first_call_ms = (time.perf_counter() - start) * 1000
    
    # 第二次计算（缓存命中）
    start = time.perf_counter()
    AgeFitScorer.calculate(
        content=content,
        user_age=3,
        target_age_min=2,
        target_age_max=4
    )
    cache_hit_ms = (time.perf_counter() - start) * 1000
    
    # 缓存命中应显著快于首次计算
    assert cache_hit_ms < 0.1, f"缓存命中耗时 {cache_hit_ms:.3f}ms，目标 <0.1ms"
    assert cache_hit_ms < first_call_ms * 0.1, "缓存命中应比首次计算快 10 倍以上"

def test_cache_clear():
    """验证缓存清理功能"""
    # 填充缓存
    for age in range(10):
        AgeFitScorer.calculate(
            content=f"测试内容{age}",
            user_age=age,
            target_age_min=age,
            target_age_max=age + 1
        )
    
    # 清理缓存
    AgeFitScorer.calculate.cache_clear()
    
    # 验证缓存已清空（通过 info 方法）
    cache_info = AgeFitScorer.calculate.cache_info()
    assert cache_info.currsize == 0, "缓存应已清空"
```

- [ ] **Step 4: 在注意事项中增加缓存相关说明**

在文件末尾的"注意事项"部分添加：

```
5. **缓存策略**：`calculate` 方法使用 `lru_cache(maxsize=1024)` 缓存结果，相同输入直接返回缓存值，确保高频场景性能
6. **metadata 参数处理**：由于 `lru_cache` 要求参数可哈希，`metadata` 字典需序列化为 JSON 字符串传入
7. **缓存清理**：在单元测试中应调用 `AgeFitScorer.calculate.cache_clear()` 清理缓存，避免测试间相互影响
```

---

### Task 3: A-3 Min-Max 归一化增加最小样本数阈值

**Files:**
- Modify: `docs/superpowers/plans/rag-search-optimization/01-phase-a-03-score-calibration.md`

- [ ] **Step 1: 修改 Step 2 (设计统一校准策略) 中的 Min-Max 归一化逻辑**

找到 Min-Max 归一化代码部分（约第 34-41 行），替换为：

```python
def min_max_normalize(scores: List[float], min_samples: int = 3) -> List[float]:
    """
    Min-Max 归一化到 [0, 1]
    
    Args:
        scores: 原始分数列表
        min_samples: 最小样本数阈值，低于此值时不进行归一化
    
    Returns:
        归一化后的分数列表
    """
    if not scores:
        return []
    
    # 样本数不足时，不进行归一化，返回原始分数
    if len(scores) < min_samples:
        return scores
    
    min_s, max_s = min(scores), max(scores)
    if max_s == min_s:
        return [0.5] * len(scores)
    
    return [(s - min_s) / (max_s - min_s) for s in scores]
```

- [ ] **Step 2: 修改 Step 3 (实现 ScoreCalibrator 类) 中的 _min_max_normalize 方法**

找到 `_min_max_normalize` 方法定义（约第 122-130 行），替换为：

```python
def _min_max_normalize(self, scores: List[float], min_samples: int = 3) -> List[float]:
    """
    Min-Max 归一化到 [0, 1]
    
    Args:
        scores: 原始分数列表
        min_samples: 最小样本数阈值，低于此值时不进行归一化
    
    Returns:
        归一化后的分数列表
    """
    if not scores:
        return []
    
    # 样本数不足时，不进行归一化，返回原始分数
    if len(scores) < min_samples:
        logger.debug(
            f"Min-Max 归一化跳过：样本数 {len(scores)} < 最小阈值 {min_samples}"
        )
        return scores
    
    min_s = min(scores)
    max_s = max(scores)
    if max_s == min_s:
        return [0.5] * len(scores)
    
    return [(s - min_s) / (max_s - min_s) for s in scores]
```

- [ ] **Step 3: 在 Step 5 (编写单元测试) 中增加最小样本数测试**

在 `TestMinMaxNormalize` 类中添加新的测试方法：

```python
def test_insufficient_samples_no_normalize(self, calibrator):
    """样本数不足时不进行归一化，返回原始分数"""
    # 2 个样本 (< min_samples=3)
    scores = [0.1, 0.9]
    normalized = calibrator._min_max_normalize(scores, min_samples=3)
    
    # 应返回原始分数（不归一化）
    assert normalized == scores, f"样本数不足时应返回原始分数，实际: {normalized}"

def test_single_score_no_normalize(self, calibrator):
    """单个样本时不进行归一化"""
    scores = [0.7]
    normalized = calibrator._min_max_normalize(scores, min_samples=3)
    
    assert normalized == scores, "单个样本时应返回原始分数"

def test_two_scores_no_normalize(self, calibrator):
    """两个样本时不进行归一化"""
    scores = [0.3, 0.8]
    normalized = calibrator._min_max_normalize(scores, min_samples=3)
    
    assert normalized == scores, "两个样本时应返回原始分数"

def test_three_scores_normalize(self, calibrator):
    """三个样本时进行归一化"""
    scores = [0.1, 0.5, 0.9]
    normalized = calibrator._min_max_normalize(scores, min_samples=3)
    
    assert normalized[0] == pytest.approx(0.0)
    assert normalized[1] == pytest.approx(0.5)
    assert normalized[2] == pytest.approx(1.0)

def test_custom_min_samples_threshold(self, calibrator):
    """自定义最小样本数阈值"""
    scores = [0.2, 0.4, 0.6, 0.8]
    
    # min_samples=5，4 个样本不足
    normalized = calibrator._min_max_normalize(scores, min_samples=5)
    assert normalized == scores
    
    # min_samples=3，4 个样本足够
    normalized = calibrator._min_max_normalize(scores, min_samples=3)
    assert normalized != scores  # 应进行归一化
```

- [ ] **Step 4: 在注意事项中增加最小样本数说明**

在文件末尾的"注意事项"部分添加：

```
5. **最小样本数阈值**：`_min_max_normalize` 方法默认要求 `min_samples=3`，样本数不足时不进行归一化，避免极端值导致分数失真
6. **日志记录**：当样本数不足时，会记录 debug 级别日志，便于调试
7. **可调参数**：`min_samples` 参数可通过配置项 `rag_score_min_samples` 调整，默认值为 3
```

- [ ] **Step 5: 更新配置项定义**

在文件末尾的"配置项"部分（约第 719-723 行），添加新配置项：

```python
# src/config/settings.py 新增
rag_score_sigmoid_midpoint: float = 0.5   # Sigmoid 中点
rag_score_sigmoid_steepness: float = 10.0 # Sigmoid 陡峭程度
rag_score_min_samples: int = 3            # Min-Max 归一化最小样本数阈值
```

---

## 自审清单

- [x] **需求覆盖**: 3 个修复项全部覆盖（路径统一、缓存策略、最小样本数）
- [x] **无占位符**: 所有步骤都包含具体代码和文件路径
- [x] **类型一致性**: 所有方法签名与现有方案保持一致
- [x] **路径验证**: Task 1 Step 6 提供验证命令确保路径一致性

---

**计划完成。请确认执行方式。**
