# A-1: 分数分离与数据模型变更

> **所属 Phase**: Phase A (P0)
> **任务类型**: 单一任务 — 知识模型变更与分数语义解耦
> **对应问题**: 根因 1（relevance_score 混合了检索相关性和年龄适配度）

## 🎯 目标

将 `relevance_score` 与 `age_fit_score` 彻底分离，确保：
1. `relevance_score` 仅反映检索相关性（来自 Cross-Encoder 重排序后的分数）
2. `age_fit_score` 作为独立字段存在，不参与排序计算
3. 前端能分别展示两个分数

## 📋 实施步骤

- [ ] **Step 1: 分析现有分数混合逻辑**
  - [ ] 阅读 `src/service/retrieval_service.py` 中 `_convert_to_knowledge_items` 方法（第 429-537 行）
  - [ ] 定位分数混合代码：第 491-506 行，`final_score = base_score * (1 - age_weight) + age_fit_score * age_weight`
  - [ ] 确认 `relevance_score` 当前混合了 `base_score`（检索相关性）和 `age_fit_score`（年龄适配度）
  - [ ] 记录所有引用 `relevance_score` 的代码位置，确保变更影响范围清晰

- [ ] **Step 2: 修改 KnowledgeItem 数据模型**
  - [ ] 阅读 `src/model/schemas.py` 中 `KnowledgeItem` 定义（第 126-141 行）
  - [ ] 在 `KnowledgeItem` 中新增字段：
    ```python
    age_fit_score: float = Field(default=0.0, ge=0.0, le=1.0, description="年龄适配度分数（0-1 连续值，独立于检索相关性）")
    ```
  - [ ] 保持 `relevance_score` 字段不变，但更新注释说明其语义：
    ```python
    relevance_score: float = Field(default=0.0, description="检索相关性分数（来自 Cross-Encoder 重排序，不混合年龄适配度）")
    ```
  - [ ] 确保 `age_fit_score` 默认值为 0.0，保持向后兼容

- [ ] **Step 3: 修改 `_convert_to_knowledge_items` 方法**
  - [ ] 移除分数混合逻辑（原第 491-506 行）：
    ```python
    # 删除以下代码：
    # final_score = base_score
    # age_fit_score = 1.0
    # if user_age is not None:
    #     age_fit_score = child_development_engine.calculate_age_appropriateness(...)
    #     metadata_age_fit = self._calculate_age_fit_score(...)
    #     age_fit_score = 0.7 * age_fit_score + 0.3 * metadata_age_fit
    #     age_weight = settings.rag_age_fit_weight
    #     final_score = base_score * (1 - age_weight) + age_fit_score * age_weight
    ```
  - [ ] 替换为分离逻辑：
    ```python
    # relevance_score 直接使用 base_score（来自 Cross-Encoder 重排序后的分数）
    relevance_score = base_score
    
    # age_fit_score 独立计算（后续由 AgeFitScorer 负责，此处暂时保留旧逻辑作为过渡）
    age_fit_score = 1.0
    if user_age is not None:
        age_fit_score = child_development_engine.calculate_age_appropriateness(content, user_age)
        metadata_age_fit = self._calculate_age_fit_score(user_age, target_age_min, target_age_max)
        age_fit_score = 0.7 * age_fit_score + 0.3 * metadata_age_fit
    ```
  - [ ] 修改 `KnowledgeItem` 构造，传入两个独立分数：
    ```python
    item = KnowledgeItem(
        content=content.strip(),
        source_book=source,
        ...
        relevance_score=float(relevance_score),  # 仅检索相关性
        age_fit_score=float(age_fit_score),      # 独立年龄适配度
    )
    ```
  - [ ] 移除按 `final_score` 重新排序的逻辑（原第 535 行），改为按 `relevance_score` 排序：
    ```python
    results.sort(key=lambda x: x.relevance_score, reverse=True)
    ```

