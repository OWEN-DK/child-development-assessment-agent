# Phase 1.2: 热更新机制

> **前置文档:** [Overview](./01-phase-1-00-overview.md) | [工厂类重构](./01-phase-1-02-factory-refactor.md)
> **状态:** ⏳ 完全待实现

> **⚠️ 实施顺序调整**: 配置校验层 (Task 1.3.1) 需在工厂类重构 (Task 1.2.2) 之前实现，因为工厂依赖校验器。

### 🔴 1.3 热更新机制（⏳ 完全待实现）
> 说明：当前尚未实现配置变更监听、实例自动重建、废弃实例延迟销毁等热更新能力，配置修改后需要重启服务才能生效。

#### Task 1.3.1: 实现配置校验层
**Files:**
- Create: `src/core/llm/config_validator.py`
- Test: `tests/core/llm/test_config_validator.py`

> **⚠️ 复用 Pydantic 校验**: 不再手动实现校验规则，直接使用 `LLMSceneConfig.model_validate()` 进行校验，避免双重校验规则 diverge。

- [ ] **Step 1: 编写测试用例**
```python
def test_llm_config_validator():
    from src.config.modules.models.llm import LLMSceneConfig
    
    # 测试有效配置（使用 Pydantic 校验）
    valid_config = {
        "provider": "dashscope",
        "model": "qwen3.5-plus",
        "temperature": 0.7,
        "max_tokens": 2000,
        "top_p": 0.8,
        "presence_penalty": 0.0,
        "frequency_penalty": 0.0
    }
    result = LLMSceneConfig.model_validate(valid_config)
    assert result.provider == "dashscope"
    
    # 测试无效配置（temperature超出范围）
    import pytest
    invalid_config = valid_config.copy()
    invalid_config["temperature"] = 3.0
    with pytest.raises(Exception):  # Pydantic ValidationError
        LLMSceneConfig.model_validate(invalid_config)
    
    # 测试max_tokens为负数
    invalid_config = valid_config.copy()
    invalid_config["max_tokens"] = -100
    with pytest.raises(Exception):
        LLMSceneConfig.model_validate(invalid_config)
```

- [ ] **Step 2: 运行测试验证失败**
Run: `pytest tests/core/llm/test_config_validator.py::test_llm_config_validator -v`
Expected: FAIL with "ModuleNotFoundError"

- [ ] **Step 3: 实现配置校验层**
```python
from typing import List, Dict, Any
from pydantic import BaseModel, Field, ValidationError

class ValidationResult(BaseModel):
    is_valid: bool = Field(default=True)
    errors: List[str] = Field(default_factory=list)

class LLMConfigValidator:
    """LLM配置校验器（复用 Pydantic LLMSceneConfig 的约束）"""
    
    def validate(self, config: Dict[str, Any]) -> ValidationResult:
        """校验LLM配置是否合法（使用 Pydantic model_validate）"""
        result = ValidationResult()
        
        try:
            from src.config.modules.models.llm import LLMSceneConfig
            LLMSceneConfig.model_validate(config)
        except ValidationError as e:
            result.is_valid = False
            for error in e.errors():
                field = ".".join(str(x) for x in error.get("loc", []))
                msg = error.get("msg", "")
                result.errors.append(f"{field}: {msg}")
        
        return result

# 全局校验器实例
llm_config_validator = LLMConfigValidator()
```

- [ ] **Step 4: 运行测试验证通过**
Run: `pytest tests/core/llm/test_config_validator.py::test_llm_config_validator -v`
Expected: PASS



#### Task 1.3.2: 测试零停机实例重建
**Files:**
- Test: `tests/core/llm/test_hot_reload.py`

- [ ] **Step 1: 编写热更新测试用例**

> **测试要点**: 验证引用计数机制确保旧实例在活跃请求完成后才清理，而非固定延迟。
> **⚠️ ConfigChangedEvent 签名修正**: 使用 `event_bus.py` 实际签名 `(version_id, changed_keys)`。
> **⚠️ 模块级单例定义**: 测试中使用工厂实例而非未定义的模块级变量。

