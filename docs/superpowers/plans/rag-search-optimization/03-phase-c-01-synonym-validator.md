# C-1: 同义词质量验证器

> **所属 Phase**: Phase C (P1)
> **任务类型**: 单一任务 — 构建严格的多维度同义词质量验证器
> **对应问题**: 测试 12（同义词扩展引入噪声：如"注意力"扩展出"视力"、"感统"扩展出"感觉"）

## 🎯 目标

替换当前仅做格式检查的 `_validate_expansion` 方法，构建基于**领域词典 + 语义相关性 + 粒度控制**的多维度同义词验证器，确保扩展词不引入不相关或太宽泛的词汇。

## 📋 实施步骤

- [ ] **Step 1: 分析现有 `_validate_expansion` 的不足**
  - [ ] 阅读 `backend/src/service/retrieval_service.py` 第 876-910 行的 `_validate_expansion` 方法
  - [ ] 确认当前验证规则：
    ```python
    # 1. 长度检查：不应超过 200 字符
    # 2. 格式检查：不应包含完整句子（句号、感叹号、问号、冒号）
    # 3. 必须包含原查询
    # 4. 不应包含敏感词或无关内容（"抱歉"、"无法"、"不知道"等）
    ```
  - [ ] 确认缺失的验证维度：
    - **无领域相关性检查**：不验证扩展词是否属于儿童发展/感统训练领域
    - **无粒度控制**：不检测扩展词是否比原词太宽泛（如"感统"→"感觉"）
    - **无不相关词过滤**：不检测扩展词是否与原始查询语义偏离（如"注意力"→"视力"）
    - **无黑名单机制**：没有已知的"不应扩展"词列表

- [ ] **Step 2: 构建领域验证词典**
  - [ ] 创建 `backend/src/data/synonym_validation.json`，包含以下结构：
    ```json
    {
      "domain_terms": {
        "注意力": {
          "valid": ["专注力", "集中力", "注意力集中", "注意广度"],
          "invalid": ["视力", "听力", "观察力", "记忆力", "想象力"],
          "too_broad": ["注意", "力"]
        },
        "感统": {
          "valid": ["感觉统合", "感觉整合", "感官统合", "sensory integration"],
          "invalid": ["感觉", "统合", "感官", "感觉系统"],
          "too_broad": ["感", "统"]
        },
        "精细动作": {
          "valid": ["小肌肉", "手眼协调", "手指灵活", "精细运动", "小肌肉群"],
          "invalid": ["动作", "精细", "肌肉", "运动"],
          "too_broad": ["精细", "动作"]
        }
      },
      "domain_whitelist": [
        "前庭觉", "本体觉", "触觉", "大动作", "精细动作", "语言发展",
        "认知发展", "社交技能", "注意力", "专注力", "感统", "感觉统合",
        "平衡感", "协调性", "手眼协调", "核心力量", "情绪调节",
        "视觉追踪", "听觉辨别", "触觉防御", "重力不安全感"
      ],
      "domain_blacklist": [
        "视力", "听力", "嗅觉", "味觉", "记忆力", "想象力",
        "创造力", "逻辑思维", "数学能力", "阅读能力"
      ]
    }
    ```
  - [ ] **词典加载策略**：
    - 优先从数据库配置表加载（`system_configs` 表，key=`rag_synonym_validation_rules`）
    - 降级到本地 JSON 文件
    - 降级到空词典（仅使用通用规则）