- [ ] **Step 4: 修改 `_process_search_results` 方法**
  - [ ] 阅读 `src/service/retrieval_service.py` 中 `_process_search_results` 方法（第 588-806 行）
  - [ ] **确认当前逻辑**：
    - 该方法被 `search_content` 方法（第 239-315 行）调用，用于前端知识库搜索页（`/knowledge` 路由）
    - 返回的是 `List[dict]`（非 `KnowledgeItem`），字典结构见第 782-797 行
    - 当前使用 `display_score` 作为前端展示分数，`raw_score` 作为内部分数
    - **未混合年龄适配度**（因为 `search_content` 不接收 `age` 参数）
  - [ ] **需要修改的内容**：
    - 在返回字典中新增 `age_fit_score` 字段（保持与 `KnowledgeItem` 一致的数据结构）
    - 由于 `search_content` 不接收年龄参数，`age_fit_score` 暂时设为 `null` 或 `0.0`
    - 修改第 782-797 行的字典构造，新增字段：
      ```python
      results.append(
          {
              "id": node.node_id,
              "content": content,
              "score": display_score,
              "raw_score": final_score,
              "age_fit_score": None,  # 搜索页不计算年龄适配度，后续如需支持需修改 search_content 签名
              "source_book": source_book,
              "chapter_title": metadata.get("chapter_title"),
              "page_label": page_label,
              "target_age_min": metadata.get("target_age_min", 0),
              "target_age_max": metadata.get("target_age_max", 18),
              "brain_regions": metadata.get("brain_regions", []),
              "topics": metadata.get("topics", []),
              "file_hash": metadata.get("file_hash"),
          }
      )
      ```
  - [ ] **不需要修改的内容**：
    - `display_score` 和 `raw_score` 的计算逻辑保持不变（仅反映检索相关性）
    - 阈值过滤、关键词加成等逻辑保持不变
    - 去重逻辑（`_is_content_duplicate`）保持不变

- [ ] **Step 5: 检查并更新所有引用 `relevance_score` 的代码**
  - [ ] **5.1 搜索影响范围**：运行以下命令定位所有引用：
    ```bash
    cd backend && grep -rn "relevance_score" src/ --include="*.py"
    ```
  - [ ] **5.2 逐个文件分析与处理**：
    
    **文件 1: `src/core/nodes/scoring.py`**
    - [ ] 第 125 行：`avg_relevance = sum(d.relevance_score for d in docs) / len(docs)`
      - **影响分析**：用于计算科学依据评分，`docs` 是 `List[KnowledgeItem]`
      - **处理方式**：**无需修改**。分离后 `relevance_score` 仅反映检索相关性，更符合"科学依据"的语义（检索到的内容越相关，科学依据越充分）
    - [ ] 第 278 行：`high_relevance_docs = [d for d in docs if d.relevance_score > 0.8]`
      - **影响分析**：筛选高相关性文档用于报告展示
      - **处理方式**：**无需修改**。阈值 0.8 仍适用于纯检索相关性分数
    
    **文件 2: `src/service/rag_test_manager.py`**
    - [ ] 第 874 行：`score=item.relevance_score`
      - **影响分析**：用于 RAG 测试中记录检索结果分数
      - **处理方式**：**无需修改**。测试评估的是检索质量，应使用纯检索相关性分数
    
    **文件 3: `src/service/rag_test_case_service.py`**
    - [ ] 第 399-409 行：`relevance_score = self._calculate_relevance(...)`
      - **影响分析**：这是测试用例生成时计算的相关性分数，与 `KnowledgeItem.relevance_score` 无关
      - **处理方式**：**无需修改**
    
    **文件 4: `src/core/rag_evaluator.py`**
    - [ ] 多处使用 `relevance_scores`（字典类型，用于评估指标计算）
      - **影响分析**：这是评估系统中的 ground truth 相关性评分，与 `KnowledgeItem.relevance_score` 无关
      - **处理方式**：**无需修改**
    
    **文件 5: `src/model/schemas.py`**
    - [ ] 第 140 行：`relevance_score: float = 0.0`
      - **处理方式**：已在 Step 2 中更新注释，无需额外修改

  - [ ] **5.3 前端影响分析**：
    - [ ] 前端类型定义：`frontend/src/api/knowledge/types.ts` 中 `SearchResultItem` 使用 `score: number`（非 `relevance_score`）
      - **处理方式**：无需修改，前端使用 `score` 字段与后端 `display_score` 对应
    - [ ] 前端展示组件：`frontend/src/components/knowledge/SearchResultList.tsx` 第 71 行使用 `item.score`
      - **处理方式**：无需修改
    - [ ] 前端详情弹窗：`frontend/src/components/knowledge/ResultDetailModal.tsx` 第 49 行使用 `item.score`
      - **处理方式**：无需修改
    - [ ] **结论**：前端当前未直接使用 `KnowledgeItem` 类型（仅使用 `SearchResultItem`），因此无需修改前端类型定义

  - [ ] **5.4 如需同时考虑年龄适配度的场景**：
    - [ ] 在 Agent 评分场景（`scoring.py`），如需同时考虑年龄适配度，应在业务层组合：
      ```python
      # 示例：在 scoring.py 中计算综合分数
      combined_score = (
          doc.relevance_score * 0.7 +  # 检索相关性权重 70%
          doc.age_fit_score * 0.3      # 年龄适配度权重 30%
      )
      ```
    - [ ] **本步骤不实现此类组合逻辑**，保持数据模型层的纯粹性

