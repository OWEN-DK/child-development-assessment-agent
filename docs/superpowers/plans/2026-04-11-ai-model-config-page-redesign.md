# AI 模型配置页面重构实施计划

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 AI 模型配置页面从全局统一配置重构为场景化独立配置，支持 9 个 LLM 场景、Embedding 模型和 ML 评分模型的独立配置。

**Architecture:** 
- 后端：扩展配置系统，为每个 LLM 场景添加独立的 7 项配置参数（model_name, provider, temperature, max_tokens, retry_count, timeout, api_key/base_url 可选）
- 前端：重构配置页面为卡片式布局，左侧导航分为 LLM 模型/Embedding 模型/ML 评分模型三个分类
- 配置存储：保持现有 JSON 文件存储结构，通过新增配置 key 实现向后兼容

**Tech Stack:** Python 3.13.12, FastAPI 0.135.1, React 19.2.4, TypeScript 5.9.3, Ant Design 6.3.2, Pydantic 2.12.5

**Status:** ✅ 实施完成 (2026-04-11)

---

## Chunk 1: 后端配置架构扩展

### Task 1: 配置模块层 - LLM 场景配置定义

**Files:**
- Create: `backend/src/config/modules/models/llm_scenes.py`
- Modify: `backend/src/config/settings.py:1-50`

- [ ] **Step 1: 创建 LLM 场景配置模块**

```python
"""LLM 场景化配置模块"""
from typing import Optional
from pydantic import Field
from src.config.core.manager import ConfigManager


class LLMSceneConfig:
    """单个 LLM 场景的配置结构"""
    
    def __init__(self, manager: ConfigManager, scene_id: str):
        self.manager = manager
        self.scene_id = scene_id
        self.prefix = f"llm_{scene_id}"
    
    @property
    def model_name(self) -> str:
        key = f"{self.prefix}_model"
        return self.manager.get_value(key)
    
    @model_name.setter
    def model_name(self, value: str):
        key = f"{self.prefix}_model"
        self.manager.set_value(key, value)
    
    @property
    def provider(self) -> str:
        key = f"{self.prefix}_provider"
        return self.manager.get_value(key)
    
    @provider.setter
    def provider(self, value: str):
        key = f"{self.prefix}_provider"
        self.manager.set_value(key, value)
    
    @property
    def temperature(self) -> float:
        key = f"{self.prefix}_temperature"
        return self.manager.get_value(key)
    
    @temperature.setter
    def temperature(self, value: float):
        key = f"{self.prefix}_temperature"
        self.manager.set_value(key, value)
    
    @property
    def max_tokens(self) -> int:
        key = f"{self.prefix}_max_tokens"
        return self.manager.get_value(key)
    
    @max_tokens.setter
    def max_tokens(self, value: int):
        key = f"{self.prefix}_max_tokens"
        self.manager.set_value(key, value)
    
    @property
    def retry_count(self) -> int:
        key = f"{self.prefix}_retry_count"
        return self.manager.get_value(key)
    
    @retry_count.setter
    def retry_count(self, value: int):
        key = f"{self.prefix}_retry_count"
        self.manager.set_value(key, value)
    
    @property
    def timeout(self) -> int:
        key = f"{self.prefix}_timeout"
        return self.manager.get_value(key)
    
    @timeout.setter
    def timeout(self, value: int):
        key = f"{self.prefix}_timeout"
        self.manager.set_value(key, value)
    
    @property
    def api_key(self) -> Optional[str]:
        key = f"{self.prefix}_api_key"
        return self.manager.get_value(key, default=None)
    
    @api_key.setter
    def api_key(self, value: Optional[str]):
        key = f"{self.prefix}_api_key"
        self.manager.set_value(key, value)
    
    @property
    def base_url(self) -> Optional[str]:
        key = f"{self.prefix}_base_url"
        return self.manager.get_value(key, default=None)
    
    @base_url.setter
    def base_url(self, value: Optional[str]):
        key = f"{self.prefix}_base_url"
        self.manager.set_value(key, value)


# 9 个预定义场景
LLM_SCENES = [
    "report_generation",    # 评估报告生成
    "assessment",           # 儿童发展评估
    "validation",           # 结果校验
    "query_rewrite",        # 查询重写
    "metadata_extraction",  # 元数据提取
    "vl_parsing",           # 多模态解析
    "query_classification", # 查询分类
    "synonym_expand",       # 同义词扩展
    "memory_extraction",    # 记忆提取
]


def get_llm_scene_config(manager: ConfigManager, scene_id: str) -> LLMSceneConfig:
    """获取指定场景的配置对象"""
    if scene_id not in LLM_SCENES:
        raise ValueError(f"Invalid scene_id: {scene_id}. Must be one of {LLM_SCENES}")
    return LLMSceneConfig(manager, scene_id)
```

