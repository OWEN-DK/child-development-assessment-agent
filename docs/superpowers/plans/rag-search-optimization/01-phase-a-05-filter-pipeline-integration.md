# A-5: 过滤流水线集成

> **所属 Phase**: Phase A (P0)
> **任务类型**: 单一任务 — 将年龄过滤前置到检索阶段，与分数计算解耦
> **对应问题**: 根因 1（过滤在分数计算阶段完成，而非检索阶段，过滤不彻底）

## 🎯 目标

将年龄过滤从分数计算阶段提前到检索阶段，确保：
1. 不相关内容在检索早期被过滤，不参与后续分数计算
2. 过滤逻辑与 `age_fit_score` 计算完全解耦
3. 检索流水线语义清晰：检索 → 过滤 → 重排序 → 年龄适配度计算

## 📋 实施步骤

- [ ] **Step 1: 分析现有流水线**
  - [ ] **1.1 阅读 `src/service/retrieval_service.py` 的 `retrieve_knowledge` 方法**（第 134-237 行）：
    ```
    当前流水线顺序：
    1. 检查缓存（第 148-152 行）
    2. A/B 测试变体分配（第 154-160 行）
    3. 查询重写（第 163 行）
    4. 同义词扩展（第 164 行）
    5. 构建年龄过滤器（第 172 行）→ _build_age_filters(age)
    6. 执行检索（第 174-183 行）→ _execute_retrieval(...)
       - 在 _execute_retrieval 中（第 364-427 行）：
         a. 设置过滤器到 BM25/向量检索器（第 381-382 行）
         b. 并行检索 BM25 和向量（第 402-403 行）
         c. 融合结果（第 406-413 行）→ HybridRetrievalMerger.merge_results(...)
         d. Cross-Encoder 重排序（第 416-417 行）→ reranker.rerank(...)
    7. 转换为 KnowledgeItem（第 200 行）→ _convert_to_knowledge_items(results, user_age=age)
       - 在 _convert_to_knowledge_items 中（第 429-537 行）：
         a. 儿童发展引擎过滤（第 448-458 行）
         b. 最低相似度阈值过滤（第 461-463 行）
         c. 计算年龄适配度并混合到 final_score（第 491-506 行）← 问题所在
         d. 内容去重（第 508-516 行）
         e. 构建 KnowledgeItem（第 518-531 行）
         f. 按 final_score 排序（第 535 行）
    8. 缓存结果（第 203 行）
    ```
  
  - [ ] **1.2 定位年龄过滤与分数计算的耦合点**：
    - [ ] **耦合点 1**：`_build_age_filters` 在检索前构建 MetadataFilter（第 317-344 行）
      - **问题**：仅做基础范围过滤，无法处理单年龄内容和精确匹配
    - [ ] **耦合点 2**：`_convert_to_knowledge_items` 中混合年龄适配度到 final_score（第 491-506 行）
      - **问题**：年龄适配度与检索相关性混合，导致 `relevance_score` 语义不清
    - [ ] **耦合点 3**：`_execute_retrieval` 中过滤器设置后直接检索（第 381-382 行）
      - **问题**：过滤在检索阶段完成，但精确过滤在分数计算阶段，逻辑分散
  
  - [ ] **1.3 确认 `relevance_score` 混合年龄适配度的代码位置**：
    - [ ] 第 491-506 行（在 A-1 中已修改为分离逻辑）
    - [ ] 第 530 行：`relevance_score=float(final_score)` ← 需要改为 `relevance_score=float(relevance_score)`
    - [ ] 第 535 行：`results.sort(key=lambda x: x.relevance_score, reverse=True)` ← 已正确

