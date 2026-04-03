# 配置管理系统设计方案

**日期**: 2026-04-02  
**状态**: 待审批  
**作者**: AI Assistant

---

## 一、核心设计理念

1. **`.env.dev` 作为默认配置**：保持现有 `.env.dev` 文件作为初始默认值
2. **数据库存储运行时配置**：新增配置表，存储用户通过前端修改的配置值
3. **配置优先级**：数据库配置 > `.env.dev` 默认配置
4. **配置分类管理**：按功能模块分组展示配置项

---

## 二、后端改动

### 2.1 新增配置管理模块

#### 文件：`backend/src/model/config.py` (新建)

```python
from sqlalchemy import Column, String, Float, Boolean, Integer, DateTime, JSON
from datetime import datetime
from src.core.database import Base

class ConfigItem(Base):
    __tablename__ = "config_items"
    
    id = Column(String, primary_key=True)  # 配置项标识，如 "rag_hybrid_bm25_weight"
    value = Column(JSON, nullable=False)   # 配置值，支持多种类型
    category = Column(String, nullable=False)  # 配置分类，如 "RAG", "Model", "App"
    description = Column(String)  # 配置描述
    is_active = Column(Boolean, default=True)  # 是否启用
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    updated_by = Column(String)  # 更新者（前端用户 ID 或"system"）


class ConfigHistory(Base):
    __tablename__ = "config_history"
    
    id = Column(String, primary_key=True)
    config_key = Column(String, ForeignKey("config_items.id"))
    old_value = Column(JSON)
    new_value = Column(JSON)
    changed_by = Column(String)
    changed_at = Column(DateTime, default=datetime.utcnow)
    reason = Column(String)  # 变更原因（可选）
```

#### 文件：`backend/src/service/config_service.py` (新建)

```python
from typing import Any, Dict, List, Optional, Tuple
from src.model.config import ConfigItem, ConfigHistory
from src.config.settings import settings
import json

class ConfigService:
    """配置管理服务"""
    
    def get_config(self, key: str) -> Optional[Any]:
        """获取配置值（仅从数据库）"""
        # 实现从数据库查询配置
        pass
    
    def get_config_or_default(self, key: str) -> Any:
        """获取配置值（数据库 > 默认值）"""
        db_value = self.get_config(key)
        if db_value is not None:
            return db_value
        # 从 settings 获取默认值
        return getattr(settings, key, None)
    
    def get_all_configs(self) -> Dict[str, Any]:
        """获取所有配置"""
        pass
    
    def update_config(
        self, 
        key: str, 
        value: Any, 
        category: str, 
        description: str = None,
        updated_by: str = "user"
    ) -> bool:
        """更新配置值"""
        pass
    
    def batch_update_configs(self, configs: Dict[str, Any]) -> bool:
        """批量更新配置"""
        pass
    
    def reset_config_to_default(self, key: str) -> bool:
        """重置为.env.dev 默认值"""
        pass
    
    def reset_all_configs(self) -> bool:
        """重置所有配置为默认值"""
        pass
    
    def get_config_categories(self) -> List[str]:
        """获取所有配置分类"""
        pass
    
    def get_config_schema(self) -> Dict[str, Dict]:
        """获取配置 Schema（包含元数据）"""
        pass
    
    def validate_config_value(self, key: str, value: Any) -> Tuple[bool, str]:
        """验证配置值是否合法"""
        pass
    
    def get_config_history(self, key: str, limit: int = 20) -> List[Dict]:
        """获取配置变更历史"""
        pass


config_service = ConfigService()
```

### 2.2 修改配置读取逻辑

#### 文件：`backend/src/config/settings.py` (修改)

**改动点 1**: 添加配置缓存和动态读取机制

```python
class Settings(BaseSettings):
    # ... 现有字段保持不变 ...
    
    # 新增：运行时配置缓存
    _runtime_config_cache: Dict[str, Any] = {}
    
    def get_runtime_value(self, key: str, default_value: Any) -> Any:
        """获取运行时配置值（数据库 > 缓存 > 默认值）"""
        # 1. 检查缓存
        if key in self._runtime_config_cache:
            return self._runtime_config_cache[key]
        
        # 2. 查询数据库
        try:
            from src.service.config_service import config_service
            db_value = config_service.get_config(key)
            if db_value is not None:
                self._runtime_config_cache[key] = db_value
                return db_value
        except Exception as e:
            # 数据库不可用时使用默认值
            import logging
            logging.getLogger("src.config.settings").debug(
                f"Database config not available for {key}, using default: {e}"
            )
        
        # 3. 返回默认值
        return default_value
    
    def refresh_config_cache(self, key: str = None):
        """刷新配置缓存"""
        if key:
            self._runtime_config_cache.pop(key, None)
        else:
            self._runtime_config_cache.clear()
```

**改动点 2**: 为每个配置项添加元数据（以部分配置为例）

```python
class Settings(BaseSettings):
    # App 配置
    app_name: str = Field(
        "Child Development Assessment Agent",
        validation_alias="APP_NAME",
        description="应用名称",
        json_schema_extra={
            "category": "App",
            "display_name": "应用名称",
            "value_type": "str"
        }
    )
    
    debug: bool = Field(
        True,
        validation_alias="DEBUG",
        description="是否开启调试模式",
        json_schema_extra={
            "category": "App",
            "display_name": "调试模式",
            "value_type": "bool"
        }
    )
    
    app_port: int = Field(
        8000,
        validation_alias="APP_PORT",
        description="服务监听端口",
        ge=1024,
        le=65535,
        json_schema_extra={
            "category": "App",
            "display_name": "端口号",
            "value_type": "int",
            "validation_rules": {"min": 1024, "max": 65535}
        }
    )
    
    # RAG 配置示例
    rag_hybrid_bm25_weight: float = Field(
        0.5,
        validation_alias="RAG_HYBRID_BM25_WEIGHT",
        description="混合检索中 BM25 关键词检索的权重",
        ge=0,
        le=1,
        json_schema_extra={
            "category": "RAG",
            "display_name": "BM25 权重",
            "value_type": "float",
            "validation_rules": {"min": 0, "max": 1, "step": 0.01}
        }
    )
    
    rag_cache_enabled: bool = Field(
        True,
        validation_alias="RAG_CACHE_ENABLED",
        description="是否开启 RAG 查询缓存",
        json_schema_extra={
            "category": "RAG",
            "display_name": "缓存开关",
            "value_type": "bool"
        }
    )
    
    rag_chunk_size: int = Field(
        1024,
        validation_alias="RAG_CHUNK_SIZE",
        description="通用文本分块大小",
        ge=100,
        le=8192,
        json_schema_extra={
            "category": "RAG",
            "display_name": "分块大小",
            "value_type": "int",
            "validation_rules": {"min": 100, "max": 8192, "step": 100}
        }
    )
```

