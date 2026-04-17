# C-2: LLM 失败本地兜底策略

> **所属 Phase**: Phase C (P1)
> **任务类型**: 单一任务 — 构建高质量的本地同义词扩展兜底机制
> **对应问题**: 测试 12（LLM 失败时无本地兜底机制）+ 需求 4.5

## 🎯 目标

将当前简陋的 `_local_expand_synonyms` 方法升级为**基于领域词典 + 规则引擎**的高质量兜底策略，确保 LLM 不可用时仍能提供 ≥80% 成功率的同义词扩展。

## 📋 实施步骤

- [ ] **Step 1: 分析现有 `_local_expand_synonyms` 的不足**
  - [ ] 阅读 `src/service/retrieval_service.py` 第 1020-1038 行当前实现：
    ```python
    def _local_expand_synonyms(self, query: str) -> str:
        synonyms_dict = {
            "大运动": ["粗大动作", "运动能力", "平衡能力"],
            "精细动作": ["手眼协调", "手指灵活性"],
            "语言": ["表达能力", "沟通能力", "词汇量"],
            "认知": ["思维能力", "逻辑推理", "注意力"],  # ⚠️ "注意力" 与"认知"关联弱
            "社交": ["人际交往", "情绪管理", "同伴关系"],
            "专注力": ["注意力", "集中力"],
            "感统": ["感觉统合", "前庭觉", "触觉"],  # ⚠️ "前庭觉" 是子类，不是同义词
            "家长": ["父母", "家长教育", "家庭教育", "亲子", "育儿"],
        }
        # ... 简单子串匹配
    ```
  - [ ] 确认问题：
    - **词典规模小**：仅 8 个词条，覆盖率极低
    - **语义不精确**：部分扩展词不是真正的同义词（如"感统"→"前庭觉"是子类关系）
    - **匹配策略简单**：仅使用 `if word in query` 的子串匹配，无法处理组合查询
    - **无质量验证**：扩展后不验证结果质量

- [ ] **Step 2: 构建本地同义词词典**
  - [ ] 创建 `src/data/local_synonyms.json`，按**领域分类 + 同义词组**组织：
    ```json
    {
      "sensory_integration": {
        "感统": ["感觉统合", "感觉整合", "感官统合"],
        "前庭觉": ["前庭感", "平衡觉", "前庭系统", "vestibular"],
        "本体觉": ["本体感", "本体感觉", "proprioception"],
        "触觉": ["触觉系统", "触觉防御", "触觉敏感", "tactile"],
        "感觉统合": ["感统", "感觉整合", "感官统合"],
        "前庭觉训练": ["平衡训练", "前庭刺激", "前庭活动"],
        "本体觉训练": ["重力训练", "关节压力活动", "本体刺激"]
      },
      "motor_development": {
        "大运动": ["粗大动作", "大肌肉运动", "gross motor"],
        "精细动作": ["精细运动", "小肌肉", "手眼协调", "fine motor"],
        "大动作": ["粗大动作", "大肌肉运动", "全身运动"],
        "手眼协调": ["精细动作", "手眼配合", "抓握能力"],
        "平衡能力": ["平衡感", "前庭觉", "稳定性"]
      },
      "cognitive_development": {
        "注意力": ["专注力", "集中力", "注意力集中", "attention"],
        "专注力": ["注意力", "集中力", "专注"],
        "认知": ["认知能力", "认知发展", "思维能力"],
        "记忆力": ["记忆能力", "回忆能力", "memory"],
        "注意力训练": ["专注力训练", "集中力提升", "注意力提升"]
      },
      "language_development": {
        "语言": ["语言能力", "语言表达", "语言发展"],
        "表达": ["表达能力", "语言表达", "沟通能力"],
        "沟通": ["沟通能力", "交流能力", "社交沟通"]
      },
      "social_emotional": {
        "社交": ["社交能力", "人际交往", "社交技能", "social"],
        "情绪": ["情绪管理", "情绪调节", "情绪控制"],
        "情绪调节": ["情绪管理", "情绪控制", "自我安抚"]
      }
    }
    ```
  - [ ] **词典设计原则**：
    - 每个词条的扩展词必须是**真正的同义词或高度相关词**，不是上位词/下位词
    - 优先使用领域内的标准术语（如"感觉统合"而非"感觉"）
    - 包含中英文对照（如"attention"）
    - 初始词典覆盖诊断测试中的 3 个标注查询 + 常见查询场景（约 30 个词条）

