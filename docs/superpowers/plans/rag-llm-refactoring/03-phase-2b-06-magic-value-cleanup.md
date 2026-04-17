# Phase 2B.6: 魔法值清理与重构

> **状态:** ⏳ 待实现
> **前置任务:** [05-config-migration.md](./03-phase-2b-05-config-migration.md)

## 目标

彻底清理代码中遗留的魔法值，重构相关代码结构，确保所有可配置参数已外部化，并通过单元测试验证算法行为一致性。

## 实施任务

### 1. 遗留魔法值清查

- [ ] **1.1 全代码扫描遗留魔法值**
  ```bash
  # 扫描硬编码数字 (排除注释、字符串、端口号、版本号、HTTP状态码)
  grep -rn "[0-9]\{2,\}" src/ --include="*.py" \
    | grep -v "test" | grep -v "__pycache__" \
    | grep -v "#" \
    | grep -v '["\x27]' \
    | grep -v "port\s*=\|version\s*=\|HTTP_\|status_code\|timeout"

  # 扫描硬编码字符串常量
  grep -rn '"[a-z_]\{3,\}"' src/ --include="*.py" | grep -v "test"
  ```

- [ ] **1.2 分类处理**
  - **应外部化的配置**: 迁移到 ConfigManager
  - **应保留的代码常量**: 添加注释说明 (如 `MAX_RETRIES = 3  # 最大重试次数`)
  - **应消除的重复代码**: 提取为常量或配置

### 2. 代码重构

- [ ] **2.1 提取模块级常量**
  ```python
  # src/service/retrieval_service.py - 改造前
  def search(self, query: str, age: int, limit: int = 10):
      if limit > 50:  # 魔法数字
          limit = 50
      ...

  # src/service/retrieval_service.py - 改造后
  MAX_SEARCH_LIMIT = 50  # 最大检索数量限制

  def search(self, query: str, age: int, limit: int = 10):
      if limit > MAX_SEARCH_LIMIT:
          limit = MAX_SEARCH_LIMIT
      ...
  ```

- [ ] **2.2 消除重复配置读取**
  ```python
  # 改造前 - 多次读取同一配置
  def method_a(self):
      threshold = settings.rag.dedup.similarity_threshold
      ...

  def method_b(self):
      threshold = settings.rag.dedup.similarity_threshold  # 重复
      ...

  # 改造后 - 提取为属性或缓存
  @property
  def dedup_threshold(self):
      return settings.rag.dedup.similarity_threshold

  def method_a(self):
      threshold = self.dedup_threshold
      ...
  ```

- [ ] **2.3 统一配置访问模式**
  - 通过 DI 注入 `Settings` 实例，**使用 property 动态读取**以支持热更新
  - **禁止在 `__init__` 中缓存配置引用**，否则热更新后仍指向旧对象
  ```python
  # ✅ 推荐模式: 使用 property 动态读取，支持热更新
  class RetrievalService:
      def __init__(self, settings: Settings):
          self._settings = settings

      @property
      def _dedup_config(self):
          return self._settings.rag.retrieval.dedup

      def _deduplicate(self, results):
          # 每次通过 property 读取最新配置值，热更新后自动生效
          threshold = self._dedup_config.containment_threshold
          ...

  # ❌ 错误模式: 在 __init__ 中缓存配置引用，热更新后不会更新
  class RetrievalService:
      def __init__(self, settings: Settings):
          self._dedup_config = settings.rag.retrieval.dedup  # ❌ 热更新后仍指向旧对象
  ```

### 3. 业务规则验证

> **⚠️ 职责边界**: 本节仅验证 rules.json 加载和热更新逻辑正确性，降级场景测试归入 [07-compatibility.md](./03-phase-2b-07-compatibility.md)。

- [ ] **3.1 验证 rules.json 加载正确性**
  ```python
  # tests/config/test_rules_json.py
  def test_age_filter_stages_loaded(rules_manager):
      stages = rules_manager.get_rules("age_filter_stages")
      assert "infant" in stages
      assert stages["infant"]["age_max"] == 1
      assert stages["infant"]["tolerance"] == 1
      assert stages["infant"]["strictness"] == 0.9
      assert stages["infant"]["weight"] == 0.5
  ```

### 4. 单元测试覆盖

> **⚠️ 职责边界**: 本节仅验证配置项默认值和算法行为一致性，回归测试和热更新端到端测试归入 [07-compatibility.md](./03-phase-2b-07-compatibility.md)。

- [ ] **4.1 为每个迁移的配置项编写单元测试**
  ```python
  # tests/config/test_rag_scoring_config.py
  def test_scoring_config_defaults():
      config = RagScoringConfig()
      assert config.base_display_score == 0.60
      assert config.max_display_score == 0.98
      assert config.keyword_bonus_multiplier == 0.2
      assert config.high_relevance_threshold == 0.8

  def test_scoring_config_validation():
      with pytest.raises(ValidationError):
          RagScoringConfig(base_display_score=1.5)  # 超出合理范围
  ```

- [ ] **4.2 验证算法行为一致性**
  ```python
  # tests/service/test_retrieval_algorithm_consistency.py
  def test_dedup_behavior_unchanged_after_migration():
      """验证去重算法迁移后行为与迁移前一致"""
      # 使用相同的输入数据
      chunks = [create_chunk("..."), create_chunk("...")]

      # 迁移前结果 (硬编码阈值)
      old_result = old_dedup_function(chunks)

      # 迁移后结果 (从配置读取)
      new_result = new_dedup_function(chunks, settings.rag.dedup)

      # 对比结果应完全一致
      assert old_result == new_result
  ```

### 5. 代码审查与清理

- [ ] **5.1 审查所有配置访问点**
  - 确保无直接访问 `settings.xxx` 的散落代码
  - 统一通过辅助类或属性访问

- [ ] **5.2 清理无用的导入和常量**
  - 移除迁移后不再使用的硬编码常量
  - 清理无用的导入语句

- [ ] **5.3 更新文档注释**
  - 为每个配置项添加清晰的 docstring
  - 说明配置项的作用、默认值、合理范围

---

## 重构检查清单

每个模块重构时需完成以下检查:

- [ ] 无遗留的魔法值 (通过 grep 扫描验证)
- [ ] 配置访问模式统一 (通过辅助类或属性)
- [ ] 业务规则正确从 rules.json 读取
- [ ] 单元测试覆盖所有配置项
- [ ] 算法行为一致性验证通过
- [ ] 代码注释和文档更新完成

---

## 验收标准

- [ ] 代码中无遗留的魔法值 (合理的代码常量除外)
- [ ] 配置访问模式统一且清晰
- [ ] rules.json 加载正确性验证通过
- [ ] 单元测试覆盖所有配置项默认值和算法逻辑
- [ ] 算法行为一致性验证通过 (迁移前后输出完全一致)
- [ ] 热更新和降级场景测试归入 [07-compatibility.md](./03-phase-2b-07-compatibility.md) 并验证通过

---

**上一任务:** [05-config-migration.md](./03-phase-2b-05-config-migration.md)  
**下一任务:** [07-compatibility.md](./03-phase-2b-07-compatibility.md)