### 2.3 新增配置管理 API

#### 文件：`backend/src/controller/config_controller.py` (新建)

```python
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Any, Dict, List, Optional
from src.service.config_service import config_service
from src.utils.logger import logger

router = APIRouter(prefix="/config", tags=["Configuration"])


class ConfigItemResponse(BaseModel):
    key: str
    value: Any
    category: str
    description: str
    default_value: Any
    value_type: str
    validation_rules: Optional[Dict] = None
    is_modified: bool = False


class ConfigUpdateRequest(BaseModel):
    key: str
    value: Any
    category: str
    description: Optional[str] = None


class ConfigBatchUpdateRequest(BaseModel):
    configs: List[ConfigUpdateRequest]
    reason: Optional[str] = None


@router.get("")
async def get_all_configs() -> Dict[str, Any]:
    """获取所有配置项"""
    try:
        configs = config_service.get_all_configs()
        return {"status": "success", "configs": configs}
    except Exception as e:
        logger.error(f"Failed to get all configs: {e}")
        raise HTTPException(status_code=500, detail=f"获取配置失败：{str(e)}")


@router.get("/categories")
async def get_config_categories() -> Dict[str, List[str]]:
    """获取所有配置分类"""
    try:
        categories = config_service.get_config_categories()
        return {"status": "success", "categories": categories}
    except Exception as e:
        logger.error(f"Failed to get config categories: {e}")
        raise HTTPException(status_code=500, detail=f"获取分类失败：{str(e)}")


@router.get("/{category}")
async def get_configs_by_category(category: str) -> Dict[str, Any]:
    """按分类获取配置项"""
    try:
        configs = config_service.get_all_configs()
        filtered = {
            k: v for k, v in configs.items() 
            if v.get("category") == category
        }
        return {"status": "success", "configs": filtered}
    except Exception as e:
        logger.error(f"Failed to get configs for category {category}: {e}")
        raise HTTPException(status_code=500, detail=f"获取配置失败：{str(e)}")


@router.get("/schema")
async def get_config_schema() -> Dict[str, Any]:
    """获取配置 Schema（包含元数据）"""
    try:
        schema = config_service.get_config_schema()
        return {"status": "success", "schema": schema}
    except Exception as e:
        logger.error(f"Failed to get config schema: {e}")
        raise HTTPException(status_code=500, detail=f"获取配置 Schema 失败：{str(e)}")


@router.put("/{key}")
async def update_config(key: str, request: ConfigUpdateRequest) -> Dict[str, str]:
    """更新单个配置项"""
    try:
        # 验证配置值
        is_valid, error_msg = config_service.validate_config_value(key, request.value)
        if not is_valid:
            raise HTTPException(status_code=400, detail=error_msg)
        
        success = config_service.update_config(
            key=key,
            value=request.value,
            category=request.category,
            description=request.description
        )
        
        if success:
            return {"status": "success", "message": f"配置 {key} 已更新"}
        else:
            raise HTTPException(status_code=500, detail="更新配置失败")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update config {key}: {e}")
        raise HTTPException(status_code=500, detail=f"更新配置失败：{str(e)}")


@router.post("/batch")
async def batch_update_configs(request: ConfigBatchUpdateRequest) -> Dict[str, Any]:
    """批量更新配置"""
    try:
        configs_dict = {
            cfg.key: {
                "value": cfg.value,
                "category": cfg.category,
                "description": cfg.description
            }
            for cfg in request.configs
        }
        
        success = config_service.batch_update_configs(configs_dict)
        
        if success:
            return {
                "status": "success",
                "message": f"成功更新 {len(request.configs)} 个配置项"
            }
        else:
            raise HTTPException(status_code=500, detail="批量更新配置失败")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to batch update configs: {e}")
        raise HTTPException(status_code=500, detail=f"批量更新配置失败：{str(e)}")


@router.post("/reset/{key}")
async def reset_config(key: str) -> Dict[str, str]:
    """重置单个配置项为默认值"""
    try:
        success = config_service.reset_config_to_default(key)
        if success:
            return {"status": "success", "message": f"配置 {key} 已重置为默认值"}
        else:
            raise HTTPException(status_code=500, detail="重置配置失败")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to reset config {key}: {e}")
        raise HTTPException(status_code=500, detail=f"重置配置失败：{str(e)}")


@router.post("/reset-all")
async def reset_all_configs() -> Dict[str, str]:
    """重置所有配置为默认值"""
    try:
        success = config_service.reset_all_configs()
        if success:
            return {"status": "success", "message": "所有配置已重置为默认值"}
        else:
            raise HTTPException(status_code=500, detail="重置配置失败")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to reset all configs: {e}")
        raise HTTPException(status_code=500, detail=f"重置配置失败：{str(e)}")


@router.get("/history/{key}")
async def get_config_history(
    key: str, 
    limit: int = Query(20, ge=1, le=100)
) -> Dict[str, Any]:
    """获取配置变更历史"""
    try:
        history = config_service.get_config_history(key, limit)
        return {"status": "success", "history": history}
    except Exception as e:
        logger.error(f"Failed to get config history for {key}: {e}")
        raise HTTPException(status_code=500, detail=f"获取配置历史失败：{str(e)}")


@router.get("/export")
async def export_configs() -> str:
    """导出配置为 JSON 格式"""
    try:
        configs = config_service.get_all_configs()
        import json
        return json.dumps(configs, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Failed to export configs: {e}")
        raise HTTPException(status_code=500, detail=f"导出配置失败：{str(e)}")


@router.post("/import")
async def import_configs(configs: Dict[str, Any]) -> Dict[str, str]:
    """从 JSON 导入配置"""
    try:
        success = config_service.batch_update_configs(configs)
        if success:
            return {"status": "success", "message": f"成功导入 {len(configs)} 个配置项"}
        else:
            raise HTTPException(status_code=500, detail="导入配置失败")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to import configs: {e}")
        raise HTTPException(status_code=500, detail=f"导入配置失败：{str(e)}")
```

