# 08 - Layer 5a: Embedding 质量 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 08 - Layer 5a: Embedding 质量

**Architecture:** 参考下方原文档的实现方案和数据模型

**Tech Stack:** Python, FastAPI, TypeScript, React

---

### Task 1: 实现核心逻辑与测试

**Files:**
- Create: `backend/src/core/validation/layers/layer5a_embedding.py`
- Create: `backend/src/core/validation/synonym_query_pairs.json`
- Test: `backend/tests/test_placeholder.py`

- [ ] **Step 1: Write the failing test**
  - 根据下方的验收标准和测试方案，编写对应的测试用例
- [ ] **Step 2: Run test to verify it fails**
  - 执行测试并确保看到预期失败信息 (Red)
- [ ] **Step 3: Write minimal implementation**
  - 根据下方"实现方案"中的步骤，编写或修改业务代码
- [ ] **Step 4: Run test to verify it passes**
  - 执行测试确保通过 (Green)
- [ ] **Step 5: Commit**
  - `git add` 相关文件并提交 commit

---

## 原始需求与设计细节 (供参考)

> **需求来源**: spec 文档 `05-validation-layers.md` 中 `5.5.1 校验 5a: Embedding 质量校验` 节
> **所属 Phase**: Phase 4

## 需求定义

检查 Embedding 模型的语义区分能力。同义查询对验证 + Silhouette Score + 异常向量检测。

## 验收标准

- [ ] 同义对相似度 ≥ 0.85，低于则警告
- [ ] Silhouette Score ≥ 0.5 良好，< 0.3 警告
- [ ] 异常向量检测（零向量/NaN/维度异常）
- [ ] 同义查询对优先级：手动 > 自动提取 > 内置

## 涉及文件

| 文件路径 | 操作 | 说明 |
|---------|------|------|
| `backend/src/core/validation/layers/layer5a_embedding.py` | 新增 | Layer 5a 实现 |
| `backend/src/core/validation/synonym_query_pairs.json` | 新增 | 内置同义查询对 |

## 实现方案

### 后端实现

