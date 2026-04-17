# Phase 2B.5: 配置收拢与接入

> **状态:** ⏳ 待实现
> **前置任务:** [04-config-scan.md](./03-phase-2b-04-config-scan.md)

## 目标

将扫描到的魔法值按 P0/P1/P2 优先级分批收拢至 ConfigManager，更新代码调用方式，并将业务规则分离到 ConfigManager (MySQL 存储)。

## 实施任务

### 1. P0 配置收拢 (LLM 参数集中化)

> **⚠️ 与 Phase 1 职责边界说明**:
> - **Phase 1 负责**: 定义 `LLMSceneConfig`/`LLMConfig` 配置模型、Provider Registry、热更新机制、配置校验层
> - **Phase 2B P0 负责**: 移除 15+ 调用点文件中的硬编码 `temperature`/`max_tokens`，改为从 `settings.llm.*` 读取
> - **前提**: Phase 1 完成后，配置模型和热更新机制已就绪，Phase 2B 仅需改造调用点

- [ ] **1.1 确认 Phase 1 已定义的配置模型**
  - 验证 `src/config/modules/models/llm.py` 中 `LLMSceneConfig` 和 `LLMConfig` 已定义
  - 验证 8 个场景 (assessment/reporting/validation/metadata_extraction/query_rewrite/synonym_expansion/query_classification/layered_content) 的默认值与原硬编码值一致
  - 若 Phase 1 未覆盖某个场景，在此补充定义

- [ ] **1.2 移除硬编码参数，改为通过工厂自动读取配置**
  ```python
  # src/core/nodes/assessment.py - 改造前
  llm = LLMServiceFactory.create(
      scene="assessment",
      temperature=0.5,
      max_tokens=1024
  )

  # src/core/nodes/assessment.py - 改造后 (工厂内部通过 ConfigManager 自动读取场景配置)
  class AssessmentNode:
      def __init__(self, prompt_manager: PromptManager):
          self.prompt_manager = prompt_manager

      def execute(self, state: GraphState):
          # 工厂内部自动从 ConfigManager 读取 assessment 场景的 provider/model/temperature 等参数
          llm = await llm_service_factory.create("assessment", framework="langchain")
          # 使用完毕后释放引用
          # await llm_service_factory.release("assessment", framework="langchain")
  ```
  > **⚠️ 与 Phase 1 职责边界**: Phase 1 已完成工厂内部配置读取逻辑（通过 `config_manager.get_full_config()` 解析 `llm_assessment` 键），Phase 2B P0 仅需移除调用点中的硬编码参数，无需再手动传递 temperature/max_tokens。

- [ ] **1.3 批量改造 15+ 文件中的 LLM 调用点**
  - `src/core/nodes/assessment.py`
  - `src/core/nodes/validation.py`
  - `src/core/nodes/reporting.py`
  - `src/core/nodes/scoring.py`
  - `src/core/nodes/preprocessing.py`
  - `src/core/nodes/retrieval.py`
  - `src/core/query_router.py`
  - `src/core/metadata_extractor.py`
  - `src/core/layered_content_generator.py`
  - `src/core/memory_manager.py`
  - `src/service/retrieval_service.py`
  - `src/service/rag_test_manager.py`
  - `src/controller/task_controller.py`
  - `src/core/parsers.py`
  - `src/core/ml/qwen_scorer.py`

- [ ] **1.4 验证所有 LLM 调用参数正确加载**
  - 编写单元测试验证各场景参数从配置读取
  - 验证热更新机制生效 (配置变更后参数自动更新)

### 2. P1 配置收拢 (RAG 检索阈值与参数)

> **⚠️ 配置模块路径对齐说明**: 以下配置项归入现有 `src/config/modules/rag/` 模块，不新增独立文件。
> - 评分相关 → `src/config/modules/rag/core.py` (核心 RAG 配置)
> - 去重相关 → `src/config/modules/rag/retrieval.py` (检索配置)
> - 元数据/分块 → 已有 `src/config/modules/rag/chunking.py`