### 2.4 配置 Schema 自动生成

#### 文件：`backend/src/service/config_service.py` (补充)

```python
def get_config_schema(self) -> Dict[str, Dict]:
    """从 Settings 类自动生成配置 Schema"""
    from src.config.settings import Settings
    import inspect
    
    schema = {}
    
    for field_name, field_info in Settings.model_fields.items():
        # 跳过内部字段
        if field_name.startswith('_'):
            continue
        
        # 提取元数据
        json_schema_extra = field_info.json_schema_extra or {}
        category = json_schema_extra.get("category", "Uncategorized")
        display_name = json_schema_extra.get("display_name", field_name)
        value_type = json_schema_extra.get("value_type", field_info.annotation.__name__)
        
        # 构建验证规则
        validation_rules = {}
        if hasattr(field_info, 'ge') and field_info.ge is not None:
            validation_rules["min"] = field_info.ge
        if hasattr(field_info, 'le') and field_info.le is not None:
            validation_rules["max"] = field_info.le
        if value_type == "float":
            validation_rules["step"] = 0.01
        elif value_type == "int":
            validation_rules["step"] = 1
        
        schema[field_name] = {
            "key": field_name,
            "default_value": field_info.default,
            "value_type": value_type,
            "description": field_info.description or "",
            "category": category,
            "display_name": display_name,
            "validation_rules": validation_rules if validation_rules else None,
            "env_alias": field_info.validation_alias
        }
    
    return schema
```

### 2.5 配置热更新机制

#### 文件：`backend/src/core/event_bus.py` (修改)

```python
from enum import Enum

class EventType(Enum):
    # ... 现有事件类型 ...
    CONFIG_UPDATED = "config_updated"
    CONFIG_RESET = "config_reset"


# 发布配置变更事件
def publish_config_update(key: str, new_value: Any):
    event_bus.publish(EventType.CONFIG_UPDATED, {"key": key, "value": new_value})


# 订阅配置变更的模块示例
@event_bus.subscribe(EventType.CONFIG_UPDATED)
def on_config_updated(event):
    """配置更新后的处理逻辑"""
    key = event.data["key"]
    new_value = event.data["value"]
    
    # 刷新 Settings 缓存
    from src.config.settings import settings
    settings.refresh_config_cache(key)
    
    # 根据配置类型触发相应的重载逻辑
    if key.startswith("rag_"):
        from src.service.rag_service import rag_service
        rag_service.reload_config()
        logger.info(f"RAG config {key} reloaded")
    
    if key.startswith("model_"):
        # 重新初始化 LLM 模型
        pass
```

---

## 三、前端改动

### 3.1 新增配置管理页面

#### 文件：`frontend/src/pages/SettingsPage.tsx` (新建)