- [ ] **Step 3: 实现 `LocalSynonymExpander` 类**
  - [ ] 创建新文件 `src/core/local_synonym_expander.py`
  - [ ] 实现核心类结构：
    ```python
    class LocalSynonymExpander:
        """本地同义词扩展器（LLM 失败时兜底）"""
        
        def __init__(self, synonyms_file: Optional[str] = None):
            self._synonyms_dict = self._load_synonyms(synonyms_file)
        
        def expand(self, query: str) -> List[str]:
            """
            扩展查询的同义词
            
            Args:
                query: 原始查询
                
            Returns:
                扩展后的同义词列表（包含原词）
            """
            result = {query}  # 必须包含原词
            
            # 策略 1：精确匹配
            matched = self._exact_match(query)
            result.update(matched)
            
            # 策略 2：子串匹配（查询包含词典中的词）
            matched = self._substring_match(query)
            result.update(matched)
            
            # 策略 3：分词匹配（对长查询分词后逐个匹配）
            if len(query) > 4:
                matched = self._tokenized_match(query)
                result.update(matched)
            
            # 去重并保持顺序
            return list(dict.fromkeys(result))
    ```
  - [ ] 实现 `_exact_match` 方法：
    ```python
    def _exact_match(self, query: str) -> Set[str]:
        """精确匹配：查询词完全等于词典中的键"""
        synonyms = set()
        
        for category, terms in self._synonyms_dict.items():
            if query in terms:
                synonyms.update(terms[query])
                break
            # 反向查找：查询词是否在某个词条的 value 中
            for key, values in terms.items():
                if query in values:
                    synonyms.add(key)  # 添加键
                    synonyms.update([v for v in values if v != query])
                    break
        
        return synonyms
    ```
  - [ ] 实现 `_substring_match` 方法：
    ```python
    def _substring_match(self, query: str) -> Set[str]:
        """子串匹配：查询包含词典中的词"""
        synonyms = set()
        
        for category, terms in self._synonyms_dict.items():
            for key, values in terms.items():
                if key in query and len(key) >= 2:  # 至少 2 字
                    synonyms.update(values)
        
        return synonyms
    ```
  - [ ] 实现 `_tokenized_match` 方法：
    ```python
    def _tokenized_match(self, query: str) -> Set[str]:
        """分词匹配：对长查询分词后逐个匹配"""
        synonyms = set()
        
        # 简单分词：按常见分割点切分
        # 对于中文，使用滑动窗口提取 2-4 字词组
        tokens = self._extract_ngrams(query, min_n=2, max_n=4)
        
        for token in tokens:
            for category, terms in self._synonyms_dict.items():
                if token in terms:
                    synonyms.update(terms[token])
        
        return synonyms
    
    @staticmethod
    def _extract_ngrams(text: str, min_n: int = 2, max_n: int = 4) -> List[str]:
        """提取 n-gram 词组"""
        tokens = []
        for n in range(min_n, max_n + 1):
            for i in range(len(text) - n + 1):
                tokens.append(text[i:i+n])
        return tokens
    ```

- [ ] **Step 4: 集成到 `_expand_synonyms` 流程**
  - [ ] 阅读 `src/service/retrieval_service.py` 第 1020-1038 行当前 `_local_expand_synonyms`
  - [ ] 替换为调用 `LocalSynonymExpander`：
    ```python
    def _local_expand_synonyms(self, query: str) -> str:
        """本地同义词扩展兜底逻辑"""
        if not self._local_expander:
            # 如果 expander 未初始化，使用极简兜底
            return query
        
        synonyms = self._local_expander.expand(query)
        
        # 质量验证（复用 C-1 的验证器）
        if self._synonym_validator:
            report = self._synonym_validator.validate(synonyms, query)
            synonyms = report.valid_terms
        
        return " ".join(synonyms)
    ```
  - [ ] 在 `RetrievalService.__init__` 中初始化 `LocalSynonymExpander`：
    ```python
    from src.core.local_synonym_expander import LocalSynonymExpander
    self._local_expander = LocalSynonymExpander()
    ```