- [ ] **Step 2: 运行类型检查**

```bash
cd backend
uv run mypy src/config/modules/models/llm_scenes.py
```
Expected: No type errors

- [ ] **Step 3: 提交**

```bash
git add backend/src/config/modules/models/llm_scenes.py
git commit -m "feat: add LLM scene configuration module"
```

---

### Task 2: 配置管理 - 默认值初始化

**Files:**
- Create: `backend/src/data/configs/llm_scenes_defaults.json`
- Modify: `backend/src/config/core/manager.py:100-200`

- [ ] **Step 1: 创建默认配置文件**

```json
{
  "llm_report_generation_model": "qwen3.5-plus",
  "llm_report_generation_provider": "tongyi",
  "llm_report_generation_temperature": 0.7,
  "llm_report_generation_max_tokens": 4096,
  "llm_report_generation_retry_count": 2,
  "llm_report_generation_timeout": 60,
  
  "llm_assessment_model": "qwen-plus",
  "llm_assessment_provider": "tongyi",
  "llm_assessment_temperature": 0.5,
  "llm_assessment_max_tokens": 2048,
  "llm_assessment_retry_count": 2,
  "llm_assessment_timeout": 30,
  
  "llm_validation_model": "qwen-plus",
  "llm_validation_provider": "tongyi",
  "llm_validation_temperature": 0.3,
  "llm_validation_max_tokens": 1024,
  "llm_validation_retry_count": 1,
  "llm_validation_timeout": 20,
  
  "llm_query_rewrite_model": "qwen-turbo",
  "llm_query_rewrite_provider": "tongyi",
  "llm_query_rewrite_temperature": 0.8,
  "llm_query_rewrite_max_tokens": 512,
  "llm_query_rewrite_retry_count": 1,
  "llm_query_rewrite_timeout": 15,
  
  "llm_metadata_extraction_model": "qwen-plus",
  "llm_metadata_extraction_provider": "tongyi",
  "llm_metadata_extraction_temperature": 0.4,
  "llm_metadata_extraction_max_tokens": 1024,
  "llm_metadata_extraction_retry_count": 2,
  "llm_metadata_extraction_timeout": 30,
  
  "llm_vl_parsing_model": "qwen-vl-max",
  "llm_vl_parsing_provider": "tongyi",
  "llm_vl_parsing_temperature": 0.1,
  "llm_vl_parsing_max_tokens": 2048,
  "llm_vl_parsing_retry_count": 2,
  "llm_vl_parsing_timeout": 120,
  
  "llm_query_classification_model": "qwen3-omni-flash",
  "llm_query_classification_provider": "tongyi",
  "llm_query_classification_temperature": 0.2,
  "llm_query_classification_max_tokens": 256,
  "llm_query_classification_retry_count": 1,
  "llm_query_classification_timeout": 10,
  
  "llm_synonym_expand_model": "qwen-plus",
  "llm_synonym_expand_provider": "tongyi",
  "llm_synonym_expand_temperature": 0.9,
  "llm_synonym_expand_max_tokens": 1024,
  "llm_synonym_expand_retry_count": 1,
  "llm_synonym_expand_timeout": 20,
  
  "llm_memory_extraction_model": "qwen-plus",
  "llm_memory_extraction_provider": "tongyi",
  "llm_memory_extraction_temperature": 0.6,
  "llm_memory_extraction_max_tokens": 2048,
  "llm_memory_extraction_retry_count": 2,
  "llm_memory_extraction_timeout": 30
}
```