- [ ] **2.1 在现有 rag 配置模块中新增相关配置项**
  ```python
  # src/config/modules/rag/core.py - 新增评分配置
  class RagScoringConfig(BaseModel):
      """RAG 评分配置"""
      base_display_score: float = Field(default=0.60)
      max_display_score: float = Field(default=0.98)
      keyword_bonus_multiplier: float = Field(default=0.2)
      high_relevance_threshold: float = Field(default=0.8)
      age_fit_weights: Tuple[float, float] = Field(default=(0.7, 0.3))

  # 在 RagCoreConfig 中新增 scoring 字段
  class RagCoreConfig(BaseModel):
      scoring: RagScoringConfig = Field(default_factory=RagScoringConfig)
      # ... 已有字段
  ```

  ```python
  # src/config/modules/rag/retrieval.py - 新增去重配置
  class RagDedupConfig(BaseModel):
      """RAG 去重配置"""
      containment_threshold: float = Field(default=0.8)
      length_diff_threshold: float = Field(default=0.2)
      similarity_threshold: float = Field(default=0.9)

  # 在 RagRetrievalConfig 中新增 dedup 字段
  class RagRetrievalConfig(BaseModel):
      dedup: RagDedupConfig = Field(default_factory=RagDedupConfig)
      # ... 已有字段
  ```

- [ ] **2.2 移除 retrieval_service.py 和 scoring.py 中的硬编码阈值**
  ```python
  # src/service/retrieval_service.py - 改造前
  if similarity > 0.8:  # 硬编码阈值
      ...

  # src/service/retrieval_service.py - 改造后 (通过 DI 注入 settings)
  class RetrievalService:
      def __init__(self, settings: Settings):
          self.settings = settings

      def _deduplicate(self, results):
          dedup_config = self.settings.rag.retrieval.dedup
          if similarity > dedup_config.containment_threshold:
              ...
  ```

- [ ] **2.3 通过单元测试验证算法行为一致性**
  - 对比迁移前后检索结果完全一致
  - 验证阈值从配置读取后逻辑无变化

### 3. P2 配置收拢 (文档处理与业务规则)

> **⚠️ 配置模块路径对齐说明**:
> - 元数据/分块参数 → 归入已有 `src/config/modules/rag/chunking.py`
> - 业务规则 → 归入 `src/config/modules/rag/rules.py`（通过 ConfigManager 存 MySQL）

- [ ] **3.1 在已有 chunking.py 中新增元数据相关配置项**
  ```python
  # src/config/modules/rag/chunking.py - 新增元数据处理配置
  class RagMetadataConfig(BaseModel):
      """RAG 元数据配置"""
      cache_max_size: int = Field(default=10000)
      min_text_length: int = Field(default=10)
      text_truncation_length: int = Field(default=2000)
      max_topics: int = Field(default=8)
      max_workers: int = Field(default=20)

  # 在 RagChunkingConfig 中新增 metadata 和 english_threshold 字段
  class RagChunkingConfig(BaseModel):
      metadata: RagMetadataConfig = Field(default_factory=RagMetadataConfig)
      english_threshold: float = Field(default=0.7)
      merge_ratio: Tuple[float, float] = Field(default=(1.2, 1.5))
      # ... 已有字段
  ```

- [ ] **3.2 将 age_filter.py 年龄段参数提取至 ConfigManager（MySQL 存储）**
  > **⚠️ CLAUDE.md 约束**: 禁止使用本地 JSON 文件存储配置。业务规则必须通过 ConfigManager 存入 MySQL `config_snapshots` 表，支持多实例共享与热更新。

  在 `src/config/modules/rag/rules.py` 中定义规则 Pydantic 模型：
  ```python
  from pydantic import BaseModel, Field
  from typing import Dict

  class AgeFilterStageConfig(BaseModel):
      age_max: int
      tolerance: int
      strictness: float
      weight: float

  class AgeFilterRules(BaseModel):
      """年龄段过滤规则（通过 ConfigManager 从 MySQL 读取）"""
      age_filter_stages: Dict[str, AgeFilterStageConfig] = Field(default_factory=lambda: {
          "infant": {"age_max": 1, "tolerance": 1, "strictness": 0.9, "weight": 0.5},
          "toddler": {"age_max": 3, "tolerance": 2, "strictness": 0.8, "weight": 0.4},
          "preschool": {"age_max": 6, "tolerance": 2, "strictness": 0.7, "weight": 0.3},
          "school_age": {"age_max": 12, "tolerance": 3, "strictness": 0.6, "weight": 0.25},
      })
  ```