- [ ] **Step 5: 优化 LLM Prompt（减少失败率）**
  - [ ] 阅读 `src/core/prompts_fallback.py` 第 33-58 行的 `SYNONYM_EXPANSION_PROMPT`
  - [ ] 当前 Prompt 已包含严格的 JSON 格式约束，但缺少**领域约束**和**负面示例**
  - [ ] 在 Prompt 中新增以下约束（通过数据库更新提示词，同步更新 fallback 文件）：
    ```
    【领域约束】
    - 同义词必须属于儿童发展/感统训练/脑科学/教育心理学领域
    - 禁止扩展为上位词（如"感统"→"感觉"）、下位词（如"感统"→"前庭觉"）
    - 禁止扩展为不相关领域词汇（如"注意力"→"视力"、"记忆力"）
    
    【负面示例】
    - ❌ 错误："注意力" → ["视力", "听力", "记忆力"]（不相关领域）
    - ❌ 错误："感统" → ["感觉", "统合"]（太宽泛的上位词）
    - ❌ 错误："精细动作" → ["动作", "肌肉"]（太宽泛的上位词）
    - ✅ 正确："注意力" → ["专注力", "集中力", "注意力集中"]
    - ✅ 正确："感统" → ["感觉统合", "感觉整合", "感官统合"]
    ```

- [ ] **Step 6: 编写单元测试**
  - [ ] 创建 `tests/test_local_synonym_expander.py`
  - [ ] **测试用例 1：精确匹配**
    ```python
    def test_exact_match():
        expander = LocalSynonymExpander()
        
        synonyms = expander.expand("注意力")
        assert "专注力" in synonyms
        assert "集中力" in synonyms
        assert "注意力" in synonyms  # 必须包含原词
    
    def test_exact_match_terminology():
        expander = LocalSynonymExpander()
        
        synonyms = expander.expand("感统")
        assert "感觉统合" in synonyms
        assert "感觉整合" in synonyms
        assert "感官统合" in synonyms
    ```
  - [ ] **测试用例 2：子串匹配**
    ```python
    def test_substring_match():
        expander = LocalSynonymExpander()
        
        # 查询包含"精细动作"
        synonyms = expander.expand("精细动作训练方法")
        assert "手眼协调" in synonyms
        assert "精细运动" in synonyms
    ```
  - [ ] **测试用例 3：分词匹配**
    ```python
    def test_tokenized_match():
        expander = LocalSynonymExpander()
        
        # 长查询："孩子注意力不集中怎么办"
        synonyms = expander.expand("孩子注意力不集中怎么办")
        assert "专注力" in synonyms
        assert "集中力" in synonyms
    ```
  - [ ] **测试用例 4：兜底成功率验证**
    ```python
    def test_fallback_success_rate():
        """验证本地兜底对常见查询的成功率 ≥80%"""
        expander = LocalSynonymExpander()
        
        test_queries = [
            "注意力", "感统", "精细动作", "大运动", "前庭觉",
            "本体觉", "触觉", "语言", "认知", "社交",
            "专注力", "情绪调节", "平衡能力", "手眼协调"
        ]
        
        success_count = 0
        for query in test_queries:
            synonyms = expander.expand(query)
            # 成功标准：至少返回原词 + 1 个扩展词
            if len(synonyms) >= 2:
                success_count += 1
        
        rate = success_count / len(test_queries)
        assert rate >= 0.8, f"本地兜底成功率 {rate:.2%} < 80%"
    ```
  - [ ] **测试用例 5：诊断查询验证**
    ```python
    def test_diagnosis_queries():
        """验证诊断测试中的 3 个标注查询"""
        expander = LocalSynonymExpander()
        
        # 注意力
        synonyms = expander.expand("注意力")
        assert "专注力" in synonyms
        assert "集中力" in synonyms
        assert "视力" not in synonyms  # 不应出现
        assert "听力" not in synonyms
        
        # 感统
        synonyms = expander.expand("感统")
        assert "感觉统合" in synonyms
        assert "感觉整合" in synonyms
        assert "感觉" not in synonyms  # 太宽泛
        assert "统合" not in synonyms
        
        # 精细动作
        synonyms = expander.expand("精细动作")
        assert "手眼协调" in synonyms
        assert "小肌肉" in synonyms
        assert "动作" not in synonyms  # 太宽泛
        assert "肌肉" not in synonyms
    ```

- [ ] **Step 7: 集成验证**
  - [ ] 模拟 LLM 不可用场景（设置 `dashscope_available=False`），运行诊断测试：
    ```bash
    cd backend && uv run pytest tests/diagnose_rag_comprehensive_v2.py -v -k "test_12_synonym"
    ```
  - [ ] 确认本地兜底对 3 个标注查询的扩展质量：
    | 查询 | 期望扩展词 | 不应扩展词 | 结果 |
    |------|-----------|-----------|------|
    | 注意力 | 专注力、集中力 | 视力、听力 | 待验证 |
    | 感统 | 感觉统合、感觉整合 | 感觉、统合 | 待验证 |
    | 精细动作 | 手眼协调、小肌肉 | 动作、肌肉 | 待验证 |
  - [ ] 确认本地兜底成功率 ≥80%（14 个常见查询中至少 12 个成功扩展）