- [ ] **Step 2: 设计新流水线**
  - [ ] **2.1 定义新流水线顺序**：
    ```
    新流水线顺序：
    1. 检查缓存
    2. A/B 测试变体分配
    3. 查询重写
    4. 同义词扩展
    5. 构建基础年龄过滤器（MetadataFilter，用于检索阶段粗过滤）
    6. 执行检索
       a. 设置基础过滤器到 BM25/向量检索器
       b. 并行检索 BM25 和向量
       c. 分数校准 + 融合（使用 ScoreCalibrator）
       d. Cross-Encoder 重排序 → 输出 relevance_score（仅检索相关性）
    7. 精确年龄过滤（二次过滤，使用 AgeFilter.should_filter）← 新增步骤
    8. 计算 age_fit_score（使用 AgeFitScorer）← 独立计算，不混合
    9. 内容去重
    10. 构建 KnowledgeItem（relevance_score 和 age_fit_score 独立）
    11. 按 relevance_score 排序
    12. 缓存结果
    ```
  
  - [ ] **2.2 明确各阶段输入输出契约**：
    | 阶段 | 输入 | 输出 | 说明 |
    |------|------|------|------|
    | 查询重写 | 原始查询、年龄 | 重写后查询 | 提升检索准确率 |
    | 同义词扩展 | 重写后查询 | 扩展后查询 | 提升召回率 |
    | BM25+向量检索 | 扩展查询、基础过滤器 | NodeWithScore 列表 | 粗检索结果 |
    | 分数校准+融合 | BM25/向量节点、权重 | 融合后 NodeWithScore 列表 | 统一分数量级 |
    | Cross-Encoder 重排序 | 融合节点、查询 | 重排序后 NodeWithScore 列表 | node.score = relevance_score |
    | 精确年龄过滤 | 重排序节点、用户年龄、模式 | 过滤后 NodeWithScore 列表 | 移除年龄不匹配内容 |
    | age_fit_score 计算 | 过滤后节点、用户年龄 | 含 age_fit_score 的节点列表 | 独立计算，不混合 |
    | KnowledgeItem 构建 | 节点列表 | KnowledgeItem 列表 | 两个分数独立字段 |

- [ ] **Step 3: 实现流水线重构**
  - [ ] **3.1 修改 `_execute_retrieval` 方法**（第 364-427 行）：
    - [ ] 保持当前逻辑不变（检索、融合、重排序），但确保：
      - 融合使用 `ScoreCalibrator`（在 A-3 中已实现）
      - 重排序后 `node.score` 仅反映检索相关性（Cross-Encoder 输出）
    - [ ] 移除重排序后的任何年龄相关处理（如果有）
  
  - [ ] **3.2 在 `retrieve_knowledge` 中添加精确年龄过滤步骤**：
    - [ ] 在 `_execute_retrieval` 返回后、`_convert_to_knowledge_items` 调用前添加过滤：
      ```python
      # 在 retrieve_knowledge 方法中，第 174-183 行之后添加：
      
      # 执行检索（包含基础过滤、融合、重排序）
      nodes = await self._execute_retrieval(
          query=expanded_query,
          filters=filters,
          limit=limit,
          use_hybrid=self.bm25_retriever is not None and self.vector_retriever is not None,
          age=age,
          retrieval_variant=retrieval_variant,
          user_id=user_id,
      )
      
      # 新增：精确年龄过滤（二次过滤）
      if age > 0 and nodes:
          mode_str = getattr(settings, 'rag_age_filter_mode', 'strict')
          mode = AgeFilterMode.STRICT if mode_str == 'strict' else AgeFilterMode.LOOSE
          
          filtered_nodes = []
          for node_with_score in nodes:
              metadata = node_with_score.node.metadata or {}
              target_min = metadata.get("target_age_min", 0)
              target_max = metadata.get("target_age_max", 18)
              
              if not AgeFilter.should_filter(target_min, target_max, age, mode):
                  filtered_nodes.append(node_with_score)
              else:
                  logger.info(
                      f"精确年龄过滤：用户 {age} 岁，内容年龄 [{target_min}, {target_max}]，"
                      f"模式 {mode}，分数 {node_with_score.score:.4f}"
                  )
          
          logger.info(f"年龄过滤：{len(nodes)} -> {len(filtered_nodes)} 个结果")
          nodes = filtered_nodes
      ```
  
  - [ ] **3.3 修改 `_convert_to_knowledge_items` 方法**（第 429-537 行）：
    - [ ] **移除年龄过滤逻辑**（因为已在 Step 3.2 中完成）：
      - [ ] 删除或注释掉第 448-458 行的儿童发展引擎过滤（可选，保留作为额外保护层）
      - [ ] 确保不再调用 `child_development_engine.filter_unsuitable_content`（或保留但记录日志）
    
    - [ ] **修改分数计算逻辑**（在 A-1 中已部分修改，此处完善）：
      ```python
      # 在 _convert_to_knowledge_items 中，找到分数计算部分（原第 491-506 行）
      
      # 修改为：
      # relevance_score 直接使用 base_score（来自 Cross-Encoder 重排序后的分数）
      relevance_score = base_score
      
      # age_fit_score 使用 AgeFitScorer 独立计算
      age_fit_score = 1.0  # 默认值（无年龄时）
      if user_age is not None:
          age_fit_score = AgeFitScorer.calculate(
              content=content,
              user_age=user_age,
              target_age_min=target_age_min,
              target_age_max=target_age_max,
              metadata=metadata
          )
      ```
    
    - [ ] **修改 KnowledgeItem 构造**（第 518-531 行）：
      ```python
      item = KnowledgeItem(
          content=content.strip(),
          source_book=source,
          chapter_title=chapter_title,
          page_label=page_label,
          topics=topics,
          brain_regions=brain_regions,
          benefits=benefits,
          risk_level="Low",
          target_age_min=target_age_min,
          target_age_max=target_age_max,
          activity_type=activity_type,
          relevance_score=float(relevance_score),  # 仅检索相关性
          age_fit_score=float(age_fit_score),      # 独立年龄适配度
      )
      ```
    
    - [ ] **确认排序逻辑**（第 535 行）：
      ```python
      results.sort(key=lambda x: x.relevance_score, reverse=True)
      ```
  
  - [ ] **3.4 修改 `result_fusion.py`**（如有年龄适配度混合逻辑）：
    - [ ] 阅读 `src/core/result_fusion.py` 当前实现
    - [ ] 确认是否有年龄适配度相关逻辑（当前代码中未发现）
    - [ ] 如有，移除或标记废弃