- [ ] **Step 6: 编写单元测试**
  - [ ] 创建 `tests/test_score_separation.py`
  - [ ] **测试环境准备**：
    ```python
    import pytest
    from src.model.schemas import KnowledgeItem
    from src.service.retrieval_service import RetrievalService
    from unittest.mock import MagicMock, AsyncMock
    from llama_index.core.schema import NodeWithScore, TextNode
    
    @pytest.fixture
    def mock_index_manager():
        manager = MagicMock()
        manager.get_index.return_value = MagicMock()
        manager.is_index_available.return_value = True
        manager.get_corpus_size.return_value = 100
        manager.index_version = "v1"
        manager.config_fingerprint = "abc123"
        return manager
    
    @pytest.fixture
    def mock_cache_service():
        cache = MagicMock()
        cache.get = AsyncMock(return_value=None)
        cache.set = AsyncMock()
        cache.clear = MagicMock()
        return cache
    
    @pytest.fixture
    def retrieval_service(mock_index_manager, mock_cache_service):
        return RetrievalService(mock_index_manager, mock_cache_service)
    ```
  
  - [ ] **测试用例 1：验证 `KnowledgeItem` 包含 `age_fit_score` 字段，默认值为 0.0**
    ```python
    def test_knowledge_item_has_age_fit_score_field():
        """验证 KnowledgeItem 新增 age_fit_score 字段，默认值为 0.0"""
        item = KnowledgeItem(
            content="测试内容",
            source_book="测试书籍",
            relevance_score=0.8
        )
        assert hasattr(item, 'age_fit_score')
        assert item.age_fit_score == 0.0  # 默认值
        assert item.relevance_score == 0.8
    
    def test_knowledge_item_age_fit_score_validation():
        """验证 age_fit_score 字段校验（0-1 范围）"""
        # 合法值
        item1 = KnowledgeItem(
            content="测试", source_book="测试",
            relevance_score=0.8, age_fit_score=0.5
        )
        assert item1.age_fit_score == 0.5
        
        # 边界值
        item2 = KnowledgeItem(
            content="测试", source_book="测试",
            relevance_score=0.8, age_fit_score=0.0
        )
        assert item2.age_fit_score == 0.0
        
        item3 = KnowledgeItem(
            content="测试", source_book="测试",
            relevance_score=0.8, age_fit_score=1.0
        )
        assert item3.age_fit_score == 1.0
    ```
  
  - [ ] **测试用例 2：验证 `relevance_score` 与 `age_fit_score` 无混合计算**
    ```python
    def test_scores_are_independent(retrieval_service):
        """验证 relevance_score 和 age_fit_score 独立赋值，互不影响"""
        # 模拟 Cross-Encoder 重排序后的节点
        node = NodeWithScore(
            node=TextNode(
                node_id="test_001",
                text="适合 3 岁儿童的精细动作训练方法",
                metadata={
                    "content": "适合 3 岁儿童的精细动作训练方法",
                    "file_name": "测试书籍.pdf",
                    "target_age_min": 3,
                    "target_age_max": 4,
                    "topics": ["精细动作"],
                    "brain_regions": [],
                    "benefits": []
                }
            ),
            score=0.85  # Cross-Encoder 分数
        )
        
        # 调用 _convert_to_knowledge_items
        items = retrieval_service._convert_to_knowledge_items([node], user_age=3)
        
        assert len(items) == 1
        item = items[0]
        
        # relevance_score 应直接来自 Cross-Encoder（0.85）
        assert item.relevance_score == pytest.approx(0.85, abs=0.01)
        
        # age_fit_score 应独立计算（不混合到 relevance_score）
        assert 0.0 <= item.age_fit_score <= 1.0
        
        # 验证两者不相等（证明未混合）
        # 如果混合了，relevance_score 会偏离 0.85
        assert abs(item.relevance_score - 0.85) < 0.05
    ```
  
  - [ ] **测试用例 3：验证排序仅基于 `relevance_score`**
    ```python
    def test_sorting_by_relevance_score_only(retrieval_service):
        """验证结果按 relevance_score 排序，不受 age_fit_score 影响"""
        # 模拟 3 个节点，Cross-Encoder 分数递减
        nodes = [
            NodeWithScore(
                node=TextNode(node_id="n1", text="内容 1", metadata={"content": "内容 1", "file_name": "书", "target_age_min": 0, "target_age_max": 18, "topics": [], "brain_regions": [], "benefits": []}),
                score=0.9  # 最高相关性
            ),
            NodeWithScore(
                node=TextNode(node_id="n2", text="内容 2", metadata={"content": "内容 2", "file_name": "书", "target_age_min": 0, "target_age_max": 18, "topics": [], "brain_regions": [], "benefits": []}),
                score=0.7  # 中等相关性
            ),
            NodeWithScore(
                node=TextNode(node_id="n3", text="内容 3", metadata={"content": "内容 3", "file_name": "书", "target_age_min": 0, "target_age_max": 18, "topics": [], "brain_regions": [], "benefits": []}),
                score=0.5  # 最低相关性
            ),
        ]
        
        items = retrieval_service._convert_to_knowledge_items(nodes, user_age=3)
        
        # 验证排序顺序
        assert items[0].relevance_score >= items[1].relevance_score >= items[2].relevance_score
        
        # 验证顺序与 Cross-Encoder 分数一致
        assert items[0].content == "内容 1"
        assert items[1].content == "内容 2"
        assert items[2].content == "内容 3"
    ```
  
  - [ ] **测试用例 4：验证向后兼容**
    ```python
    def test_backward_compatibility():
        """验证旧版 API 响应（无 age_fit_score）不崩溃"""
        # 模拟旧版字典响应（无 age_fit_score 字段）
        old_response = {
            "id": "test_001",
            "content": "测试内容",
            "score": 85.0,
            "raw_score": 0.85,
            "source_book": "测试书籍",
            "target_age_min": 3,
            "target_age_max": 4,
            "topics": [],
            "brain_regions": [],
            "file_hash": "abc123"
        }
        
        # 前端应能正常处理（使用可选链或默认值）
        # 验证 TypeScript 类型兼容性：age_fit_score 应为可选字段
        assert "age_fit_score" not in old_response  # 旧响应无此字段
        
        # 如果使用 Pydantic 模型解析，应设置默认值
        # 此处验证前端 SearchResultItem 类型中 age_fit_score 为可选
        # （在 Step 5.3 中已确认前端使用 score 字段，不直接使用 age_fit_score）
    
    def test_process_search_results_returns_age_fit_score(retrieval_service):
        """验证 _process_search_results 返回字典包含 age_fit_score 字段"""
        # 模拟节点
        node = NodeWithScore(
            node=TextNode(
                node_id="test_001",
                text="测试内容",
                metadata={"content": "测试内容", "file_name": "测试.pdf", "file_hash": "abc", "target_age_min": 3, "target_age_max": 4, "topics": [], "brain_regions": []}
            ),
            score=0.85
        )
        
        # 调用 _process_search_results
        results = retrieval_service._process_search_results(
            [node], original_query="测试", expanded_query="测试", bm25_nodes=[]
        )
        
        assert len(results) > 0
        assert "age_fit_score" in results[0]
        assert results[0]["age_fit_score"] is None  # 搜索页不计算年龄适配度
    ```

