# P1 级别修复：提示词迁移 + 12 种认知维度矩阵

**优先级**: 🟡 重要  
**工作量**: 4h  

---

## 一、P1-1：迁移 3 处绕过 PromptManager 的代码

### 1.1 问题描述

**现状**：3 处业务代码直接导入 `prompts_fallback.py`，绕过了 `PromptManager` 的版本管理、缓存、A/B 测试能力。

| 文件 | 行号 | 当前代码 |
|------|------|----------|
| `backend/src/core/nodes/retrieval.py` | L4 | `from src.core.prompts_fallback import RAG_QUERY_TEMPLATE` |
| `backend/src/service/rag_test/draft_service.py` | L13 | `from src.core.prompts_fallback import TEST_CASE_DRAFT_GENERATION_PROMPT` |
| `backend/src/service/rag_test_case_service.py` | L20 | `from src.core.prompts_fallback import TEST_CASE_DRAFT_GENERATION_PROMPT` |

### 1.2 修复方案

**⚠️ 重要发现：PromptManager 已内置 fallback 逻辑，无需新建 PromptLoader**

**实际代码**（`prompt_impl/facade.py:16-43`）：
```python
async def get_prompt(self, prompt_key: str, variables: Optional[Dict[str, Any]] = None) -> str:
    # 1. 尝试从缓存/数据库获取
    cached = await self.cache.get(cache_key)
    if cached:
        return self._render_template(cached, variables) if variables else cached
    
    # 2. 从数据库获取最新版本
    prompt_version = await self.prompt_storage.get_prompt_version(prompt_key, version)
    if not prompt_version:
        # 3. Fallback 到 prompts_fallback.py（保留作为兜底，类似 .env）
        fallback = self.prompt_storage._get_fallback_prompt(prompt_key)
        return self._render_template(fallback, variables) if variables else fallback
    
    # 4. 渲染模板变量
    return self._render_template(prompt_content, variables) if variables else prompt_content
```

**结论**：`PromptManager` 已实现方案初稿中 `PromptLoader` 的全部能力（缓存 + fallback + 变量渲染），**直接复用即可**。

**兜底策略**（类似 `.env`）：
- `prompts_fallback.py` **保留不删除**，作为提示词的默认兜底值
- 优先级：MySQL 数据库（主） > `prompts_fallback.py`（兜底）
- 数据库未配置或启动初始化时使用 fallback
- 前端配置页面修改提示词后，写入 MySQL，不修改 `prompts_fallback.py`

---

#### Step 1：修改 3 处直接导入

**文件 1**：`backend/src/core/nodes/retrieval.py`

```python
# 修改前
from src.core.prompts_fallback import RAG_QUERY_TEMPLATE

# 修改后
from src.core.prompt_impl.facade import prompt_manager

# 使用时（异步）
prompt = await prompt_manager.get_prompt(
    "rag_query_rewrite",  # prompt_key
    variables={"query": query, "age_range": age_range}
)
```

**文件 2**：`backend/src/service/rag_test/draft_service.py`

```python
# 修改前
from src.core.prompts_fallback import TEST_CASE_DRAFT_GENERATION_PROMPT

# 修改后
from src.core.prompt_impl.facade import prompt_manager

# 使用时（异步）
prompt = await prompt_manager.get_prompt(
    "test_case_generation",  # prompt_key
    variables={"domain": domain, "age_range": age_range}
)
```

**文件 3**：`backend/src/service/rag_test_case_service.py`

```python
# 修改前
from src.core.prompts_fallback import TEST_CASE_DRAFT_GENERATION_PROMPT

# 修改后
from src.core.prompt_impl.facade import prompt_manager

# 使用时（异步）
prompt = await prompt_manager.get_prompt(
    "test_case_generation",  # prompt_key
    variables={"domain": domain, "age_range": age_range}
)
```

**注意**：
- `prompt_manager` 是全局单例（`prompt_impl/facade.py:99`）
- `get_prompt()` 是异步方法，调用处需改为 `await`
- prompt_key 映射关系见 `prompt_storage.py:127-141` 的 `fallbacks` 字典

### 1.3 验收标准

- [ ] 3 处文件不再直接导入 `prompts_fallback.py`
- [ ] 所有提示词通过 `prompt_manager.get_prompt()` 加载（复用现有单例）
- [ ] 调用处改为异步（`await prompt_manager.get_prompt(...)`）
- [ ] 数据库提示词正常加载
- [ ] 数据库故障时降级到 `prompts_fallback.py`（PromptManager 已内置）
- [ ] 变量替换正常工作（使用 `.format(**variables)` 语法）
- [ ] `prompts_fallback.py` 保留作为兜底（类似 `.env`）

---

## 二、P1-2：实现 12 种认知维度矩阵

### 2.1 问题描述