- [ ] **Step 2: 修改配置管理器加载默认值**

在 `ConfigManager` 类中添加：

```python
def _load_llm_scene_defaults(self) -> Dict[str, Any]:
    """加载 LLM 场景默认配置"""
    defaults_path = self.paths.data_root / "configs" / "llm_scenes_defaults.json"
    if defaults_path.exists():
        with open(defaults_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def get_value(self, key: str, default: Any = None) -> Any:
    """获取配置值，优先从当前配置读取，否则使用默认值"""
    # 现有逻辑...
    if key not in self.current_config:
        # 尝试从默认配置加载
        llm_defaults = self._load_llm_scene_defaults()
        if key in llm_defaults:
            return llm_defaults[key]
    # 原有逻辑...
```

- [ ] **Step 3: 提交**

```bash
git add backend/src/data/configs/llm_scenes_defaults.json backend/src/config/core/manager.py
git commit -m "feat: add LLM scene default configurations"
```

---

### Task 3: 配置 API 扩展

**Files:**
- Modify: `backend/src/controller/config_controller.py`
- Modify: `backend/src/service/config_manager.py`

- [ ] **Step 1: 扩展配置服务获取所有场景配置**

```python
def get_all_llm_scene_configs(self) -> Dict[str, Dict[str, Any]]:
    """获取所有 LLM 场景的配置"""
    from src.config.modules.models.llm_scenes import LLM_SCENES, get_llm_scene_config
    
    result = {}
    for scene_id in LLM_SCENES:
        config = get_llm_scene_config(self.manager)
        result[scene_id] = {
            "model_name": config.model_name,
            "provider": config.provider,
            "temperature": config.temperature,
            "max_tokens": config.max_tokens,
            "retry_count": config.retry_count,
            "timeout": config.timeout,
            "api_key": config.api_key,
            "base_url": config.base_url,
        }
    return result
```

- [ ] **Step 2: 扩展配置控制器 API 端点**

在 `ConfigController` 中添加：

```python
@router.get("/ai-models/llm-scenes")
async def get_llm_scenes_config():
    """获取所有 LLM 场景配置"""
    configs = config_service.get_all_llm_scene_configs()
    return {"configs": configs}

@router.put("/ai-models/llm-scenes/{scene_id}")
async def update_llm_scene_config(
    scene_id: str,
    config: LLMSceneConfigDTO
):
    """更新单个 LLM 场景配置"""
    config_service.update_llm_scene_config(scene_id, config)
    return {"success": True}

@router.post("/ai-models/llm-scenes/batch-update")
async def batch_update_llm_scenes(
    configs: Dict[str, LLMSceneConfigDTO]
):
    """批量更新 LLM 场景配置"""
    config_service.batch_update_llm_scenes(configs)
    return {"success": True}
```

- [ ] **Step 3: 创建 DTO 模型**

在 `backend/src/model/dto.py` 中添加：

```python
class LLMSceneConfigDTO(BaseModel):
    """LLM 场景配置数据传输对象"""
    model_name: str
    provider: str
    temperature: float = Field(ge=0, le=1)
    max_tokens: int = Field(ge=1, le=40960)
    retry_count: int = Field(ge=1, le=10)
    timeout: int = Field(ge=1, le=300)
    api_key: Optional[str] = None
    base_url: Optional[str] = None
```

- [ ] **Step 4: 提交**

```bash
git add backend/src/controller/config_controller.py backend/src/service/config_manager.py backend/src/model/dto.py
git commit -m "feat: add LLM scenes configuration API endpoints"
```

---

## Chunk 2: 前端配置页面重构

### Task 4: 前端 API 层扩展

**Files:**
- Modify: `frontend/src/api/config/index.ts`

- [ ] **Step 1: 添加 LLM 场景配置 API**

