# A-3: BM25/向量分数校准统一

> **所属 Phase**: Phase A (P0)
> **任务类型**: 单一任务 — 统一分数校准策略
> **对应问题**: 测试 2 失败（BM25 与向量分数最大差异 0.804，目标 <0.2）

## 🎯 目标

确保 BM25 和向量检索的分数在同一量级可比，确保：
1. BM25 与向量分数最大差异 <0.2
2. 校准策略数学性质一致，融合后排序不失真
3. Precision@5 ≥0.75

## 📋 实施步骤

- [ ] **Step 1: 分析现有校准逻辑**
  - [ ] 阅读 `backend/src/core/hybrid_retrieval.py` 中 `_calibrate_bm25_score` 方法（第 12-17 行）
  - [ ] 阅读 `_calibrate_vector_score` 方法（第 84-115 行）
  - [ ] 阅读 `_normalize_all_scores` 方法（第 20-82 行）
  - [ ] 确认当前问题：
    - BM25 使用 Sigmoid 校准 (`1 / (1 + exp(-score / scale_factor))`)
    - 向量分数使用分段校准（高分保持、中等压缩、低分显著压缩）
    - 两种校准策略数学性质不同，导致校准后分数仍不在同一量级
    - `_normalize_all_scores` 使用多种策略（保持、线性归一化），但逻辑复杂且可能失真

- [ ] **Step 2: 设计统一校准策略**
  - [ ] **核心思路**：使用 Min-Max 归一化 + Sigmoid 校准的组合策略
    ```
    步骤 1: 对 BM25 和向量分数分别进行 Min-Max 归一化到 [0, 1]
    步骤 2: 使用相同的 Sigmoid 函数对归一化后的分数进行校准
    步骤 3: 融合时使用统一权重
    ```
  - [ ] **Min-Max 归一化**（对各自检索结果的内部相对分数进行归一化）：
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
  - [ ] **统一 Sigmoid 校准**（对归一化后的分数进行平滑压缩）：
    ```python
    def unified_sigmoid_calibrate(score: float, midpoint: float = 0.5, steepness: float = 10.0) -> float:
        """
        统一 Sigmoid 校准函数
        
        Args:
            score: 归一化后的分数 [0, 1]
            midpoint: Sigmoid 中点（分数为 0.5 时输出 0.5）
            steepness: 陡峭程度（越大，区分度越高）
        
        Returns:
            校准后的分数 [0, 1]
        """
        return 1 / (1 + math.exp(-steepness * (score - midpoint)))
    ```
  - [ ] **为什么选择此策略**：
    - Min-Max 归一化确保 BM25 和向量分数都在 [0, 1] 范围内，消除量级差异
    - 统一 Sigmoid 校准对两者使用相同的数学函数，确保校准后分数分布一致
    - Sigmoid 的中点和陡峭程度可配置，便于后续调优

