# B-2: 动态权重决策逻辑

> **所属 Phase**: Phase B (P1)
> **任务类型**: 单一任务 — 基于查询类型分析结果动态调整 BM25/向量权重
> **对应问题**: 测试 4（查询权重分配不合理）+ 需求 4.4

## 🎯 目标

将 `HybridRetrievalMerger.get_dynamic_weights` 中不适配中文的 `keyword_density` 逻辑替换为基于 `QueryAnalyzer` 分类结果的权重决策，确保不同查询类型使用最优权重配比。

## 📋 实施步骤

- [ ] **Step 1: 定义权重决策规则表**
  - [ ] 基于需求文档测试 4 的期望权重，定义以下规则：
    
    | 查询类型 | BM25 权重 | 向量权重 | 依据 |
    |----------|-----------|----------|------|
    | SHORT (<5 字) | 0.3 | 0.7 | 短查询语义信息少，向量检索优势大 |
    | TERMINOLOGY (专业术语) | 0.7 | 0.3 | 专业术语精确匹配，BM25 优势大 |
    | DESCRIPTIVE (描述性) | 0.4 | 0.6 | 描述性查询偏语义，向量略重 |
    | COMPLEX (复杂) | 0.5 | 0.5 | 复杂查询需均衡，配合查询重写 |
    | DEFAULT (默认) | 0.5 | 0.5 | 兜底均衡权重 |

  - [ ] **权重必须通过配置管理**，不可硬编码：
    - 在 `src/config/modules/rag/retrieval.py` 中新增配置项：
      ```python
      rag_weight_strategy: str = Field(
          default="dynamic",
          validation_alias="RAG_WEIGHT_STRATEGY",
          description="权重策略：dynamic（动态）/ fixed（固定）",
      )
      rag_weight_by_query_type: Dict[str, Dict[str, float]] = Field(
          default_factory=lambda: {
              "short": {"bm25": 0.3, "vector": 0.7},
              "terminology": {"bm25": 0.7, "vector": 0.3},
              "descriptive": {"bm25": 0.4, "vector": 0.6},
              "complex": {"bm25": 0.5, "vector": 0.5},
              "default": {"bm25": 0.5, "vector": 0.5},
          },
          description="按查询类型的权重配置",
      )
      ```

- [ ] **Step 2: 重构 `get_dynamic_weights` 方法**
  - [ ] 阅读 `src/core/hybrid_retrieval.py` 第 118-140 行当前实现
  - [ ] 替换为基于 `QueryAnalyzer` 的新逻辑：
    ```python
    @staticmethod
    def get_dynamic_weights(
        query: str,
        age: int = None,
        query_analyzer: Optional[QueryAnalyzer] = None,
        weight_config: Optional[Dict[str, Dict[str, float]]] = None,
        strategy: str = "dynamic",
    ) -> tuple[float, float]:
        """基于查询类型动态返回权重（适配中文场景）"""
        
        # 回滚开关：固定权重模式
        if strategy == "fixed":
            bm25_weight = settings.rag_hybrid_bm25_weight
            return bm25_weight, 1 - bm25_weight
        
        # 使用 QueryAnalyzer 分析查询类型
        if query_analyzer is None:
            query_analyzer = _get_default_analyzer()
        
        analysis = query_analyzer.analyze(query)
        
        # 从配置获取权重
        if weight_config is None:
            weight_config = settings.rag_weight_by_query_type
        
        # 按查询类型获取权重
        type_key = analysis.query_type.value
        weights = weight_config.get(type_key, weight_config["default"])
        
        bm25_weight = weights["bm25"]
        vector_weight = weights["vector"]
        
        # 年龄微调（保留原有逻辑，但降低影响幅度）
        if age is not None and age < 3:
            bm25_weight *= 0.95  # 低龄儿童语义匹配略重要（从 0.9 降至 0.95）
            bm25_weight = max(bm25_weight, 0.2)  # 不低于 0.2
        
        logger.debug(
            f"动态权重决策：query='{query[:30]}', type={type_key}, "
            f"BM25={bm25_weight:.2f}, Vector={vector_weight:.2f}"
        )
        
        return bm25_weight, vector_weight
    ```
  - [ ] **保留向后兼容**：
    - 当 `query_analyzer` 为 `None` 时，使用全局单例（通过 DI 或懒加载）
    - 当 `strategy="fixed"` 时，回退到旧版固定权重