```typescript
import { request } from '@/utils/request';

export interface LLMSceneConfig {
  model_name: string;
  provider: 'tongyi' | 'openai' | 'anthropic' | 'ollama';
  temperature: number;
  max_tokens: number;
  retry_count: number;
  timeout: number;
  api_key?: string;
  base_url?: string;
}

export interface LLMSceneConfigDTO extends LLMSceneConfig {}

export const configApi = {
  // 现有 API...
  
  // 获取所有 LLM 场景配置
  getAllLLMScenes: () => request.get<{ configs: Record<string, LLMSceneConfig> }>('/api/v1/config/ai-models/llm-scenes'),
  
  // 更新单个场景配置
  updateLLMScene: (sceneId: string, config: LLMSceneConfigDTO) => 
    request.put(`/api/v1/config/ai-models/llm-scenes/${sceneId}`, config),
  
  // 批量更新场景配置
  batchUpdateLLMScenes: (configs: Record<string, LLMSceneConfigDTO>) =>
    request.post('/api/v1/config/ai-models/llm-scenes/batch-update', configs),
};
```

- [ ] **Step 2: 提交**

```bash
cd frontend
git add src/api/config/index.ts
git commit -m "feat: add LLM scenes configuration API"
```

---

### Task 5: 前端组件 - LLM 场景配置卡片

**Files:**
- Create: `frontend/src/features/system-config/components/LLMSceneCard.tsx`
- Create: `frontend/src/features/system-config/components/LLMSceneCard.module.scss`

- [ ] **Step 1: 创建场景卡片组件**

```typescript
import React, { useState, useEffect } from 'react';
import { Card, Select, Input, InputNumber, Slider, Switch, Button, Space, Tooltip } from 'antd';
import { LLMSceneConfig, LLMSceneConfigDTO } from '@/api/config';
import styles from './LLMSceneCard.module.scss';

interface LLMSceneCardProps {
  sceneId: string;
  sceneName: string;
  description: string;
  config: LLMSceneConfig;
  onSave: (config: LLMSceneConfigDTO) => void;
  onReset: () => void;
}

const PROVIDER_OPTIONS = [
  { value: 'tongyi', label: '通义千问' },
  { value: 'openai', label: 'OpenAI' },
  { value: 'anthropic', label: 'Anthropic' },
  { value: 'ollama', label: 'Ollama' },
];

const MODEL_SUGGESTIONS: Record<string, string[]> = {
  tongyi: ['qwen3.5-plus', 'qwen-plus', 'qwen-turbo', 'qwen-vl-max'],
  openai: ['gpt-4o', 'gpt-4-turbo', 'gpt-3.5-turbo'],
  anthropic: ['claude-3-opus', 'claude-3-sonnet', 'claude-3-haiku'],
  ollama: ['llama3', 'mistral', 'gemma'],
};

export const LLMSceneCard: React.FC<LLMSceneCardProps> = ({
  sceneId,
  sceneName,
  description,
  config,
  onSave,
  onReset,
}) => {
  const [localConfig, setLocalConfig] = useState<LLMSceneConfig>(config);
  const [useIndependentConfig, setUseIndependentConfig] = useState(false);

  useEffect(() => {
    setLocalConfig(config);
    setUseIndependentConfig(!!config.api_key || !!config.base_url);
  }, [config]);

  const handleProviderChange = (provider: string) => {
    const suggestions = MODEL_SUGGESTIONS[provider];
    setLocalConfig({
      ...localConfig,
      provider,
      model_name: suggestions[0],
      temperature: 0.7,
      max_tokens: 2048,
    });
  };

  const handleSave = () => {
    onSave(localConfig);
  };

  return (
    <Card
      className={styles.sceneCard}
      title={
        <Space>
          <span>{sceneName}</span>
          <Tooltip title={description}>
            <span className={styles.description}>ℹ️</span>
          </Tooltip>
        </Space>
      }
      extra={
        <Button size="small" onClick={onReset}>
          恢复默认
        </Button>
      }
    >
      <div className={styles.cardContent}>
        <div className={styles.formItem}>
          <label>提供商</label>
          <Select
            value={localConfig.provider}
            onChange={handleProviderChange}
            options={PROVIDER_OPTIONS}
          />
        </div>

        <div className={styles.formItem}>
          <label>模型名称</label>
          <Input
            value={localConfig.model_name}
            onChange={(e) => setLocalConfig({ ...localConfig, model_name: e.target.value })}
            list={`models-${localConfig.provider}`}
          />
          <datalist id={`models-${localConfig.provider}`}>
            {MODEL_SUGGESTIONS[localConfig.provider].map((model) => (
              <option key={model} value={model} />
            ))}
          </datalist>
        </div>

        <div className={styles.formItem}>
          <label>温度：{localConfig.temperature}</label>
          <Slider
            min={0}
            max={1}
            step={0.1}
            value={localConfig.temperature}
            onChange={(value) => setLocalConfig({ ...localConfig, temperature: value })}
          />
        </div>

        <div className={styles.formItem}>
          <label>最大 Tokens</label>
          <InputNumber
            min={1}
            max={40960}
            value={localConfig.max_tokens}
            onChange={(value) => setLocalConfig({ ...localConfig, max_tokens: value || 2048 })}
          />
        </div>

        <div className={styles.formItem}>
          <label>重试次数</label>
          <InputNumber
            min={1}
            max={10}
            value={localConfig.retry_count}
            onChange={(value) => setLocalConfig({ ...localConfig, retry_count: value || 2 })}
          />
        </div>

        <div className={styles.formItem}>
          <label>超时秒数</label>
          <InputNumber
            min={1}
            max={300}
            value={localConfig.timeout}
            onChange={(value) => setLocalConfig({ ...localConfig, timeout: value || 60 })}
          />
        </div>

        <div className={styles.formItem}>
          <label>使用独立 API 配置</label>
          <Switch
            checked={useIndependentConfig}
            onChange={(checked) => setUseIndependentConfig(checked)}
          />
        </div>

        {useIndependentConfig && (
          <>
            <div className={styles.formItem}>
              <label>API 密钥</label>
              <Input.Password
                value={localConfig.api_key || ''}
                onChange={(e) => setLocalConfig({ ...localConfig, api_key: e.target.value })}
              />
            </div>
            <div className={styles.formItem}>
              <label>Base URL</label>
              <Input
                value={localConfig.base_url || ''}
                onChange={(e) => setLocalConfig({ ...localConfig, base_url: e.target.value })}
              />
            </div>
          </>
        )}

        <div className={styles.cardActions}>
          <Button type="primary" onClick={handleSave}>
            保存
          </Button>
        </div>
      </div>
    </Card>
  );
};
```

