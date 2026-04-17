# Phase 2B: 提示词/配置收拢

> **状态:** ✅ 方案已完成
> **预计工期:** 5 人天
> **依赖前置:** Phase 1 LLM 供应商重构完成、PromptManager 与 ConfigManager 基础设施稳定运行

## 概述

本 Phase 全面清查并收拢散落在代码中的硬编码提示词与业务配置，统一接入 PromptManager 和 ConfigManager。

## 子文档索引

| 步骤 | 内容 | 状态 | 详细文档 |
|------|------|------|----------|
| 1 | 提示词扫描与盘点 | ⏳ 待实施 | [01-prompt-scan.md](./03-phase-2b-01-prompt-scan.md) |
| 2 | 提示词迁移与接入 | ⏳ 待实施 | [02-prompt-migration.md](./03-phase-2b-02-prompt-migration.md) |
| 3 | 提示词校验与测试 | ⏳ 待实施 | [03-prompt-validation.md](./03-phase-2b-03-prompt-validation.md) |
| 4 | 配置扫描与盘点 | ⏳ 待实施 | [04-config-scan.md](./03-phase-2b-04-config-scan.md) |
| 5 | 配置迁移与接入 | ⏳ 待实施 | [05-config-migration.md](./03-phase-2b-05-config-migration.md) |
| 6 | 魔法值清理与重构 | ⏳ 待实施 | [06-magic-value-cleanup.md](./03-phase-2b-06-magic-value-cleanup.md) |
| 7 | 兼容性与降级处理 | ⏳ 待实施 | [07-compatibility.md](./03-phase-2b-07-compatibility.md) |

## 实施任务

### 2B.1 提示词迁移 (P0/P1/P2)

- [ ] **2B.1.1 P0: 节点级系统提示词迁移**
  - `assessment_system` - `src/core/nodes/assessment.py:67`
  - `reporting_system` - `src/core/prompts.py:182-297` + `src/core/nodes/reporting.py:226`
  - `validation_system` - `src/core/prompts.py:102-106`
  - `intensity_inference` - `src/core/prompts.py:108-120`
  - `category_inference` - `src/core/prompts.py:122-138`

- [ ] **2B.1.2 P1: RAG 检索相关提示词迁移**
  - `rag_query_template` - `src/core/prompts.py:6`
  - `query_rewrite` - `src/core/prompts.py:8-19` + `src/service/retrieval_service.py:830-832`
  - `synonym_expansion` - `src/core/prompts.py:21-46` + `src/service/retrieval_service.py:949-951`
  - `query_classification` - `src/core/query_router.py:174-194` + `208-209`

- [ ] **2B.1.3 P2: 元数据与内容生成提示词迁移**
  - `metadata_extraction` - `src/core/prompts.py:52-73` + `src/core/metadata_extractor.py:187`
  - `test_case_draft_generation` - `src/core/prompts.py:75-95`
  - `layered_content_l0/l1/batch/combined` - `src/core/layered_content_generator.py`

- [ ] **2B.1.4 代码替换**
  - 代码中仅保留 `prompt_manager.get_prompt("key_name")` 调用
  - 确保占位符 (Variables) 正确对应
  - 每个提示词设置合理的 fallback 值

### 2B.2 业务配置迁移 (P0/P1/P2)

- [ ] **2B.2.1 P0: LLM 参数集中化**
  - 迁移 60+ 处硬编码参数到 ConfigManager
  - 覆盖 assessment/reporting/validation/metadata_extraction 等场景

- [ ] **2B.2.2 P1: RAG 检索阈值与参数迁移**
  - 去重阈值、分数基准、年龄适配权重等
  - 目标配置键：`rag.dedup.*`, `rag.scoring.*`

- [ ] **2B.2.3 P2: 文档处理与业务规则迁移**
  - 元数据缓存大小、分块参数、并行线程数等
  - 目标配置键：`rag.metadata.*`, `rag.chunking.*`

- [ ] **2B.2.4 业务规则分离到 `rules.json`**
  - 年龄段划分参数 (tolerance/strictness/weight)
  - 年龄边界和推荐规则
  - 保留核心算法在代码中，仅将可配置参数外部化

---

## 验收标准

- [ ] 所有 P0/P1/P2 提示词迁移完成
- [ ] 代码中无硬编码提示词（仅保留 fallback）
- [ ] 所有魔法值迁移到 ConfigManager
- [ ] 业务规则分离到 rules.json
- [ ] 每迁移 2-3 个提示词后完成回归测试

---

**上一阶段：** [Phase 2A](./02-phase-2a-rag-workflow.md)  
**下一阶段：** [Phase 2C](./04-phase-2c-tuning-engine.md)
