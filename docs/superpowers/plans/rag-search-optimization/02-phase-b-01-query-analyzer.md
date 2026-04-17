# B-1: 查询类型分析器

> **所属 Phase**: Phase B (P1)
> **任务类型**: 单一任务 — 构建适配中文场景的查询特征分析器
> **对应问题**: 测试 4（查询类型分析）+ 根因 3（中文关键词密度计算不准确）

## 🎯 目标

替换当前不适配中文的 `keyword_density` 计算逻辑，构建基于**查询长度 + 专业术语识别**的查询类型分析器，为动态权重决策提供可靠输入。

## 📋 实施步骤

- [ ] **Step 1: 分析现有 `get_dynamic_weights` 的问题**
  - [ ] 阅读 `backend/src/core/hybrid_retrieval.py` 第 118-140 行的 `get_dynamic_weights` 方法
  - [ ] 确认问题根因：
    ```python
    # 当前逻辑（第 121 行）
    keyword_density = len(re.findall(r'[\u4e00-\u9fa5a-zA-Z0-9]+', query)) / len(query) if query else 0.5
    ```
    - 中文查询几乎 100% 是中文字符，`keyword_density` 恒接近 1.0
    - 所有中文查询都被判定为 `keyword_query`（BM25 权重 0.7）
    - 短查询（如"运动"2 字）和长查询（如"前庭觉训练和精细动作训练的区别"15 字）使用相同权重
  - [ ] 记录当前配置值（`backend/src/config/modules/rag/retrieval.py` 第 72-79 行）：
    ```python
    hybrid_weights = {
        "default": 0.5,
        "keyword_query": 0.7,
        "semantic_query": 0.3,
    }
    ```

- [ ] **Step 2: 定义查询类型分类体系**
  - [ ] 基于需求文档测试 4 的结果，定义以下查询类型：
    
    | 类型 | 判定条件 | 示例 | 期望权重方向 |
    |------|----------|------|-------------|
    | **短查询** | 字符数 < 5 | "运动"、"游戏" | 偏重向量 (Vector ≥0.7) |
    | **专业术语** | 包含领域关键词 + 字符数 3-8 | "感统训练"、"前庭觉" | 偏重 BM25 (BM25 ≥0.7) |
    | **描述性查询** | 字符数 5-15 + 含疑问词 | "3 岁儿童语言发展迟缓怎么办" | 均衡偏向量 |
    | **复杂查询** | 字符数 > 15 + 含连接词 | "前庭觉训练和精细动作训练的区别" | 动态调整 + 查询重写 |
    | **默认** | 不满足以上任何条件 | - | 均衡 (0.5/0.5) |

  - [ ] **专业术语词典设计**：
    - 从现有知识库中提取高频专业术语，构建初始词典
    - 术语来源：`topics` 元数据字段、`brain_regions` 字段、文档标题
    - 初始词典包含：感统训练、前庭觉、本体觉、触觉防御、精细动作、大动作、语言发展、认知发展、社交技能、注意力训练 等
    - 词典存储：使用 Python `set` 加载到内存，支持热更新（通过配置表）

