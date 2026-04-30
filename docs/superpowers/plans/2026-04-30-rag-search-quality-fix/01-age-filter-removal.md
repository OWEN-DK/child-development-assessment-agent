# 01 年龄过滤整体移除

> 用户确认不再需要年龄过滤。本文件列出所有需要清理的位置。
> 作为先行步骤，移除后为后续修复减少干扰。

---

## 涉及的 24 个文件

### 第一层：核心文件（直接删除或大改）

| 文件 | 操作 | 说明 |
|------|------|------|
| `backend/src/core/age_filter.py` | **删除整个文件** | `AgeFilter` + `AgeFilterMode` + `DynamicAgeFilter` + `AgeFilterConfig` |
| `backend/src/core/rag/age_fit_scorer.py` | **删除整个文件** | 依赖 `AgeFilter.should_filter`，无独立用途 |
| `backend/src/core/pipeline/steps/age_filter.py` | **删除整个文件** | `AgeFilterStep` 管道步骤 |

### 第二层：业务代码（移除年龄相关逻辑）

| 文件 | 需移除的内容 |
|------|------------|
| `backend/src/service/retrieval/knowledge_retriever.py` | `_build_age_filters()` 方法（L37），`AgeFilter` 导入（L42），`build_metadata_filters` 调用（L49），年龄过滤逻辑（L308-311） |
| `backend/src/service/retrieval/facade.py` | `retrieve_knowledge()` 签名移除 `age` 参数，`_retrieve_via_pipeline()` 移除 `age` 参数，`search_content()` 移除 `age` 参数 |
| `backend/src/service/retrieval/result_processor.py` | 输出中 `target_age_min/max` 字段（L265-266） |
| `backend/src/service/document_ingestion/chunking_indexing.py` | 元数据回退 `target_age_min=0, target_age_max=18`（L119-120） |
| `backend/src/core/pipeline/orchestrator.py` | `"age_filter": "AgeFilterStep"` 注册（L76），`age` 参数传递 |
| `backend/src/core/pipeline/steps/__init__.py` | `AgeFilterStep` 导入（L1）和注册（L17） |
| `backend/src/core/metadata_extractor.py` | `target_age_min/max` 字段定义（L22-25）和提取逻辑（L109-110），验证/钳位逻辑（L283-312） |
| `backend/src/core/prompts_fallback.py` | prompt 模板中 `target_age_min/max` 相关指令（L88-89） |
| `backend/src/core/hybrid_retrieval.py` | `merge_for_search()` 中年龄相关参数传递（如有） |

### 第三层：Schema 定义（清理字段）

| 文件 | 需移除的内容 |
|------|------------|
| `backend/src/schemas/assessment.py` | `target_age_min/max` 字段（L142-143） |
| `backend/src/schemas/config.py` | `AgeFilterConfig` 类（L184） |
| `backend/src/schemas/metadata.py` | `target_age_min/max` 字段（L18-19） |
| `backend/src/schemas/__init__.py` | `AgeFilterConfig` 导出（L20, L195） |

### 第四层：配置文件

| 文件 | 需移除的内容 |
|------|------------|
| `backend/src/config/__init__.py` | `rag_age_filter_` 前缀过滤（L87, L172, L231） |
| `backend/src/config/modules/rag/core.py` | `rag_age_filter_stage_boundaries`（L107） |
| `backend/src/config/modules/rag/retrieval.py` | `rag_age_filter_mode`, `rag_age_filter_tolerance_strict`, `rag_age_filter_tolerance_loose`, `rag_age_filter_strictness`, `rag_age_filter_tolerance`（L181-201） |
| `backend/config/rag_pipeline.yaml` | complex pipeline 中 `age_filter` 步骤 |

### 第五层：测试文件

| 文件 | 操作 |
|------|------|
| `backend/tests/test_age_filter.py` | **删除整个文件** |
| `backend/tests/test_age_fit_scorer.py` | **删除整个文件** |
| `backend/tests/test_score_separation.py` | 移除 `target_age_min/max` 测试 fixture |
| `backend/tests/test_nodes_scoring.py` | 移除 `target_age_min/max` 测试 fixture |
| `backend/tests/diagnose_rag_comprehensive.py` | 移除 `test_age_filter()` 函数（L374） |
| `backend/tests/diagnose_rag_comprehensive_v2.py` | 移除 `test_age_filter_accuracy()`（L742） |
| `backend/tests/diagnose_rag_comprehensive_v3.py` | 移除 `AgeFilter` 导入和 `test_age_filter_accuracy()`（L854） |
| `backend/tests/diagnose_rag_relevance.py` | 移除 `test_age_filter_effectiveness()`（L153） |
| `backend/tests/unit/tuning/test_performance_baseline.py` | 移除 `rag_age_filter_strictness` 引用（L95） |
| `backend/tests/unit/tuning/test_rule_engine.py` | 移除 `rag_age_filter_strictness` 引用（L94, L159, L253） |

### 第六层：脚本

| 文件 | 需移除的内容 |
|------|------------|
| `backend/scripts/debug/debug_search_score.py` | `target_age_min/max` 打印（L55） |
| `backend/src/service/config_conflict_detector.py` | `_check_age_filter()` 方法（L115） |

---

## 实施步骤

### Step 1：删除核心文件（3 个文件）

```bash
rm backend/src/core/age_filter.py
rm backend/src/core/rag/age_fit_scorer.py
rm backend/src/core/pipeline/steps/age_filter.py
```

### Step 2：修改业务代码

**`knowledge_retriever.py`**：
- 删除 `_build_age_filters()` 方法
- 删除 `from src.core.age_filter import AgeFilter, AgeFilterMode`
- 在 `_execute_retrieval()` 中移除年龄过滤调用
- 在 `_convert_to_knowledge_items()` 中移除 `AgeFilter.should_filter()` 调用（L308-311）

**`facade.py`**：
- `retrieve_knowledge(query, age, limit, user_id)` → `retrieve_knowledge(query, limit, user_id)`
- `_retrieve_via_pipeline(query, age, limit)` → `_retrieve_via_pipeline(query, limit)`
- `search_content(query, age, ...)` → `search_content(query, ...)`
- 所有调用方的 `age` 参数传递一并清理

**`chunking_indexing.py`**：
- 删除元数据回退中的 `target_age_min=0, target_age_max=18`

### Step 3：清理 Schema 和配置

按上表逐一移除字段和配置项。

### Step 4：YAML pipeline 移除 age_filter 步骤

```yaml
# complex pipeline 移除这一步
# - name: age_filter
#   type: AgeFilterStep
```

### Step 5：删除测试文件，修复残留测试

删除 `test_age_filter.py` 和 `test_age_fit_scorer.py`。
其余测试文件移除年龄相关 fixture 和断言。

### Step 6：全局搜索确认无残留

```bash
grep -r "age_filter\|AgeFilter\|target_age_min\|target_age_max\|age_fit_scorer" backend/src/ --include="*.py" -l
```

结果应为空。

---

## 验证

- [ ] `cd backend && uv run pytest` 通过（除年龄相关测试外无回归）
- [ ] `grep -r "AgeFilter\|age_filter\|target_age" backend/src/` 返回空
- [ ] `uv run start` 正常启动
- [ ] 知识库搜索正常返回结果（无年龄过滤）
