# Phase 2B.7: 兼容性与降级处理

> **状态:** ⏳ 待实现
> **前置任务:** [06-magic-value-cleanup.md](./03-phase-2b-06-magic-value-cleanup.md)

## 目标

确保提示词和配置迁移后的系统具备完善的降级机制，在 PromptManager 或 ConfigManager 不可用时仍可降级运行，并完成最终的兼容性验证与文档更新。

## 实施任务

### 1. Fallback 机制完善

> **⚠️ 前置依赖说明**: 以下代码示例假设 PromptManager 已具备 fallback 能力 (Redis 缓存 → 数据库 → 内嵌 fallback 三级降级)。若 Phase 1 未实现此能力，需在此 Phase 补充。

- [ ] **1.1 提示词 Fallback 验证**
  ```python
  # src/core/prompt/manager.py (假设已具备 fallback 能力)
  def get_prompt(self, prompt_key: str, variables: Dict[str, Any] = None) -> str:
      try:
          # 尝试从 Redis 缓存读取
          cached = self._cache.get(prompt_key)
          if cached:
              return self._render_template(cached, variables)

          # 尝试从数据库读取
          prompt = self.repository.get_latest_version(prompt_key)
          if prompt:
              self._cache.set(prompt_key, prompt.content)
              return self._render_template(prompt.content, variables)

          # 降级到内嵌 fallback (从 prompts_fallback.py 读取)
          logger.warning(f"Prompt '{prompt_key}' not found, using fallback")
          fallback = self._get_fallback(prompt_key)
          if fallback:
              return self._render_template(fallback, variables)

          raise PromptNotFoundError(f"Prompt '{prompt_key}' not found and no fallback available")

      except Exception as e:
          logger.error(f"Failed to get prompt '{prompt_key}': {e}")
          # 最终降级到 fallback
          fallback = self._get_fallback(prompt_key)
          if fallback:
              return self._render_template(fallback, variables)
          raise
  ```

- [ ] **1.2 配置 Fallback 验证**
  ```python
  # src/config/modules/rag/scoring.py
  class RagScoringConfig(BaseModel):
      """RAG 评分配置 (带默认值作为 fallback)"""
      base_display_score: float = Field(default=0.60)  # 默认值即 fallback
      max_display_score: float = Field(default=0.98)
      keyword_bonus_multiplier: float = Field(default=0.2)
      ...

  # ConfigManager 读取失败时使用默认值
  def get_rag_scoring_config(self) -> RagScoringConfig:
      try:
          return self._load_config("rag.scoring", RagScoringConfig)
      except ConfigLoadError as e:
          logger.warning(f"Failed to load rag.scoring config: {e}, using defaults")
          return RagScoringConfig()  # 返回默认值
  ```

### 2. 降级场景测试

- [ ] **2.1 模拟 PromptManager 不可用**
  ```python
  # tests/core/prompts/test_prompt_degradation.py
  def test_degradation_when_prompt_manager_down(mock_db, mock_cache):
      mock_db.get_latest_version.side_effect = DatabaseError("Connection refused")
      mock_cache.get.return_value = None  # 缓存未命中

      # 验证降级到 fallback
      result = prompt_manager.get_prompt("assessment_system")
      assert "你是一个儿童发展评估专家" in result  # fallback 内容
  ```

- [ ] **2.2 模拟 ConfigManager 不可用**
  ```python
  def test_degradation_when_config_manager_down(mock_config_db):
      mock_config_db.load.side_effect = ConfigLoadError("Redis unavailable")

      # 验证使用默认配置
      config = settings.rag.scoring
      assert config.base_display_score == 0.60  # 默认值
      assert config.max_display_score == 0.98
  ```

- [ ] **2.3 模拟 rules.json 不可用**
  ```python
  def test_degradation_when_rules_unavailable(mock_rules_db):
      mock_rules_db.get_rules.side_effect = RulesLoadError("File not found")

      # 验证使用内嵌默认规则
      stages = rules_manager.get_rules("age_filter_stages")
      assert "infant" in stages
      assert stages["infant"]["tolerance"] == 1  # 内嵌默认值
  ```

### 3. 热更新最终验证

- [ ] **3.1 提示词热更新端到端测试**
  ```python
  def test_prompt_hot_reload_end_to_end(prompt_manager, config_manager):
      # 1. 获取当前提示词
      old_prompt = prompt_manager.get_prompt("assessment_system")

      # 2. 更新提示词版本
      new_content = old_prompt.replace("评估专家", "高级评估专家")
      prompt_manager.save_prompt("assessment_system", new_content, version=2)

      # 3. 验证缓存失效
      prompt_manager.invalidate_cache("assessment_system")

      # 4. 获取新提示词
      new_prompt = prompt_manager.get_prompt("assessment_system")
      assert "高级评估专家" in new_prompt
  ```