```tsx
import { useState, useEffect } from 'react';
import {
  Card, Typography, Table, Input, Button, Space, Tag, Modal, App,
  Switch, InputNumber, Select, Divider, Badge, Tooltip, Popconfirm
} from 'antd';
import {
  SearchOutlined, ReloadOutlined, ExportOutlined, ImportOutlined,
  SaveOutlined, HistoryOutlined, UndoOutlined, SettingOutlined
} from '@ant-design/icons';
import {
  getConfigs, getConfigSchema, updateConfig, batchUpdateConfigs,
  resetConfig, resetAllConfigs, exportConfigs, ConfigItem
} from '../api/client';
import ConfigEditor from '../components/ConfigEditor';
import styles from './SettingsPage.module.scss';

const { Title, Text } = Typography;

const SettingsPage: React.FC = () => {
  const { message, modal } = App.useApp();
  
  // 状态管理
  const [configs, setConfigs] = useState<Record<string, ConfigItem>>({});
  const [schema, setSchema] = useState<Record<string, any>>({});
  const [loading, setLoading] = useState(false);
  const [searchKeyword, setSearchKeyword] = useState('');
  const [selectedCategory, setSelectedCategory] = useState<string>('all');
  const [modifiedConfigs, setModifiedConfigs] = useState<Set<string>>(new Set());
  const [categories, setCategories] = useState<string[]>([]);
  
  // 加载配置
  useEffect(() => {
    loadConfigs();
    loadSchema();
  }, []);
  
  const loadConfigs = async () => {
    setLoading(true);
    try {
      const response = await getConfigs();
      setConfigs(response.configs);
      
      // 提取分类列表
      const cats = new Set<string>();
      Object.values(response.configs).forEach((config: any) => {
        if (config.category) cats.add(config.category);
      });
      setCategories(['all', ...Array.from(cats)]);
    } catch (error) {
      message.error('加载配置失败');
    } finally {
      setLoading(false);
    }
  };
  
  const loadSchema = async () => {
    try {
      const response = await getConfigSchema();
      setSchema(response.schema);
    } catch (error) {
      message.error('加载配置 Schema 失败');
    }
  };
  
  // 处理配置修改
  const handleConfigChange = (key: string, newValue: any) => {
    setConfigs(prev => ({
      ...prev,
      [key]: { ...prev[key], value: newValue }
    }));
    setModifiedConfigs(prev => new Set(prev).add(key));
  };
  
  // 保存单个配置
  const handleSaveConfig = async (key: string) => {
    try {
      const config = configs[key];
      await updateConfig(key, {
        value: config.value,
        category: config.category,
        description: config.description
      });
      setModifiedConfigs(prev => {
        const next = new Set(prev);
        next.delete(key);
        return next;
      });
      message.success(`配置 ${key} 已保存`);
    } catch (error) {
      message.error(`保存配置失败：${error}`);
    }
  };
  
  // 批量保存
  const handleBatchSave = async () => {
    const configsToSave = Array.from(modifiedConfigs).map(key => ({
      key,
      value: configs[key].value,
      category: configs[key].category,
      description: configs[key].description
    }));
    
    try {
      await batchUpdateConfigs(configsToSave);
      setModifiedConfigs(new Set());
      message.success(`成功保存 ${configsToSave.length} 个配置项`);
    } catch (error) {
      message.error(`批量保存失败：${error}`);
    }
  };
  
  // 重置单个配置
  const handleResetConfig = async (key: string) => {
    try {
      await resetConfig(key);
      setConfigs(prev => ({
        ...prev,
        [key]: { ...prev[key], value: schema[key]?.default_value }
      }));
      setModifiedConfigs(prev => {
        const next = new Set(prev);
        next.delete(key);
        return next;
      });
      message.success(`配置 ${key} 已重置`);
    } catch (error) {
      message.error(`重置配置失败：${error}`);
    }
  };
  
  // 重置所有配置
  const handleResetAll = () => {
    modal.confirm({
      title: '确认重置所有配置？',
      content: '此操作将把所有配置恢复为默认值，且不可恢复！',
      okText: '确认重置',
      okType: 'danger',
      cancelText: '取消',
      onOk: async () => {
        try {
          await resetAllConfigs();
          loadConfigs();
          setModifiedConfigs(new Set());
          message.success('所有配置已重置为默认值');
        } catch (error) {
          message.error(`重置失败：${error}`);
        }
      }
    });
  };
  
  // 导出配置
  const handleExport = async () => {
    try {
      const data = await exportConfigs();
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `config_backup_${new Date().getTime()}.json`;
      a.click();
      URL.revokeObjectURL(url);
      message.success('配置导出成功');
    } catch (error) {
      message.error(`导出失败：${error}`);
    }
  };
  
  // 过滤配置
  const filteredConfigs = Object.entries(configs).filter(([key, config]) => {
    const matchSearch = searchKeyword === '' || 
      key.toLowerCase().includes(searchKeyword.toLowerCase()) ||
      config.description?.toLowerCase().includes(searchKeyword.toLowerCase());
    const matchCategory = selectedCategory === 'all' || 
      config.category === selectedCategory;
    return matchSearch && matchCategory;
  });
  
  // 按分类分组
  const groupedConfigs = filteredConfigs.reduce((acc, [key, config]) => {
    const category = config.category || 'Uncategorized';
    if (!acc[category]) acc[category] = [];
    acc[category].push([key, config]);
    return acc;
  }, {} as Record<string, [string, ConfigItem][]>);
  
  return (
    <div className={styles.container}>
      {/* 顶部操作栏 */}
      <Card className={styles.headerCard}>
        <div className={styles.toolbar}>
          <Input
            placeholder="搜索配置项..."
            prefix={<SearchOutlined />}
            value={searchKeyword}
            onChange={e => setSearchKeyword(e.target.value)}
            style={{ width: 300 }}
          />
          
          <Select
            value={selectedCategory}
            onChange={setSelectedCategory}
            style={{ width: 200 }}
            options={categories.map(cat => ({
              label: cat === 'all' ? '全部分类' : cat,
              value: cat
            }))}
          />
          
          <Space>
            <Badge count={modifiedConfigs.size} showZero>
              <Button
                type="primary"
                icon={<SaveOutlined />}
                onClick={handleBatchSave}
                disabled={modifiedConfigs.size === 0}
              >
                保存全部
              </Button>
            </Badge>
            
            <Button icon={<ExportOutlined />} onClick={handleExport}>
              导出
            </Button>
            
            <Button icon={<ImportOutlined />}>
              导入
            </Button>
            
            <Popconfirm
              title="确认重置所有配置？"
              onConfirm={handleResetAll}
              okText="确认"
              cancelText="取消"
            >
              <Button icon={<ReloadOutlined />} danger>
                重置全部
              </Button>
            </Popconfirm>
          </Space>
        </div>
      </Card>
      
      {/* 配置列表 */}
      {Object.entries(groupedConfigs).map(([category, categoryConfigs]) => (
        <Card
          key={category}
          title={
            <Space>
              <SettingOutlined />
              <Text>{category}</Text>
              <Tag color="blue">{categoryConfigs.length}项</Tag>
            </Space>
          }
          className={styles.categoryCard}
        >
          {categoryConfigs.map(([key, config]) => (
            <div key={key} className={styles.configItem}>
              <div className={styles.configHeader}>
                <Space>
                  <Text strong>{config.display_name || key}</Text>
                  <Text code>{key}</Text>
                  {modifiedConfigs.has(key) && (
                    <Tag color="orange">已修改</Tag>
                  )}
                </Space>
                
                <Space>
                  <Tooltip title="查看历史记录">
                    <Button
                      type="text"
                      icon={<HistoryOutlined />}
                      onClick={() => {/* TODO: 显示历史 */}}
                    />
                  </Tooltip>
                  
                  <Popconfirm
                    title="确认重置此项配置？"
                    onConfirm={() => handleResetConfig(key)}
                    okText="确认"
                    cancelText="取消"
                  >
                    <Button
                      type="text"
                      icon={<UndoOutlined />}
                      disabled={!modifiedConfigs.has(key)}
                    />
                  </Popconfirm>
                  
                  <Button
                    type="link"
                    onClick={() => handleSaveConfig(key)}
                    disabled={!modifiedConfigs.has(key)}
                  >
                    保存
                  </Button>
                </Space>
              </div>
              
              <div className={styles.configContent}>
                <ConfigEditor
                  config={config}
                  value={config.value}
                  onChange={value => handleConfigChange(key, value)}
                />
              </div>
              
              {config.description && (
                <div className={styles.configDescription}>
                  <Text type="secondary">{config.description}</Text>
                </div>
              )}
              
              <div className={styles.configDefault}>
                <Text type="secondary">
                  默认值：{JSON.stringify(schema[key]?.default_value ?? config.value)}
                </Text>
              </div>
            </div>
          ))}
        </Card>
      ))}
    </div>
  );
};

export default SettingsPage;
```

