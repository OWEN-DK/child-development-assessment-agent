# Phase 1.1: 配置层改造

> **前置文档:** [Overview](./01-phase-1-00-overview.md)
> **状态:** ⏳ 完全待实现

### 🔴 1.1 配置层改造（⏳ 完全待实现）
> 说明：当前项目配置为单一场景模型定义结构，尚未支持多提供商统一配置、模型定价等规划中的功能

> **⚠️ ConfigManager 配置访问修正**: 当前 `ConfigManager` 仅有 `get_config_value(key)` 和 `get_full_config()`，无 `get("llm")` 方法。工厂类需使用 `get_full_config()` 后解析嵌套路径（如 `llm_report_generation`）。
> **⚠️ ConfigChangedEvent 双定义问题**: `event_bus.py` 定义 `ConfigChangedEvent(version_id, changed_keys)`，`events.py` 定义 `ConfigChangedEvent(from_version, to_version, changed_keys, config_snapshot)`。工厂类应使用 `event_bus.py` 版本，通过 `changed_keys` 判断是否触发热更新。
> **⚠️ 配置加载优先级**: `ConfigManager (MySQL)` > `.env` 环境变量（不同环境兜底） > Pydantic 默认值。所有配置模型优先从 MySQL 读取，`.env` 仅作为本地开发/无数据库时的降级方案。

#### Task 1.1.1: 扩展 LLM 配置模块
**Files:**
- Modify: `src/config/modules/models/llm.py`
- Test: `tests/config/test_llm_config.py`

- [ ] **Step 1: 编写测试用例**
```python
def test_llm_providers_config():
    from src.config import settings
    
    # 验证场景配置包含provider字段（使用 qwen3.5-plus 而非 qwen-plus）
    assert settings.model_report_generation.provider == "dashscope"
    assert settings.model_report_generation.model == "qwen3.5-plus"
    assert settings.model_assessment.provider == "dashscope"
    
    # 验证提供商配置
    assert "dashscope" in settings.llm_providers
    assert settings.llm_providers["dashscope"].api_key is not None
```

- [ ] **Step 2: 运行测试验证失败**
Run: `pytest tests/config/test_llm_config.py::test_llm_providers_config -v`
Expected: FAIL with "provider not in model_report_generation"

- [ ] **Step 3: 实现配置扩展**

> **⚠️ 配置迁移策略**: 当前项目使用扁平化配置（如 `model_report_generation: str`），需迁移为嵌套结构。使用 `model_config = SettingsConfigDict(env_nested_delimiter="__")` 支持环境变量覆盖。
> **⚠️ 模型名称修正**: 项目实际使用 `qwen3.5-plus` / `qwen3.5-turbo` / `qwen3-omni-flash`，非 `qwen-plus`。

```python
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Dict, Optional

class LLMProviderConfig(BaseModel):
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    api_version: Optional[str] = None

class ModelPricingConfig(BaseModel):
    input_per_million: float = Field(description="输入Token每百万个费用")
    output_per_million: float = Field(description="输出Token每百万个费用")
    currency: str = Field(default="CNY", description="货币单位")

class LLMSceneConfig(BaseModel):
    provider: str = Field(default="dashscope", description="LLM提供商")
    model: str = Field(description="模型名称")
    temperature: float = Field(default=0.7, ge=0, le=2)
    max_tokens: int = Field(default=2000, gt=0)
    top_p: float = Field(default=0.8, ge=0, le=1)
    presence_penalty: float = Field(default=0.0, ge=-2, le=2)
    frequency_penalty: float = Field(default=0.0, ge=-2, le=2)

class LLMConfig(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env.dev",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
    )
    
    llm_providers: Dict[str, LLMProviderConfig] = Field(default_factory=dict)
    model_pricing: Dict[str, ModelPricingConfig] = Field(default_factory=dict)
    
    # 9大业务场景配置（模型名称使用项目实际的 qwen3.5 系列）
    report_generation: LLMSceneConfig = Field(default_factory=lambda: LLMSceneConfig(model="qwen3.5-plus"))
    assessment: LLMSceneConfig = Field(default_factory=lambda: LLMSceneConfig(model="qwen3.5-plus"))
    validation: LLMSceneConfig = Field(default_factory=lambda: LLMSceneConfig(model="qwen3.5-turbo"))
    metadata_extraction: LLMSceneConfig = Field(default_factory=lambda: LLMSceneConfig(model="qwen3-omni-flash"))
    query_rewrite: LLMSceneConfig = Field(default_factory=lambda: LLMSceneConfig(model="qwen3-omni-flash"))
    query_routing: LLMSceneConfig = Field(default_factory=lambda: LLMSceneConfig(model="qwen3-omni-flash"))
    content_generation: LLMSceneConfig = Field(default_factory=lambda: LLMSceneConfig(model="qwen3.5-plus"))
    vl_parsing: LLMSceneConfig = Field(default_factory=lambda: LLMSceneConfig(model="qwen3-omni-flash"))
    ml_scoring: LLMSceneConfig = Field(default_factory=lambda: LLMSceneConfig(model="qwen3.5-turbo"))
```