- [ ] **Step 3: 实现 `QueryAnalyzer` 类**
  - [ ] 创建新文件 `backend/src/core/rag/query_analyzer.py`
  - [ ] 实现核心类结构：
    ```python
    class QueryType(Enum):
        SHORT = "short"              # 短查询
        TERMINOLOGY = "terminology"  # 专业术语
        DESCRIPTIVE = "descriptive"  # 描述性查询
        COMPLEX = "complex"          # 复杂查询
        DEFAULT = "default"          # 默认

    @dataclass
    class QueryAnalysis:
        query_type: QueryType
        original_query: str
        char_length: int
        has_terminology: bool
        matched_terminology: List[str]
        has_question_word: bool       # 是否含疑问词（怎么办、如何、为什么）
        has_conjunction: bool         # 是否含连接词（和、与、区别、比较）
        confidence: float             # 分类置信度 (0-1)

    class QueryAnalyzer:
        """查询类型分析器（适配中文场景）"""
        
        def __init__(self, terminology_file: Optional[str] = None):
            self._terminology_set: Set[str] = self._load_terminology(terminology_file)
            self._question_words = {"怎么办", "如何", "为什么", "怎样", "什么", "哪些"}
            self._conjunction_words = {"和", "与", "的区别", "比较", "对比", "还是"}
        
        def analyze(self, query: str) -> QueryAnalysis:
            """分析查询类型"""
            # 1. 计算字符长度
            # 2. 检测专业术语
            # 3. 检测疑问词/连接词
            # 4. 综合判定查询类型
            # 5. 返回 QueryAnalysis
    ```
  - [ ] 实现 `analyze` 方法的判定逻辑（按优先级顺序）：
    ```python
    def analyze(self, query: str) -> QueryAnalysis:
        char_length = len(query.strip())
        
        # 提取特征
        matched_terms = self._match_terminology(query)
        has_question = any(w in query for w in self._question_words)
        has_conjunction = any(w in query for w in self._conjunction_words)
        
        # 判定逻辑（优先级从高到低）
        if char_length > 15 and has_conjunction:
            query_type = QueryType.COMPLEX
        elif char_length < 5:
            query_type = QueryType.SHORT
        elif matched_terms and 3 <= char_length <= 8:
            query_type = QueryType.TERMINOLOGY
        elif 5 <= char_length <= 15 and has_question:
            query_type = QueryType.DESCRIPTIVE
        else:
            query_type = QueryType.DEFAULT
        
        # 计算置信度（基于特征匹配强度）
        confidence = self._calculate_confidence(query_type, char_length, matched_terms, has_question, has_conjunction)
        
        return QueryAnalysis(
            query_type=query_type,
            original_query=query,
            char_length=char_length,
            has_terminology=bool(matched_terms),
            matched_terminology=matched_terms,
            has_question_word=has_question,
            has_conjunction=has_conjunction,
            confidence=confidence,
        )
    ```

- [ ] **Step 4: 实现专业术语加载与匹配**
  - [ ] `_load_terminology` 方法：
    - 优先从数据库配置表加载（`system_configs` 表，key=`rag_terminology_list`）
    - 降级到本地 JSON 文件（`backend/src/data/terminology.json`）
    - 降级到内置默认词典（硬编码的 `set`，仅作为最后兜底）
  - [ ] `_match_terminology` 方法：
    - 使用最长匹配优先策略（避免"感统"和"感统训练"同时匹配）
    - 返回匹配到的术语列表
    - 复杂度 O(n*m)，n=术语数，m=查询长度，实际性能可忽略

- [ ] **Step 5: 编写单元测试**
  - [ ] 创建 `backend/tests/test_query_analyzer.py`
  - [ ] **测试用例 1：短查询识别**
    ```python
    def test_short_query_detection():
        analyzer = QueryAnalyzer()
        
        # 2 字查询
        result = analyzer.analyze("运动")
        assert result.query_type == QueryType.SHORT
        assert result.char_length == 2
        
        # 4 字查询
        result = analyzer.analyze("游戏")
        assert result.query_type == QueryType.SHORT
        assert result.char_length == 4
    ```
  - [ ] **测试用例 2：专业术语识别**
    ```python
    def test_terminology_detection():
        analyzer = QueryAnalyzer()
        
        result = analyzer.analyze("感统训练")
        assert result.query_type == QueryType.TERMINOLOGY
        assert result.has_terminology is True
        assert "感统训练" in result.matched_terminology
        
        result = analyzer.analyze("前庭觉")
        assert result.query_type == QueryType.TERMINOLOGY
        assert "前庭觉" in result.matched_terminology
    ```
  - [ ] **测试用例 3：描述性查询识别**
    ```python
    def test_descriptive_query_detection():
        analyzer = QueryAnalyzer()
        
        result = analyzer.analyze("3 岁儿童语言发展迟缓怎么办")
        assert result.query_type == QueryType.DESCRIPTIVE
        assert result.has_question_word is True
    ```
  - [ ] **测试用例 4：复杂查询识别**
    ```python
    def test_complex_query_detection():
        analyzer = QueryAnalyzer()
        
        result = analyzer.analyze("前庭觉训练和精细动作训练的区别")
        assert result.query_type == QueryType.COMPLEX
        assert result.has_conjunction is True
        assert result.char_length > 15
    ```
  - [ ] **测试用例 5：边界情况**
    ```python
    def test_edge_cases():
        analyzer = QueryAnalyzer()
        
        # 空查询
        result = analyzer.analyze("")
        assert result.char_length == 0
        assert result.query_type == QueryType.DEFAULT
        
        # 纯空格
        result = analyzer.analyze("   ")
        assert result.char_length == 0
        
        # 特殊字符（应被过滤，在 B-2 或 D-5 中处理，此处仅测试分析器不崩溃）
        result = analyzer.analyze("感统训练！！！")
        assert result.query_type in (QueryType.TERMINOLOGY, QueryType.DEFAULT)
    ```
  - [ ] **测试用例 6：置信度计算**
    ```python
    def test_confidence_calculation():
        analyzer = QueryAnalyzer()
        
        # 明确的专业术语，置信度应高
        result = analyzer.analyze("感统训练")
        assert result.confidence >= 0.8
        
        # 模糊查询，置信度应低
        result = analyzer.analyze("儿童训练方法")
        assert result.confidence < 0.8  # 可能命中多个类型
    ```