- [ ] **Step 3: 更新调用方**
  - [ ] 阅读 `src/service/retrieval_service.py` 第 397 行附近的调用：
    ```python
    bm25_weight, vector_weight = HybridRetrievalMerger.get_dynamic_weights(
        query, user_age
    )
    ```
  - [ ] 修改为注入 `QueryAnalyzer` 实例：
    ```python
    bm25_weight, vector_weight = HybridRetrievalMerger.get_dynamic_weights(
        query,
        user_age,
        query_analyzer=self._query_analyzer,  # 通过 __init__ 注入
        strategy=settings.rag_weight_strategy,
    )
    ```
  - [ ] 在 `RetrievalService.__init__` 中初始化 `QueryAnalyzer`：
    ```python
    from src.core.query_analyzer import QueryAnalyzer
    self._query_analyzer = QueryAnalyzer()
    ```

- [ ] **Step 4: 同步更新 `merge_for_search` 的默认权重**
  - [ ] 阅读 `src/core/hybrid_retrieval.py` 第 216-298 行的 `merge_for_search` 方法
  - [ ] 当前默认权重 `bm25_weight=0.7, vector_weight=0.3` 不适配所有场景
  - [ ] 修改签名，接受动态权重参数：
    ```python
    @staticmethod
    def merge_for_search(
        bm25_nodes: List[NodeWithScore],
        vector_nodes: List[NodeWithScore],
        query: str = "",
        age: int = None,
        query_analyzer: Optional[QueryAnalyzer] = None,
        limit: int = 20,
    ) -> List[NodeWithScore]:
        # 内部调用 get_dynamic_weights 获取权重
        bm25_weight, vector_weight = HybridRetrievalMerger.get_dynamic_weights(
            query, age, query_analyzer
        )
        # ... 后续融合逻辑不变
    ```

- [ ] **Step 5: 编写单元测试**
  - [ ] 创建 `tests/test_weight_decision.py`
  - [ ] **测试用例 1：短查询权重**
    ```python
    def test_short_query_weights():
        analyzer = QueryAnalyzer()
        bm25_w, vector_w = HybridRetrievalMerger.get_dynamic_weights(
            "运动", query_analyzer=analyzer
        )
        assert bm25_w == pytest.approx(0.3, abs=0.01)
        assert vector_w == pytest.approx(0.7, abs=0.01)
    ```
  - [ ] **测试用例 2：专业术语权重**
    ```python
    def test_terminology_weights():
        analyzer = QueryAnalyzer()
        bm25_w, vector_w = HybridRetrievalMerger.get_dynamic_weights(
            "感统训练", query_analyzer=analyzer
        )
        assert bm25_w == pytest.approx(0.7, abs=0.01)
        assert vector_w == pytest.approx(0.3, abs=0.01)
    ```
  - [ ] **测试用例 3：描述性查询权重**
    ```python
    def test_descriptive_weights():
        analyzer = QueryAnalyzer()
        bm25_w, vector_w = HybridRetrievalMerger.get_dynamic_weights(
            "3 岁儿童语言发展迟缓怎么办", query_analyzer=analyzer
        )
        assert bm25_w == pytest.approx(0.4, abs=0.01)
        assert vector_w == pytest.approx(0.6, abs=0.01)
    ```
  - [ ] **测试用例 4：复杂查询权重**
    ```python
    def test_complex_weights():
        analyzer = QueryAnalyzer()
        bm25_w, vector_w = HybridRetrievalMerger.get_dynamic_weights(
            "前庭觉训练和精细动作训练的区别", query_analyzer=analyzer
        )
        assert bm25_w == pytest.approx(0.5, abs=0.01)
        assert vector_w == pytest.approx(0.5, abs=0.01)
    ```
  - [ ] **测试用例 5：固定权重回滚**
    ```python
    def test_fixed_weight_fallback():
        analyzer = QueryAnalyzer()
        bm25_w, vector_w = HybridRetrievalMerger.get_dynamic_weights(
            "运动",
            query_analyzer=analyzer,
            strategy="fixed",
        )
        assert bm25_w == pytest.approx(settings.rag_hybrid_bm25_weight, abs=0.01)
    ```
  - [ ] **测试用例 6：年龄微调**
    ```python
    def test_age_micro_adjustment():
        analyzer = QueryAnalyzer()
        
        # 2 岁用户，短查询
        bm25_w, vector_w = HybridRetrievalMerger.get_dynamic_weights(
            "运动", age=2, query_analyzer=analyzer
        )
        # BM25 权重应从 0.3 降至 0.3*0.95=0.285
        assert bm25_w == pytest.approx(0.285, abs=0.01)
        
        # 验证不低于下限
        bm25_w, vector_w = HybridRetrievalMerger.get_dynamic_weights(
            "运动", age=1, query_analyzer=analyzer
        )
        assert bm25_w >= 0.2
    ```
  - [ ] **测试用例 7：配置覆盖**
    ```python
    def test_custom_weight_config():
        analyzer = QueryAnalyzer()
        custom_config = {
            "short": {"bm25": 0.2, "vector": 0.8},
            "default": {"bm25": 0.5, "vector": 0.5},
        }
        bm25_w, vector_w = HybridRetrievalMerger.get_dynamic_weights(
            "运动",
            query_analyzer=analyzer,
            weight_config=custom_config,
        )
        assert bm25_w == pytest.approx(0.2, abs=0.01)
        assert vector_w == pytest.approx(0.8, abs=0.01)
    ```