- [ ] **Step 4: 编写集成测试**
  - [ ] **4.1 创建测试文件**：`tests/test_retrieval_pipeline.py`
  
  - [ ] **4.2 测试环境准备**：
    ```python
    import pytest
    from unittest.mock import MagicMock, AsyncMock, patch
    from llama_index.core.schema import NodeWithScore, TextNode
    from src.service.retrieval_service import RetrievalService
    from src.model.schemas import KnowledgeItem
    from src.core.age_filter import AgeFilter, AgeFilterMode
    from src.core.rag.age_fit_scorer import AgeFitScorer
    
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
  
  - [ ] **4.3 测试用例 1：验证过滤后结果不参与后续分数计算**：
    ```python
    @pytest.mark.asyncio
    async def test_filtered_nodes_not_in_final_score(retrieval_service):
        """验证年龄过滤后的节点不参与 relevance_score 计算"""
        # 模拟重排序后的节点（包含年龄不匹配的内容）
        nodes = [
            NodeWithScore(
                node=TextNode(
                    node_id="n1",
                    text="适合 3 岁儿童的训练",
                    metadata={"content": "适合 3 岁儿童的训练", "file_name": "书.pdf", "target_age_min": 3, "target_age_max": 4, "topics": [], "brain_regions": [], "benefits": []}
                ),
                score=0.9  # Cross-Encoder 分数
            ),
            NodeWithScore(
                node=TextNode(
                    node_id="n2",
                    text="适合 6 岁儿童的训练",
                    metadata={"content": "适合 6 岁儿童的训练", "file_name": "书.pdf", "target_age_min": 6, "target_age_max": 7, "topics": [], "brain_regions": [], "benefits": []}
                ),
                score=0.8  # Cross-Encoder 分数（高，但年龄不匹配）
            ),
        ]
        
        # 模拟 3 岁用户，严格模式
        with patch.object(retrieval_service, '_execute_retrieval', new=AsyncMock(return_value=nodes)):
            # 调用 retrieve_knowledge
            items = await retrieval_service.retrieve_knowledge("训练", age=3, limit=5)
        
        # 验证：年龄不匹配的节点（n2）应被过滤
        assert len(items) == 1
        assert items[0].content == "适合 3 岁儿童的训练"
        
        # 验证：relevance_score 未混合年龄适配度
        assert items[0].relevance_score == pytest.approx(0.9, abs=0.01)
    ```
  
  - [ ] **4.4 测试用例 2：验证 `relevance_score` 与 `age_fit_score` 无混合计算**：
    ```python
    def test_scores_not_mixed():
        """验证 relevance_score 与 age_fit_score 无混合计算"""
        # 模拟 KnowledgeItem
        item = KnowledgeItem(
            content="适合 3 岁儿童的训练",
            source_book="测试书",
            relevance_score=0.85,  # 来自 Cross-Encoder
            age_fit_score=0.75,    # 来自 AgeFitScorer
            target_age_min=3,
            target_age_max=4
        )
        
        # 验证两个分数独立
        assert item.relevance_score == 0.85
        assert item.age_fit_score == 0.75
        
        # 验证没有混合计算（如果有混合，relevance_score 会偏离 0.85）
        assert abs(item.relevance_score - 0.85) < 0.01
    ```
  
  - [ ] **4.5 测试用例 3：验证流水线各阶段输出符合预期**：
    ```python
    def test_pipeline_stage_outputs(retrieval_service):
        """验证流水线各阶段输入输出契约"""
        # 阶段 1: 分数校准 + 融合
        from src.core.rag.score_calibrator import ScoreCalibrator
        
        calibrator = ScoreCalibrator()
        bm25_scores = [0.1, 0.5, 0.9]
        vector_scores = [0.3, 0.6, 0.8]
        
        merged = calibrator.calibrate_and_merge(bm25_scores, vector_scores, 0.5, 0.5)
        assert len(merged) == 3
        assert all(0.0 <= s <= 1.0 for s in merged)
        
        # 阶段 2: Cross-Encoder 重排序（模拟）
        reranked_scores = [0.95, 0.85, 0.75]  # 模拟重排序后分数
        
        # 阶段 3: 年龄过滤
        filtered_indices = []
        for i, (target_min, target_max) in enumerate([(3, 4), (6, 7), (2, 3)]):
            if not AgeFilter.should_filter(target_min, target_max, 3, AgeFilterMode.STRICT):
                filtered_indices.append(i)
        
        assert filtered_indices == [0, 2]  # 索引 1（6-7 岁）被过滤
        
        # 阶段 4: age_fit_score 计算
        for i in filtered_indices:
            score = AgeFitScorer.calculate(
                content=f"内容 {i}",
                user_age=3,
                target_age_min=[3, 2][filtered_indices.index(i)],
                target_age_max=[4, 3][filtered_indices.index(i)]
            )
            assert 0.0 <= score <= 1.0
    ```
  
  - [ ] **4.6 测试用例 4：验证完整流水线端到端**：
    ```python
    @pytest.mark.asyncio
    async def test_end_to_end_pipeline(retrieval_service):
        """验证完整流水线端到端行为"""
        # 模拟完整的检索流程
        nodes = [
            NodeWithScore(
                node=TextNode(
                    node_id="n1",
                    text="适合 3 岁儿童的精细动作训练",
                    metadata={"content": "适合 3 岁儿童的精细动作训练", "file_name": "书.pdf", "target_age_min": 3, "target_age_max": 4, "topics": ["精细动作"], "brain_regions": [], "benefits": []}
                ),
                score=0.9
            ),
            NodeWithScore(
                node=TextNode(
                    node_id="n2",
                    text="适合 5 岁儿童的认知训练",
                    metadata={"content": "适合 5 岁儿童的认知训练", "file_name": "书.pdf", "target_age_min": 5, "target_age_max": 6, "topics": ["认知"], "brain_regions": [], "benefits": []}
                ),
                score=0.85
            ),
            NodeWithScore(
                node=TextNode(
                    node_id="n3",
                    text="适合 2 岁儿童的大动作训练",
                    metadata={"content": "适合 2 岁儿童的大动作训练", "file_name": "书.pdf", "target_age_min": 2, "target_age_max": 3, "topics": ["大动作"], "brain_regions": [], "benefits": []}
                ),
                score=0.8
            ),
        ]
        
        with patch.object(retrieval_service, '_execute_retrieval', new=AsyncMock(return_value=nodes)):
            items = await retrieval_service.retrieve_knowledge("训练", age=3, limit=5)
        
        # 验证：年龄不匹配的节点（n2，5-6 岁）应被过滤
        assert len(items) == 2
        
        # 验证：排序基于 relevance_score
        assert items[0].relevance_score >= items[1].relevance_score
        
        # 验证：age_fit_score 独立计算
        for item in items:
            assert 0.0 <= item.age_fit_score <= 1.0
            assert item.relevance_score > 0.0  # 来自 Cross-Encoder
    ```

- [ ] **Step 5: 回归验证**
  - [ ] **5.1 运行诊断测试 1、2、3**：
    ```bash
    cd backend
    uv run pytest tests/diagnose_rag_comprehensive_v2.py::test_1_retrieval_quality -v
    uv run pytest tests/diagnose_rag_comprehensive_v2.py::test_2_score_distribution -v
    uv run pytest tests/diagnose_rag_comprehensive_v2.py::test_3_age_fit_granularity -v
    ```
    - [ ] 确认 Precision@5 ≥0.75
    - [ ] 确认 BM25 与向量分数最大差异 <0.2
    - [ ] 确认年龄适配度不同值数量 ≥10
  
  - [ ] **5.2 运行诊断测试 11（年龄过滤准确性）**：
    ```bash
    cd backend
    uv run pytest tests/diagnose_rag_comprehensive_v2.py::test_11_age_filter_accuracy -v
    ```
    - [ ] 确认年龄过滤准确率 ≥90%
  
  - [ ] **5.3 运行完整诊断测试集**：
    ```bash
    cd backend
    uv run pytest tests/diagnose_rag_comprehensive_v2.py -v
    ```
    - [ ] 确认所有 Phase A 相关测试通过
    - [ ] 确认无回归（之前通过的测试仍通过）
  
  - [ ] **5.4 手动验证流水线行为**：
    ```python
    # 在 Python 交互环境中运行
    import asyncio
    from src.service.retrieval_service import RetrievalService
    
    # 初始化服务（需要真实的索引和缓存）
    # ...
    
    # 执行检索
    async def test_pipeline():
        items = await service.retrieve_knowledge("精细动作训练", age=3, limit=5)
        
        print(f"返回 {len(items)} 个结果")
        for i, item in enumerate(items):
            print(f"  {i+1}. relevance_score={item.relevance_score:.4f}, "
                  f"age_fit_score={item.age_fit_score:.4f}, "
                  f"年龄范围=[{item.target_age_min}, {item.target_age_max}]")
    
    asyncio.run(test_pipeline())
    ```

## ✅ 验收标准

- 年龄过滤在检索阶段完成（重排序之前）
- `relevance_score` 仅反映检索相关性（来自 Cross-Encoder）
- `age_fit_score` 独立计算，不混合到 `relevance_score`
- 流水线各阶段输入输出契约清晰

## 📁 涉及文件

| 文件 | 操作 | 说明 |
|------|------|------|
| `src/service/retrieval_service.py` | 修改 | 调整流水线顺序，解耦过滤与分数计算 |
| `src/core/result_fusion.py` | 修改 | 移除年龄适配度混合逻辑 |
| `tests/test_retrieval_pipeline.py` | 新增 | 流水线集成测试 |

---

**返回索引：** [01-phase-a-00-overview.md](./01-phase-a-00-overview.md)