- [ ] **Step 3: 实现 `ScoreCalibrator` 类**
  - [ ] 创建新文件 `backend/src/core/rag/score_calibrator.py`
  - [ ] 实现 `ScoreCalibrator` 类：
    ```python
    import math
    from typing import List, Tuple
    from backend.src.utils.logger import logger
    
    class ScoreCalibrator:
        """BM25/向量分数校准器"""
        
        def __init__(
            self,
            sigmoid_midpoint: float = 0.5,
            sigmoid_steepness: float = 10.0,
            min_samples: int = 3
        ):
            """
            Args:
                sigmoid_midpoint: Sigmoid 中点
                sigmoid_steepness: Sigmoid 陡峭程度
                min_samples: Min-Max 归一化最小样本数阈值
            """
            self.sigmoid_midpoint = sigmoid_midpoint
            self.sigmoid_steepness = sigmoid_steepness
            self.min_samples = min_samples
        
        def calibrate_and_merge(
            self,
            bm25_scores: List[float],
            vector_scores: List[float],
            bm25_weight: float = 0.5,
            vector_weight: float = 0.5
        ) -> List[float]:
            """
            校准并融合 BM25 和向量分数
            
            Args:
                bm25_scores: BM25 原始分数列表
                vector_scores: 向量原始分数列表
                bm25_weight: BM25 权重
                vector_weight: 向量权重
            
            Returns:
                融合后的分数列表（与输入顺序对应）
            """
            # Step 1: 分别归一化
            bm25_normalized = self._min_max_normalize(bm25_scores)
            vector_normalized = self._min_max_normalize(vector_scores)
            
            # Step 2: 统一 Sigmoid 校准
            bm25_calibrated = [self._sigmoid(s) for s in bm25_normalized]
            vector_calibrated = [self._sigmoid(s) for s in vector_normalized]
            
            # Step 3: 加权融合
            merged = []
            for b, v in zip(bm25_calibrated, vector_calibrated):
                merged.append(b * bm25_weight + v * vector_weight)
            
            return merged
        
        def _min_max_normalize(self, scores: List[float], min_samples: int = None) -> List[float]:
            """
            Min-Max 归一化到 [0, 1]
            
            Args:
                scores: 原始分数列表
                min_samples: 最小样本数阈值，低于此值时不进行归一化（默认使用构造函数的 min_samples）
            
            Returns:
                归一化后的分数列表
            """
            if min_samples is None:
                min_samples = self.min_samples
            
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
        
        def _sigmoid(self, score: float) -> float:
            """统一 Sigmoid 校准"""
            return 1 / (1 + math.exp(-self.sigmoid_steepness * (score - self.sigmoid_midpoint)))
    ```
  - [ ] 确保所有方法有中文注释
  - [ ] 添加配置项支持（`sigmoid_midpoint` 和 `sigmoid_steepness` 可从 settings 读取）