### 3.2 配置编辑器组件

#### 文件：`frontend/src/components/ConfigEditor.tsx` (新建)

```tsx
import React from 'react';
import { Input, InputNumber, Switch, Select, Space } from 'antd';
import { ConfigItem } from '../api/client';

interface ConfigEditorProps {
  config: ConfigItem;
  value: any;
  onChange: (value: any) => void;
}

const ConfigEditor: React.FC<ConfigEditorProps> = ({ config, value, onChange }) => {
  const { value_type, validation_rules } = config;
  
  switch (value_type) {
    case 'bool':
      return (
        <Switch
          checked={value}
          onChange={onChange}
          checkedChildren="开启"
          unCheckedChildren="关闭"
        />
      );
    
    case 'float':
      return (
        <InputNumber
          value={value}
          onChange={onChange}
          min={validation_rules?.min}
          max={validation_rules?.max}
          step={validation_rules?.step || 0.01}
          precision={2}
          style={{ width: 200 }}
          formatter={val => {
            if (typeof val === 'number' && val >= 0 && val <= 1) {
              return `${(val * 100).toFixed(0)}%`;
            }
            return `${val}`;
          }}
        />
      );
    
    case 'int':
      return (
        <InputNumber
          value={value}
          onChange={onChange}
          min={validation_rules?.min}
          max={validation_rules?.max}
          step={validation_rules?.step || 1}
          style={{ width: 200 }}
          addonAfter={getUnit(config.key)}
        />
      );
    
    case 'str':
      if (config.key.includes('_DIR') || config.key.includes('_PATH')) {
        return (
          <Input
            value={value}
            onChange={e => onChange(e.target.value)}
            style={{ width: 400 }}
            placeholder="请输入路径"
          />
        );
      }
      if (config.key.includes('API_KEY') || config.key.includes('SECRET')) {
        return (
          <Input.Password
            value={value}
            onChange={e => onChange(e.target.value)}
            style={{ width: 400 }}
            placeholder="请输入密钥"
          />
        );
      }
      return (
        <Input
          value={value}
          onChange={e => onChange(e.target.value)}
          style={{ width: 400 }}
        />
      );
    
    case 'list':
      return (
        <Select
          mode="tags"
          value={value}
          onChange={onChange}
          style={{ width: 400 }}
          placeholder="添加选项"
          tokenSeparators={[',', '，']}
        />
      );
    
    case 'dict':
      return (
        <Input.TextArea
          value={JSON.stringify(value, null, 2)}
          onChange={e => {
            try {
              onChange(JSON.parse(e.target.value));
            } catch {
              // 忽略解析错误
            }
          }}
          style={{ width: 500, fontFamily: 'monospace' }}
          rows={4}
        />
      );
    
    default:
      return (
        <Input
          value={String(value)}
          onChange={e => onChange(e.target.value)}
          style={{ width: 400 }}
        />
      );
  }
};

// 辅助函数：根据配置键名返回单位
const getUnit = (key: string): string => {
  if (key.includes('_SIZE') || key.includes('_LENGTH')) return '字符';
  if (key.includes('_TIMEOUT') || key.includes('_TTL')) return '秒';
  if (key.includes('_COUNT') || key.includes('_LIMIT')) return '个';
  if (key.includes('_PORT')) return '端口';
  return '';
};

export default ConfigEditor;
```

### 3.3 样式文件

#### 文件：`frontend/src/pages/SettingsPage.module.scss` (新建)

```scss
.container {
  padding: 24px;
  background-color: #f0f2f5;
  min-height: 100vh;
}

.headerCard {
  margin-bottom: 24px;
  
  .toolbar {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 16px;
    flex-wrap: wrap;
  }
}

.categoryCard {
  margin-bottom: 24px;
}

.configItem {
  padding: 16px 0;
  border-bottom: 1px solid #f0f0f0;
  
  &:last-child {
    border-bottom: none;
  }
}

.configHeader {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.configContent {
  margin: 12px 0;
}

.configDescription {
  margin: 8px 0;
  font-size: 13px;
}

.configDefault {
  margin-top: 8px;
  font-size: 12px;
}
```

### 3.4 API 客户端

#### 文件：`frontend/src/api/client.ts` (修改)

```typescript
// 新增配置相关接口和函数

export interface ConfigItem {
  key: string;
  value: any;
  category: string;
  description: string;
  default_value: any;
  value_type: string;
  display_name?: string;
  validation_rules?: {
    min?: number;
    max?: number;
    step?: number;
  };
  is_modified?: boolean;
}

export interface ConfigUpdateRequest {
  key: string;
  value: any;
  category: string;
  description?: string;
}

export const getConfigs = () => api.get('/config');
export const getConfigsByCategory = (category: string) => api.get(`/config/${category}`);
export const getConfigSchema = () => api.get('/config/schema');
export const updateConfig = (key: string, data: ConfigUpdateRequest) => 
  api.put(`/config/${key}`, data);
export const batchUpdateConfigs = (configs: ConfigUpdateRequest[]) => 
  api.post('/config/batch', { configs });
export const resetConfig = (key: string) => api.post(`/config/reset/${key}`);
export const resetAllConfigs = () => api.post('/config/reset-all');
export const getConfigHistory = (key: string, limit?: number) => 
  api.get(`/config/history/${key}`, { params: { limit } });
export const exportConfigs = () => api.get('/config/export');
export const importConfigs = (configs: Record<string, any>) => 
  api.post('/config/import', configs);
```