```python
import asyncio
import pytest
from src.core.llm.factory import LLMServiceFactory
from src.core.event_bus import ConfigChangedEvent

@pytest.mark.asyncio
async def test_hot_reload_zero_downtime(llm_service_factory: LLMServiceFactory):
    # 创建初始实例
    initial_llm = await llm_service_factory.create("report_generation")
    initial_id = id(initial_llm)
    
    # 模拟配置变更事件（使用实际签名）
    event = ConfigChangedEvent(
        version_id="test_v1",
        changed_keys=["llm_report_generation_temperature"]
    )
    await llm_service_factory._on_config_changed(event)
    
    # 创建新实例（应返回新实例）
    new_llm = await llm_service_factory.create("report_generation")
    new_id = id(new_llm)
    
    # 验证实例已更新
    assert initial_id != new_id
    
    # 验证旧实例仍在 deprecated 列表中（因为初始实例引用计数未释放）
    assert len(llm_service_factory._deprecated_instances) == 1
    
    # 释放初始实例引用
    await llm_service_factory.release("report_generation")
    
    # 验证旧实例已被清理（引用计数归零）
    assert len(llm_service_factory._deprecated_instances) == 0


@pytest.mark.asyncio
async def test_hot_reload_concurrent_requests(llm_service_factory: LLMServiceFactory):
    """测试并发请求场景下热更新安全性"""
    # 创建 3 个并发请求
    tasks = [
        llm_service_factory.create("report_generation")
        for _ in range(3)
    ]
    instances = await asyncio.gather(*tasks)
    
    # 验证所有请求获取到同一实例
    assert len(set(id(inst) for inst in instances)) == 1
    
    # 触发配置变更
    event = ConfigChangedEvent(
        version_id="test_v2",
        changed_keys=["llm_report_generation_model"]
    )
    await llm_service_factory._on_config_changed(event)
    
    # 旧实例应在 deprecated 中，引用计数为 3
    deprecated = list(llm_service_factory._deprecated_instances.values())
    assert len(deprecated) == 1
    assert deprecated[0]["ref_count"] == 3
    
    # 逐个释放引用
    for _ in range(3):
        await llm_service_factory.release("report_generation")
    
    # 验证所有旧实例已清理
    assert len(llm_service_factory._deprecated_instances) == 0
```

- [ ] **Step 2: 运行测试验证**
Run: `pytest tests/core/llm/test_hot_reload.py::test_hot_reload_zero_downtime -v`
Expected: PASS



#### Task 1.3.3: 接入 EventBus
**Files:**
- Modify: `src/core/llm/factory.py` (已在Task 1.2.2中完成)
- Test: `tests/core/llm/test_event_bus_integration.py`

- [ ] **Step 1: 编写事件集成测试**

> **测试要点**: 验证 EventBus 发布配置变更事件后，工厂正确触发实例重建。
> **⚠️ ConfigChangedEvent 签名修正**: 使用 `(version_id, changed_keys)`。

```python
import asyncio
import pytest
from src.config import ConfigManager
from src.core.event_bus import event_bus, ConfigChangedEvent

@pytest.mark.asyncio
async def test_config_change_event_triggers_rebuild(llm_service_factory):
    # 创建初始实例
    initial_llm = await llm_service_factory.create("report_generation")
    initial_id = id(initial_llm)
    
    # 发布配置变更事件（使用实际签名）
    event = ConfigChangedEvent(
        version_id="test_v3",
        changed_keys=["llm_report_generation_model"]
    )
    event_bus.publish(event)
    
    # 给异步 handler 一点时间执行
    await asyncio.sleep(0.1)
    
    # 创建新实例（应触发重建）
    new_llm = await llm_service_factory.create("report_generation")
    
    # 验证实例已重建
    assert initial_id != id(new_llm)
    assert hasattr(new_llm, "model") or hasattr(new_llm, "model_name")
```

- [ ] **Step 2: 运行测试验证通过**
Run: `pytest tests/core/llm/test_event_bus_integration.py::test_config_change_event_triggers_rebuild -v`
Expected: PASS