- [ ] **Step 4: 修改 `HybridRetrievalMerger` 集成校准器**
  - [ ] **4.1 修改导入语句**：
    - [ ] 在 `backend/src/core/hybrid_retrieval.py` 顶部（第 1-6 行之后）添加导入：
      ```python
      from backend.src.core.rag.score_calibrator import ScoreCalibrator
      from backend.src.config import settings
      ```
  
  - [ ] **4.2 修改 `merge_results` 方法**（第 142-213 行）：
    - [ ] **定位当前融合流程**：
      ```
      当前流程：
      1. 校准 BM25 分数（_calibrate_bm25_score）→ 第 162-165 行
      2. 应用 BM25 权重 → 第 170-176 行
      3. 应用向量权重 → 第 179-193 行
      4. 全局归一化（_normalize_all_scores）→ 第 196-199 行
      5. 排序并截断 → 第 204-206 行
      ```
    
    - [ ] **替换为新的融合流程**：
      ```python
      @staticmethod
      def merge_results(
          bm25_nodes: List[NodeWithScore],
          vector_nodes: List[NodeWithScore],
          bm25_weight: float = 0.5,
          vector_weight: float = 0.5,
          merge_mode: str = "OR",
          limit: int = 10,
          normalize_scores: bool = True,
      ) -> List[NodeWithScore]:
          """
          使用 ScoreCalibrator 统一校准并融合 BM25 和向量分数
          """
          if not bm25_nodes and not vector_nodes:
              logger.debug("merge_results: 无 BM25 和向量结果，返回空列表")
              return []

          logger.info(
              f"merge_results: 开始融合，BM25={len(bm25_nodes)}个，"
              f"向量={len(vector_nodes)}个，权重=BM25:{bm25_weight}/向量:{vector_weight}"
          )

          # Step 1: 提取原始分数
          bm25_scores = [node.score or 0.0 for node in bm25_nodes]
          vector_scores = [node.score or 0.0 for node in vector_nodes]
          
          logger.debug(
              f"merge_results: BM25 原始分数范围=[{min(bm25_scores):.4f}, {max(bm25_scores):.4f}], "
              f"向量原始分数范围=[{min(vector_scores):.4f}, {max(vector_scores):.4f}]"
          )

          # Step 2: 使用 ScoreCalibrator 校准并融合
          calibrator = ScoreCalibrator(
              sigmoid_midpoint=getattr(settings, 'rag_score_sigmoid_midpoint', 0.5),
              sigmoid_sigmoid_steepness=getattr(settings, 'rag_score_sigmoid_steepness', 10.0)
          )
          
          # 校准后的分数（归一化到 [0,1] 并 Sigmoid 校准）
          bm25_calibrated = calibrator.calibrate_scores(bm25_scores)
          vector_calibrated = calibrator.calibrate_scores(vector_scores)
          
          logger.debug(
              f"merge_results: BM25 校准后范围=[{min(bm25_calibrated):.4f}, {max(bm25_calibrated):.4f}], "
              f"向量校准后范围=[{min(vector_calibrated):.4f}, {max(vector_calibrated):.4f}]"
          )

          # Step 3: 构建节点映射并应用校准后分数
          node_map: Dict[str, NodeWithScore] = {}

          # 处理 BM25 节点
          for i, node in enumerate(bm25_nodes):
              node_id = node.node.node_id
              node.score = bm25_calibrated[i] * bm25_weight
              node_map[node_id] = node
              logger.debug(
                  f"merge_results: BM25 节点 {node_id}, "
                  f"原始={bm25_scores[i]:.4f}, 校准={bm25_calibrated[i]:.4f}, "
                  f"加权={node.score:.4f}"
              )

          # 处理向量节点
          for i, node in enumerate(vector_nodes):
              node_id = node.node.node_id
              vector_score = vector_calibrated[i] * vector_weight

              if node_id in node_map:
                  # 节点同时出现在 BM25 和向量结果中，融合分数
                  existing_node = node_map[node_id]
                  old_score = existing_node.score or 0.0
                  existing_node.score = old_score + vector_score
                  logger.debug(
                      f"merge_results: 融合节点 {node_id}, "
                      f"BM25={old_score:.4f}, 向量={vector_score:.4f}, "
                      f"融合={existing_node.score:.4f}"
                  )
              else:
                  if merge_mode == "OR":
                      node.score = vector_score
                      node_map[node_id] = node
                      logger.debug(
                          f"merge_results: 纯向量节点 {node_id}, 分数={node.score:.4f}"
                      )

          # Step 4: 排序并截断
          all_nodes = list(node_map.values())
          merged_nodes = sorted(
              all_nodes, key=lambda x: x.score or 0.0, reverse=True
          )[:limit]

          logger.info(
              f"merge_results: 融合完成，BM25={len(bm25_nodes)}个，"
              f"向量={len(vector_nodes)}个，最终={len(merged_nodes)}个结果"
          )
          if merged_nodes:
              logger.info(
                  f"merge_results: Top 3 分数："
                  f"{[f'{n.score:.4f}' for n in merged_nodes[:3]]}"
              )
          return merged_nodes
      ```
    
    - [ ] **关键变更说明**：
      - **删除**：`_calibrate_bm25_score` 调用（原第 162-165 行）
      - **删除**：`_normalize_all_scores` 调用（原第 196-199 行）
      - **新增**：`ScoreCalibrator` 实例化和校准逻辑
      - **保留**：节点映射逻辑（`node_map`）、融合逻辑（OR 模式）、排序截断逻辑

  - [ ] **4.3 保留 `merge_for_search` 方法不变**：
    - [ ] 确认 `merge_for_search` 方法（第 216-298 行）用于前端搜索页，不修改
    - [ ] 原因：搜索页使用不同的分数展示逻辑（`display_score` 映射），与 Agent 检索的 `merge_results` 独立

  - [ ] **4.4 标记废弃旧方法**（而非直接删除）：
    - [ ] 对 `_calibrate_bm25_score` 方法（第 12-17 行）添加废弃标记：
      ```python
      @staticmethod
      def _calibrate_bm25_score(score: float, corpus_quantile: float = None) -> float:
          """
          [已废弃] 使用 Sigmoid 校准 BM25 分数。
          已被 ScoreCalibrator 替代，保留仅用于 rag_score_method=legacy 回滚。
          """
          # 原有逻辑保持不变
          ...
      ```
    - [ ] 对 `_calibrate_vector_score` 方法（第 84-115 行）添加相同废弃标记
    - [ ] 对 `_normalize_all_scores` 方法（第 20-82 行）添加相同废弃标记

  - [ ] **4.5 完善 `ScoreCalibrator` 类**：
    - [ ] 补充 `calibrate_scores` 方法（在 Step 3 的类定义中已有 `_min_max_normalize` 和 `_sigmoid`，需要添加公共方法）：
      ```python
      def calibrate_scores(self, scores: List[float]) -> List[float]:
          """
          对分数列表进行 Min-Max 归一化 + Sigmoid 校准
          
          Args:
              scores: 原始分数列表
          
          Returns:
              校准后的分数列表 [0, 1]
          """
          if not scores:
              return []
          
          # Step 1: Min-Max 归一化
          normalized = self._min_max_normalize(scores)
          
          # Step 2: Sigmoid 校准
          calibrated = [self._sigmoid(s) for s in normalized]
          
          return calibrated
      ```
    - [ ] 添加批量校准方法（用于诊断测试）：
      ```python
      def calibrate_and_compare(
          self,
          bm25_scores: List[float],
          vector_scores: List[float]
      ) -> Dict[str, float]:
          """
          校准并比较 BM25 与向量分数的差异
          
          Returns:
              包含最大差异、平均差异等统计信息的字典
          """
          bm25_calibrated = self.calibrate_scores(bm25_scores)
          vector_calibrated = self.calibrate_scores(vector_scores)
          
          # 计算差异（取相同索引位置，假设已按相关性排序）
          min_len = min(len(bm25_calibrated), len(vector_calibrated))
          if min_len == 0:
              return {"max_diff": 0.0, "avg_diff": 0.0}
          
          diffs = [
              abs(bm25_calibrated[i] - vector_calibrated[i])
              for i in range(min_len)
          ]
          
          return {
              "max_diff": max(diffs),
              "avg_diff": sum(diffs) / len(diffs),
              "bm25_range": (min(bm25_calibrated), max(bm25_calibrated)),
              "vector_range": (min(vector_calibrated), max(vector_calibrated)),
          }
      ```