- [ ] **Step 3: 实现 `SynonymValidator` 类**
  - [ ] 创建新文件 `backend/src/core/rag/synonym_validator.py`
  - [ ] 实现核心类结构：
    ```python
    @dataclass
    class ValidationReport:
        is_valid: bool                    # 整体是否通过
        valid_terms: List[str]            # 通过的词
        rejected_terms: List[Tuple[str, str]]  # (被拒词, 拒绝原因)
        confidence: float                 # 验证置信度 (0-1)

    class SynonymValidator:
        """同义词质量验证器"""
        
        def __init__(self, validation_file: Optional[str] = None):
            self._validation_rules = self._load_rules(validation_file)
        
        def validate(
            self,
            synonym_list: List[str],
            original_query: str,
        ) -> ValidationReport:
            """验证同义词列表质量"""
            valid_terms = []
            rejected_terms = []
            
            for term in synonym_list:
                if term == original_query:
                    valid_terms.append(term)
                    continue
                
                reason = self._check_term(term, original_query)
                if reason is None:
                    valid_terms.append(term)
                else:
                    rejected_terms.append((term, reason))
            
            # 计算置信度
            total = len(synonym_list)
            valid_count = len(valid_terms)
            confidence = valid_count / total if total > 0 else 0.0
            
            return ValidationReport(
                is_valid=confidence >= 0.8,  # 80% 以上通过即认为有效
                valid_terms=valid_terms,
                rejected_terms=rejected_terms,
                confidence=confidence,
            )
    ```
  - [ ] 实现 `_check_term` 方法，按优先级执行以下检查：
    ```python
    def _check_term(self, term: str, original_query: str) -> Optional[str]:
        """检查单个扩展词，返回 None 表示通过，否则返回拒绝原因"""
        
        # 检查 1：长度合理性（1 字太短，>15 字太长）
        if len(term) < 2:
            return "太短（单字）"
        if len(term) > 15:
            return "太长（超过 15 字）"
        
        # 检查 2：字符类型（仅允许中英文、数字）
        if not re.match(r'^[\u4e00-\u9fa5a-zA-Z0-9\s]+$', term):
            return "包含非法字符"
        
        # 检查 3：黑名单过滤（已知不相关词）
        if term in self._validation_rules.get("domain_blacklist", []):
            return "在黑名单中（不相关领域）"
        
        # 检查 4：粒度控制 — 不应比原词太宽泛
        if self._is_too_broad(term, original_query):
            return "太宽泛（粒度不如原词）"
        
        # 检查 5：领域白名单优先通过
        if term in self._validation_rules.get("domain_whitelist", []):
            return None
        
        # 检查 6：原词专属规则
        if self._matches_query_specific_rule(term, original_query):
            return None
        
        # 检查 7：语义相关性 — 至少包含原词的一个字（中文）或一个词根（英文）
        if not self._has_semantic_overlap(term, original_query):
            return "与原词语义无重叠"
        
        # 通过所有检查
        return None
    ```
  - [ ] 实现 `_is_too_broad` 方法：
    ```python
    def _is_too_broad(self, term: str, original_query: str) -> bool:
        """判断扩展词是否比原词太宽泛"""
        # 规则 1：检查专属规则中的 too_broad 列表
        query_rules = self._validation_rules.get("domain_terms", {}).get(original_query, {})
        if term in query_rules.get("too_broad", []):
            return True
        
        # 规则 2：原词包含扩展词，但扩展词是常见上位词
        # 例如："精细动作" 包含 "动作"，"动作" 是上位词
        if len(term) < len(original_query) and term in original_query:
            # 如果扩展词是原词的一个子串，且长度差 ≥2，判定为太宽泛
            if len(original_query) - len(term) >= 2:
                return True
        
        # 规则 3：扩展词在领域白名单中但原词不在，且扩展词比原词短很多
        whitelist = self._validation_rules.get("domain_whitelist", [])
        if term in whitelist and original_query not in whitelist:
            if len(term) <= len(original_query) * 0.5:
                return True
        
        return False
    ```
  - [ ] 实现 `_has_semantic_overlap` 方法：
    ```python
    def _has_semantic_overlap(self, term: str, original_query: str) -> bool:
        """检查扩展词与原词是否有语义重叠"""
        # 中文：至少共享一个字符
        if re.search(r'[\u4e00-\u9fa5]', original_query):
            shared_chars = set(term) & set(original_query)
            if shared_chars:
                return True
        
        # 英文：至少共享一个词根（3 字母以上）
        if re.search(r'[a-zA-Z]', original_query):
            term_words = set(re.findall(r'[a-zA-Z]{3,}', term.lower()))
            query_words = set(re.findall(r'[a-zA-Z]{3,}', original_query.lower()))
            if term_words & query_words:
                return True
        
        return False
    ```
  - [ ] 实现 `_matches_query_specific_rule` 方法：
    ```python
    def _matches_query_specific_rule(self, term: str, original_query: str) -> bool:
        """检查是否匹配原词专属规则中的 valid 列表"""
        query_rules = self._validation_rules.get("domain_terms", {}).get(original_query, {})
        valid_terms = query_rules.get("valid", [])
        return term in valid_terms
    ```