### 3.5 路由配置

#### 文件：`frontend/src/router/index.tsx` (修改)

```tsx
import { createBrowserRouter } from 'react-router-dom';
import App from '../App';
import HomePage from '../pages/HomePage';
import KnowledgeBasePage from '../pages/KnowledgeBasePage';
import KnowledgeSearchPage from '../pages/KnowledgeSearchPage';
import RagTestPage from '../pages/RagTestPage';
import SettingsPage from '../pages/SettingsPage'; // 新增

export const router = createBrowserRouter([
  {
    path: '/',
    element: <App />,
    children: [
      { index: true, element: <HomePage /> },
      { path: 'knowledge-base', element: <KnowledgeBasePage /> },
      { path: 'knowledge-search', element: <KnowledgeSearchPage /> },
      { path: 'rag-test', element: <RagTestPage /> },
      { path: 'settings', element: <SettingsPage /> }, // 新增
    ],
  },
]);
```

#### 文件：`frontend/src/App.tsx` (修改)

```tsx
import { SettingOutlined } from '@ant-design/icons';

// 在 menuDataRender 中添加
menuDataRender={() => [
  { path: '/', name: '首页' },
  { path: '/knowledge-base', name: '知识库' },
  { path: '/knowledge-search', name: '内容搜索' },
  { path: '/rag-test', name: '回撤测试' },
  { path: '/settings', name: '系统配置', icon: <SettingOutlined /> }, // 新增
]}
```

---

## 四、配置分类方案

| 分类 | 配置项示例 | 前端展示名称 |
|------|-----------|-------------|
| **App** | app_name, app_version, debug, app_host, app_port | 应用基础 |
| **Model** | dashscope_api_key, model_report_generation, model_assessment | 模型配置 |
| **RAG** | rag_hybrid_bm25_weight, rag_cache_enabled, rag_chunk_size | RAG 检索 |
| **RAG-OCR** | rag_ocr_extraction_rate_threshold, rag_ocr_min_avg_length_threshold | RAG-OCR |
| **RAG-Threshold** | rag_hybrid_base_threshold, rag_vector_base_threshold | RAG-阈值 |
| **RAG-Search** | rag_search_bm25_weight, rag_search_score_threshold_hybrid | RAG-搜索 |
| **RAG-AgeFilter** | rag_age_filter_strictness, rag_age_filter_tolerance | RAG-年龄过滤 |
| **Embedding** | embedding_model_name, embedding_max_text_length | Embedding |
| **VectorStore** | vector_store_type, vector_store_config | 向量存储 |
| **SemanticSplitter** | semantic_splitter_buffer_size, semantic_splitter_breakpoint_threshold | 语义分块 |
| **Log** | log_level, log_file | 日志配置 |
| **PageIndex** | pageindex_enabled, pageindex_api_key, pageindex_timeout_seconds | PageIndex |
| **QueryRouter** | query_router_llm_enabled, query_router_confidence_threshold | 查询路由 |
| **ML-Scoring** | ml_scoring_enabled, ml_scoring_mode, ml_scoring_weight_ahp | ML 评分 |

---

## 五、数据库迁移

### 5.1 Alembic 迁移脚本

#### 文件：`backend/alembic/versions/0001_add_config_items_table.py` (新建)

```python
"""add config items table

Revision ID: 0001
Revises: 
Create Date: 2026-04-02

"""
from alembic import op
import sqlalchemy as sa

revision = '0001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 创建配置项表
    op.create_table(
        'config_items',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('value', sa.JSON(), nullable=False),
        sa.Column('category', sa.String(), nullable=False),
        sa.Column('description', sa.String(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True, default=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('updated_by', sa.String(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    
    # 创建配置历史表
    op.create_table(
        'config_history',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('config_key', sa.String(), sa.ForeignKey('config_items.id'), nullable=False),
        sa.Column('old_value', sa.JSON(), nullable=True),
        sa.Column('new_value', sa.JSON(), nullable=False),
        sa.Column('changed_by', sa.String(), nullable=True),
        sa.Column('changed_at', sa.DateTime(), nullable=True),
        sa.Column('reason', sa.String(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    
    # 创建索引
    op.create_index('ix_config_items_category', 'config_items', ['category'])
    op.create_index('ix_config_history_config_key', 'config_history', ['config_key'])
    op.create_index('ix_config_history_changed_at', 'config_history', ['changed_at'])


def downgrade() -> None:
    op.drop_index('ix_config_history_changed_at')
    op.drop_index('ix_config_history_config_key')
    op.drop_index('ix_config_items_category')
    op.drop_table('config_history')
    op.drop_table('config_items')
```

### 5.2 配置初始化脚本

#### 文件：`backend/src/cli/config.py` (新建)