**现状**：
- `DraftService.generate_test_case_drafts()` 使用单一 Prompt 生成
- `TestDomain` 枚举只有 6 个领域（gross_motor, fine_motor, language, cognitive, social_emotional, sensory_integration）
- 缺少细粒度认知维度模板系统
- 无去重机制（生成重复查询）

**目标**：
- 实现 `TestCaseDraftGenerator` 类
- 支持 12 种认知维度
- 50+ 提问角度模板
- difflib 相似度去重（>0.85 抛弃）

---

### 2.2 详细设计

#### Step 1：新增 `CognitiveDimension` 枚举

**文件**：`backend/src/schemas/cognitive_dimension.py`（新建，实体类必须在 schemas/ 目录）

**⚠️ 遵循 CLAUDE.md 规范**：
> "绝对禁止在 service/、controller/、core/ 中定义 class xxx(BaseModel)"

```python
from enum import Enum

class CognitiveDimension(Enum):
    """12 种认知维度（实体类统一在 schemas/ 目录，命名统一使用全称）"""
    
    FACT_RETRIEVAL = "fact_retrieval"              # 事实检索
    CONCEPT_COMPARISON = "concept_comparison"       # 概念对比
    INTERVENTION_DESIGN = "intervention_design"     # 干预设计
    SYMPTOM_IDENTIFICATION = "symptom_identification"  # 症状识别（修正：统一全称）
    DEVELOPMENTAL_MILESTONE = "developmental_milestone"  # 发展里程碑（修正：统一全称）
    ASSESSMENT_METHOD = "assessment_method"         # 评估方法
    CAUSE_ANALYSIS = "cause_analysis"               # 原因分析
    PROGRESSION_PREDICTION = "progression_prediction"  # 进展预测（修正：统一全称）
    ACTIVITY_PLANNING = "activity_planning"         # 活动规划
    RESOURCE_RECOMMENDATION = "resource_recommendation"  # 资源推荐（修正：统一全称）
    RISK_EVALUATION = "risk_evaluation"             # 风险评估（修正：统一全称）
    PARENT_GUIDANCE = "parent_guidance"             # 家长指导
```

---

#### Step 2：编写 50+ 提问角度模板

**文件**：`backend/src/service/rag_test/question_templates.json`（新建）

```json
{
  "fact_retrieval": [
    "{{age}}岁儿童的{{domain}}发展标准是什么？",
    "{{domain}}的核心考核指标有哪些？",
    "如何判断{{domain}}发展是否正常？",
    "{{domain}}发展的关键期是什么时候？"
  ],
  "concept_comparison": [
    "{{domain_a}}和{{domain_b}}的主要区别是什么？",
    "对比{{age_a}}岁和{{age_b}}岁的{{domain}}发展差异",
    "正常发育和发育迟缓在{{domain}}上有何不同？",
    "{{method_a}}和{{method_b}}评估方法哪个更适合{{domain}}？"
  ],
  "intervention_design": [
    "针对{{domain}}发育迟缓的干预方案有哪些？",
    "如何为{{age}}岁儿童设计{{domain}}训练计划？",
    "{{domain}}干预的最佳频率和时长是多少？",
    "家庭干预和专业干预在{{domain}}上的效果对比？"
  ],
  "symptom_identification": [
    "{{domain}}发育迟缓的早期症状有哪些？",
    "如何识别{{domain}}发展异常的警示信号？",
    "{{symptom}}是否属于{{domain}}发育问题？",
    "{{age}}岁儿童出现{{symptom}}需要就医吗？"
  ],
  "developmental_milestone": [
    "{{age}}岁儿童在{{domain}}上应该达到什么里程碑？",
    "{{domain}}发展的关键里程碑有哪些？",
    "如何评估{{domain}}里程碑是否达标？",
    "错过{{domain}}里程碑后如何追赶？"
  ],
  "assessment_method": [
    "评估{{domain}}发展的标准化工具有哪些？",
    "{{assessment_tool}}适合评估哪个年龄段？",
    "如何选择合适的{{domain}}评估方法？",
    "评估{{domain}}时需要注意哪些干扰因素？"
  ],
  "cause_analysis": [
    "{{domain}}发育迟缓的常见原因有哪些？",
    "遗传因素对{{domain}}发展的影响有多大？",
    "环境因素如何影响{{domain}}发展？",
    "{{factor}}是否会导致{{domain}}发育问题？"
  ],
  "progression_prediction": [
    "{{domain}}发育迟缓儿童的未来预后如何？",
    "早期干预对{{domain}}发展的长期效果？",
    "如何预测{{domain}}发展轨迹？",
    "{{age}}岁开始干预{{domain}}还来得及吗？"
  ],
  "activity_planning": [
    "适合{{age}}岁儿童的{{domain}}训练活动有哪些？",
    "如何设计循序渐进的{{domain}}训练计划？",
    "{{domain}}训练活动的安全注意事项？",
    "每天应该安排多少{{domain}}训练时间？"
  ],
  "resource_recommendation": [
    "推荐{{domain}}发育评估的专业机构？",
    "{{domain}}训练有哪些优质资源？",
    "如何选择合适的{{domain}}康复师？",
    "{{domain}}发展相关的书籍或课程推荐？"
  ],
  "risk_evaluation": [
    "{{factor}}对{{domain}}发展的风险有多大？",
    "如何评估{{domain}}发育迟缓的风险等级？",
    "早产对{{domain}}发展的长期影响？",
    "{{age}}岁儿童{{domain}}发育落后的风险？"
  ],
  "parent_guidance": [
    "家长如何在家促进儿童{{domain}}发展？",
    "{{domain}}发育迟缓儿童家长的心理调适？",
    "家长观察记录{{domain}}发展的要点？",
    "何时应该寻求专业帮助评估{{domain}}？"
  ]
}
```