- [ ] **Step 4: 集成到 `_expand_synonyms` 流程**
  - [ ] 阅读 `backend/src/service/retrieval_service.py` 第 912-1018 行的 `_expand_synonyms` 方法
  - [ ] 在 LLM 返回解析后（第 988-1006 行之间），插入验证逻辑：
    ```python
    # 原代码（第 1005-1006 行）：
    # all_terms = list(dict.fromkeys(synonym_list))
    # expanded_query = " ".join(all_terms)
    
    # 替换为：
    all_terms = list(dict.fromkeys(synonym_list))
    
    # 质量验证（新增）
    if self._synonym_validator:
        report = self._synonym_validator.validate(all_terms, query)
        
        if not report.is_valid:
            logger.warning(
                f"同义词质量验证未通过：{len(report.rejected_terms)} 个词被拒绝，"
                f"原因：{report.rejected_terms[:3]}"
            )
            # 过滤掉被拒绝的词，仅保留有效词
            all_terms = report.valid_terms
            
            # 如果过滤后只剩原词，说明扩展质量太差，回退到本地扩展
            if len(all_terms) <= 1:
                logger.warning("同义词质量验证后无有效扩展词，使用本地扩展")
                return self._local_expand_synonyms(query)
        
        logger.info(
            f"同义词验证通过：{len(report.valid_terms)} 个有效词，"
            f"{len(report.rejected_terms)} 个被过滤"
        )
    
    expanded_query = " ".join(all_terms)
    ```
  - [ ] 在 `RetrievalService.__init__` 中初始化 `SynonymValidator`：
    ```python
    from backend.src.core.synonym_validator import SynonymValidator
    self._synonym_validator = SynonymValidator()
    ```

- [ ] **Step 5: 编写单元测试**
  - [ ] 创建 `backend/tests/test_synonym_validator.py`
  - [ ] **测试用例 1：黑名单过滤**
    ```python
    def test_blacklist_rejection():
        validator = SynonymValidator()
        report = validator.validate(
            ["注意力", "专注力", "集中力", "视力", "听力"],
            original_query="注意力"
        )
        assert "视力" in [t for t, _ in report.rejected_terms]
        assert "听力" in [t for t, _ in report.rejected_terms]
        assert "专注力" in report.valid_terms
    ```
  - [ ] **测试用例 2：粒度控制**
    ```python
    def test_granularity_control():
        validator = SynonymValidator()
        
        # "感统" → "感觉" 应被拒绝（太宽泛）
        report = validator.validate(
            ["感统", "感觉统合", "感觉", "感官统合"],
            original_query="感统"
        )
        assert "感觉" in [t for t, _ in report.rejected_terms]
        assert "感觉统合" in report.valid_terms
        
        # "精细动作" → "动作" 应被拒绝
        report = validator.validate(
            ["精细动作", "手眼协调", "动作", "肌肉"],
            original_query="精细动作"
        )
        assert "动作" in [t for t, _ in report.rejected_terms]
        assert "肌肉" in [t for t, _ in report.rejected_terms]
    ```
  - [ ] **测试用例 3：白名单优先通过**
    ```python
    def test_whitelist_pass():
        validator = SynonymValidator()
        report = validator.validate(
            ["注意力", "前庭觉", "本体觉", "平衡感"],
            original_query="注意力"
        )
        assert "前庭觉" in report.valid_terms
        assert "本体觉" in report.valid_terms
    ```
  - [ ] **测试用例 4：语义重叠检查**
    ```python
    def test_semantic_overlap():
        validator = SynonymValidator()
        
        # 无重叠应被拒绝
        report = validator.validate(
            ["注意力", "数学能力", "阅读能力"],
            original_query="注意力"
        )
        assert "数学能力" in [t for t, _ in report.rejected_terms]
    ```
  - [ ] **测试用例 5：验证通过率计算**
    ```python
    def test_validation_confidence():
        validator = SynonymValidator()
        
        # 80% 通过 → is_valid=True
        report = validator.validate(
            ["注意力", "专注力", "集中力", "视力"],  # 3/4 = 75%
            original_query="注意力"
        )
        assert report.confidence == pytest.approx(0.75, abs=0.01)
        
        # 75% < 80% → is_valid=False
        assert report.is_valid is False
    ```
  - [ ] **测试用例 6：边界情况**
    ```python
    def test_edge_cases():
        validator = SynonymValidator()
        
        # 单字应被拒绝
        report = validator.validate(["感统", "感", "统"], original_query="感统")
        assert "感" in [t for t, _ in report.rejected_terms]
        assert "统" in [t for t, _ in report.rejected_terms]
        
        # 超长词应被拒绝
        report = validator.validate(
            ["注意力", "这是一个非常非常长的同义词超过了十五个字"],
            original_query="注意力"
        )
        assert len([t for t, _ in report.rejected_terms if "长" in t[1]]) > 0
        
        # 特殊字符应被拒绝
        report = validator.validate(
            ["注意力", "专注力!!!", "集中力"],
            original_query="注意力"
        )
        assert "专注力!!!" in [t for t, _ in report.rejected_terms]
    ```