```python
# backend/src/core/validation/layers/layer5a_embedding.py
import json
import logging
import numpy as np
from typing import Any
from pathlib import Path

logger = logging.getLogger(__name__)

SYNONYM_PAIRS_FILE = Path(__file__).parent / "synonym_query_pairs.json"

class Layer5aEmbeddingQuality:
    """Layer 5a: Embedding 质量校验"""
    
    def __init__(self, db, test_run):
        self.db = db
        self.test_run = test_run
    
    async def execute(self) -> dict:
        """执行 Embedding 质量校验"""
        test_cases = self.test_run.test_cases or []
        queries = [tc.get("query", "") for tc in test_cases if tc.get("query")]
        
        if not queries:
            return {"status": "skipped", "data": {"reason": "缺少查询列表"}}
        
        synonym_pairs = await self._get_synonym_pairs()
        
        warnings = []
        
        # 1. 同义查询对验证
        synonym_similarity = await self._check_synonym_pairs(synonym_pairs)
        if synonym_similarity is not None and synonym_similarity < 0.85:
            warnings.append({
                "level": "warning",
                "message": f"同义对相似度低 ({synonym_similarity:.2f} < 0.85)",
            })
        
        # 2. Silhouette Score
        silhouette = await self._calc_silhouette_score(test_cases)
        if silhouette is not None and silhouette < 0.3:
            warnings.append({
                "level": "warning",
                "message": f"区分度低 (Silhouette {silhouette:.2f} < 0.3)",
            })
        
        # 3. 异常向量检测
        anomalies = await self._detect_anomalies(queries)
        if anomalies:
            warnings.append({
                "level": "critical",
                "message": f"发现 {len(anomalies)} 个异常向量",
            })
        
        return {
            "status": "completed",
            "data": {
                "synonym_similarity": synonym_similarity,
                "silhouette_score": silhouette,
                "anomalies": anomalies,
                "warnings": warnings,
            },
        }
    
    async def _get_synonym_pairs(self) -> list:
        """获取同义查询对（优先级：手动 > 自动提取 > 内置）"""
        from sqlalchemy import select, case
        from src.models.synonym_query_pair import SynonymQueryPair

        SOURCE_PRIORITY = {"manual": 3, "auto_extracted": 2, "builtin": 1}
        order_expr = case(
            *(
                (SynonymQueryPair.source == k, v)
                for k, v in SOURCE_PRIORITY.items()
            ),
            else_=0,
        ).desc()

        stmt = (
            select(SynonymQueryPair)
            .where(SynonymQueryPair.active == True)
            .order_by(order_expr, SynonymQueryPair.created_at.desc())
            .limit(50)
        )
        result = await self.db.execute(stmt)
        db_pairs = result.scalars().all()

        if len(db_pairs) >= 10:
            return [{"query_a": p.query_a, "query_b": p.query_b} for p in db_pairs]

        if SYNONYM_PAIRS_FILE.exists():
            builtin_pairs = json.loads(SYNONYM_PAIRS_FILE.read_text())
            return [{"query_a": p["query_a"], "query_b": p["query_b"]} for p in builtin_pairs[:20]]

        return []
    
    async def _check_synonym_pairs(self, pairs: list) -> float | None:
        """检查同义对相似度"""
        if not pairs:
            return None
        
        from src.core.embedding.factory import get_embedding
        
        embedding = get_embedding()
        similarities = []
        
        for pair in pairs:
            vec_a = await embedding.aembed_query(pair["query_a"])
            vec_b = await embedding.aembed_query(pair["query_b"])
            if vec_a and vec_b:
                sim = self._cosine_similarity(vec_a, vec_b)
                similarities.append(sim)
        
        return sum(similarities) / len(similarities) if similarities else None
    
    async def _calc_silhouette_score(self, test_cases: list) -> float | None:
        """计算 Silhouette Score（按领域分组）"""
        valid_cases = [tc for tc in test_cases if tc.get("query") and tc.get("domain")]
        if len(valid_cases) < 10:
            return None
        
        from src.core.embedding.factory import get_embedding
        from sklearn.metrics import silhouette_score
        
        embedding = get_embedding()
        vectors = []
        labels = []
        domain_to_label = {}
        label_counter = 0
        
        for tc in valid_cases:
            vec = await embedding.aembed_query(tc["query"])
            if vec:
                domain = tc["domain"]
                if domain not in domain_to_label:
                    domain_to_label[domain] = label_counter
                    label_counter += 1
                vectors.append(vec)
                labels.append(domain_to_label[domain])
        
        if len(vectors) < 10 or len(set(labels)) < 2:
            return None
        
        return silhouette_score(vectors, labels)
    
    async def _detect_anomalies(self, queries: list) -> list:
        """检测异常向量（随机抽样 20 条，覆盖更广）"""
        import random
        from src.core.embedding.factory import get_embedding

        embedding = get_embedding()
        anomalies = []
        sample_size = min(20, len(queries))
        sampled_queries = random.sample(queries, sample_size) if len(queries) > 20 else queries

        for q in sampled_queries:
            vec = await embedding.aembed_query(q)
            if vec is None:
                anomalies.append({"query": q, "type": "None"})
            elif np.allclose(vec, 0):
                anomalies.append({"query": q, "type": "zero_vector"})
            elif np.any(np.isnan(vec)):
                anomalies.append({"query": q, "type": "nan"})

        return anomalies
    
    def _cosine_similarity(self, a: list, b: list) -> float:
        """计算余弦相似度"""
        a, b = np.array(a), np.array(b)
        norm_a, norm_b = np.linalg.norm(a), np.linalg.norm(b)
        if norm_a == 0 or norm_b == 0:
            return 0
        return float(np.dot(a, b) / (norm_a * norm_b))
```

### 内置同义查询对

```json
[
  {"query_a": "什么是感统训练", "query_b": "感统训练是什么", "domain": "感统"},
  {"query_a": "如何进行语言干预", "query_b": "语言干预怎么做", "domain": "语言"},
  {"query_a": "认知发展阶段有哪些", "query_b": "认知发展分哪几个阶段", "domain": "认知"},
  {"query_a": "社交能力如何培养", "query_b": "怎么培养社交能力", "domain": "社交"},
  {"query_a": "情绪管理的方法", "query_b": "如何管理情绪", "domain": "情绪"}
]
```

## 测试方案

```python
@pytest.mark.asyncio
async def test_synonym_similarity():
    """同义对相似度计算正确"""
    ...

@pytest.mark.asyncio
async def test_anomaly_detection():
    """异常向量检测正确"""
    ...
```

## 注意事项

- 使用 SafeDashScopeEmbedding 包装器处理 API 异常
- Silhouette Score 需要 sklearn 依赖