```python
"""配置管理 CLI 命令"""
import click
from src.service.config_service import config_service
from src.config.settings import settings
import json

@click.group()
def config():
    """配置管理命令"""
    pass

@config.command()
def init():
    """从.env.dev 初始化配置表"""
    click.echo("正在从.env.dev 初始化配置...")
    
    count = 0
    for field_name, field_info in settings.model_fields.items():
        if field_name.startswith('_'):
            continue
        
        default_value = field_info.default
        json_schema_extra = field_info.json_schema_extra or {}
        category = json_schema_extra.get("category", "Uncategorized")
        description = field_info.description or ""
        
        config_service.update_config(
            key=field_name,
            value=default_value,
            category=category,
            description=description,
            updated_by="system"
        )
        count += 1
    
    click.echo(click.style(f"✓ 成功初始化 {count} 个配置项", fg='green'))

@config.command()
@click.option('--key', '-k', help='配置项键名')
def show(key):
    """显示配置值"""
    if key:
        value = config_service.get_config_or_default(key)
        click.echo(f"{key} = {json.dumps(value, ensure_ascii=False, indent=2)}")
    else:
        all_configs = config_service.get_all_configs()
        click.echo(json.dumps(all_configs, ensure_ascii=False, indent=2))

@config.command()
@click.option('--key', '-k', required=True, help='配置项键名')
@click.option('--value', '-v', required=True, help='配置值 (JSON 格式)')
def set(key, value):
    """设置配置值"""
    try:
        parsed_value = json.loads(value)
    except json.JSONDecodeError:
        parsed_value = value
    
    success = config_service.update_config(key, parsed_value, "manual", updated_by="cli")
    if success:
        click.echo(click.style(f"✓ 配置 {key} 已更新", fg='green'))
    else:
        click.echo(click.style("✗ 更新失败", fg='red'))

if __name__ == '__main__':
    config()
```

---

## 六、配置验证与错误处理

### 6.1 后端验证

```python
def validate_config_value(self, key: str, value: Any) -> Tuple[bool, str]:
    """验证配置值是否合法"""
    schema = self.get_config_schema()
    
    if key not in schema:
        return False, f"未知配置项：{key}"
    
    config_schema = schema[key]
    expected_type = config_schema["value_type"]
    
    # 类型检查
    type_mapping = {
        "str": str,
        "int": int,
        "float": float,
        "bool": bool,
        "list": list,
        "dict": dict
    }
    
    if expected_type in type_mapping:
        if not isinstance(value, type_mapping[expected_type]):
            return False, f"类型错误，期望 {expected_type}，实际为 {type(value).__name__}"
    
    # 范围检查
    validation_rules = config_schema.get("validation_rules")
    if validation_rules:
        if "min" in validation_rules and value < validation_rules["min"]:
            return False, f"值不能小于 {validation_rules['min']}"
        if "max" in validation_rules and value > validation_rules["max"]:
            return False, f"值不能大于 {validation_rules['max']}"
    
    # 特殊验证：API_KEY 不能为空
    if key.endswith('_API_KEY') and isinstance(value, str) and not value.strip():
        return False, "API Key 不能为空"
    
    return True, ""
```

### 6.2 前端验证

```tsx
// 在 ConfigEditor 组件中添加验证反馈
const ConfigEditor: React.FC<ConfigEditorProps> = ({ config, value, onChange }) => {
  const [error, setError] = useState<string | null>(null);
  
  const validateAndChange = (newValue: any) => {
    // 简单的前端验证
    if (config.validation_rules) {
      if (config.validation_rules.min !== undefined && newValue < config.validation_rules.min) {
        setError(`值不能小于 ${config.validation_rules.min}`);
        return;
      }
      if (config.validation_rules.max !== undefined && newValue > config.validation_rules.max) {
        setError(`值不能大于 ${config.validation_rules.max}`);
        return;
      }
    }
    setError(null);
    onChange(newValue);
  };
  
  return (
    <div>
      {/* 渲染输入控件 */}
      <InputNumber value={value} onChange={validateAndChange} />
      
      {error && (
        <div style={{ color: 'red', fontSize: '12px', marginTop: '4px' }}>
          {error}
        </div>
      )}
    </div>
  );
};
```

---

## 七、配置导入导出

### 7.1 后端 API

```python
@router.get("/export")
async def export_configs(format: str = Query("json", regex="^(json|env)$")) -> str:
    """导出配置为指定格式"""
    configs = config_service.get_all_configs()
    
    if format == "env":
        # 导出为.env 格式
        lines = []
        for key, config in configs.items():
            env_key = config.get("env_alias", key).upper()
            value = config["value"]
            if isinstance(value, str):
                value = f'"{value}"'
            elif isinstance(value, bool):
                value = str(value)
            lines.append(f"{env_key}={value}")
        return "\n".join(lines)
    else:
        # 导出为 JSON
        import json
        return json.dumps(configs, indent=2, ensure_ascii=False)
```

### 7.2 前端导入功能

```tsx
// 在 SettingsPage 中添加导入处理
const handleImport = () => {
  const input = document.createElement('input');
  input.type = 'file';
  input.accept = '.json';
  input.onchange = async (e) => {
    const file = (e.target as HTMLInputElement).files?.[0];
    if (!file) return;
    
    const reader = new FileReader();
    reader.onload = async (event) => {
      try {
        const configs = JSON.parse(event.target?.result as string);
        
        // 预览变更
        modal.confirm({
          title: '确认导入配置？',
          content: `将导入 ${Object.keys(configs).length} 个配置项，当前值将被覆盖。`,
          onOk: async () => {
            await importConfigs(configs);
            loadConfigs();
            message.success('配置导入成功');
          }
        });
      } catch (error) {
        message.error('配置文件格式错误');
      }
    };
    reader.readAsText(file);
  };
  input.click();
};
```

---

## 八、测试计划

### 8.1 单元测试

#### 文件：`backend/tests/test_config_service.py` (新建)