## ✅ 验收标准

| 验收项 | 标准 | 验证方法 |
|--------|------|----------|
| 精确匹配 | 词典中的词 100% 精确匹配 | 单元测试 |
| 子串匹配 | 查询包含词典词时正确扩展 | 单元测试 |
| 分词匹配 | 长查询能提取有效同义词 | 单元测试 |
| 本地兜底成功率 | ≥80%（14 个常见查询） | 单元测试 |
| 诊断查询质量 | 3 个标注查询扩展词无噪声 | 集成验证 |
| 与验证器集成 | 本地扩展结果通过 C-1 验证器过滤 | 集成验证 |

## 📁 涉及文件

| 文件 | 操作 | 说明 |
|------|------|------|
| `src/core/local_synonym_expander.py` | 新增 | 本地同义词扩展器 |
| `src/data/local_synonyms.json` | 新增 | 本地同义词词典（约 30 词条） |
| `src/service/retrieval_service.py` | 修改 | 替换 `_local_expand_synonyms` 实现 |
| `src/core/prompts_fallback.py` | 修改 | 优化 `SYNONYM_EXPANSION_PROMPT`（新增领域约束和负面示例） |
| `tests/test_local_synonym_expander.py` | 新增 | 单元测试（5 个测试用例） |

### Step 5 补充：Prompt 数据库更新流程

**重要**: 根据 CLAUDE.md 配置管理规范，所有提示词变更必须通过数据库完成，禁止直接修改 `prompts_fallback.py` 文件。`prompts_fallback.py` 仅作为初始化和降级兜底使用。

**更新流程**:

1. **通过系统配置页面或 SQL 脚本更新**:
```sql
-- 更新 synonym_expansion 提示词
UPDATE prompt_templates
SET content = '<完整优化后的 Prompt 内容>',
    version = version + 1,
    updated_at = NOW(),
    updated_by = 'rag-search-optimization-phase-c',
    change_log = '新增领域约束和负面示例，减少不相关同义词生成'
WHERE prompt_key = 'synonym_expansion';
```

2. **同步更新 fallback 文件** (仅作为代码初始值，运行时以数据库为准):
   - 修改 `src/core/prompts_fallback.py` 中的 `SYNONYM_EXPANSION_PROMPT`
   - 确保与数据库内容一致
   - 下次系统初始化时，若数据库无记录，会从 fallback 文件导入

3. **验证 Prompt 更新生效**:
```bash
# 通过 API 验证当前生效的 Prompt 内容
curl http://localhost:8000/api/system-config/prompts/synonym_expansion

# 确认返回内容包含新增的【领域约束】和【负面示例】部分
```

**Prompt 新增内容** (追加到现有【强制约束】之后):

```
【领域约束】
- 同义词必须属于儿童发展/感统训练/脑科学/教育心理学领域
- 禁止扩展为上位词（如"感统"→"感觉"）、下位词（如"感统"→"前庭觉"）
- 禁止扩展为不相关领域词汇（如"注意力"→"视力"、"记忆力"）

【负面示例】
- ❌ 错误："注意力" → ["视力", "听力", "记忆力"]（不相关领域）
- ❌ 错误："感统" → ["感觉", "统合"]（太宽泛的上位词）
- ❌ 错误："精细动作" → ["动作", "肌肉"]（太宽泛的上位词）
- ✅ 正确："注意力" → ["专注力", "集中力", "注意力集中"]
- ✅ 正确："感统" → ["感觉统合", "感觉整合", "感官统合"]
- ✅ 正确："精细动作" → ["手眼协调", "小肌肉", "精细运动"]
```

### Step 2 补充：本地词典维护策略

本地同义词词典 (`local_synonyms.json`) 的维护遵循以下原则：

1. **初始规模**: 覆盖 5 大领域约 30 个词条，确保诊断测试 3 个标注查询 + 14 个常见查询的兜底成功率 ≥80%

2. **扩展策略**:
   - 通过 `rag_synonym_log_rejected` 配置记录被验证器拒绝的 LLM 生成词
   - 定期分析日志，将高频出现的"有效但被误拒"的词加入本地词典
   - 通过 `rag_local_synonyms_dict` 配置项动态更新，无需发版