- [ ] **Step 6: 集成验证**
  - [ ] 使用诊断测试的 3 个标注查询验证过滤效果：
    ```
    查询"注意力"：
      - 应通过：专注力、集中力、注意力集中
      - 应拒绝：视力、听力、观察力
    
    查询"感统"：
      - 应通过：感觉统合、感觉整合、感官统合
      - 应拒绝：感觉、统合、感官
    
    查询"精细动作"：
      - 应通过：小肌肉、手眼协调、手指灵活
      - 应拒绝：动作、精细、肌肉
    ```
  - [ ] 确认验证通过率 ≥95%（即不应扩展的词 100% 被拒绝）

## ✅ 验收标准

| 验收项 | 标准 | 验证方法 |
|--------|------|----------|
| 黑名单过滤 | 已知不相关词 100% 被拒绝 | 单元测试 |
| 粒度控制 | 太宽泛的词 100% 被拒绝 | 单元测试 |
| 白名单优先 | 领域白名单词直接通过 | 单元测试 |
| 语义重叠 | 与原词无重叠的词被拒绝 | 单元测试 |
| 诊断测试通过率 | ≥95% | 集成验证 |
| 验证耗时 | 单次验证 <1ms | 性能测试 |

## 📁 涉及文件

| 文件 | 操作 | 说明 |
|------|------|------|
| `backend/src/core/rag/synonym_validator.py` | 新增 | 同义词质量验证器 |
| `backend/src/data/synonym_validation.json` | 新增 | 验证规则词典 |
| `backend/src/service/retrieval_service.py` | 修改 | 集成验证器到 `_expand_synonyms` 流程 |
| `backend/tests/test_synonym_validator.py` | 新增 | 单元测试（6 个测试用例） |

### Step 2 补充：配置加载策略细节

验证规则词典采用**三级降级加载**，确保系统在任何环境下都能正常运行：

```python
def _load_rules(self, validation_file: Optional[str] = None) -> dict:
    """加载验证规则，三级降级"""
    # 优先级 1：从数据库 system_configs 表加载
    try:
        from src.core.database import get_config
        config_value = get_config('rag_synonym_validation_rules')
        if config_value:
            import json
            rules = json.loads(config_value)
            logger.info("同义词验证规则从数据库加载成功")
            return rules
    except Exception as e:
        logger.warning(f"从数据库加载同义词验证规则失败: {e}")
    
    # 优先级 2：从本地 JSON 文件加载
    try:
        file_path = validation_file or str(
            Path(__file__).parent.parent / "data" / "synonym_validation.json"
        )
        if Path(file_path).exists():
            import json
            with open(file_path, 'r', encoding='utf-8') as f:
                rules = json.load(f)
            logger.info(f"同义词验证规则从本地文件加载成功: {file_path}")
            return rules
    except Exception as e:
        logger.warning(f"从本地文件加载同义词验证规则失败: {e}")
    
    # 优先级 3：返回空词典（仅使用通用规则）
    logger.warning("使用空验证规则词典，仅启用通用检查（长度/字符/语义重叠）")
    return {
        "domain_terms": {},
        "domain_whitelist": [],
        "domain_blacklist": []
    }
```

### Step 3 补充：性能优化

验证器单次调用耗时目标 **<1ms**，实现策略：

1. **黑名单/白名单使用 set 存储**：O(1) 查找复杂度
2. **专属规则使用 dict 索引**：O(1) 查找复杂度
3. **语义重叠检查使用 set 交集**：避免循环比较
4. **初始化时预编译正则表达式**：避免每次调用重复编译