- [ ] **Step 6: 集成验证**
  - [ ] 运行诊断测试的测试 4（查询类型分析），验证权重分配：
    ```bash
    cd backend && uv run pytest tests/diagnose_rag_comprehensive_v2.py -v -k "test_4_query_type"
    ```
  - [ ] 确认以下权重分配符合预期：
    | 查询 | 类型 | 目标 BM25 | 目标 Vector |
    |------|------|-----------|-------------|
    | 运动 | 短词 | 0.3 | 0.7 |
    | 感统训练 | 专业术语 | 0.7 | 0.3 |
    | 3 岁儿童语言发展迟缓怎么办 | 描述性 | 0.4 | 0.6 |
    | 前庭觉训练和精细动作训练的区别 | 复杂 | 0.5 | 0.5 |
  - [ ] 运行完整诊断测试，确认 Precision@5 未退化（允许暂时不提升，但不应下降）：
    ```bash
    cd backend && uv run pytest tests/diagnose_rag_comprehensive_v2.py -v -k "test_1_retrieval_quality"
    ```
  - [ ] 验证 Agent 评分不受影响：
    ```bash
    cd backend && uv run pytest tests/core/nodes/test_scoring.py -v
    ```

## ✅ 验收标准

| 验收项 | 标准 | 验证方法 |
|--------|------|----------|
| 短查询权重 | BM25 ≤0.3, Vector ≥0.7 | 单元测试 |
| 专业术语权重 | BM25 ≥0.7, Vector ≤0.3 | 单元测试 |
| 描述性查询权重 | BM25 ≤0.4, Vector ≥0.6 | 单元测试 |
| 固定权重回滚 | `strategy=fixed` 时恢复旧版权重 | 单元测试 |
| 年龄微调 | 低龄用户 BM25 权重降低，但不低于 0.2 | 单元测试 |
| 配置覆盖 | 自定义权重配置生效 | 单元测试 |
| 诊断测试 4 通过率 | 所有查询权重分配符合期望 | 集成验证 |

## 📁 涉及文件

| 文件 | 操作 | 说明 |
|------|------|------|
| `src/core/hybrid_retrieval.py` | 修改 | 重构 `get_dynamic_weights`，更新 `merge_for_search` 签名 |
| `src/service/retrieval_service.py` | 修改 | 注入 `QueryAnalyzer`，更新调用方式 |
| `src/config/modules/rag/retrieval.py` | 修改 | 新增 `rag_weight_strategy` 和 `rag_weight_by_query_type` 配置项 |
| `tests/test_weight_decision.py` | 新增 | 权重决策单元测试（7 个测试用例） |

## ⚠️ 注意事项

1. **权重值必须通过配置管理**，禁止硬编码在 `get_dynamic_weights` 中
2. **保持向后兼容**：`strategy="fixed"` 时必须完全回退到旧版行为
3. **年龄微调幅度降低**：从原来的 `*=0.9` 降至 `*=0.95`，避免过度影响权重配比
4. **本 Phase 不涉及查询重写**：复杂查询的查询重写/意图提取在 Phase C 中处理
5. **权重决策与分数校准解耦**：权重只影响 BM25/向量的融合比例，不影响分数校准逻辑（Phase A 处理）

---

**返回索引：** [02-phase-b-00-overview.md](./02-phase-b-00-overview.md)