- [ ] **3.2 配置热更新端到端测试**
  ```python
  # tests/config/test_config_hot_reload.py
  import asyncio

  async def test_config_hot_reload_end_to_end(config_manager, event_bus):
      # 1. 获取当前配置
      old_threshold = settings.rag.dedup.containment_threshold
      assert old_threshold == 0.8

      # 2. 更新配置
      config_manager.update_config("rag.dedup.containment_threshold", 0.85)

      # 3. 等待事件传播 (使用 asyncio.sleep 而非 time.sleep，避免阻塞事件循环)
      await asyncio.sleep(0.1)

      # 4. 验证配置已更新
      new_threshold = settings.rag.dedup.containment_threshold
      assert new_threshold == 0.85
  ```

### 4. 全链路回归测试

- [ ] **4.1 核心评估流程回归测试**
  ```bash
  pytest tests/e2e/test_assessment_workflow.py -v
  ```
  - 验证完整评估流程输出与迁移前一致
  - 验证提示词和配置降级场景下功能可用

- [ ] **4.2 RAG 检索流程回归测试**
  ```bash
  pytest tests/service/test_retrieval_service.py tests/core/test_hybrid_retrieval.py -v
  ```
  - 验证检索结果质量无退化
  - 验证阈值配置变更后检索行为正确

- [ ] **4.3 文档导入流程回归测试**
  ```bash
  pytest tests/core/test_metadata_extractor.py tests/core/test_layered_content.py -v
  ```
  - 验证元数据提取和分层内容生成质量

### 5. 文档更新

- [ ] **5.1 更新 AGENTS.md**
  - 更新配置系统架构图
  - 更新提示词管理系统说明
  - 标注已完成的迁移项

- [ ] **5.2 更新 CLAUDE.md**
  - 更新项目结构说明
  - 更新核心模块职责
  - 更新 API 端点变更 (如有)

- [ ] **5.3 更新 Spec 文档**
  - 标记 Phase 2B 已完成
  - 记录实施过程中的调整和发现

- [ ] **5.4 添加更新记录**
  ```
  2026-04-14: [Phase 2B] 提示词/配置收拢完成
  - 迁移 15 个提示词至 PromptManager (P0/P1/P2)
  - 迁移 60+ 魔法值至 ConfigManager
  - 业务规则分离到 rules.json
  - 完善降级机制和热更新验证
  ```

### 6. 上线检查清单

- [ ] **6.1 代码审查**
  - 所有提示词和配置迁移完成
  - 无遗留的硬编码提示词和魔法值
  - 降级机制完善

- [ ] **6.2 测试验证**
  - 单元测试覆盖率 ≥90%
  - 回归测试 100% 通过
  - 性能测试满足基线要求

- [ ] **6.3 文档更新**
  - AGENTS.md 已更新
  - CLAUDE.md 已更新
  - Spec 文档已标记完成

- [ ] **6.4 部署准备**
  - 数据库迁移脚本就绪，详情如下:
    | 迁移脚本 | 操作 | 说明 |
    |---------|------|------|
    | `005_extend_prompt_version_variables` | ALTER TABLE `prompt_versions` | 扩展 `variables` 字段 (JSON 类型)，支持更多占位符类型；若已为 JSON 类型则跳过 |
  - 提示词初始数据脚本就绪 (`src/scripts/seed_prompts.py`)
  - 回滚方案就绪:
    - 代码回滚: `git revert` 到迁移前版本
    - 数据库回滚: `alembic downgrade -1`
    - **提示词数据清理**: 若 `seed_prompts.py` 已执行，需额外清理已写入的提示词数据:
      ```sql
      DELETE FROM prompt_versions WHERE key IN (
        'assessment_system', 'reporting_system', 'validation_system',
        'intensity_inference', 'category_inference', 'rag_query_template',
        'query_rewrite', 'synonym_expansion', 'query_classification',
        'metadata_extraction', 'test_case_draft_generation',
        'layered_content_l0', 'layered_content_l1', 'layered_content_batch',
        'layered_content_combined'
      );
      ```
  - 监控告警配置完成

---

## 降级策略总结

| 组件 | 不可用场景 | 降级行为 | 影响范围 |
|------|-----------|---------|---------|
| PromptManager | 数据库/Redis 不可用 | 使用内嵌 fallback 提示词 | 提示词版本控制失效，功能降级可用 |
| ConfigManager | Redis/MySQL 不可用 | 使用 Pydantic 默认值 | 配置变更需重启生效，功能可用 |
| rules.json | 文件不可读 | 使用内嵌默认规则 | 业务规则固定，功能可用 |

---

## 验收标准

- [ ] 所有降级场景测试通过
- [ ] 热更新端到端测试通过
- [ ] 全链路回归测试 100% 通过
- [ ] AGENTS.md 和 CLAUDE.md 已更新
- [ ] 上线检查清单全部完成

---

**上一任务:** [06-magic-value-cleanup.md](./03-phase-2b-06-magic-value-cleanup.md)  
**下一任务:** [Phase 2C](./04-phase-2c-tuning-engine.md)