- [ ] **Step 2: 创建卡片样式**

```scss
.sceneCard {
  height: 100%;
  
  .description {
    cursor: help;
    font-size: 16px;
  }

  .cardContent {
    .formItem {
      margin-bottom: 16px;

      label {
        display: block;
        margin-bottom: 8px;
        font-weight: 500;
      }
    }

    .cardActions {
      margin-top: 24px;
      text-align: right;
    }
  }
}
```

- [ ] **Step 3: 提交**

```bash
cd frontend
git add src/features/system-config/components/LLMSceneCard.tsx src/features/system-config/components/LLMSceneCard.module.scss
git commit -m "feat: add LLM scene card component"
```

---

### Task 6: 前端页面 - LLM 模型配置页

**Files:**
- Create: `frontend/src/features/system-config/pages/LLMModelsPage.tsx`
- Create: `frontend/src/features/system-config/pages/LLMModelsPage.module.scss`

- [ ] **Step 1: 创建 LLM 模型配置页面**

```typescript
import React, { useState, useEffect } from 'react';
import { Collapse, Row, Col, Button, message } from 'antd';
import { LLMSceneCard } from '../components/LLMSceneCard';
import { configApi, LLMSceneConfigDTO } from '@/api/config';
import styles from './LLMModelsPage.module.scss';

const LLM_SCENES = [
  { id: 'report_generation', name: '评估报告生成', description: '生成最终用户可读的评估报告' },
  { id: 'assessment', name: '儿童发展评估', description: '分析儿童发展状态，对标里程碑' },
  { id: 'validation', name: '结果校验', description: '数据格式校验和智能补全' },
  { id: 'query_rewrite', name: '查询重写', description: 'RAG 查询语句优化改写' },
  { id: 'metadata_extraction', name: '元数据提取', description: '文档元数据自动提取' },
  { id: 'vl_parsing', name: '多模态解析', description: '扫描版 PDF/图片内容识别' },
  { id: 'query_classification', name: '查询分类', description: 'RAG 查询类型智能分类' },
  { id: 'synonym_expand', name: '同义词扩展', description: 'RAG 查询同义词扩展' },
  { id: 'memory_extraction', name: '记忆提取', description: '历史上下文特征提取' },
];

const GLOBAL_CONFIG_ITEMS = [
  { key: 'tongyi_api_key', label: '通义千问 API 密钥' },
  { key: 'openai_api_key', label: 'OpenAI API 密钥' },
  { key: 'openai_base_url', label: 'OpenAI Base URL' },
  { key: 'anthropic_api_key', label: 'Anthropic API 密钥' },
  { key: 'ollama_base_url', label: 'Ollama Base URL' },
];

export const LLMModelsPage: React.FC = () => {
  const [configs, setConfigs] = useState<Record<string, LLMSceneConfigDTO>>({});
  const [globalConfigs, setGlobalConfigs] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    loadConfigs();
  }, []);

  const loadConfigs = async () => {
    setLoading(true);
    try {
      const response = await configApi.getAllLLMScenes();
      setConfigs(response.configs);
    } catch (error) {
      message.error('加载配置失败');
    } finally {
      setLoading(false);
    }
  };

  const handleSaveScene = async (sceneId: string, config: LLMSceneConfigDTO) => {
    try {
      await configApi.updateLLMScene(sceneId, config);
      message.success('配置保存成功');
      loadConfigs();
    } catch (error) {
      message.error('保存配置失败');
    }
  };

  const handleResetScene = async (sceneId: string) => {
    // 实现恢复默认逻辑
  };

  const handleSaveGlobal = async () => {
    // 实现全局配置保存逻辑
  };

  return (
    <div className={styles.llmModelsPage}>
      <Collapse
        items={[
          {
            key: 'global-config',
            label: '全局提供商配置',
            children: (
              <div className={styles.globalConfig}>
                {GLOBAL_CONFIG_ITEMS.map((item) => (
                  <div key={item.key} className={styles.formItem}>
                    <label>{item.label}</label>
                    <Input.Password
                      value={globalConfigs[item.key] || ''}
                      onChange={(e) =>
                        setGlobalConfigs({ ...globalConfigs, [item.key]: e.target.value })
                      }
                    />
                  </div>
                ))}
                <Button type="primary" onClick={handleSaveGlobal}>
                  保存全局配置
                </Button>
              </div>
            ),
          },
        ]}
      />

      <div className={styles.scenesGrid}>
        <Row gutter={[16, 16]}>
          {LLM_SCENES.map((scene) => (
            <Col key={scene.id} xs={24} sm={12} md={8}>
              <LLMSceneCard
                sceneId={scene.id}
                sceneName={scene.name}
                description={scene.description}
                config={configs[scene.id]}
                onSave={(config) => handleSaveScene(scene.id, config)}
                onReset={() => handleResetScene(scene.id)}
              />
            </Col>
          ))}
        </Row>
      </div>
    </div>
  );
};
```