- [ ] **Step 7: 集成验证**
  - [ ] **7.1 运行诊断测试**：
    ```bash
    cd backend
    uv run pytest tests/diagnose_rag_comprehensive_v2.py -v -k "test_1_retrieval_quality or test_2_score_distribution or test_3_age_fit_granularity"
    ```
    - [ ] 确认测试 1（检索质量指标）中 Precision@5 未退化（允许暂时不提升，但不应下降）
    - [ ] 确认测试 2（分数分布）中 BM25 与向量分数差异未恶化
    - [ ] 确认测试 3（年龄适配度）仍输出 ≥3 个不同值（细粒度化在 A-2 中完成）
  
  - [ ] **7.2 验证 `relevance_score` 与 Cross-Encoder 分数相关性**：
    ```python
    # 在诊断测试中添加验证逻辑
    import numpy as np
    from scipy.stats import pearsonr
    
    # 收集 Cross-Encoder 原始分数和 relevance_score
    cross_encoder_scores = []
    relevance_scores = []
    
    for item in results:
        cross_encoder_scores.append(item._cross_encoder_score)  # 需要从节点元数据获取
        relevance_scores.append(item.relevance_score)
    
    correlation, p_value = pearsonr(cross_encoder_scores, relevance_scores)
    assert correlation >= 0.9, f"relevance_score 与 Cross-Encoder 分数相关性不足：r={correlation:.3f}"
    ```
  
  - [ ] **7.3 验证前端不崩溃**：
    ```bash
    # 启动后端
    cd backend && uv run start
    
    # 启动前端
    cd frontend && npm run dev
    
    # 手动测试：
    # 1. 访问 /knowledge 路由
    # 2. 执行搜索（如"感统训练"）
    # 3. 确认搜索结果正常展示
    # 4. 点击"查看详情"，确认弹窗正常展示
    # 5. 检查浏览器控制台无 JavaScript 错误
    ```
  
  - [ ] **7.4 验证 Agent 评分不受影响**：
    ```bash
    # 运行 Agent 相关测试
    cd backend
    uv run pytest tests/core/nodes/test_scoring.py -v
    ```
    - [ ] 确认 `scoring.py` 中 `avg_relevance` 计算正常
    - [ ] 确认 `high_relevance_docs` 筛选正常
    - [ ] 确认评分结果与变更前一致（或更合理，因为现在 `relevance_score` 是纯检索相关性）
  
  - [ ] **7.5 验证 RAG 测试不受影响**：
    ```bash
    # 运行 RAG 测试相关用例
    cd backend
    uv run pytest tests/test_rag_hybrid.py tests/test_rag_optimizations.py -v
    ```
    - [ ] 确认测试通过率不下降
    - [ ] 确认 `rag_test_manager.py` 中 `score=item.relevance_score` 仍正确记录分数