3. **质量控制**:
   - 每个词条的扩展词必须是**真正的同义词或高度相关词**
   - 禁止包含上位词（如"动作"）或下位词（如"前庭觉"）
   - 优先使用领域标准术语（如"感觉统合"而非"感觉"）
   - 包含中英文对照（如"attention"）便于检索

4. **加载策略** (与验证器一致的三级降级):
```python
def _load_synonyms(self, synonyms_file: Optional[str] = None) -> dict:
    """加载本地同义词词典，三级降级"""
    # 优先级 1：从数据库 system_configs 表加载
    try:
        from src.core.database import get_config
        config_value = get_config('rag_local_synonyms_dict')
        if config_value:
            import json
            return json.loads(config_value)
    except Exception as e:
        logger.warning(f"从数据库加载本地同义词词典失败: {e}")
    
    # 优先级 2：从本地 JSON 文件加载
    try:
        file_path = synonyms_file or str(
            Path(__file__).parent.parent / "data" / "local_synonyms.json"
        )
        if Path(file_path).exists():
            import json
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        logger.warning(f"从本地文件加载本地同义词词典失败: {e}")
    
    # 优先级 3：返回空词典（仅保留原词）
    return {}
```

### Step 4 补充：与 Phase A/B/D 的集成点

| 集成 Phase | 集成方式 | 说明 |
|------------|----------|------|
| **Phase A** | 无直接依赖 | Phase C 兜底策略独立于分数语义重构 |
| **Phase B** | 复用专业术语词库 | Phase B 的 `QueryAnalyzer` 维护的专业术语词库可作为本地词典的补充来源 |
| **Phase D** | 边界场景协同 | Phase D 处理空查询/特殊字符查询后，若查询被清洗为空字符串，直接跳过同义词扩展 |

**与 Phase D 集成的具体方式**:
```python
# Phase D 的输入校验在同义词扩展之前执行
async def _expand_synonyms(self, query: str) -> str:
    # Phase D: 输入校验与预处理
    query = self._boundary_handler.validate_and_clean(query)
    if not query:  # 空查询或无效查询
        return ""
    
    # Phase C: 正常的同义词扩展与兜底流程
    # ...
```

## ✅ 验收标准

| 验收项 | 标准 | 验证方法 |
|--------|------|----------|
| 精确匹配 | 词典中的词 100% 精确匹配 | 单元测试 |
| 子串匹配 | 查询包含词典词时正确扩展 | 单元测试 |
| 分词匹配 | 长查询能提取有效同义词 | 单元测试 |
| 本地兜底成功率 | ≥80%（14 个常见查询） | 单元测试 |
| 诊断查询质量 | 3 个标注查询扩展词无噪声 | 集成验证 |
| 与验证器集成 | 本地扩展结果通过 C-1 验证器过滤 | 集成验证 |
| Prompt 更新生效 | 数据库更新后 LLM 输出质量提升 | 手动验证 |
| 配置加载降级 | 数据库不可用时自动降级到 JSON 文件 | 单元测试 |

## 📁 涉及文件

| 文件 | 操作 | 说明 |
|------|------|------|
| `src/core/rag/local_synonym_expander.py` | 新增 | 本地同义词扩展器 |
| `src/data/local_synonyms.json` | 新增 | 本地同义词词典（约 30 词条，本地降级文件） |
| `src/service/retrieval_service.py` | 修改 | 替换 `_local_expand_synonyms` 实现 |
| `src/core/prompts_fallback.py` | 修改 | 优化 `SYNONYM_EXPANSION_PROMPT`（新增领域约束和负面示例） |
| `src/config/settings.py` | 修改 | 新增 `rag_local_synonyms_dict` 等配置项 |
| `tests/test_local_synonym_expander.py` | 新增 | 单元测试（7 个测试用例，含 1 个降级测试） |

## ⚠️ 注意事项

1. **本地词典必须通过配置管理**，禁止硬编码在扩展器代码中
2. **本地扩展是兜底策略**，主要依赖 LLM 扩展，本地仅保证 LLM 失败时不崩溃
3. **本地扩展结果必须经过 C-1 验证器过滤**，确保质量
4. **Prompt 优化通过数据库更新**，同步更新 fallback 文件，禁止直接修改 fallback 文件作为唯一手段
5. **本 Phase 不涉及查询重写**，复杂查询的意图提取在 Phase D 的边界场景处理中
6. **本地扩展器必须支持三级降级加载**：数据库 → 本地 JSON → 空词典
7. **词典维护是持续过程**，通过分析被拒词日志不断优化词典覆盖范围

---

**返回索引：** [03-phase-c-00-overview.md](./03-phase-c-00-overview.md)