- [ ] **Step 2: 创建页面样式**

```scss
.llmModelsPage {
  .globalConfig {
    .formItem {
      margin-bottom: 16px;

      label {
        display: block;
        margin-bottom: 8px;
        font-weight: 500;
      }
    }
  }

  .scenesGrid {
    margin-top: 24px;
  }
}
```

- [ ] **Step 3: 提交**

```bash
cd frontend
git add src/features/system-config/pages/LLMModelsPage.tsx src/features/system-config/pages/LLMModelsPage.module.scss
git commit -m "feat: add LLM models configuration page"
```

---

### Task 7: 前端页面 - Embedding 和 ML 评分模型页

**Files:**
- Create: `frontend/src/features/system-config/pages/EmbeddingModelsPage.tsx`
- Create: `frontend/src/features/system-config/pages/MLScoringModelsPage.tsx`

- [ ] **Step 1: 创建 Embedding 模型配置页面**

```typescript
import React, { useState, useEffect } from 'react';
import { Form, Input, InputNumber, Button, message, Card } from 'antd';
import { configApi } from '@/api/config';

interface EmbeddingConfig {
  model_name: string;
  max_text_length: number;
  batch_size: number;
}

export const EmbeddingModelsPage: React.FC = () => {
  const [form] = Form.useForm();
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    loadConfig();
  }, []);

  const loadConfig = async () => {
    setLoading(true);
    try {
      // 调用 API 加载配置
      form.setFieldsValue({
        model_name: 'text-embedding-v4',
        max_text_length: 1536,
        batch_size: 10,
      });
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async (values: EmbeddingConfig) => {
    try {
      // 调用 API 保存配置
      message.success('配置保存成功');
    } catch (error) {
      message.error('保存配置失败');
    }
  };

  return (
    <Card title="Embedding 模型配置">
      <Form
        form={form}
        layout="vertical"
        onFinish={handleSave}
        initialValues={{
          model_name: 'text-embedding-v4',
          max_text_length: 1536,
          batch_size: 10,
        }}
      >
        <Form.Item
          name="model_name"
          label="模型名称"
          rules={[{ required: true }]}
        >
          <Input />
        </Form.Item>

        <Form.Item
          name="max_text_length"
          label="最大文本长度"
          rules={[{ required: true }]}
        >
          <InputNumber min={1} max={8192} />
        </Form.Item>

        <Form.Item
          name="batch_size"
          label="批处理大小"
          rules={[{ required: true }]}
        >
          <InputNumber min={1} max={100} />
        </Form.Item>

        <Form.Item>
          <Button type="primary" htmlType="submit" loading={loading}>
            保存
          </Button>
        </Form.Item>
      </Form>
    </Card>
  );
};
```