```python
# __init__ 中预编译
self._chinese_pattern = re.compile(r'[\u4e00-\u9fa5]')
self._valid_char_pattern = re.compile(r'^[\u4e00-\u9fa5a-zA-Z0-9\s]+$')

# 初始化时转换为 set
self._blacklist_set = set(self._validation_rules.get("domain_blacklist", []))
self._whitelist_set = set(self._validation_rules.get("domain_whitelist", []))
```

### Step 4 补充：与 Phase A/B/D 的集成点

| 集成 Phase | 集成方式 | 说明 |
|------------|----------|------|
| **Phase A** | 无直接依赖 | Phase C 验证器独立于分数语义重构，可独立部署验证 |
| **Phase B** | 复用领域词库 | Phase B 的 `QueryAnalyzer` 维护专业术语词库，Phase C 验证器可复用此词库作为白名单补充 |
| **Phase D** | 边界场景协同 | Phase D 的超长查询意图提取结果作为 `original_query` 传入验证器，避免对提取后的短意图做过度扩展 |

**与 Phase B 集成的具体方式**:
```python
# 在 SynonymValidator 初始化时，可选择性注入 Phase B 的领域词库
def __init__(
    self, 
    validation_file: Optional[str] = None,
    domain_terms_from_analyzer: Optional[List[str]] = None,
):
    self._validation_rules = self._load_rules(validation_file)
    
    # 合并 Phase B 提供的专业术语词库
    if domain_terms_from_analyzer:
        existing_whitelist = set(self._validation_rules.get("domain_whitelist", []))
        existing_whitelist.update(domain_terms_from_analyzer)
        self._validation_rules["domain_whitelist"] = list(existing_whitelist)
```

**与 Phase D 集成的具体方式**:
```python
# Phase D 的边界处理器提取意图后，调用同义词扩展
# 使用提取后的意图作为 original_query，而非原始超长查询
async def _expand_synonyms(self, query: str) -> str:
    # Phase D: 超长查询意图提取
    if len(query) > 50:
        query = await self._boundary_handler.extract_intent(query)
    
    # Phase C: 正常的同义词扩展与验证流程
    # ...
```

## ✅ 验收标准

| 验收项 | 标准 | 验证方法 |
|--------|------|----------|
| 黑名单过滤 | 已知不相关词 100% 被拒绝 | 单元测试 |
| 粒度控制 | 太宽泛的词 100% 被拒绝 | 单元测试 |
| 白名单优先 | 领域白名单词直接通过 | 单元测试 |
| 语义重叠 | 与原词无重叠的词被拒绝 | 单元测试 |
| 诊断测试通过率 | ≥95% | 集成验证 |
| 验证耗时 | 单次验证 <1ms | 性能测试 |
| 配置加载降级 | 数据库不可用时自动降级到 JSON 文件 | 单元测试 |
| 空词典降级 | 所有配置不可用时仍启用通用检查 | 单元测试 |

## 📁 涉及文件

| 文件 | 操作 | 说明 |
|------|------|------|
| `backend/src/core/rag/synonym_validator.py` | 新增 | 同义词质量验证器 |
| `backend/src/data/synonym_validation.json` | 新增 | 验证规则词典（本地降级文件） |
| `backend/src/service/retrieval_service.py` | 修改 | 集成验证器到 `_expand_synonyms` 流程 |
| `backend/src/config/settings.py` | 修改 | 新增 `rag_synonym_quality_threshold` 等配置项 |
| `backend/tests/test_synonym_validator.py` | 新增 | 单元测试（8 个测试用例，含 2 个降级测试） |

## ⚠️ 注意事项

1. **验证器只负责过滤，不负责生成**，生成逻辑在 LLM 或本地兜底中
2. **被拒绝的词应记录日志**，便于后续优化词典（通过 `rag_synonym_log_rejected` 配置控制）
3. **验证通过率阈值 80%** 是经验值，通过 `rag_synonym_quality_threshold` 配置项可调
4. **领域词典必须通过配置管理**，禁止硬编码在验证器代码中
5. **本步骤不改变 LLM Prompt**，Prompt 优化在 C-2 中处理
6. **验证器必须支持三级降级加载**：数据库 → 本地 JSON → 空词典
7. **初始化时预编译正则和转换 set**，确保单次验证耗时 <1ms

---

**返回索引：** [03-phase-c-00-overview.md](./03-phase-c-00-overview.md)
