# Phase 2B.3: 提示词校验与测试

> **状态:** ⏳ 待实现
> **前置任务:** [02-prompt-migration.md](./03-phase-2b-02-prompt-migration.md)

## 目标

建立提示词校验机制，确保迁移后的提示词占位符正确、渲染无误，并通过完整的测试覆盖验证提示词质量。

## 实施任务

### 1. 占位符校验机制

- [ ] **1.1 实现占位符一致性校验器**
  ```python
  # src/core/prompt/validator.py (与 manager.py 同级目录)
  import re
  from dataclasses import dataclass
  from typing import List

  @dataclass
  class ValidationResult:
      is_valid: bool
      missing: List[str]
      extra: List[str]

  class PromptValidator:
      @staticmethod
      def validate_variables(prompt_key: str, template: str, declared_variables: List[str]) -> ValidationResult:
          """
          校验模板中的实际占位符与声明的 variables 是否一致
          """
          actual_variables = re.findall(r'\{(\w+)\}', template)
          missing = set(actual_variables) - set(declared_variables)
          extra = set(declared_variables) - set(actual_variables)
          return ValidationResult(
              is_valid=len(missing) == 0 and len(extra) == 0,
              missing=list(missing),
              extra=list(extra)
          )
  ```

- [ ] **1.2 集成到 PromptManager 保存流程**
  ```python
  # src/core/prompt/manager.py
  def save_prompt(self, prompt_key: str, content: str, variables: List[str], ...):
      # 校验占位符一致性
      result = PromptValidator.validate_variables(prompt_key, content, variables)
      if not result.is_valid:
          raise PromptValidationError(f"Prompt '{prompt_key}' variables mismatch: {result}")

      # 校验通过后保存
      ...
  ```

### 2. 提示词渲染测试

- [ ] **2.1 编写提示词渲染单元测试**
  ```python
  # tests/core/prompts/test_prompt_rendering.py
  @pytest.mark.parametrize("prompt_key,variables,expected_substrings", [
      ("assessment_system", {"child_age": 3, "issues": "..."}, ["3岁", "评估"]),
      ("query_rewrite", {"query": "前庭觉训练"}, ["前庭觉"]),
      ("metadata_extraction", {"content": "..."}, ["topics", "brain_regions"]),
  ])
  def test_prompt_rendering(prompt_key, variables, expected_substrings, prompt_manager):
      rendered = prompt_manager.get_prompt(prompt_key, variables=variables)
      for substring in expected_substrings:
          assert substring in rendered, f"Expected '{substring}' in rendered prompt"
  ```

- [ ] **2.2 边界条件测试**
  - 空变量值渲染
  - 特殊字符 (引号、换行、JSON) 在变量中的转义
  - 超长变量值渲染 (验证模板截断行为)

### 3. Fallback 机制测试

- [ ] **3.1 模拟 PromptManager 不可用**
  ```python
  # tests/core/prompts/test_prompt_fallback.py
  def test_fallback_when_prompt_manager_unavailable(mock_prompt_manager):
      mock_prompt_manager.get_prompt.side_effect = PromptManagerUnavailable()

      # 验证降级到 fallback
      result = some_function_using_prompt("assessment_system")
      assert "你是一个儿童发展评估专家" in result  # fallback 内容
  ```

- [ ] **3.2 验证 fallback 内容完整性**
  - 确保 fallback 包含所有必要指令
  - 验证 fallback 占位符可正确渲染

### 4. 回归测试

- [ ] **4.1 核心评估流程回归测试**
  ```bash
  pytest tests/e2e/test_assessment_workflow.py -v
  ```
  - 验证完整评估流程输出与迁移前一致
  - 对比报告内容、分数、建议等关键字段

- [ ] **4.2 RAG 检索流程回归测试**
  ```bash
  pytest tests/service/test_retrieval_service.py -v
  ```
  - 验证检索结果数量和质量无退化
  - 对比同义词扩展、查询重写效果

- [ ] **4.3 文档导入流程回归测试**
  ```bash
  pytest tests/core/test_metadata_extractor.py tests/core/test_layered_content.py -v
  ```
  - 验证元数据提取准确性
  - 验证分层内容生成质量

### 5. 性能测试

- [ ] **5.1 提示词加载延迟测试**
  ```python
  # tests/core/prompts/test_prompt_performance.py
  def test_prompt_load_latency(prompt_manager):
      start = time.perf_counter()
      prompt_manager.get_prompt("assessment_system")
      latency = time.perf_counter() - start

      # Redis 缓存命中应 <5ms
      assert latency < 0.005, f"Prompt load latency too high: {latency*1000:.2f}ms"
  ```

- [ ] **5.2 并发加载测试**
  - 验证多线程/异步并发加载提示词时无竞态条件
  - 验证 Redis 缓存并发安全

### 6. A/B 测试支持验证

- [ ] **6.1 验证 A/B 测试分流功能**
  - 创建两个版本的提示词
  - 配置 A/B 测试流量分配 (如 50/50)
  - 验证请求被正确分流到不同版本

- [ ] **6.2 验证版本切换功能**
  - 切换提示词到指定版本
  - 验证缓存失效并加载新版本

---

## 测试覆盖要求

| 测试类型 | 覆盖范围 | 最低覆盖率 |
|---------|---------|-----------|
| 单元测试 | 占位符校验、渲染逻辑、Fallback | 90% |
| 集成测试 | PromptManager 完整流程 | 100% |
| 回归测试 | 核心评估流程、RAG 检索、文档导入 | 全部通过 |
| 性能测试 | 加载延迟、并发安全 | 满足基线 |

---

## 验收标准

- [ ] 占位符一致性校验器实现并集成到保存流程
- [ ] 所有提示词渲染测试通过
- [ ] Fallback 机制测试通过
- [ ] 回归测试 100% 通过
- [ ] 性能测试满足基线要求 (缓存命中 <5ms)
- [ ] A/B 测试分流和版本切换功能验证通过

---

**上一任务:** [02-prompt-migration.md](./03-phase-2b-02-prompt-migration.md)  
**下一任务:** [04-config-scan.md](./03-phase-2b-04-config-scan.md)
