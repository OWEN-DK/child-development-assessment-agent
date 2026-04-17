# Phase 2B.2: 提示词收拢与接入

> **状态:** ⏳ 待实现
> **前置任务:** [01-prompt-scan.md](./03-phase-2b-01-prompt-scan.md)

## 目标

将扫描到的硬编码提示词按 P0/P1/P2 优先级分批收拢至 PromptManager，更新代码调用方式，并为每个提示词配置合理的 fallback 值。

## 实施任务

### 1. P0 提示词收拢 (核心评估流程)

- [ ] **1.1 迁移 `assessment_system` 提示词**
  - **来源**: `src/core/nodes/assessment.py:67`
  - **操作**:
    1. 提取提示词内容，通过 `prompt_manager.save_prompt()` 存入 MySQL
    2. 设置 `prompt_key = "assessment_system"`
    3. 配置 `variables = ["child_age", "issues", "milestones"]`
    4. 设置 `fallback` 为原硬编码内容
    5. 更新 `assessment.py` 代码 (通过 DI 注入 PromptManager):
       ```python
       # src/core/nodes/assessment.py - 改造前
       system_message = "你是一个儿童发展评估专家..."  # 硬编码

       # src/core/nodes/assessment.py - 改造后
       class AssessmentNode:
           def __init__(self, prompt_manager: PromptManager):
               self.prompt_manager = prompt_manager

           def execute(self, state: GraphState):
               system_message = self.prompt_manager.get_prompt("assessment_system", variables={
                   "child_age": state.child_profile.age,
                   "issues": state.child_profile.issues,
                   "milestones": state.milestones_json
               })
       ```
       > **DI 注入说明**: 项目使用 `injector` 库进行依赖注入。所有 Node 类通过 `__init__` 接收 `PromptManager` 实例，由 DI 容器在 `src/core/di_container.py` 中自动装配。若 Node 由 LangGraph 直接实例化，则在 `src/core/graph.py` 的 StateGraph 构建阶段手动注入。

- [ ] **1.2 迁移 `reporting_system` 提示词**
  - **来源**: `src/core/prompts.py:182-297` + `src/core/nodes/reporting.py:226`
  - **操作**:
    1. 合并两处提示词内容，消除重复
    2. 设置 `prompt_key = "reporting_system"`
    3. 配置 `variables = ["child_state", "evaluation_result", "retrieved_docs", "radar_data"]`
    4. 更新 `reporting.py` 调用方式
    5. 移除 `src/core/prompts.py` 中的重复定义

- [ ] **1.3 迁移 `validation_system`、`intensity_inference`、`category_inference`**
  - **来源**: `src/core/prompts.py:102-138`
  - **操作**:
    1. 分别提取三个提示词，设置对应的 `prompt_key`
    2. 更新 `src/core/nodes/validation.py` 调用方式
    3. 配置 fallback 值

- [ ] **1.4 P0 回归测试**
  - 运行核心评估流程端到端测试
  - 验证输出报告质量与迁移前一致
  - **对比方法**:
    1. 运行迁移前的基准测试，保存输出结果到 `tests/baseline/`
    2. 运行迁移后的测试，对比输出差异
    3. 允许的差异: JSON 字段顺序变化、数值差异 <0.001
    4. 不允许的差异: 缺失字段、新增字段、数值差异 >0.001

### 2. P1 提示词迁移 (RAG 检索)

- [ ] **2.1 迁移 `rag_query_template`、`query_rewrite`、`synonym_expansion`**
  - **来源**: `src/core/prompts.py` + `src/service/retrieval_service.py`
  - **操作**:
    1. 提取提示词内容，存入 PromptManager
    2. 更新 `retrieval_service.py` 中的调用 (通过 DI 注入 PromptManager):
       ```python
       # src/service/retrieval_service.py - 改造前
       prompt = QUERY_REWRITE_TEMPLATE.format(query=query)

       # src/service/retrieval_service.py - 改造后
       class RetrievalService:
           def __init__(self, prompt_manager: PromptManager, settings: Settings):
               self.prompt_manager = prompt_manager
               self.settings = settings

           def _rewrite_query(self, query: str) -> str:
               prompt = self.prompt_manager.get_prompt("query_rewrite", variables={"query": query})
               ...
       ```

- [ ] **2.2 迁移 `query_classification`**
  - **来源**: `src/core/query_router.py:174-194`
  - **操作**:
    1. 提取分类提示词，设置 `prompt_key = "query_classification"`
    2. 更新 `query_router.py` 调用方式

- [ ] **2.3 P1 回归测试**
  - 运行 RAG 检索流程测试
  - 验证检索结果质量与迁移前一致
  - **对比方法**: 对比检索结果数量、排序顺序、分数差异 <0.01

### 3. P2 提示词迁移 (元数据与内容生成)

- [ ] **3.1 迁移 `metadata_extraction`**
  - **来源**: `src/core/prompts.py:52-73` + `src/core/metadata_extractor.py:187`
  - **操作**:
    1. 提取提示词，设置 `prompt_key = "metadata_extraction"`
    2. 更新 `metadata_extractor.py` 调用

- [ ] **3.2 迁移 `test_case_draft_generation`**
  - **来源**: `src/core/prompts.py:75-95`
  - **操作**:
    1. 提取提示词，设置 `prompt_key = "test_case_draft_generation"`
    2. 更新相关调用代码

- [ ] **3.3 迁移 `layered_content_*` 系列提示词**
  - **来源**: `src/core/layered_content_generator.py`
  - **操作**:
    1. 分别提取 4 个提示词 (l0/l1/batch/combined)
    2. 设置对应的 `prompt_key`
    3. 更新 `layered_content_generator.py` 调用