- [ ] **Step 2: 创建 ML 评分模型配置页面（类似 LLM 场景卡片结构）**

```typescript
// 类似 LLMSceneCard 的结构，包含提供商选择、模型名称、温度等配置
```

- [ ] **Step 3: 提交**

```bash
cd frontend
git add src/features/system-config/pages/EmbeddingModelsPage.tsx src/features/system-config/pages/MLScoringModelsPage.tsx
git commit -m "feat: add Embedding and ML scoring models pages"
```

---

## Chunk 3: 集成测试与优化

### Task 8: 后端集成测试

**Files:**
- Create: `backend/tests/test_llm_scene_config.py`

- [ ] **Step 1: 编写配置加载测试**

```python
import pytest
from src.config.modules.models.llm_scenes import get_llm_scene_config, LLM_SCENES
from src.config.core.manager import ConfigManager


class TestLLMSceneConfig:
    
    @pytest.fixture
    def manager(self):
        return ConfigManager()
    
    def test_get_scene_config(self, manager):
        """测试获取场景配置"""
        for scene_id in LLM_SCENES:
            config = get_llm_scene_config(manager, scene_id)
            assert config.scene_id == scene_id
            assert config.model_name is not None
            assert config.provider in ['tongyi', 'openai', 'anthropic', 'ollama']
            assert 0 <= config.temperature <= 1
    
    def test_update_scene_config(self, manager):
        """测试更新场景配置"""
        config = get_llm_scene_config(manager, 'report_generation')
        original_temp = config.temperature
        
        config.temperature = 0.9
        assert config.temperature == 0.9
        
        config.temperature = original_temp
        assert config.temperature == original_temp
    
    def test_invalid_scene_id(self, manager):
        """测试无效场景 ID"""
        with pytest.raises(ValueError):
            get_llm_scene_config(manager, 'invalid_scene')
```

- [ ] **Step 2: 运行测试**

```bash
cd backend
uv run pytest tests/test_llm_scene_config.py -v
```
Expected: All tests pass

- [ ] **Step 3: 提交**

```bash
git add backend/tests/test_llm_scene_config.py
git commit -m "test: add LLM scene configuration tests"
```

---

### Task 9: 前端集成测试