**环境变量示例 (.env.dev)**:
```bash
# 提供商凭证配置（使用双下划线分隔层级）
LLM__LLM_PROVIDERS__DASHSCOPE__API_KEY=sk-xxx
LLM__LLM_PROVIDERS__OPENAI__API_KEY=sk-xxx
LLM__LLM_PROVIDERS__OPENAI__BASE_URL=https://api.openai.com/v1

# 场景配置
LLM__REPORT_GENERATION__PROVIDER=dashscope
LLM__REPORT_GENERATION__MODEL=qwen3.5-plus
LLM__REPORT_GENERATION__TEMPERATURE=0.7
```

- [ ] **Step 4: 运行测试验证通过**
Run: `pytest tests/config/test_llm_config.py::test_llm_providers_config -v`
Expected: PASS



#### Task 1.1.2: 扩展 Embedding 配置模块
**Files:**
- Modify: `src/config/modules/models/embedding.py`
- Test: `tests/config/test_embedding_config.py`

- [ ] **Step 1: 编写测试用例**
```python
def test_embedding_provider_config():
    from src.config import settings
    assert hasattr(settings.embedding, "provider")
    assert settings.embedding.provider in ["dashscope", "openai", "ollama"]
```

- [ ] **Step 2: 运行测试验证失败**
Run: `pytest tests/config/test_embedding_config.py::test_embedding_provider_config -v`
Expected: FAIL with "provider not in embedding config"

- [ ] **Step 3: 实现配置扩展**

> **⚠️ 环境变量映射规则**: 所有配置类统一继承 `BaseSettings`，使用 `env_nested_delimiter="__"` 支持环境变量覆盖。

```python
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

class EmbeddingConfig(BaseSettings):
    model_config = SettingsConfigDict(env_nested_delimiter="__")
    provider: str = Field(default="dashscope", description="Embedding提供商")
    model: str = Field(default="text-embedding-v4", description="Embedding模型名称")
    batch_size: int = Field(default=10, description="批量处理大小")
    max_length: int = Field(default=1536, description="最大文本长度")
```

- [ ] **Step 4: 运行测试验证通过**
Run: `pytest tests/config/test_embedding_config.py::test_embedding_provider_config -v`
Expected: PASS



#### Task 1.1.3: 扩展 RAG 检索配置模块
**Files:**
- Modify: `src/config/modules/rag/retrieval.py`
- Test: `tests/config/test_rag_config.py`

- [ ] **Step 1: 编写测试用例**
```python
def test_reranker_provider_config():
    from src.config import settings
    assert hasattr(settings.rag.retrieval, "reranker_provider")
    assert settings.rag.retrieval.reranker_provider == "local"
```

- [ ] **Step 2: 运行测试验证失败**
Run: `pytest tests/config/test_rag_config.py::test_reranker_provider_config -v`
Expected: FAIL with "reranker_provider not in retrieval config"

- [ ] **Step 3: 实现配置扩展**

> **⚠️ 环境变量映射规则**: RetrievalConfig 继承 `BaseSettings` 支持环境变量覆盖。

```python
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

class RetrievalConfig(BaseSettings):
    model_config = SettingsConfigDict(env_nested_delimiter="__")
    reranker_provider: str = Field(default="local", description="Reranker提供商")
    reranker_model: str = Field(default="bge-reranker-v2-m3", description="Reranker模型")
    # ... 原有字段保持不变
```

- [ ] **Step 4: 运行测试验证通过**
Run: `pytest tests/config/test_rag_config.py::test_reranker_provider_config -v`
Expected: PASS