```python
import pytest
from src.service.config_service import config_service

class TestConfigService:
    
    def test_get_config_or_default(self):
        # 测试从数据库读取配置
        config_service.update_config("test_key", "test_value", "Test")
        assert config_service.get_config_or_default("test_key") == "test_value"
        
        # 测试使用默认值
        assert config_service.get_config_or_default("non_existent_key") is None
    
    def test_update_config(self):
        success = config_service.update_config(
            "rag_hybrid_bm25_weight",
            0.7,
            "RAG",
            "测试更新"
        )
        assert success is True
        
        config = config_service.get_config_or_default("rag_hybrid_bm25_weight")
        assert config == 0.7
    
    def test_validate_config_value(self):
        # 测试有效值
        is_valid, _ = config_service.validate_config_value("rag_hybrid_bm25_weight", 0.5)
        assert is_valid is True
        
        # 测试超出范围
        is_valid, error_msg = config_service.validate_config_value("rag_hybrid_bm25_weight", 1.5)
        assert is_valid is False
        assert "不能大于" in error_msg
        
        # 测试类型错误
        is_valid, error_msg = config_service.validate_config_value("rag_hybrid_bm25_weight", "invalid")
        assert is_valid is False
    
    def test_batch_update_configs(self):
        configs = {
            "rag_cache_enabled": {"value": True, "category": "RAG"},
            "rag_chunk_size": {"value": 512, "category": "RAG"}
        }
        success = config_service.batch_update_configs(configs)
        assert success is True
    
    def test_reset_config(self):
        # 先修改
        config_service.update_config("rag_chunk_size", 999, "RAG")
        # 再重置
        config_service.reset_config_to_default("rag_chunk_size")
        # 验证恢复默认值
        default = getattr(settings, "rag_chunk_size")
        current = config_service.get_config_or_default("rag_chunk_size")
        assert current == default
```

### 8.2 集成测试

#### 文件：`backend/tests/test_config_api.py` (新建)

```python
from fastapi.testclient import TestClient
from src.server import create_app

client = TestClient(create_app())

def test_get_all_configs():
    response = client.get("/config")
    assert response.status_code == 200
    assert "configs" in response.json()

def test_update_config():
    response = client.put(
        "/config/rag_hybrid_bm25_weight",
        json={"value": 0.6, "category": "RAG"}
    )
    assert response.status_code == 200
    assert response.json()["status"] == "success"

def test_update_invalid_config():
    response = client.put(
        "/config/rag_hybrid_bm25_weight",
        json={"value": 2.0, "category": "RAG"}  # 超出范围
    )
    assert response.status_code == 400

def test_batch_update():
    response = client.post(
        "/config/batch",
        json={
            "configs": [
                {"key": "rag_cache_enabled", "value": False, "category": "RAG"},
                {"key": "debug", "value": True, "category": "App"}
            ]
        }
    )
    assert response.status_code == 200

def test_reset_all():
    response = client.post("/config/reset-all")
    assert response.status_code == 200
```

### 8.3 前端测试

#### 文件：`frontend/src/pages/__tests__/SettingsPage.test.tsx` (新建)

```tsx
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import SettingsPage from '../SettingsPage';
import { QueryClientProvider } from '@tanstack/react-query';
import { queryClient } from '../../lib/queryClient';

describe('SettingsPage', () => {
  it('renders configuration categories', async () => {
    render(
      <QueryClientProvider client={queryClient}>
        <SettingsPage />
      </QueryClientProvider>
    );
    
    await waitFor(() => {
      expect(screen.getByText(/RAG/i)).toBeInTheDocument();
    });
  });
  
  it('allows editing float configuration', async () => {
    render(
      <QueryClientProvider client={queryClient}>
        <SettingsPage />
      </QueryClientProvider>
    );
    
    const bm25Input = await screen.findByLabelText(/BM25 权重/i);
    fireEvent.change(bm25Input, { target: { value: '0.8' } });
    
    const saveButton = screen.getByText('保存');
    fireEvent.click(saveButton);
    
    await waitFor(() => {
      expect(screen.getByText(/已保存/i)).toBeInTheDocument();
    });
  });
  
  it('shows validation error for out-of-range value', async () => {
    render(
      <QueryClientProvider client={queryClient}>
        <SettingsPage />
      </QueryClientProvider>
    );
    
    const bm25Input = await screen.findByLabelText(/BM25 权重/i);
    fireEvent.change(bm25Input, { target: { value: '1.5' } });  // 超出范围
    
    expect(screen.getByText(/不能大于/i)).toBeInTheDocument();
  });
});
```

---

## 九、部署与迁移

### 9.1 数据库迁移

```bash
# 应用迁移
alembic upgrade head

# 验证迁移
alembic current
```

### 9.2 配置初始化

```bash
# 方法 1: 使用 CLI
cd backend
python -m src.cli.config init

# 方法 2: 应用启动时自动初始化（如果表为空）
```

### 9.3 向后兼容

- 保留 `.env.dev` 文件，作为默认值来源
- 数据库不可用时自动降级使用 `.env.dev`
- 所有配置读取都通过 `get_config_or_default()` 方法

---

## 十、后续扩展

1. **配置模板**：预设多套配置模板（开发/测试/生产），一键切换
2. **配置对比**：对比当前配置与默认配置的差异
3. **配置推荐**：基于使用场景推荐配置值（如"密集文档模式"自动调高 BM25 权重）
4. **配置监控**：监控配置变更对系统性能的影响
5. **配置审计**：记录配置变更的操作日志，支持审计追溯
6. **配置权限**：基于角色的配置访问控制（管理员/普通用户）

---

## 十一、风险与缓解

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| 数据库不可用 | 配置读取失败 | 自动降级使用.env.dev 默认值 |
| 配置值非法 | 系统行为异常 | 前后端双重验证 + 范围检查 |
| 配置热更新失败 | 需要重启服务 | 提供配置重载 API + 错误回滚 |
| 配置冲突 | 多用户同时修改 | 乐观锁 + 最后写入优先策略 |
| 敏感配置泄露 | 安全风险 | API Key 等字段加密存储 + 脱敏显示 |

---

## 十二、验收标准

- [ ] 所有配置项可在前端页面查看和修改
- [ ] 配置修改后实时生效（无需重启服务）
- [ ] 支持按分类筛选和搜索配置项
- [ ] 支持批量保存和重置配置
- [ ] 支持配置导入导出
- [ ] 配置变更历史记录可查询
- [ ] 配置值验证正确（类型、范围）
- [ ] 数据库不可用时自动降级使用默认值
- [ ] 单元测试覆盖率 > 80%
- [ ] 前端交互流畅，无卡顿

---

**文档结束**
