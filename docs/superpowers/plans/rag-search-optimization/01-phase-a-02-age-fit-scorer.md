# A-2: 年龄适配度细粒度计算器

> **所属 Phase**: Phase A (P0)
> **任务类型**: 单一任务 — 实现细粒度年龄适配度计算
> **对应问题**: 测试 3 失败（年龄适配度仅 3 个固定值，目标 ≥10 个不同值）

## 🎯 目标

将年龄适配度从三档固定值 (0.3, 0.7, 1.0) 改为细粒度的连续值 (0-1)，确保：
1. 输出 ≥10 个不同值（0-1 连续分布）
2. 计算逻辑考虑多维度因素，而非仅判断年龄差值
3. 单次计算耗时 ≤5ms

## 📋 实施步骤

- [ ] **Step 1: 分析现有计算逻辑**
  - [ ] 阅读 `backend/src/service/retrieval_service.py` 中 `_calculate_age_fit_score` 方法（第 346-362 行）
  - [ ] 阅读 `backend/src/core/age_filter.py` 中 `calculate_age_fit_score` 方法（第 104-137 行）
  - [ ] 确认当前逻辑仅基于年龄差值返回固定值（1.0 / 0.7 / 0.3 或基于 decay_factor 的线性衰减）
  - [ ] 记录当前逻辑的局限性：未考虑内容特征、领域匹配度、元数据年龄范围细粒度

- [ ] **Step 2: 设计三维度计算模型**
  - [ ] 定义三个计算维度及权重：
    ```
    维度 1: 年龄范围匹配度 (weight=0.4, 范围 0-0.4)
    维度 2: 内容特征适配度 (weight=0.3, 范围 0-0.3)
    维度 3: 领域匹配度 (weight=0.3, 范围 0-0.3)
    ```
  - [ ] **维度 1 详细规则**（基于用户年龄与内容目标年龄范围的关系）：
    ```python
    # 完全在范围内
    if target_min <= user_age <= target_max:
        # 计算在范围内的相对位置，越靠近中心越适配
        range_center = (target_min + target_max) / 2
        range_span = max(target_max - target_min, 1)
        distance_from_center = abs(user_age - range_center)
        # 距离中心越近，分数越高 [0.35, 0.4]
        dimension1 = 0.35 + 0.05 * (1 - distance_from_center / (range_span / 2))
    
    # 差 1 岁 [0.25, 0.35]
    elif abs(user_age - target_min) == 1 or abs(user_age - target_max) == 1:
        dimension1 = 0.25 + 0.1 * (1 - abs(user_age - target_min if user_age < target_min else user_age - target_max) / 2)
    
    # 差 2 岁 [0.1, 0.25]
    elif abs(user_age - target_min) == 2 or abs(user_age - target_max) == 2:
        dimension1 = 0.1 + 0.15 * (1 - abs(user_age - target_min if user_age < target_min else user_age - target_max) / 3)
    
    # 差 3 岁以上 [0, 0.1]
    else:
        diff = max(target_min - user_age, user_age - target_max)
        dimension1 = max(0, 0.1 * (1 - (diff - 3) / 5))
    ```
  - [ ] **维度 2 详细规则**（基于内容特征）：
    ```python
    # 内容长度适配（句子数、字数）
    char_count = len(content)
    sentence_count = content.count('。') + content.count('！') + content.count('？')
    
    # 不同年龄段适合的内容长度特征
    age_length_profiles = {
        (0, 2): {'ideal_chars': (30, 100), 'ideal_sentences': (1, 3)},    # 婴儿：短句
        (2, 4): {'ideal_chars': (50, 200), 'ideal_sentences': (2, 5)},    # 幼儿：中等
        (4, 6): {'ideal_chars': (100, 400), 'ideal_sentences': (3, 8)},   # 学前：较长
        (6, 12): {'ideal_chars': (200, 800), 'ideal_sentences': (5, 15)}, # 学龄：长文
    }
    
    # 计算长度适配度
    profile = None
    for (min_a, max_a), p in age_length_profiles.items():
        if min_a <= user_age <= max_a:
            profile = p
            break
    
    if profile:
        char_score = 1.0 - min(1.0, abs(char_count - sum(profile['ideal_chars'])/2) / sum(profile['ideal_chars']))
        sentence_score = 1.0 - min(1.0, abs(sentence_count - sum(profile['ideal_sentences'])/2) / sum(profile['ideal_sentences']))
        length_fit = (char_score + sentence_score) / 2
    else:
        length_fit = 0.5  # 默认
    
    # 专业术语密度适配
    domain_terms = ['前庭觉', '精细动作', '感统', '认知发展', '语言发展', '社交技能']
    term_count = sum(1 for term in domain_terms if term in content)
    term_density = term_count / max(sentence_count, 1)
    
    # 低龄儿童术语密度应低，高龄可高
    if user_age <= 3:
        term_fit = 1.0 - min(1.0, term_density / 0.3)  # 术语密度 >0.3 时得分降低
    else:
        term_fit = min(1.0, term_density / 0.1)  # 术语密度 >0.1 时得分增加
    
    dimension2 = 0.15 * length_fit + 0.15 * term_fit  # 范围 0-0.3
    ```
  - [ ] **维度 3 详细规则**（基于领域匹配度）：
    ```python
    # 内容涉及的发展领域与年龄段匹配
    # 提取内容中的领域关键词
    domain_keywords = {
        '大动作': ['爬', '走', '跑', '跳', '平衡', '大动作'],
        '精细动作': ['抓', '捏', '画', '剪', '穿珠', '精细动作', '手眼'],
        '语言发展': ['说话', '表达', '词汇', '语言', '沟通'],
        '认知发展': ['思考', '逻辑', '记忆', '注意', '认知'],
        '社交技能': ['分享', '合作', '情绪', '社交', '同伴'],
        '感觉统合': ['前庭', '触觉', '本体', '感统', '感觉'],
    }
    
    # 不同年龄段重点发展领域
    age_domain_priority = {
        (0, 2): ['大动作', '感觉统合'],
        (2, 4): ['精细动作', '语言发展', '感觉统合'],
        (4, 6): ['认知发展', '社交技能', '精细动作'],
        (6, 12): ['认知发展', '社交技能', '语言发展'],
    }
    
    # 识别内容涉及的领域
    content_domains = []
    for domain, keywords in domain_keywords.items():
        if any(kw in content for kw in keywords):
            content_domains.append(domain)
    
    # 计算领域匹配度
    priority_domains = []
    for (min_a, max_a), domains in age_domain_priority.items():
        if min_a <= user_age <= max_a:
            priority_domains = domains
            break
    
    if not content_domains:
        domain_fit = 0.5  # 无法识别领域，给中等分数
    elif not priority_domains:
        domain_fit = 0.5
    else:
        # 计算内容领域与优先领域的重叠度
        overlap = len(set(content_domains) & set(priority_domains))
        domain_fit = overlap / max(len(priority_domains), 1)
    
    dimension3 = 0.3 * domain_fit  # 范围 0-0.3
    ```