- [ ] **Step 6: 集成验证**
  - [ ] 在 `backend/src/core/hybrid_retrieval.py` 的 `get_dynamic_weights` 中临时调用 `QueryAnalyzer`，打印分类结果
  - [ ] 使用诊断测试的 8 个标注查询验证分类准确率：
    ```
    2 岁儿童前庭觉失调的表现      → 预期：DESCRIPTIVE 或 TERMINOLOGY
    婴幼儿精细动作训练方法        → 预期：TERMINOLOGY
    3 岁儿童语言发展迟缓怎么办    → 预期：DESCRIPTIVE
    感统训练                     → 预期：TERMINOLOGY
    运动                         → 预期：SHORT
    4 岁孩子注意力不集中怎么办    → 预期：DESCRIPTIVE
    前庭觉训练和精细动作训练的区别 → 预期：COMPLEX
    如何评估孩子的大动作发展水平  → 预期：DESCRIPTIVE 或 COMPLEX
    ```
  - [ ] 确认分类准确率 ≥87.5%（7/8 个查询正确分类）

## ✅ 验收标准

| 验收项 | 标准 | 验证方法 |
|--------|------|----------|
| 短查询识别 | <5 字查询 100% 识别为 SHORT | 单元测试 |
| 专业术语识别 | 术语词典中的词 100% 命中 | 单元测试 |
| 描述性查询识别 | 含疑问词 +5-15 字 识别为 DESCRIPTIVE | 单元测试 |
| 复杂查询识别 | >15 字 + 连接词 识别为 COMPLEX | 单元测试 |
| 诊断查询分类准确率 | ≥87.5%（7/8） | 集成验证 |
| 分析耗时 | 单次分析 <1ms | 性能测试 |

## 📁 涉及文件

| 文件 | 操作 | 说明 |
|------|------|------|
| `backend/src/core/rag/query_analyzer.py` | 新增 | 查询类型分析器 |
| `backend/src/data/terminology.json` | 新增 | 专业术语词典（初始版本） |
| `backend/tests/test_query_analyzer.py` | 新增 | 单元测试（6 个测试用例） |
| `backend/src/config/modules/rag/retrieval.py` | 可选修改 | 新增术语词典配置项 |

## ⚠️ 注意事项

1. **术语词典不要硬编码在代码中**，必须通过配置表或 JSON 文件加载，支持热更新
2. **分析器只负责分类，不负责权重决策**，权重决策在 B-2 中实现
3. **置信度仅用于调试和日志**，不影响权重决策逻辑（Phase B 不使用置信度）
4. **术语匹配使用最长匹配优先**，避免短术语覆盖长术语（如"感统"vs"感统训练"）

---

**返回索引：** [02-phase-b-00-overview.md](./02-phase-b-00-overview.md)