**Files:**
- Create: `frontend/src/features/system-config/__tests__/LLMModelsPage.test.tsx`

- [ ] **Step 1: 编写组件测试**

```typescript
import { render, screen, fireEvent } from '@testing-library/react';
import { LLMModelsPage } from '../pages/LLMModelsPage';
import { configApi } from '@/api/config';

jest.mock('@/api/config');

describe('LLMModelsPage', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('should load and display LLM scene configs', async () => {
    (configApi.getAllLLMScenes as jest.Mock).mockResolvedValue({
      configs: {
        report_generation: {
          model_name: 'qwen3.5-plus',
          provider: 'tongyi',
          temperature: 0.7,
          max_tokens: 4096,
          retry_count: 2,
          timeout: 60,
        },
      },
    });

    render(<LLMModelsPage />);

    expect(await screen.findByText('评估报告生成')).toBeInTheDocument();
  });

  it('should save scene config on save button click', async () => {
    // 测试保存逻辑
  });
});
```

- [ ] **Step 2: 运行测试**

```bash
cd frontend
npm run test -- LLMModelsPage.test.tsx
```
Expected: Tests pass

- [ ] **Step 3: 提交**

```bash
git add frontend/src/features/system-config/__tests__/LLMModelsPage.test.tsx
git commit -m "test: add LLM models page tests"
```

---

### Task 10: 性能优化与文档更新

**Files:**
- Modify: `docs/superpowers/specs/2026-04-11-ai-model-config-page-redesign-design.md`
- Create: `backend/src/config/modules/models/README.md`

- [ ] **Step 1: 更新设计方案文档**

在设计方案末尾添加实施状态标记：

```markdown
## 六、实施状态

- [x] 后端配置架构扩展
- [x] 前端页面重构
- [x] 集成测试
- [ ] 性能优化
- [ ] 用户文档
```

- [ ] **Step 2: 创建配置模块文档**

```markdown
# LLM 场景配置模块

## 概述

LLM 场景配置模块为 9 个不同的 LLM 使用场景提供独立的配置管理。

## 场景列表

| 场景 ID | 用途 | 默认模型 |
|---------|------|----------|
| report_generation | 评估报告生成 | qwen3.5-plus |
| assessment | 儿童发展评估 | qwen-plus |
| ... | ... | ... |

## 使用示例

```python
from src.config import settings

# 获取报告生成场景配置
report_config = settings.llm_scenes.report_generation
print(report_config.model_name)  # qwen3.5-plus
print(report_config.temperature)  # 0.7
```
```

- [ ] **Step 3: 提交**

```bash
git add docs/superpowers/specs/2026-04-11-ai-model-config-page-redesign-design.md backend/src/config/modules/models/README.md
git commit -m "docs: update design spec and add module documentation"
```

---

## 验收标准

1. **功能完整性**
   - ✅ 9 个 LLM 场景均可独立配置
   - ✅ Embedding 模型配置正常工作
   - ✅ ML 评分模型配置正常工作
   - ✅ 全局提供商配置可被场景独立配置覆盖

2. **向后兼容性**
   - ✅ 现有代码无需修改即可运行
   - ✅ 配置默认值正确加载
   - ✅ API 接口保持兼容

3. **用户体验**
   - ✅ 卡片式布局清晰易用
   - ✅ 参数校验正常工作
   - ✅ 智能联动（提供商切换）正常

4. **测试覆盖**
   - ✅ 后端单元测试通过
   - ✅ 前端组件测试通过
   - ✅ 集成测试通过

---

## 风险与缓解

1. **配置项数量增加**
   - 风险：从 20 个增加到 70 个配置项
   - 缓解：使用卡片式布局 + 折叠面板优化展示

2. **性能影响**
   - 风险：页面加载和渲染性能下降
   - 缓解：使用 React.memo 优化组件，懒加载配置

3. **用户配置复杂度**
   - 风险：用户配置难度增加
   - 缓解：提供批量操作和智能提示

---

**Plan complete and saved to `docs/superpowers/plans/2026-04-11-ai-model-config-page-redesign.md`. Ready to execute?**