**模板统计**：12 种维度 × 4 条模板 = **48 条基础模板**（可扩展至 50+）

---

#### Step 3：实现 `TestCaseDraftGenerator` 类（门面模式，拆分至 <500 行）

**文件结构**（遵循类职责拆分规则）：

```
backend/src/service/rag_test/
├── draft_generator_facade.py      # 门面类（<150 行）
├── template_loader.py             # 模板加载器（<100 行）
├── dimension_allocator.py         # 维度分配器（<100 行）
└── deduplication_checker.py       # 去重检查器（<100 行）
```

**门面类**：`backend/src/service/rag_test/draft_generator_facade.py`

```python
"""测试用例草稿生成器门面 - 协调子服务（<150 行）"""

from typing import List
from src.schemas.test_case import TestCaseDraft
from src.service.rag_test.template_loader import TemplateLoader
from src.service.rag_test.dimension_allocator import DimensionAllocator
from src.service.rag_test.deduplication_checker import DeduplicationChecker

class TestCaseDraftGeneratorFacade:
    """测试用例草稿生成器（门面模式）"""
    
    def __init__(self):
        self.template_loader = TemplateLoader()
        self.allocator = DimensionAllocator()
        self.dedup_checker = DeduplicationChecker()
    
    def generate_drafts(
        self,
        age_range: str,
        target_domains: List[str],
        count: int,
        existing_queries: List[str]
    ) -> List[TestCaseDraft]:
        """生成测试用例草稿"""
        # 1. 按维度分配生成数量
        dimension_counts = self.allocator.allocate(count, target_domains)
        
        # 2. 逐个维度生成
        drafts = []
        for dimension, num in dimension_counts.items():
            templates = self.template_loader.load(dimension)
            if not templates:
                continue
            
            for _ in range(num):
                draft = self._generate_single_draft(
                    dimension=dimension,
                    templates=templates,
                    age_range=age_range,
                    target_domains=target_domains
                )
                
                if draft is None:
                    continue
                
                # 3. 去重检查
                if self.dedup_checker.is_duplicate(draft.query, existing_queries):
                    continue
                
                drafts.append(draft)
                existing_queries.append(draft.query)
        
        return drafts
    
    def _generate_single_draft(self, ...) -> Optional[TestCaseDraft]:
        """生成单个草稿（调用 LLM）"""
        # ... 实现（复用 utils.template.render_template）
```

**子服务**：

```python
# template_loader.py（<100 行）
class TemplateLoader:
    """模板加载器"""
    def load(self, dimension: str) -> List[str]: ...

# dimension_allocator.py（<100 行）
class DimensionAllocator:
    """维度数量分配器"""
    def allocate(self, count: int, domains: List[str]) -> Dict[str, int]: ...

# deduplication_checker.py（<100 行）
class DeduplicationChecker:
    """去重检查器"""
    def is_duplicate(self, query: str, existing: List[str]) -> bool: ...
```

---

### 2.3 验收标准

- [ ] 支持 12 种认知维度，每种 4-6 个模板
- [ ] 生成 500 条用例时，去重率 < 15%
- [ ] 单次生成耗时 < 60s（batch_size=5，并发调用 LLM）
- [ ] 草稿包含 `cognitive_dimension` 字段
- [ ] 模板变量正确替换（`{{age}}`、`{{domain}}` 等）

---

### 2.4 影响分析

| 影响维度 | 说明 |
|----------|------|
| **向后兼容** | 新增 `cognitive_dimension` 字段，使用 `default=None` 兼容旧数据 |
| **性能影响** | 去重检查增加 O(n) 开销，n 为已有查询数量 |
| **风险等级** | 低（纯新增功能，不影响现有逻辑） |