## ✅ 验收标准

| 验收项 | 标准 | 验证方法 |
|--------|------|----------|
| 字段分离 | `KnowledgeItem` 包含 `relevance_score` 和 `age_fit_score` 两个独立字段 | 单元测试验证 |
| 语义清晰 | `relevance_score` 仅来自 Cross-Encoder，不混合年龄适配度 | 代码审查 + 单元测试 |
| 向后兼容 | `age_fit_score` 默认值 0.0，旧版 API 响应不崩溃 | 集成测试 |
| 排序正确 | 结果按 `relevance_score` 排序，不受年龄适配度影响 | 单元测试 |

## 📁 涉及文件

| 文件 | 操作 | 说明 |
|------|------|------|
| `src/model/schemas.py` | 修改 | `KnowledgeItem` 新增 `age_fit_score` 字段 |
| `src/service/retrieval_service.py` | 修改 | `_convert_to_knowledge_items` 移除分数混合逻辑，`_process_search_results` 新增 `age_fit_score` 字段 |
| `src/core/nodes/scoring.py` | 检查 | 确认 `relevance_score` 使用无需修改（第 125、278 行） |
| `src/service/rag_test_manager.py` | 检查 | 确认 `relevance_score` 使用无需修改（第 874 行） |
| `frontend/src/api/knowledge/types.ts` | 可选修改 | 如需在搜索结果中展示年龄适配度，新增 `age_fit_score?: number` |
| `frontend/src/components/knowledge/SearchResultList.tsx` | 可选修改 | 如需展示年龄适配度，新增 Tag 组件 |
| `tests/test_score_separation.py` | 新增 | 分数分离单元测试（4 个测试用例） |

## ⚠️ 注意事项

1. **不要在此步骤中修改 `age_fit_score` 的计算逻辑**，细粒度化在 A-2 任务中完成
2. **不要修改 Cross-Encoder 的输出**，`relevance_score` 应直接取自重排序后的分数
3. **保持向后兼容**：`age_fit_score` 必须设置默认值 0.0，确保旧版前端不崩溃
4. **配置项预留**：在 `src/config/settings.py` 中预留 `rag_score_method` 配置项（`"separated"` / `"legacy"`），但本步骤不实现回滚逻辑

---

**返回索引：** [01-phase-a-00-overview.md](./01-phase-a-00-overview.md)