- [ ] **Step 5: 编写单元测试**
  - [ ] **5.1 创建测试文件**：`backend/tests/test_score_calibrator.py`
  
  - [ ] **5.2 测试环境准备**：
    ```python
    import pytest
    import math
    from backend.src.core.rag.score_calibrator import ScoreCalibrator
    
    # 诊断测试中的实际分数数据（模拟）
    DIAGNOSTIC_BM25_SCORES = [0.106, 0.234, 0.456, 0.678, 0.948]
    DIAGNOSTIC_VECTOR_SCORES = [0.500, 0.620, 0.710, 0.830, 0.950]
    
    @pytest.fixture
    def calibrator():
        return ScoreCalibrator(
            sigmoid_midpoint=0.5,
            sigmoid_sigmoid_steepness=10.0
        )
    ```
  
  - [ ] **5.3 测试用例 1：验证 Min-Max 归一化正确性**
    ```python
    class TestMinMaxNormalize:
        """Min-Max 归一化测试"""
        
        def test_normal_case(self, calibrator):
            """正常场景：不同分数"""
            scores = [10.0, 20.0, 30.0, 40.0, 50.0]
            normalized = calibrator._min_max_normalize(scores)
            
            assert normalized[0] == pytest.approx(0.0)   # 最小值 → 0
            assert normalized[-1] == pytest.approx(1.0)  # 最大值 → 1
            assert normalized[2] == pytest.approx(0.5)   # 中间值 → 0.5
        
        def test_all_same_scores(self, calibrator):
            """边界场景：所有分数相同"""
            scores = [0.5, 0.5, 0.5]
            normalized = calibrator._min_max_normalize(scores)
            
            assert all(n == 0.5 for n in normalized)
        
        def test_empty_list(self, calibrator):
            """边界场景：空列表"""
            assert calibrator._min_max_normalize([]) == []
        
        def test_single_score(self, calibrator):
            """边界场景：单个分数（min_samples=1 时进行归一化）"""
            assert calibrator._min_max_normalize([0.7], min_samples=1) == [0.5]
        
        def test_negative_scores(self, calibrator):
            """边界场景：负数分数（BM25 可能为负）"""
            scores = [-5.0, 0.0, 5.0]
            normalized = calibrator._min_max_normalize(scores)
            
            assert normalized[0] == pytest.approx(0.0)
            assert normalized[1] == pytest.approx(0.5)
            assert normalized[2] == pytest.approx(1.0)
        
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
            
            assert normalized == scores, "单个样本时，应返回原始分数"

        def test_two_scores_no_normalize(self, calibrator):
            """两个样本时不进行归一化"""
            scores = [0.3, 0.8]
            normalized = calibrator._min_max_normalize(scores, min_samples=3)
            
            assert normalized == scores, "两个样本时，应返回原始分数"

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
  
  - [ ] **5.4 测试用例 2：验证 Sigmoid 校准输出在 [0, 1] 内**
    ```python
    class TestSigmoidCalibration:
        """Sigmoid 校准测试"""
        
        def test_output_range(self, calibrator):
            """验证输出在 [0, 1] 范围内"""
            for score in [0.0, 0.1, 0.3, 0.5, 0.7, 0.9, 1.0]:
                result = calibrator._sigmoid(score)
                assert 0.0 < result < 1.0, f"score={score}, result={result} 超出 (0,1)"
        
        def test_midpoint(self, calibrator):
            """验证中点分数为 0.5 时输出 0.5"""
            result = calibrator._sigmoid(0.5)
            assert result == pytest.approx(0.5, abs=0.001)
        
        def test_monotonicity(self, calibrator):
            """验证单调递增：输入越大，输出越大"""
            scores = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]
            results = [calibrator._sigmoid(s) for s in scores]
            
            for i in range(len(results) - 1):
                assert results[i] < results[i+1], f"非单调：{results[i]} >= {results[i+1]}"
        
        def test_steepness_effect(self):
            """验证 steepness 参数对区分度的影响"""
            calibrator_steep = ScoreCalibrator(sigmoid_steepness=20.0)
            calibrator_flat = ScoreCalibrator(sigmoid_steepness=5.0)
            
            # 高分和低分的差异
            high_steep = calibrator_steep._sigmoid(0.8) - calibrator_steep._sigmoid(0.2)
            high_flat = calibrator_flat._sigmoid(0.8) - calibrator_flat._sigmoid(0.2)
            
            assert high_steep > high_flat, "steepness 越大，区分度应越高"
    ```
  
  - [ ] **5.5 测试用例 3：验证 BM25 与向量分数最大差异 <0.2**
    ```python
    class TestScoreDifference:
        """分数差异测试"""
        
        def test_diagnostic_data_difference(self, calibrator):
            """使用诊断测试数据验证最大差异 <0.2"""
            bm25_calibrated = calibrator.calibrate_scores(DIAGNOSTIC_BM25_SCORES)
            vector_calibrated = calibrator.calibrate_scores(DIAGNOSTIC_VECTOR_SCORES)
            
            # 计算对应位置的差异
            diffs = [
                abs(bm25_calibrated[i] - vector_calibrated[i])
                for i in range(min(len(bm25_calibrated), len(vector_calibrated)))
            ]
            
            max_diff = max(diffs)
            avg_diff = sum(diffs) / len(diffs)
            
            assert max_diff < 0.2, f"最大差异 {max_diff:.4f} >= 0.2"
            assert avg_diff < 0.15, f"平均差异 {avg_diff:.4f} >= 0.15"
        
        def test_extreme_case_difference(self, calibrator):
            """极端场景：BM25 和向量分数范围差异很大"""
            # BM25 范围 [0.1, 0.9]，向量范围 [0.5, 0.95]
            bm25 = [0.1, 0.3, 0.5, 0.7, 0.9]
            vector = [0.5, 0.6, 0.7, 0.8, 0.95]
            
            bm25_cal = calibrator.calibrate_scores(bm25)
            vector_cal = calibrator.calibrate_scores(vector)
            
            diffs = [abs(bm25_cal[i] - vector_cal[i]) for i in range(5)]
            max_diff = max(diffs)
            
            assert max_diff < 0.2, f"极端场景最大差异 {max_diff:.4f} >= 0.2"
        
        def test_calibrate_and_compare_method(self, calibrator):
            """验证 calibrate_and_compare 方法返回正确统计信息"""
            result = calibrator.calibrate_and_compare(
                DIAGNOSTIC_BM25_SCORES,
                DIAGNOSTIC_VECTOR_SCORES
            )
            
            assert "max_diff" in result
            assert "avg_diff" in result
            assert "bm25_range" in result
            assert "vector_range" in result
            assert result["max_diff"] < 0.2
    ```
  
  - [ ] **5.6 测试用例 4：验证融合后排序不失真**
    ```python
    class TestMergeOrderPreservation:
        """融合排序测试"""
        
        def test_high_score_stays_high(self, calibrator):
            """验证高分节点融合后仍排在前面"""
            from llama_index.core.schema import NodeWithScore, TextNode
            
            # 构造节点：BM25 和向量分数都高的节点
            bm25_nodes = [
                NodeWithScore(node=TextNode(node_id="b1", text="高相关"), score=0.9),
                NodeWithScore(node=TextNode(node_id="b2", text="中相关"), score=0.5),
                NodeWithScore(node=TextNode(node_id="b3", text="低相关"), score=0.1),
            ]
            vector_nodes = [
                NodeWithScore(node=TextNode(node_id="v1", text="高相关"), score=0.9),
                NodeWithScore(node=TextNode(node_id="v2", text="中相关"), score=0.5),
                NodeWithScore(node=TextNode(node_id="v3", text="低相关"), score=0.1),
            ]
            
            merged_scores = calibrator.calibrate_and_merge(
                [n.score for n in bm25_nodes],
                [n.score for n in vector_nodes],
                bm25_weight=0.5,
                vector_weight=0.5
            )
            
            # 验证融合后分数保持顺序
            assert merged_scores[0] > merged_scores[1] > merged_scores[2]
        
        def test_mixed_sources_order(self, calibrator):
            """验证混合来源（BM25 独有、向量独有、两者共有）节点排序正确"""
            # BM25 独有高分节点
            bm25_scores = [0.9, 0.3]
            # 向量独有高分节点
            vector_scores = [0.85, 0.2]
            
            merged = calibrator.calibrate_and_merge(
                bm25_scores, vector_scores,
                bm25_weight=0.5, vector_weight=0.5
            )
            
            # 验证高分节点排在前面
            assert merged[0] > merged[1]
    ```
  
  - [ ] **5.7 测试用例 5：验证不同 steepness 参数对区分度的影响**
    ```python
    class TestSteepnessParameter:
        """steepness 参数测试"""
        
        def test_low_steepness(self):
            """低 steepness：分数区分度低，分布平缓"""
            calibrator = ScoreCalibrator(sigmoid_steepness=5.0)
            scores = [0.2, 0.4, 0.6, 0.8]
            calibrated = calibrator.calibrate_scores(scores)
            
            # 分数差异较小
            diff = calibrated[-1] - calibrated[0]
            assert diff < 0.5, f"低 steepness 区分度过高：{diff:.4f}"
        
        def test_medium_steepness(self):
            """中等 steepness：平衡区分度和稳定性"""
            calibrator = ScoreCalibrator(sigmoid_steepness=10.0)
            scores = [0.2, 0.4, 0.6, 0.8]
            calibrated = calibrator.calibrate_scores(scores)
            
            diff = calibrated[-1] - calibrated[0]
            assert 0.5 <= diff <= 0.8, f"中等 steepness 区分度异常：{diff:.4f}"
        
        def test_high_steepness(self):
            """高 steepness：分数区分度高，接近二值化"""
            calibrator = ScoreCalibrator(sigmoid_steepness=20.0)
            scores = [0.2, 0.4, 0.6, 0.8]
            calibrated = calibrator.calibrate_scores(scores)
            
            diff = calibrated[-1] - calibrated[0]
            assert diff > 0.8, f"高 steepness 区分度过低：{diff:.4f}"
        
        @pytest.mark.parametrize("steepness", [5.0, 10.0, 15.0, 20.0])
        def test_output_range_independent_of_steepness(self, steepness):
            """验证无论 steepness 如何，输出都在 (0, 1) 范围内"""
            calibrator = ScoreCalibrator(sigmoid_steepness=steepness)
            for score in [0.0, 0.25, 0.5, 0.75, 1.0]:
                result = calibrator._sigmoid(score)
                assert 0.0 < result < 1.0
    ```

- [ ] **Step 6: 集成验证**
  - [ ] **6.1 运行诊断测试 2（分数分布分析）**：
    ```bash
    cd backend
    uv run pytest backend/tests/diagnose_rag_comprehensive_v2.py::test_2_score_distribution -v
    ```
    - [ ] 确认输出中 BM25 与向量分数最大差异 <0.2
    - [ ] 确认平均差异 <0.15
    - [ ] 如果失败，打印校准前后的分数对比：
      ```python
      # 在诊断测试中添加调试输出
      print(f"校准前 BM25 范围: [{min(bm25_raw):.4f}, {max(bm25_raw):.4f}]")
      print(f"校准前向量范围: [{min(vector_raw):.4f}, {max(vector_raw):.4f}]")
      print(f"校准后 BM25 范围: [{min(bm25_cal):.4f}, {max(bm25_cal):.4f}]")
      print(f"校准后向量范围: [{min(vector_cal):.4f}, {max(vector_cal):.4f}]")
      print(f"最大差异: {max_diff:.4f}")
      ```
  
  - [ ] **6.2 运行诊断测试 1（检索质量指标）**：
    ```bash
    cd backend
    uv run pytest backend/tests/diagnose_rag_comprehensive_v2.py::test_1_retrieval_quality -v
    ```
    - [ ] 确认 Precision@5 ≥0.75
    - [ ] 如果 Precision@5 未达标，分析原因：
      - 检查 Sigmoid 参数是否合适（尝试调整 `steepness` 从 10.0 到 15.0）
      - 检查融合权重是否合理（尝试调整 `bm25_weight` / `vector_weight`）
      - 检查是否因校准导致原本高分的不相关节点被压低
  
  - [ ] **6.3 验证 `merge_results` 集成**：
    ```bash
    cd backend
    uv run pytest backend/tests/test_rag_hybrid.py -v -k "merge"
    ```
    - [ ] 确认融合后节点分数在合理范围内
    - [ ] 确认融合后排序正确（高分在前）
    - [ ] 确认节点数量不超过 `limit` 参数
  
  - [ ] **6.4 手动验证分数分布**：
    ```python
    # 在 Python 交互环境中运行
    from backend.src.core.rag.score_calibrator import ScoreCalibrator
    import matplotlib.pyplot as plt
    
    calibrator = ScoreCalibrator()
    
    # 使用诊断测试数据
    bm25_raw = [0.106, 0.234, 0.456, 0.678, 0.948]
    vector_raw = [0.500, 0.620, 0.710, 0.830, 0.950]
    
    bm25_cal = calibrator.calibrate_scores(bm25_raw)
    vector_cal = calibrator.calibrate_scores(vector_raw)
    
    print("校准前:")
    print(f"  BM25: {bm25_raw}")
    print(f"  向量: {vector_raw}")
    print(f"  最大差异: {max(abs(b-v) for b,v in zip(bm25_raw, vector_raw)):.4f}")
    
    print("\n校准后:")
    print(f"  BM25: {[round(x, 4) for x in bm25_cal]}")
    print(f"  向量: {[round(x, 4) for x in vector_cal]}")
    print(f"  最大差异: {max(abs(b-v) for b,v in zip(bm25_cal, vector_cal)):.4f}")
    
    # 可视化
    plt.figure(figsize=(10, 4))
    plt.subplot(1, 2, 1)
    plt.bar(['BM25', 'Vector'], [sum(bm25_raw)/5, sum(vector_raw)/5])
    plt.title('校准前平均分')
    plt.subplot(1, 2, 2)
    plt.bar(['BM25', 'Vector'], [sum(bm25_cal)/5, sum(vector_cal)/5])
    plt.title('校准后平均分')
    plt.show()
    ```
  
  - [ ] **6.5 验证 `merge_for_search` 不受影响**：
    ```bash
    # 前端搜索页使用 merge_for_search，确认不受变更影响
    cd backend
    uv run python -c "
    from src.core.hybrid_retrieval import HybridRetrievalMerger
    from llama_index.core.schema import NodeWithScore, TextNode
    
    # 模拟搜索页数据
    bm25_nodes = [
        NodeWithScore(node=TextNode(node_id='s1', text='搜索结果 1'), score=0.8),
        NodeWithScore(node=TextNode(node_id='s2', text='搜索结果 2'), score=0.5),
    ]
    vector_nodes = [
        NodeWithScore(node=TextNode(node_id='s1', text='搜索结果 1'), score=0.7),
        NodeWithScore(node=TextNode(node_id='s3', text='搜索结果 3'), score=0.6),
    ]
    
    merged = HybridRetrievalMerger.merge_for_search(
        bm25_nodes, vector_nodes,
        bm25_weight=0.7, vector_weight=0.3
    )
    
    print(f'merge_for_search 返回 {len(merged)} 个结果')
    print(f'Top 分数: {[n.score:.4f} for n in merged[:3]]')
    "
    ```
  
  - [ ] **6.6 配置参数调优验证**：
    ```bash
    # 测试不同 Sigmoid 参数组合的效果
    cd backend
    uv run python -c "
    from backend.src.core.rag.score_calibrator import ScoreCalibrator
    
    bm25 = [0.106, 0.234, 0.456, 0.678, 0.948]
    vector = [0.500, 0.620, 0.710, 0.830, 0.950]
    
    print('不同 steepness 参数的效果:')
    for steepness in [5.0, 10.0, 15.0, 20.0]:
        cal = ScoreCalibrator(sigmoid_steepness=steepness)
        result = cal.calibrate_and_compare(bm25, vector)
        print(f'  sigmoid_steepness={steepness}: max_diff={result[\"max_diff\"]:.4f}, avg_diff={result[\"avg_diff\"]:.4f}')
    "
    ```

## ✅ 验收标准

| 验收项 | 标准 | 验证方法 |
|--------|------|----------|
| 分数差异 | BM25 与向量分数最大差异 <0.2 | 分数分布分析 |
| 校准一致性 | 使用相同数学函数校准 | 代码审查 |
| 排序不失真 | 融合后高分仍高于低分 | 单元测试 |
| Precision@5 | ≥0.75 | RAG 测试集 |

## 📁 涉及文件

| 文件 | 操作 | 说明 |
|------|------|------|
| `backend/src/core/rag/score_calibrator.py` | 新增 | BM25/向量分数校准器 |
| `backend/src/core/hybrid_retrieval.py` | 修改 | 集成 `ScoreCalibrator` 替换旧校准逻辑 |
| `backend/src/config/settings.py` | 修改 | 新增校准参数配置项 |
| `backend/tests/test_score_calibrator.py` | 新增 | 单元测试 |

## 🔧 配置项

```python
# backend/src/config/settings.py 新增
rag_score_sigmoid_midpoint: float = 0.5   # Sigmoid 中点
rag_score_sigmoid_steepness: float = 10.0 # Sigmoid 陡峭程度
rag_score_min_samples: int = 3            # Min-Max 归一化最小样本数阈值
```

## ⚠️ 注意事项

1. **不要修改 Cross-Encoder 的输出**，本步骤仅影响 BM25 和向量检索的融合阶段
2. **Min-Max 归一化是全有或全无**：必须对 BM25 和向量分数都进行归一化，否则差异仍存在
3. **Sigmoid 参数可调**：`midpoint` 和 `steepness` 应通过配置管理，便于后续 A/B 测试调优
4. **向后兼容**：保留旧校准方法作为回滚选项（通过 `rag_score_method=legacy` 切换）
5. **最小样本数阈值**：`_min_max_normalize` 方法默认要求 `min_samples=3`，样本数不足时不进行归一化，避免极端值导致分数失真
6. **日志记录**：当样本数不足时，会记录 debug 级别日志，便于调试
7. **可调参数**：`min_samples` 参数可通过配置项 `rag_score_min_samples` 调整，默认值为 3

---

**返回索引：** [01-phase-a-00-overview.md](./01-phase-a-00-overview.md)