- [ ] **Step 3: 实现 `AgeFitScorer` 类**
  - [ ] 创建新文件 `backend/src/core/rag/age_fit_scorer.py`
  - [ ] 实现 `AgeFitScorer` 类，包含以下方法：
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
        
        @classmethod
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
        
        @staticmethod
        def _calculate_age_range_match(user_age: int, target_min: int, target_max: int) -> float:
            """维度 1: 年龄范围匹配度 (0-0.4)"""
            # 实现 Step 2 中的维度 1 逻辑
            ...
        
        @staticmethod
        def _calculate_content_feature_fit(content: str, user_age: int) -> float:
            """维度 2: 内容特征适配度 (0-0.3)"""
            # 实现 Step 2 中的维度 2 逻辑
            ...
        
        @staticmethod
        def _calculate_domain_match(content: str, user_age: int, metadata: Optional[Dict] = None) -> float:
            """维度 3: 领域匹配度 (0-0.3)"""
            # 实现 Step 2 中的维度 3 逻辑
            ...
    ```
  - [ ] 确保所有方法有中文注释
  - [ ] 添加性能优化：对 `domain_keywords` 和 `age_length_profiles` 等静态数据使用类级别缓存

- [ ] **Step 4: 集成到 `_convert_to_knowledge_items`**
  - [ ] **4.1 修改导入语句**：
    - [ ] 在 `backend/src/service/retrieval_service.py` 顶部（第 1-24 行之后）添加导入：
      ```python
      from backend.src.core.rag.age_fit_scorer import AgeFitScorer
      ```
  
  - [ ] **4.2 定位并替换旧计算逻辑**：
    - [ ] 找到 `_convert_to_knowledge_items` 方法中第 491-506 行的分数计算代码：
      ```python
      # 当前代码（需要替换）：
      final_score = base_score
      age_fit_score = 1.0
      if user_age is not None:
          age_fit_score = child_development_engine.calculate_age_appropriateness(
              content, user_age
          )
          metadata_age_fit = self._calculate_age_fit_score(
              user_age, target_age_min, target_age_max
          )
          age_fit_score = 0.7 * age_fit_score + 0.3 * metadata_age_fit

          age_weight = settings.rag_age_fit_weight
          final_score = base_score * (1 - age_weight) + age_fit_score * age_weight
      ```
    - [ ] 替换为新的分离逻辑：
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
  
  - [ ] **4.3 修改 `KnowledgeItem` 构造**：
    - [ ] 找到第 518-531 行的 `KnowledgeItem` 构造代码：
      ```python
      # 当前代码：
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
          relevance_score=float(final_score),
      )
      ```
    - [ ] 修改为：
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
  
  - [ ] **4.4 移除或标记废弃旧方法**：
    - [ ] `_calculate_age_fit_score` 方法（第 346-362 行）：
      - **选项 A**：删除该方法（推荐，因为已被 `AgeFitScorer` 替代）
      - **选项 B**：保留但添加 `@deprecated` 标记，作为回滚选项
      - **建议**：选择选项 B，保留作为 `rag_score_method=legacy` 回滚时的备用
    - [ ] 对 `child_development_engine.calculate_age_appropriateness` 的调用：
      - 在 Step 4.2 中已移除，不再需要
      - 确认 `child_development_engine` 在其他地方是否还有使用，如有则保留引擎实例化

  - [ ] **4.5 验证排序逻辑**：
    - [ ] 确认第 535 行的排序代码使用 `relevance_score`：
      ```python
      results.sort(key=lambda x: x.relevance_score, reverse=True)
      ```
    - [ ] 如果仍使用 `final_score` 或其他字段，修改为 `relevance_score`

- [ ] **Step 5: 编写单元测试**
  - [ ] **5.1 创建测试文件**：`backend/tests/test_age_fit_scorer.py`
  
  - [ ] **5.2 测试环境准备**：
    ```python
    import pytest
    import time
    from backend.src.core.rag.age_fit_scorer import AgeFitScorer
    
    # 测试数据：不同年龄和内容组合
    TEST_CONTENTS = [
        "适合 2 岁儿童的大动作训练，包括爬行和走路练习",
        "适合 3 岁儿童的精细动作训练，如穿珠子和画画",
        "适合 4 岁儿童的语言表达训练，通过故事讲述提高词汇量",
        "适合 5 岁儿童的认知发展训练，包括简单的逻辑推理游戏",
        "适合 6 岁儿童的社交技能训练，学习分享和合作",
        "儿童注意力训练方法，适合学龄前儿童",
        "亲子阅读技巧，培养早期语言发展",
        "儿童情绪管理，帮助幼儿学会表达情感",
        "适合 3-4 岁儿童的平衡训练，通过游戏提高协调能力",
        "适合 5-6 岁儿童的逻辑思维训练，包括分类和排序活动",
        "婴儿感官刺激，适合 0-1 岁宝宝的触觉和听觉发展",
        "学龄儿童学习方法指导，提高自主学习能",
    ]
    ```
  
  - [ ] **5.3 测试用例 1：验证输出 ≥10 个不同值**
    ```python
    def test_age_fit_score_granularity():
        """验证 age_fit_score 输出 ≥10 个不同值（细粒度连续分布）"""
        scores = set()
        
        # 使用 10 个不同年龄和内容组合
        test_cases = [
            (2, TEST_CONTENTS[0]),   # 2 岁 + 大动作
            (3, TEST_CONTENTS[1]),   # 3 岁 + 精细动作
            (4, TEST_CONTENTS[2]),   # 4 岁 + 语言
            (5, TEST_CONTENTS[3]),   # 5 岁 + 认知
            (6, TEST_CONTENTS[4]),   # 6 岁 + 社交
            (3, TEST_CONTENTS[5]),   # 3 岁 + 注意力
            (4, TEST_CONTENTS[6]),   # 4 岁 + 亲子阅读
            (5, TEST_CONTENTS[7]),   # 5 岁 + 情绪管理
            (3, TEST_CONTENTS[8]),   # 3 岁 + 平衡训练
            (6, TEST_CONTENTS[9]),   # 6 岁 + 逻辑思维
        ]
        
        for age, content in test_cases:
            score = AgeFitScorer.calculate(
                content=content,
                user_age=age,
                target_age_min=age - 1,
                target_age_max=age + 1
            )
            scores.add(round(score, 3))  # 保留 3 位小数去重
        
        assert len(scores) >= 10, f"仅输出 {len(scores)} 个不同值，目标 ≥10"
    ```
  
  - [ ] **5.4 测试用例 2：验证分数范围在 [0, 1] 内**
    ```python
    @pytest.mark.parametrize("age,content,target_min,target_max", [
        (0, TEST_CONTENTS[10], 0, 2),    # 0 岁边界
        (3, TEST_CONTENTS[1], 3, 4),     # 正常场景
        (6, TEST_CONTENTS[4], 5, 7),     # 6 岁边界
        (10, TEST_CONTENTS[11], 8, 12),  # 10 岁
        (18, TEST_CONTENTS[11], 15, 18), # 18 岁边界
        (3, TEST_CONTENTS[0], 5, 6),     # 年龄不匹配
    ])
    def test_age_fit_score_range(age, content, target_min, target_max):
        """验证 age_fit_score 输出在 [0, 1] 范围内"""
        score = AgeFitScorer.calculate(
            content=content,
            user_age=age,
            target_age_min=target_min,
            target_age_max=target_max
        )
        assert 0.0 <= score <= 1.0, f"分数 {score} 超出 [0, 1] 范围"
    ```
  
  - [ ] **5.5 测试用例 3：验证完全适配场景分数 >0.7**
    ```python
    def test_perfect_match_score():
        """验证用户年龄在目标范围内时，分数 >0.7"""
        test_cases = [
            (3, TEST_CONTENTS[1], 3, 4),   # 3 岁在 [3,4] 内
            (4, TEST_CONTENTS[2], 3, 5),   # 4 岁在 [3,5] 内
            (5, TEST_CONTENTS[3], 4, 6),   # 5 岁在 [4,6] 内
            (6, TEST_CONTENTS[4], 5, 7),   # 6 岁在 [5,7] 内
        ]
        
        for age, content, target_min, target_max in test_cases:
            score = AgeFitScorer.calculate(
                content=content,
                user_age=age,
                target_age_min=target_min,
                target_age_max=target_max
            )
            assert score > 0.7, f"年龄 {age} 在 [{target_min},{target_max}] 内，分数 {score} 应 >0.7"
    ```
  
  - [ ] **5.6 测试用例 4：验证完全不适配场景分数 <0.3**
    ```python
    def test_complete_mismatch_score():
        """验证年龄差 ≥5 岁时，分数 <0.3"""
        test_cases = [
            (0, TEST_CONTENTS[4], 5, 7),   # 0 岁 vs [5,7]
            (2, TEST_CONTENTS[9], 8, 10),  # 2 岁 vs [8,10]
            (8, TEST_CONTENTS[0], 0, 2),   # 8 岁 vs [0,2]
            (12, TEST_CONTENTS[1], 2, 4),  # 12 岁 vs [2,4]
        ]
        
        for age, content, target_min, target_max in test_cases:
            score = AgeFitScorer.calculate(
                content=content,
                user_age=age,
                target_age_min=target_min,
                target_age_max=target_max
            )
            assert score < 0.3, f"年龄差 ≥5 岁，分数 {score} 应 <0.3"
    ```
  
  - [ ] **5.7 测试用例 5：验证性能（单次计算耗时 ≤5ms）**
    ```python
    def test_calculation_performance():
        """验证单次计算耗时 ≤5ms"""
        content = TEST_CONTENTS[1]
        iterations = 100
        
        start_time = time.perf_counter()
        for _ in range(iterations):
            AgeFitScorer.calculate(
                content=content,
                user_age=3,
                target_age_min=2,
                target_age_max=4
            )
        elapsed_ms = (time.perf_counter() - start_time) * 1000 / iterations
        
        assert elapsed_ms <= 5.0, f"单次计算耗时 {elapsed_ms:.2f}ms，目标 ≤5ms"
    ```
  
  - [ ] **5.8 测试用例 6：覆盖边界场景**
    ```python
    def test_boundary_cases():
        """验证边界场景处理正确"""
        # 0 岁婴儿
        score_0 = AgeFitScorer.calculate(
            content=TEST_CONTENTS[10],
            user_age=0,
            target_age_min=0,
            target_age_max=2
        )
        assert score_0 > 0.7, "0 岁婴儿内容对 0 岁用户应高分"
        
        # 18 岁边界
        score_18 = AgeFitScorer.calculate(
            content=TEST_CONTENTS[11],
            user_age=18,
            target_age_min=15,
            target_age_max=18
        )
        assert score_18 > 0.7, "18 岁内容对 18 岁用户应高分"
        
        # 无明确年龄内容（target_min=0, target_max=18）
        score_general = AgeFitScorer.calculate(
            content=TEST_CONTENTS[5],
            user_age=3,
            target_age_min=0,
            target_age_max=18
        )
        assert 0.5 <= score_general <= 0.9, "通用内容应给中等偏上分数"
        
        # 单年龄内容（target_min == target_max）
        score_single = AgeFitScorer.calculate(
            content=TEST_CONTENTS[0],
            user_age=2,
            target_age_min=2,
            target_age_max=2
        )
        assert score_single > 0.7, "单年龄内容对匹配年龄用户应高分"
    ```
  
  - [ ] **5.9 测试用例 7：验证三维度独立计算**
    ```python
    def test_three_dimensions_independence():
        """验证三个维度独立计算，互不影响"""
        # 测试维度 1（年龄范围匹配）
        dim1 = AgeFitScorer._calculate_age_range_match(
            user_age=3, target_min=3, target_max=4
        )
        assert 0.35 <= dim1 <= 0.4, f"维度 1 分数 {dim1} 不在 [0.35, 0.4] 范围内"
        
        # 测试维度 2（内容特征适配）
        dim2 = AgeFitScorer._calculate_content_feature_fit(
            content=TEST_CONTENTS[1], user_age=3
        )
        assert 0.0 <= dim2 <= 0.3, f"维度 2 分数 {dim2} 不在 [0, 0.3] 范围内"
        
        # 测试维度 3（领域匹配）
        dim3 = AgeFitScorer._calculate_domain_match(
            content=TEST_CONTENTS[1], user_age=3, metadata={"topics": ["精细动作"]}
        )
        assert 0.0 <= dim3 <= 0.3, f"维度 3 分数 {dim3} 不在 [0, 0.3] 范围内"
        
        # 验证总分 = 维度 1 + 维度 2 + 维度 3
        total = AgeFitScorer.calculate(
            content=TEST_CONTENTS[1],
            user_age=3,
            target_age_min=3,
            target_age_max=4,
            metadata_str='{"topics": ["精细动作"]}'
        )
        assert abs(total - (dim1 + dim2 + dim3)) < 0.001, "总分应等于三维度之和"
    ```
  
  - [ ] **5.10 测试用例 8：验证缓存命中性能**
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
    ```
  
  - [ ] **5.11 测试用例 9：验证缓存清理功能**
    ```python
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

- [ ] **Step 6: 集成验证**
  - [ ] **6.1 运行诊断测试**：
    ```bash
    cd backend
    uv run pytest backend/tests/diagnose_rag_comprehensive_v2.py::test_3_age_fit_granularity -v
    ```
    - [ ] 确认年龄适配度不同值数量 ≥10
    - [ ] 确认分数分布呈连续分布（非仅 3 个固定值）
    - [ ] 如果测试失败，检查分数分布直方图，确认是否有断层或聚集
  
  - [ ] **6.2 运行完整诊断测试集**：
    ```bash
    cd backend
    uv run pytest backend/tests/diagnose_rag_comprehensive_v2.py -v
    ```
    - [ ] 确认测试 3（年龄适配度细粒度）通过
    - [ ] 确认测试 11（年龄过滤准确率）未退化（过滤逻辑在 A-4 中重构）
    - [ ] 确认其他测试未因 `age_fit_score` 变更而失败
  
  - [ ] **6.3 验证 `_convert_to_knowledge_items` 集成**：
    ```bash
    cd backend
    uv run pytest backend/tests/service/test_retrieval_service.py -v -k "knowledge_item"
    ```
    - [ ] 确认 `KnowledgeItem` 包含 `age_fit_score` 字段
    - [ ] 确认 `relevance_score` 未混合年龄适配度
    - [ ] 确认排序基于 `relevance_score`
  
  - [ ] **6.4 手动验证分数分布**：
    ```python
    # 在 Python 交互环境或 Jupyter 中运行
    from backend.src.service.retrieval_service import RetrievalService
    from backend.src.core.rag.age_fit_scorer import AgeFitScorer
    
    # 测试 10 个不同场景
    scores = []
    for age in range(0, 7):
        for content_idx in range(3):
            score = AgeFitScorer.calculate(
                content=TEST_CONTENTS[content_idx],
                user_age=age,
                target_age_min=age,
                target_age_max=age + 1
            )
            scores.append(score)
    
    # 打印不同值数量
    unique_scores = set(round(s, 3) for s in scores)
    print(f"不同值数量：{len(unique_scores)}")
    print(f"分数列表：{sorted(unique_scores)}")
    
    # 验证连续性（相邻分数差值 <0.2）
    sorted_scores = sorted(unique_scores)
    max_gap = max(b - a for a, b in zip(sorted_scores[:-1], sorted_scores[1:]))
    print(f"最大间隔：{max_gap:.3f}")
    assert max_gap < 0.2, f"分数分布不连续，最大间隔 {max_gap:.3f}"
    ```
  
  - [ ] **6.5 性能压测验证**：
    ```bash
    # 使用 pytest-benchmark 或手动压测
    cd backend
    uv run python -c "
    import time
    from backend.src.core.rag.age_fit_scorer import AgeFitScorer
    
    # 压测 1000 次计算
    start = time.perf_counter()
    for _ in range(1000):
        AgeFitScorer.calculate(
            content='适合 3 岁儿童的精细动作训练',
            user_age=3,
            target_age_min=2,
            target_age_max=4
        )
    elapsed_ms = (time.perf_counter() - start) * 1000
    print(f'1000 次计算耗时：{elapsed_ms:.2f}ms')
    print(f'单次平均耗时：{elapsed_ms/1000:.3f}ms')
    assert elapsed_ms / 1000 <= 5.0, '单次计算耗时 >5ms'
    "
    ```

## ✅ 验收标准

| 验收项 | 标准 | 验证方法 |
|--------|------|----------|
| 细粒度输出 | ≥10 个不同值（0-1 连续分布） | 分数分布分析 |
| 分数范围 | 所有输出在 [0, 1] 内 | 单元测试 |
| 计算性能 | 单次计算耗时 ≤5ms | 性能测试 |
| 逻辑正确 | 完全适配 >0.7，完全不适配 <0.3 | 单元测试 |

## 📁 涉及文件

| 文件 | 操作 | 说明 |
|------|------|------|
| `backend/src/core/rag/age_fit_scorer.py` | 新增 | 细粒度年龄适配度计算器 |
| `backend/src/service/retrieval_service.py` | 修改 | 集成 `AgeFitScorer` 替换旧逻辑 |
| `backend/tests/test_age_fit_scorer.py` | 新增 | 单元测试 |

## ⚠️ 注意事项

1. **不要修改 `relevance_score` 的计算**，本步骤仅影响 `age_fit_score`
2. **静态数据缓存**：`domain_keywords`、`age_length_profiles` 等应作为类级别常量，避免重复初始化
3. **性能优先**：计算逻辑应避免正则表达式和复杂字符串操作，确保 ≤5ms
4. **可扩展性**：三维度权重应可通过配置调整，为后续优化预留空间
5. **缓存策略**：`calculate` 方法使用 `lru_cache(maxsize=1024)` 缓存结果，相同输入直接返回缓存值，确保高频场景性能
6. **metadata 参数处理**：由于 `lru_cache` 要求参数可哈希，`metadata` 字典需序列化为 JSON 字符串传入
7. **缓存清理**：在单元测试中应调用 `AgeFitScorer.calculate.cache_clear()` 清理缓存，避免测试间相互影响

---

**返回索引：** [01-phase-a-00-overview.md](./01-phase-a-00-overview.md)