- [ ] **3.3 将 child_development_engine.py 年龄边界和推荐规则提取至 ConfigManager**
  ```python
  class AgeBoundaryRules(BaseModel):
      """年龄边界与推荐规则（通过 ConfigManager 从 MySQL 读取）"""
      min_age: int = Field(default=0)
      max_age: int = Field(default=12)
      default_tolerance: int = Field(default=2)
      recommendations: Dict[str, list] = Field(default_factory=lambda: {
          "0-1": ["感官刺激", "亲子互动"],
          "1-3": ["粗大动作", "语言启蒙"],
          "3-6": ["精细动作", "社交技能"],
          "6-12": ["认知能力", "逻辑思维"],
      })
  ```

- [ ] **3.4 更新代码从 ConfigManager 读取业务规则**
  ```python
  # src/core/age_filter.py - 改造后 (通过 DI 注入 ConfigManager)
  from src.config import ConfigManager
  from src.config.modules.rag.rules import AgeFilterRules

  class AgeFilter:
      def __init__(self, config_manager: ConfigManager):
          self.config_manager = config_manager

      def filter_by_age(self, results, child_age: int):
          # 从 ConfigManager 获取规则配置（支持热更新）
          full_config = self.config_manager.get_full_config()
          rules_data = full_config.get("rag_rules_age_filter", {})
          rules = AgeFilterRules(**rules_data) if rules_data else AgeFilterRules()

          stage_config = rules.age_filter_stages.get(stage_name)
          if stage_config:
              tolerance = stage_config.tolerance
              strictness = stage_config.strictness
          ...
  ```
  > **DI 注入说明**: `ConfigManager` 通过 injector 容器注入，与 `PromptManager` 的注入方式一致。业务规则数据存储在 MySQL `config_snapshots` 表中，通过 ConfigManager 统一读写，支持热更新与多实例共享。

### 4. 配置热更新验证

- [ ] **4.1 验证 LLM 参数热更新**
  - 修改配置中的 temperature 值
  - 验证下次 LLM 调用使用新参数

- [ ] **4.2 验证 RAG 阈值热更新**
  - 修改去重阈值
  - 验证检索结果按新阈值过滤

- [ ] **4.3 验证业务规则热更新**
  - 通过 ConfigManager 修改年龄段参数（MySQL 存储）
  - 验证年龄过滤逻辑按新参数执行

---

## 迁移检查清单

每个配置项迁移时需完成以下检查:

- [ ] 配置项已在对应模块中定义 (带 Pydantic 校验)
- [ ] 默认值与原硬编码值一致
- [ ] 代码调用已更新为从 settings 读取
- [ ] 热更新机制验证通过
- [ ] 单元测试覆盖新调用方式
- [ ] 算法行为一致性验证通过

---

## 验收标准

- [ ] 所有 P0/P1/P2 魔法值迁移完成
- [ ] 代码中无硬编码阈值 (仅保留配置默认值)
- [ ] 业务规则正确分离到 ConfigManager (MySQL 存储)
- [ ] 热更新机制验证通过
- [ ] 单元测试验证算法行为一致性

---

**上一任务:** [04-config-scan.md](./03-phase-2b-04-config-scan.md)  
**下一任务:** [06-magic-value-cleanup.md](./03-phase-2b-06-magic-value-cleanup.md)