- [ ] **3.4 P2 回归测试**
  - 运行文档导入和分层内容生成测试
  - 验证生成内容质量与迁移前一致
  - **对比方法**: 对比生成的元数据字段完整性、分层内容长度差异 <5%

### 4. 提示词初始数据迁移

> **⚠️ 重要**: 提示词从代码迁移到 MySQL 数据库后，首次部署时需要执行初始化脚本将 15 个提示词写入数据库。
>
> **⚠️ 接口假设说明**: 以下脚本使用异步接口 (`await prompt_manager.save_prompt()`)。若 PromptManager 实际为同步接口，移除 `async`/`await` 关键字即可。

- [ ] **4.1 创建初始化脚本**
  ```python
  # src/scripts/seed_prompts.py
  """
  提示词初始数据迁移脚本
  用法: uv run python src/scripts/seed_prompts.py [--dry-run] [--force]
  """
  import asyncio
  from src.core.prompt.manager import PromptManager
  from src.config import settings

  PROMPTS_SEED_DATA = [
      {
          "key": "assessment_system",
          "content": "你是一个儿童发展评估专家...",  # 从 src/core/nodes/assessment.py:67 提取
          "variables": ["child_age", "issues", "milestones"],
          "category": "assessment",
          "description": "儿童发展评估专家系统消息"
      },
      {
          "key": "reporting_system",
          "content": "...",  # 从 src/core/prompts.py:182-297 提取
          "variables": ["child_state", "evaluation_result", "retrieved_docs", "radar_data"],
          "category": "reporting",
          "description": "报告生成专家系统消息"
      },
      # ... 其余 13 个提示词
  ]

  async def seed_prompts(dry_run: bool = False, force: bool = False):
      prompt_manager = PromptManager(settings)
      for prompt_data in PROMPTS_SEED_DATA:
          existing = await prompt_manager.repository.get_latest_version(prompt_data["key"])
          if existing and not force:
              print(f"跳过已存在的提示词: {prompt_data['key']}")
              continue
          if dry_run:
              print(f"[DRY RUN] 将创建/更新提示词: {prompt_data['key']}")
              continue
          await prompt_manager.save_prompt(**prompt_data)
          print(f"已创建提示词: {prompt_data['key']}")

  if __name__ == "__main__":
      asyncio.run(seed_prompts())
  ```

- [ ] **4.2 将初始化脚本集成到部署流程**
  - 在 CI/CD 中，数据库迁移 (`alembic upgrade head`) 后自动执行 `seed_prompts.py`
  - 使用 `--dry-run` 模式验证数据完整性
  - 使用 `--force` 模式仅在首次部署或紧急修复时执行

- [ ] **4.3 验证初始数据**
  ```bash
  # 验证所有提示词已写入数据库
  uv run python src/scripts/seed_prompts.py --dry-run
  # 预期输出: "跳过已存在的提示词: assessment_system" × 15
  ```

### 5. Fallback 机制配置

- [ ] **5.1 为所有提示词配置 fallback 值**
  - fallback 内容为原硬编码提示词
  - 确保 PromptManager 不可用时系统可降级运行

- [ ] **5.2 验证 fallback 触发逻辑**
  - 模拟 PromptManager 不可用场景
  - 验证系统自动降级到 fallback 提示词

### 6. 代码清理

- [ ] **6.1 处理 `src/core/prompts.py`**
  - 移除所有硬编码提示词内容
  - 重命名为 `src/core/prompts_fallback.py`，仅保留 fallback 常量字典
  - fallback 字典结构:
    ```python
    # src/core/prompts_fallback.py
    PROMPTS_FALLBACK = {
        "assessment_system": "你是一个儿童发展评估专家...",
        "reporting_system": "...",
        # ... 其余 13 个
    }
    ```
  - 更新 `src/core/prompt/manager.py` 中的 `_get_fallback()` 方法，从 `prompts_fallback.py` 读取
  > **⚠️ 维护责任**: `prompts_fallback.py` 仅作为降级备用，不作为主要维护目标。提示词的唯一真实来源是 MySQL 数据库。每次通过 PromptManager 更新提示词后，建议同步更新 fallback 文件 (可通过 CI 钩子自动同步)。

- [ ] **6.2 更新所有调用点**
  - 确保代码中仅保留 `prompt_manager.get_prompt("key_name")` 调用
  - 验证占位符 (Variables) 正确对应

---

## 迁移检查清单

每个提示词迁移时需完成以下检查:

- [ ] 提示词内容已存入 MySQL (通过 PromptManager)
- [ ] `prompt_key` 命名符合规范 (小写下划线)
- [ ] `variables` 列表完整且与模板占位符一致
- [ ] `fallback` 值设置为原硬编码内容
- [ ] 代码调用已更新为 `prompt_manager.get_prompt()`
- [ ] 单元测试覆盖新调用方式
- [ ] 回归测试通过 (每迁移 2-3 个执行一次)

---

## 验收标准

- [ ] 所有 P0/P1/P2 提示词迁移完成
- [ ] 代码中无硬编码提示词 (仅保留 fallback)
- [ ] 每个提示词的 fallback 机制验证通过
- [ ] 每迁移 2-3 个提示词后完成回归测试
- [ ] `src/core/prompts.py` 已清理，仅保留 fallback 常量

---

**上一任务:** [01-prompt-scan.md](./03-phase-2b-01-prompt-scan.md)  
**下一任务:** [03-prompt-validation.md](./03-phase-2b-03-prompt-validation.md)
