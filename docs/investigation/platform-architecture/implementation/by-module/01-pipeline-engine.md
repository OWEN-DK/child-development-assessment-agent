# 01 — 管道模型与执行引擎 · 实现规格

> **关联需求**：[01-pipeline-model-and-engine.md](../requirements/01-pipeline-model-and-engine.md)
> **目标模块**：`backend/src/core/pipeline/` + `backend/src/service/pipeline/` + `backend/src/controller/pipeline_controller.py`

---

## 1. API 契约

### 通用约定

- 基础前缀：`/api/v1`
- 认证：所有端点需 Bearer Token（通过中间件注入 `tenant_id`）
- 成功响应统一格式：

```json
{"code": 0, "message": "success", "data": {...}}
```

- 错误响应统一格式：

```json
{"code": 40001, "message": "...", "error_code": "PIPELINE_NOT_FOUND", "details": {...}, "trace_id": "..."}
```

---

### 1.1 `POST /api/v1/pipelines` — 创建管道

**Request Body**：

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `name` | `string` | 是 | 管道名称，1–100 字符 |
| `type` | `string` | 否 | `aggregation`（默认） |
| `config_snapshot` | `object` | 否 | 初始管道配置 JSON（见需求 §2.1），不传则创建空管道 |
| `change_log` | `string` | 否 | 初始版本变更说明 |

```json
{
  "name": "儿童运动评估聚合管道",
  "type": "aggregation",
  "config_snapshot": {
    "domains": [],
    "aggregation": {"nodes": [], "edges": [], "shortcut_edge": null}
  },
  "change_log": "初始创建"
}
```

**Response (201)**：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "pipeline_id": "pip_abc123",
    "version_number": 1,
    "created_at": "2026-05-14T10:00:00Z"
  }
}
```

**Errors**：`40001 PIPELINE_NAME_TOO_LONG`、`40002 PIPELINE_NAME_DUPLICATE`、`40003 PIPELINE_CONFIG_INVALID`

---

### 1.2 `GET /api/v1/pipelines` — 管道列表

**Query Parameters**：

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `page` | `int` | 否 | 页码，默认 1 |
| `page_size` | `int` | 否 | 每页大小，默认 20，最大 100 |
| `keyword` | `string` | 否 | 名称模糊搜索 |
| `type` | `string` | 否 | 按类型过滤 |

**Response (200)**：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "items": [
      {
        "id": "pip_abc123",
        "name": "儿童运动评估聚合管道",
        "type": "aggregation",
        "active_version": 3,
        "created_at": "2026-05-10T08:00:00Z",
        "updated_at": "2026-05-14T10:00:00Z"
      }
    ],
    "total": 1,
    "page": 1,
    "page_size": 20
  }
}
```

---

### 1.3 `GET /api/v1/pipelines/{id}` — 获取管道详情

**Path Parameters**：`id` (string) — 管道 ID

**Response (200)**：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "id": "pip_abc123",
    "name": "儿童运动评估聚合管道",
    "type": "aggregation",
    "tenant_id": "t_001",
    "active_version": 3,
    "current_config": {
      "domains": [ { "id": "d1", "name": "运动发育", "knowledge_base_id": "kb_01", "weight": 0.6, "activation_rules": { "keywords": ["运动","动作","粗大","精细"], "min_confidence": 0.6 }, "pipeline": { "nodes": [...], "edges": [...], "conditional_edges": [...], "degradation_edges": [...] } } ],
      "aggregation": { "nodes": [...], "edges": [...], "shortcut_edge": {"source": "query_analyzer", "target": "unified_generate"} }
    },
    "change_log": "新增敏感词过滤节点",
    "created_at": "2026-05-10T08:00:00Z",
    "updated_at": "2026-05-14T10:00:00Z"
  }
}
```

**Errors**：`40401 PIPELINE_NOT_FOUND`

---

### 1.4 `PUT /api/v1/pipelines/{id}` — 更新管道配置

**Request Body**：

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `config_snapshot` | `object` | 是 | 完整管道配置 JSON |
| `change_log` | `string` | 是 | 本次变更说明 |

```json
{
  "config_snapshot": {
    "domains": [...],
    "aggregation": {...}
  },
  "change_log": "调整 BM25 检索 top_k 从 10 改为 20"
}
```

**Response (200)**：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "pipeline_id": "pip_abc123",
    "version_number": 4,
    "created_at": "2026-05-14T11:00:00Z"
  }
}
```

**Errors**：`40401 PIPELINE_NOT_FOUND`、`40003 PIPELINE_CONFIG_INVALID`

---

### 1.5 `DELETE /api/v1/pipelines/{id}` — 删除管道

**Response (200)**：

```json
{"code": 0, "message": "success", "data": null}
```

**Errors**：`40401 PIPELINE_NOT_FOUND`

---

### 1.6 `GET /api/v1/pipelines/{id}/versions` — 版本列表

**Query Parameters**：`page` (int)、`page_size` (int)

**Response (200)**：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "items": [
      {
        "id": "pv_004",
        "pipeline_id": "pip_abc123",
        "version_number": 4,
        "change_log": "调整 BM25 检索 top_k",
        "created_at": "2026-05-14T11:00:00Z"
      }
    ],
    "total": 4,
    "page": 1,
    "page_size": 20
  }
}
```

---

### 1.7 `GET /api/v1/pipelines/{id}/versions/{v}` — 获取指定版本配置

**Path Parameters**：`id` (string)、`v` (int) — 版本号

**Response (200)**：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "id": "pv_002",
    "pipeline_id": "pip_abc123",
    "version_number": 2,
    "change_log": "新增域管道",
    "config_snapshot": { ... },
    "created_at": "2026-05-12T09:00:00Z"
  }
}
```

**Errors**：`40401 PIPELINE_NOT_FOUND`、`40402 PIPELINE_VERSION_NOT_FOUND`

---

### 1.8 `POST /api/v1/pipelines/{id}/rollback/{v}` — 回滚到指定版本

**Request Body**：

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `change_log` | `string` | 是 | 回滚说明 |

```json
{"change_log": "回滚到 v2（因 v3 查询准确率下降）"}
```

**Response (200)**：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "pipeline_id": "pip_abc123",
    "version_number": 5,
    "rollback_from_version": 3,
    "created_at": "2026-05-14T12:00:00Z"
  }
}
```

**Errors**：`40401 PIPELINE_NOT_FOUND`、`40402 PIPELINE_VERSION_NOT_FOUND`

---

### 1.9 `POST /api/v1/pipelines/compare` — 版本对比

**Request Body**：

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `pipeline_id` | `string` | 是 | 管道 ID |
| `v1` | `int` | 是 | 版本号 A |
| `v2` | `int` | 是 | 版本号 B |

```json
{"pipeline_id": "pip_abc123", "v1": 2, "v2": 4}
```

**Response (200)**：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "v1": {"version_number": 2, "node_count": 8},
    "v2": {"version_number": 4, "node_count": 10},
    "diff": {
      "nodes_added": [
        {"id": "node_9", "type": "sensitive_filter", "domain": "d1"}
      ],
      "nodes_removed": [],
      "nodes_modified": [
        {
          "node_id": "node_3",
          "changes": [
            {"field": "config.top_k", "old_value": 10, "new_value": 20}
          ]
        }
      ],
      "edges_added": [{"source": "node_9", "target": "node_7"}],
      "edges_removed": []
    }
  }
}
```

**Errors**：`40401 PIPELINE_NOT_FOUND`、`40402 PIPELINE_VERSION_NOT_FOUND`

---

### 1.10 `POST /api/v1/pipelines/{id}/validate` — 校验管道配置

**Request Body**：与 PUT 的 `config_snapshot` 结构相同（可选，不传则校验当前保存版本）

```json
{
  "config_snapshot": {
    "domains": [...],
    "aggregation": {...}
  }
}
```

**Response (200)**：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "valid": true,
    "errors": []
  }
}
```

**错误时 (200 仍返回)**：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "valid": false,
    "errors": [
      {
        "location": "domains[0].pipeline.nodes[2]",
        "node_id": "node_3",
        "node_type": "vector_search",
        "field": "config.similarity_threshold",
        "message": "similarity_threshold 必须在 0-1 之间，当前值: 1.5",
        "severity": "error"
      },
      {
        "location": "aggregation.edges[0]",
        "source": "nonexistent_node",
        "target": "unified_generate",
        "message": "source 节点 'nonexistent_node' 不存在于聚合层",
        "severity": "error"
      }
    ]
  }
}
```

---

### 1.11 `POST /api/v1/pipelines/{id}/dry-run` — 干运行

**Request Body**：

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `query` | `string` | 是 | 模拟查询文本 |
| `params` | `object` | 否 | L3 API 参数覆盖 |

```json
{
  "query": "2岁宝宝还不会走路怎么办",
  "params": {"top_k": 5}
}
```

**Response (200)**：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "compilable": true,
    "execution_plan": {
      "pipeline_id": "pip_abc123",
      "version": 3,
      "shortcut_activated": false,
      "phases": [
        {"phase": "query_analysis", "node": "query_analyzer"},
        {"phase": "domain_parallel", "domains": ["d1"], "node": "domain_dispatch"},
        {"phase": "aggregation", "nodes": ["cross_fusion", "cross_dedup", "conflict_detect", "unified_generate"]}
      ],
      "total_nodes": 12,
      "estimated_domains": 1
    },
    "warnings": ["域 'd2' 的知识库 'kb_02' 未找到匹配索引"],
    "errors": []
  }
}
```

**编译失败时**：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "compilable": false,
    "execution_plan": null,
    "warnings": [],
    "errors": [{"node_id": "...", "message": "...", "severity": "error"}]
  }
}
```

---

### 1.12 `GET /api/v1/compound-nodes` — 复合节点列表

**Query Parameters**：`page` (int)、`page_size` (int)

**Response (200)**：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "items": [
      {
        "id": "cn_001",
        "name": "标准医学检索组",
        "node_count": 3,
        "created_at": "2026-05-10T08:00:00Z"
      }
    ],
    "total": 1,
    "page": 1,
    "page_size": 20
  }
}
```

---

### 1.13 `POST /api/v1/compound-nodes` — 创建复合节点

**Request Body**：

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `name` | `string` | 是 | 复合节点名称 |
| `config_snapshot` | `object` | 是 | 复合节点配置（含 expanded_nodes、internal_edges、exposed_ports） |

```json
{
  "name": "标准医学检索组",
  "config_snapshot": {
    "id": "compound_medical_search",
    "type": "compound",
    "expanded_nodes": [
      {"id": "inner_1", "type": "term_normalize", "config": {}},
      {"id": "inner_2", "type": "hybrid_search", "config": {"top_k": 10}},
      {"id": "inner_3", "type": "rerank", "config": {"initial_k": 30, "final_k": 5}}
    ],
    "internal_edges": [
      {"source": "inner_1", "target": "inner_2"},
      {"source": "inner_2", "target": "inner_3"}
    ],
    "exposed_ports": {"input": "inner_1", "output": "inner_3"}
  }
}
```

**Response (201)**：

```json
{"code": 0, "message": "success", "data": {"id": "cn_001", "created_at": "2026-05-14T10:00:00Z"}}
```

**Errors**：`40004 COMPOUND_NODE_CONFIG_INVALID`

---

### 1.14 `DELETE /api/v1/compound-nodes/{id}` — 删除复合节点

**Response (200)**：

```json
{"code": 0, "message": "success", "data": null}
```

---

### 1.15 `POST /api/v1/compound-nodes/import` — 导入复合节点

**Request Body**：

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `config_snapshot` | `object` | 是 | 导出的完整复合节点 JSON |
| `name` | `string` | 否 | 覆盖名称，不传则用 JSON 中的名称 |

**Response (201)**：

```json
{"code": 0, "message": "success", "data": {"id": "cn_002", "name": "导入的检索组"}}
```

---

### 1.16 `GET /api/v1/compound-nodes/{id}/export` — 导出复合节点

**Response (200)**：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "id": "compound_medical_search",
    "name": "标准医学检索组",
    "type": "compound",
    "expanded_nodes": [...],
    "internal_edges": [...],
    "exposed_ports": {"input": "inner_1", "output": "inner_3"}
  }
}
```

---

### 1.17 `GET /api/v1/pipeline/node-types` — 获取所有可用节点类型

> 供编辑器渲染节点面板使用。无参数。

**Response (200)**：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "types": [
      {
        "type_id": "query_rewrite",
        "category": "query",
        "name_zh": "查询改写",
        "input_type": "RawQuery",
        "output_type": "QueryVariant[]",
        "parameters": [
          {"name": "model", "type": "string", "default": null, "config_level": "L2", "description": "LLM 模型"},
          {"name": "prompt_template", "type": "string", "default": null, "config_level": "L1", "description": "提示词模板"},
          {"name": "max_retries", "type": "int", "default": 2, "config_level": "L2", "description": "最大重试次数"}
        ]
      }
    ]
  }
}
```

---

## 2. 数据库 DDL

```sql
-- ============================================================
-- 管道引擎核心表（3 张）
-- 遵循项目约定：utf8mb4、无外键、弱关联
-- ============================================================

SET NAMES utf8mb4;

-- ----------------------------
-- 管道表
-- ----------------------------
DROP TABLE IF EXISTS `pipelines`;

CREATE TABLE `pipelines` (
    `id` VARCHAR(64) NOT NULL COMMENT '管道ID (UUID)',
    `tenant_id` VARCHAR(64) NOT NULL COMMENT '租户ID',
    `name` VARCHAR(255) NOT NULL COMMENT '管道名称',
    `type` VARCHAR(32) NOT NULL DEFAULT 'aggregation' COMMENT '管道类型：aggregation',
    `active_version` INT NOT NULL DEFAULT 1 COMMENT '当前活动版本号',
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY (`id`),
    KEY `idx_pipelines_tenant_id` (`tenant_id`),
    KEY `idx_pipelines_type` (`type`),
    KEY `idx_pipelines_name` (`name`(100)),
    KEY `idx_pipelines_tenant_type` (`tenant_id`, `type`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='管道表';

-- ----------------------------
-- 管道版本表
-- ----------------------------
DROP TABLE IF EXISTS `pipeline_versions`;

CREATE TABLE `pipeline_versions` (
    `id` VARCHAR(64) NOT NULL COMMENT '版本ID (UUID)',
    `pipeline_id` VARCHAR(64) NOT NULL COMMENT '关联管道ID',
    `tenant_id` VARCHAR(64) NOT NULL COMMENT '租户ID（冗余，与 pipelines.tenant_id 一致，用于 BaseRepository 自动注入）',
    `version_number` INT NOT NULL COMMENT '版本号（per-pipeline 自增）',
    `change_log` TEXT COMMENT '变更说明',
    `config_snapshot` JSON NOT NULL COMMENT '管道配置完整快照 JSON',
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_pipeline_version` (`pipeline_id`, `version_number`),
    KEY `idx_pipeline_versions_pipeline_id` (`pipeline_id`),
    KEY `idx_pipeline_versions_tenant_id` (`tenant_id`),
    KEY `idx_pipeline_versions_created_at` (`created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='管道版本表';

-- ----------------------------
-- 复合节点表
-- ----------------------------
DROP TABLE IF EXISTS `compound_nodes`;

CREATE TABLE `compound_nodes` (
    `id` VARCHAR(64) NOT NULL COMMENT '复合节点ID (UUID)',
    `tenant_id` VARCHAR(64) NOT NULL COMMENT '租户ID（冗余，用于 BaseRepository 自动注入）',
    `owner_id` VARCHAR(64) NOT NULL COMMENT '创建者用户ID',
    `name` VARCHAR(255) NOT NULL COMMENT '复合节点名称',
    `config_snapshot` JSON NOT NULL COMMENT '复合节点配置 JSON（含 expanded_nodes/internal_edges/exposed_ports）',
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    PRIMARY KEY (`id`),
    KEY `idx_compound_nodes_tenant_id` (`tenant_id`),
    KEY `idx_compound_nodes_owner_id` (`owner_id`),
    KEY `idx_compound_nodes_name` (`name`(100))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='复合节点表';
```

---

## 3. 服务层接口

### 3.1 实体类（`backend/src/schemas/pipeline.py`）

> 遵循集中管理规范，所有 Pydantic 模型统一放在 `schemas/` 目录。

```python
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Generic, Optional, TypeVar

from pydantic import BaseModel, Field


# ─── 枚举 ─────────────────────────────────────────────

class EdgeType(str, Enum):
    DATA = "data"
    CONDITIONAL = "conditional"
    DEGRADATION = "degradation"


class ConditionType(str, Enum):
    CACHE_HIT = "cache_hit"
    CACHE_MISS = "cache_miss"
    INTENT_ROUTE = "intent_route"


class DegradationStrategy(str, Enum):
    SKIP_NODE = "skip_node"
    REROUTE = "reroute"
    DEGRADE_CACHE = "degrade_cache"
    ABORT = "abort"


class PipelineType(str, Enum):
    AGGREGATION = "aggregation"


class ExecutionPhase(str, Enum):
    QUERY_ANALYSIS = "query_analysis"
    DOMAIN_PARALLEL = "domain_parallel"
    AGGREGATION = "aggregation"


# ─── 管道配置子模型 ──────────────────────────────────

class DisplayPosition(BaseModel):
    """画布节点坐标"""
    x: float = 0.0
    y: float = 0.0


class NodeConfig(BaseModel):
    """管道节点配置"""
    id: str = Field(description="管道内唯一节点 ID")
    type: str = Field(description="28 种节点类型标识之一")
    config: dict[str, Any] = Field(default_factory=dict, description="节点可配置参数")
    display: DisplayPosition = Field(default_factory=DisplayPosition)


class EdgeConfig(BaseModel):
    """管道边配置"""
    id: str = Field(description="边 ID")
    source: str = Field(description="源节点 ID")
    target: str = Field(description="目标节点 ID")
    type: EdgeType = EdgeType.DATA
    condition: Optional[str] = Field(default=None, description="条件类型（type=conditional 时必填）")
    strategy: Optional[DegradationStrategy] = Field(default=None, description="降级策略（type=degradation 时必填）")


class ShortcutEdge(BaseModel):
    """单域快捷边"""
    source: str = "query_analyzer"
    target: str = "unified_generate"


class ActivationRules(BaseModel):
    """域激活规则"""
    keywords: list[str] = Field(default_factory=list)
    min_confidence: float = Field(default=0.6, ge=0.0, le=1.0)


class DomainPipelineConfig(BaseModel):
    """域内管道配置"""
    nodes: list[NodeConfig] = Field(default_factory=list)
    edges: list[EdgeConfig] = Field(default_factory=list)
    conditional_edges: list[EdgeConfig] = Field(default_factory=list)
    degradation_edges: list[EdgeConfig] = Field(default_factory=list)


class DomainConfig(BaseModel):
    """域配置"""
    id: str = Field(description="域唯一 ID")
    name: str = Field(description="域名称")
    knowledge_base_id: str = Field(description="关联知识库 ID")
    weight: float = Field(default=1.0, ge=0.0, le=1.0, description="域权重")
    activation_rules: ActivationRules = Field(default_factory=ActivationRules)
    pipeline: DomainPipelineConfig = Field(default_factory=DomainPipelineConfig)


class AggregationConfig(BaseModel):
    """聚合层配置"""
    nodes: list[NodeConfig] = Field(default_factory=list)
    edges: list[EdgeConfig] = Field(default_factory=list)
    shortcut_edge: Optional[ShortcutEdge] = None


class PipelineSnapshot(BaseModel):
    """管道配置完整快照（对应 config_snapshot JSON）"""
    domains: list[DomainConfig] = Field(default_factory=list, description="域列表")
    aggregation: AggregationConfig = Field(default_factory=AggregationConfig, description="聚合层配置")


# ─── 复合节点子模型 ──────────────────────────────────

class CompoundExposedPorts(BaseModel):
    """复合节点暴露端口"""
    input: str = Field(description="输入节点 ID（内部）")
    output: str = Field(description="输出节点 ID（内部）")


class CompoundNodeSnapshot(BaseModel):
    """复合节点配置快照"""
    id: str = Field(description="复合节点唯一标识")
    name: str = Field(description="复合节点名称")
    type: str = Field(default="compound")
    expanded_nodes: list[NodeConfig] = Field(default_factory=list)
    internal_edges: list[EdgeConfig] = Field(default_factory=list)
    exposed_ports: CompoundExposedPorts


# ─── API 请求/响应模型 ───────────────────────────────

class PipelineCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    type: PipelineType = PipelineType.AGGREGATION
    config_snapshot: Optional[PipelineSnapshot] = None
    change_log: Optional[str] = None


class PipelineUpdateRequest(BaseModel):
    config_snapshot: PipelineSnapshot
    change_log: str = Field(min_length=1)


class RollbackRequest(BaseModel):
    change_log: str = Field(min_length=1)


class CompareRequest(BaseModel):
    pipeline_id: str
    v1: int = Field(ge=1)
    v2: int = Field(ge=1)


class DryRunRequest(BaseModel):
    query: str = Field(min_length=1)
    params: dict[str, Any] = Field(default_factory=dict)


class PipelineValidateRequest(BaseModel):
    config_snapshot: PipelineSnapshot


class CompoundNodeCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    config_snapshot: CompoundNodeSnapshot


class CompoundNodeImportRequest(BaseModel):
    config_snapshot: CompoundNodeSnapshot
    name: Optional[str] = None


class PipelineSummaryResponse(BaseModel):
    id: str
    name: str
    type: str
    active_version: int
    created_at: datetime
    updated_at: datetime


class PipelineDetailResponse(BaseModel):
    id: str
    name: str
    type: str
    tenant_id: str
    active_version: int
    current_config: PipelineSnapshot
    change_log: Optional[str]
    created_at: datetime
    updated_at: datetime


class PipelineCreateResponse(BaseModel):
    pipeline_id: str
    version_number: int
    created_at: datetime


class PipelineUpdateResponse(BaseModel):
    pipeline_id: str
    version_number: int
    created_at: datetime


class PipelineRollbackResponse(BaseModel):
    pipeline_id: str
    version_number: int
    rollback_from_version: int
    created_at: datetime


class VersionSummaryResponse(BaseModel):
    id: str
    pipeline_id: str
    version_number: int
    change_log: Optional[str]
    created_at: datetime


class VersionDetailResponse(BaseModel):
    id: str
    pipeline_id: str
    version_number: int
    change_log: Optional[str]
    config_snapshot: PipelineSnapshot
    created_at: datetime


class NodeDiffItem(BaseModel):
    node_id: str
    field: str
    old_value: Any
    new_value: Any


class CompareDiff(BaseModel):
    nodes_added: list[NodeConfig] = Field(default_factory=list)
    nodes_removed: list[NodeConfig] = Field(default_factory=list)
    nodes_modified: list[dict] = Field(default_factory=list)  # {node_id, changes: [NodeDiffItem]}
    edges_added: list[EdgeConfig] = Field(default_factory=list)
    edges_removed: list[EdgeConfig] = Field(default_factory=list)


class CompareResponse(BaseModel):
    v1: dict
    v2: dict
    diff: CompareDiff


class ValidationError(BaseModel):
    location: str = Field(description="错误位置，如 domains[0].pipeline.nodes[2]")
    node_id: Optional[str] = None
    node_type: Optional[str] = None
    field: Optional[str] = None
    message: str
    severity: str = "error"  # error | warning


class ValidateResponse(BaseModel):
    valid: bool
    errors: list[ValidationError] = Field(default_factory=list)


class DryRunPhase(BaseModel):
    phase: ExecutionPhase
    node: Optional[str] = None
    domains: list[str] = Field(default_factory=list)
    nodes: list[str] = Field(default_factory=list)


class ExecutionPlanSummary(BaseModel):
    pipeline_id: str
    version: int
    shortcut_activated: bool
    phases: list[DryRunPhase]
    total_nodes: int
    estimated_domains: int


class DryRunError(BaseModel):
    node_id: Optional[str]
    message: str
    severity: str


class DryRunResponse(BaseModel):
    compilable: bool
    execution_plan: Optional[ExecutionPlanSummary]
    warnings: list[ValidationError] = Field(default_factory=list)
    errors: list[DryRunError] = Field(default_factory=list)


class CompoundNodeSummaryResponse(BaseModel):
    id: str
    name: str
    node_count: int
    created_at: datetime


class CompoundNodeDetailResponse(BaseModel):
    id: str
    name: str
    config_snapshot: CompoundNodeSnapshot
    created_at: datetime


class NodeTypeParameterDef(BaseModel):
    name: str
    type: str
    default: Any
    config_level: str  # L0/L1/L2/L3
    description: str


class NodeTypeDef(BaseModel):
    type_id: str
    category: str
    name_zh: str
    input_type: str
    output_type: str
    parameters: list[NodeTypeParameterDef]


class NodeTypesResponse(BaseModel):
    types: list[NodeTypeDef]


# ─── 运行时数据类（dataclass，非 Pydantic）────────────

T = TypeVar("T")


@dataclass
class NodeContext:
    """节点执行上下文"""
    node_id: str
    node_type: str
    config: dict[str, Any]
    input_data: Any
    pipeline_id: str
    pipeline_version: int
    domain_id: Optional[str] = None
    tenant_id: str = ""
    trace_id: str = ""


@dataclass
class NodeResult(Generic[T]):
    """节点执行结果"""
    node_id: str
    node_type: str
    output: T
    duration_ms: float = 0.0
    error: Optional[str] = None
    degraded: bool = False
    degradation_strategy: Optional[DegradationStrategy] = None


@dataclass
class PipelineState:
    """管道执行状态"""
    pipeline_id: str
    pipeline_version: int
    tenant_id: str
    query: str
    params: dict[str, Any] = field(default_factory=dict)
    domain_plans: list[Any] = field(default_factory=list)
    domain_results: dict[str, Any] = field(default_factory=dict)
    aggregation_results: dict[str, Any] = field(default_factory=dict)
    final_answer: Any = None
    shortcut_activated: bool = False
    degradation_events: list[dict] = field(default_factory=list)
    errors: list[dict] = field(default_factory=list)
    node_results: dict[str, NodeResult] = field(default_factory=dict)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


@dataclass
class CompiledPipeline:
    """编译后的管道"""
    pipeline_id: str
    pipeline_version: int
    aggregation_nodes: list[NodeConfig]
    aggregation_edges: list[EdgeConfig]
    shortcut_edge: Optional[ShortcutEdge]
    domains: list[tuple[DomainConfig, list[NodeConfig], list[EdgeConfig]]]
    # 每个域：(域配置, 拓扑排序后的节点列表, 边列表)


@dataclass
class ExecutionPlan:
    """执行计划"""
    phases: list[DryRunPhase]
    total_nodes: int
    shortcut_activated: bool
    compiled_pipeline: CompiledPipeline
```

---

### 3.2 服务类签名（`backend/src/service/pipeline/`）

```python
# ─── PipelineService ──────────────────────────────────

class PipelineService:
    """管道 CRUD + 版本管理 + 校验 + 干运行"""

    def __init__(
        self,
        pipeline_repo: "PipelineRepository",
        version_repo: "PipelineVersionRepository",
        compiler: "PipelineCompiler",
        validator: "PipelineValidator",
    ): ...

    # CRUD
    async def create_pipeline(
        self, tenant_id: str, request: PipelineCreateRequest
    ) -> PipelineCreateResponse: ...

    async def list_pipelines(
        self, tenant_id: str, page: int = 1, page_size: int = 20,
        keyword: Optional[str] = None, pipe_type: Optional[str] = None
    ) -> PaginatedResponse[PipelineSummaryResponse]: ...

    async def get_pipeline(self, pipeline_id: str) -> PipelineDetailResponse: ...

    async def update_pipeline(
        self, pipeline_id: str, request: PipelineUpdateRequest
    ) -> PipelineUpdateResponse: ...

    async def delete_pipeline(self, pipeline_id: str) -> None: ...

    # 版本管理
    async def list_versions(
        self, pipeline_id: str, page: int = 1, page_size: int = 20
    ) -> PaginatedResponse[VersionSummaryResponse]: ...

    async def get_version(
        self, pipeline_id: str, version_number: int
    ) -> VersionDetailResponse: ...

    async def rollback(
        self, pipeline_id: str, version_number: int, request: RollbackRequest
    ) -> PipelineRollbackResponse: ...

    async def compare(
        self, request: CompareRequest
    ) -> CompareResponse: ...

    # 校验
    async def validate(
        self, pipeline_id: str, request: Optional[PipelineValidateRequest] = None
    ) -> ValidateResponse: ...

    # 干运行
    async def dry_run(
        self, pipeline_id: str, request: DryRunRequest
    ) -> DryRunResponse: ...


# ─── CompoundNodeService ─────────────────────────────

class CompoundNodeService:
    """复合节点 CRUD + 导入导出"""

    def __init__(self, compound_node_repo: "CompoundNodeRepository"): ...

    async def list_compound_nodes(
        self, owner_id: str, page: int = 1, page_size: int = 20
    ) -> PaginatedResponse[CompoundNodeSummaryResponse]: ...

    async def create_compound_node(
        self, owner_id: str, request: CompoundNodeCreateRequest
    ) -> CompoundNodeDetailResponse: ...

    async def delete_compound_node(self, compound_node_id: str) -> None: ...

    async def import_compound_node(
        self, owner_id: str, request: CompoundNodeImportRequest
    ) -> CompoundNodeDetailResponse: ...

    async def export_compound_node(
        self, compound_node_id: str
    ) -> CompoundNodeSnapshot: ...


# ─── PipelineCompiler ────────────────────────────────

class PipelineCompiler:
    """编译管道配置为可执行 DAG，按拓扑顺序驱动执行"""

    def __init__(self, registry: "NodeRegistry"): ...

    def compile(
        self, config_snapshot: PipelineSnapshot, query: str, params: dict[str, Any]
    ) -> CompiledPipeline:
        """编译管道配置为 CompiledPipeline。
        校验节点类型存在性、边合法性、无环。
        编译失败抛出 PipelineCompileError。"""
        ...

    async def execute(
        self, compiled: CompiledPipeline, state: PipelineState
    ) -> PipelineState:
        """按 CompiledPipeline 执行完整管道。
        返回填充了结果的 PipelineState。"""
        ...

    def _build_execution_plan(
        self, compiled: CompiledPipeline
    ) -> ExecutionPlan:
        """根据编译结果构建执行计划摘要（供干运行返回）。"""
        ...

    async def _execute_domain_pipeline(
        self, domain: DomainConfig, nodes: list[NodeConfig],
        edges: list[EdgeConfig], state: PipelineState
    ) -> Any:
        """执行单个域管道。按拓扑顺序遍历节点，处理条件边和降级边。"""
        ...

    async def _execute_aggregation(
        self, compiled: CompiledPipeline, state: PipelineState
    ) -> PipelineState:
        """执行聚合层节点。检测单域快捷路径。"""
        ...

    async def _execute_node(
        self, node_config: NodeConfig, context: NodeContext
    ) -> NodeResult:
        """执行单个节点。从 NodeRegistry 获取执行器并调用 execute()。"""
        ...

    def _evaluate_condition(
        self, node_result: NodeResult, condition: str
    ) -> bool:
        """求值条件边表达式。"""
        ...

    async def _handle_degradation(
        self, node_config: NodeConfig, degradation_edge: EdgeConfig,
        context: NodeContext, state: PipelineState
    ) -> Optional[NodeResult]:
        """执行降级策略。"""
        ...


# ─── NodeRegistry ────────────────────────────────────

from abc import ABC, abstractmethod


class BaseNodeExecutor(ABC):
    """所有节点执行器的基类"""

    @abstractmethod
    async def execute(self, context: NodeContext) -> NodeResult:
        """执行节点逻辑。context 包含输入数据和节点配置。"""
        ...

    @abstractmethod
    def validate_config(self, config: dict[str, Any]) -> list[str]:
        """校验节点配置。返回错误列表，空列表表示合法。"""
        ...


class NodeRegistry:
    """节点类型注册表。PipelineCompiler 编译时从此处查找节点执行器。"""

    _registry: dict[str, type[BaseNodeExecutor]] = {}

    @classmethod
    def register(cls, node_type: str, executor_class: type[BaseNodeExecutor]) -> None:
        """注册节点类型。发版时在模块初始化中调用。"""
        ...

    @classmethod
    def get(cls, node_type: str) -> type[BaseNodeExecutor]:
        """查找节点执行器。未注册的类型抛出 NodeNotRegisteredError。"""
        ...

    @classmethod
    def list_types(cls) -> list[str]:
        """返回所有已注册的节点类型标识列表。"""
        ...


# ─── PipelineValidator ───────────────────────────────

class PipelineValidator:
    """管道配置校验器。在校验端点和保存前调用。"""

    def __init__(self, registry: "NodeRegistry"): ...

    def validate(
        self, config_snapshot: PipelineSnapshot
    ) -> list[ValidationError]:
        """校验完整管道配置：
        - 所有节点 type 是否在 NodeRegistry 中注册
        - 每个节点的 config 通过对应执行器的 validate_config()
        - edges 的 source/target 是否指向存在的节点
        - 条件边的 condition 是否合法
        - 降级边的 strategy 是否合法
        - 有无循环依赖
        - 聚合层 shortcut_edge 的 source/target 是否存在
        - 域管道之间的节点 ID 是否无冲突
        - 复合节点嵌套深度 ≤ 3
        """
        ...


# ─── 异常类 ─────────────────────────────────────────

from src.schemas.common import AppException


class PipelineError(AppException):
    """管道模块基础异常"""


class PipelineNotFoundError(PipelineError):
    """管道不存在 (40401)"""
    code: int = 40401
    error_code: str = "PIPELINE_NOT_FOUND"


class PipelineVersionNotFoundError(PipelineError):
    """版本不存在 (40402)"""
    code: int = 40402
    error_code: str = "PIPELINE_VERSION_NOT_FOUND"


class PipelineConfigInvalidError(PipelineError):
    """管道配置不合法 (40003)"""
    code: int = 40003
    error_code: str = "PIPELINE_CONFIG_INVALID"


class CompoundNodeConfigInvalidError(PipelineError):
    """复合节点配置不合法 (40004)"""
    code: int = 40004
    error_code: str = "COMPOUND_NODE_CONFIG_INVALID"


class NodeNotRegisteredError(PipelineError):
    """节点类型未注册 (40005)"""
    code: int = 40005
    error_code: str = "NODE_NOT_REGISTERED"


class PipelineCompileError(PipelineError):
    """管道编译失败 (40006)"""
    code: int = 40006
    error_code: str = "PIPELINE_COMPILE_ERROR"


class PipelineExecutionError(PipelineError):
    """管道执行失败 (50001)"""
    code: int = 50001
    error_code: str = "PIPELINE_EXECUTION_ERROR"
```

---

### 3.3 Repository 签名

```python
# backend/src/repository/pipeline_repository.py

from src.repository.base import BaseRepository

class PipelineRepository(BaseRepository):
    """pipeline 表数据访问"""
    async def list_by_tenant(
        self, tenant_id: str, skip: int = 0, limit: int = 20,
        keyword: Optional[str] = None, pipe_type: Optional[str] = None
    ) -> tuple[list, int]: ...  # (items, total)

    async def update_active_version(self, pipeline_id: str, version_number: int) -> None: ...


class PipelineVersionRepository(BaseRepository):
    """pipeline_versions 表数据访问"""
    async def get_latest_version_number(self, pipeline_id: str) -> int: ...
    async def get_by_version(self, pipeline_id: str, version_number: int) -> Optional[Any]: ...
    async def list_by_pipeline(self, pipeline_id: str, skip: int = 0, limit: int = 20) -> tuple[list, int]: ...
    async def delete_by_pipeline(self, pipeline_id: str) -> None: ...


class CompoundNodeRepository(BaseRepository):
    """compound_nodes 表数据访问"""
    async def list_by_owner(self, owner_id: str, skip: int = 0, limit: int = 20) -> tuple[list, int]: ...
```

---

## 4. 28 节点执行器清单

| # | type_id | 执行器类名 | 文件位置 | 输入类型 | 输出类型 |
|---|---------|-----------|---------|---------|---------|
| **查询理解（7 种）** |
| 1 | `query_rewrite` | `QueryRewriteExecutor` | `core/pipeline/nodes/query/rewrite.py` | `RawQuery` | `QueryVariant[]` |
| 2 | `synonym_expand` | `SynonymExpandExecutor` | `core/pipeline/nodes/query/synonym_expand.py` | `QueryVariant` | `ExpandedQuery` |
| 3 | `query_decompose` | `QueryDecomposeExecutor` | `core/pipeline/nodes/query/decompose.py` | `ComplexQuery` | `SubQuery[]` |
| 4 | `term_normalize` | `TermNormalizeExecutor` | `core/pipeline/nodes/query/term_normalize.py` | `RawQuery` | `NormalizedQuery` |
| 5 | `intent_classify` | `IntentClassifyExecutor` | `core/pipeline/nodes/query/intent_classify.py` | `Query` | `IntentLabel[]` |
| 6 | `stopword_filter` | `StopwordFilterExecutor` | `core/pipeline/nodes/query/stopword_filter.py` | `Query` | `FilteredQuery` |
| 7 | `query_expand` | `QueryExpandExecutor` | `core/pipeline/nodes/query/query_expand.py` | `Query` | `QueryVariant[]` |
| **检索策略（5 种）** |
| 8 | `bm25_search` | `BM25SearchExecutor` | `core/pipeline/nodes/retrieval/bm25_search.py` | `Query` | `CandidateSet` |
| 9 | `vector_search` | `VectorSearchExecutor` | `core/pipeline/nodes/retrieval/vector_search.py` | `Query` | `CandidateSet` |
| 10 | `hybrid_search` | `HybridSearchExecutor` | `core/pipeline/nodes/retrieval/hybrid_search.py` | `Query` | `CandidateSet` |
| 11 | `multimodal_search` | `MultimodalSearchExecutor` | `core/pipeline/nodes/retrieval/multimodal_search.py` | `Query` | `CandidateSet` |
| 12 | `result_fusion` | `ResultFusionExecutor` | `core/pipeline/nodes/retrieval/result_fusion.py` | `CandidateSet[]` | `CandidateSet` |
| **安全合规（3 种）** |
| 13 | `sensitive_filter` | `SensitiveFilterExecutor` | `core/pipeline/nodes/security/sensitive_filter.py` | `CandidateSet` | `CandidateSet` |
| 14 | `pii_mask` | `PIIMaskExecutor` | `core/pipeline/nodes/security/pii_mask.py` | `CandidateSet` | `CandidateSet` |
| 15 | `content_audit` | `ContentAuditExecutor` | `core/pipeline/nodes/security/content_audit.py` | `CandidateSet` | `CandidateSet` |
| **质量增强（4 种）** |
| 16 | `rerank` | `RerankExecutor` | `core/pipeline/nodes/quality/rerank.py` | `CandidateSet` | `CandidateSet` |
| 17 | `dedup` | `DedupExecutor` | `core/pipeline/nodes/quality/dedup.py` | `CandidateSet` | `CandidateSet` |
| 18 | `hallucination_check` | `HallucinationCheckExecutor` | `core/pipeline/nodes/quality/hallucination_check.py` | `CandidateSet` | `CandidateSet` |
| 19 | `citation_verify` | `CitationVerifyExecutor` | `core/pipeline/nodes/quality/citation_verify.py` | `CandidateSet` | `CandidateSet` |
| **性能优化（2 种）** |
| 20 | `semantic_cache` | `SemanticCacheExecutor` | `core/pipeline/nodes/performance/semantic_cache.py` | `Query` | `CachedResult\|None` |
| 21 | `rate_limiter` | `RateLimiterExecutor` | `core/pipeline/nodes/performance/rate_limiter.py` | `Query` | `Query\|RateLimitError` |
| **答案合成（1 种）** |
| 22 | `structured_output` | `StructuredOutputExecutor` | `core/pipeline/nodes/synthesis/structured_output.py` | `CandidateSet` | `StructuredResult` |
| **聚合层（6 种）** |
| 23 | `query_analyzer` | `QueryAnalyzerExecutor` | `core/pipeline/nodes/aggregation/query_analyzer.py` | `RawQuery` | `DomainPlan[]` |
| 24 | `domain_dispatch` | `DomainDispatchExecutor` | `core/pipeline/nodes/aggregation/domain_dispatch.py` | `DomainPlan[]` | `RoutedQuery[]` |
| 25 | `cross_fusion` | `CrossFusionExecutor` | `core/pipeline/nodes/aggregation/cross_fusion.py` | `DomainResult[]` | `MergedSet` |
| 26 | `cross_dedup` | `CrossDedupExecutor` | `core/pipeline/nodes/aggregation/cross_dedup.py` | `MergedSet` | `DedupedSet` |
| 27 | `conflict_detect` | `ConflictDetectExecutor` | `core/pipeline/nodes/aggregation/conflict_detect.py` | `DedupedSet` | `ConflictReport` |
| 28 | `unified_generate` | `UnifiedGenerateExecutor` | `core/pipeline/nodes/aggregation/unified_generate.py` | `DedupedSet+ConflictReport` | `Answer` |

**注册入口**（`core/pipeline/nodes/__init__.py`）：

```python
# 在模块初始化时注册全部 28 种节点执行器
from src.core.pipeline.nodes.registry import NodeRegistry
from src.core.pipeline.nodes.query import ...
from src.core.pipeline.nodes.retrieval import ...
from src.core.pipeline.nodes.security import ...
from src.core.pipeline.nodes.quality import ...
from src.core.pipeline.nodes.performance import ...
from src.core.pipeline.nodes.synthesis import ...
from src.core.pipeline.nodes.aggregation import ...

NodeRegistry.register("query_rewrite", QueryRewriteExecutor)
NodeRegistry.register("synonym_expand", SynonymExpandExecutor)
# ... 共 28 行
```

---

## 5. 数据流

### 5.1 聚合管道完整执行流

```
[用户查询: RawQuery]
        │
        ▼
 ┌──────────────────┐
 │  query_analyzer   │  分析查询涉及的域，生成 DomainPlan[]
 │  (聚合层节点)      │  输出: [{domain_id, confidence, keywords}, ...]
 └──────┬───────────┘
        │
        │ 检测激活域数量
        ├─── 1 个域 ──────────────────────────────────────────────┐
        │    (单域快捷路径，skip: domain_dispatch, cross_fusion,    │
        │     cross_dedup, conflict_detect)                        │
        │                                                          │
        ▼                                                          │
    多域路径                                                        │
        │                                                          │
        ▼                                                          │
 ┌──────────────────┐                                              │
 │ domain_dispatch   │  将 DomainPlan[] 分发为 RoutedQuery[]        │
 │  (聚合层节点)      │  并行启动各域管道（Thread/Async 并发）       │
 └──────┬───────────┘                                              │
        │                                                          │
   ┌────┴────┬────┐                                                │
   ▼         ▼    ▼                                                │
┌───────┐ ┌───────┐ ┌───────┐                                      │
│域 1    │ │域 2    │ │域 N    │  ← 各域独立执行域内管道              │
│ 管道   │ │ 管道   │ │ 管道   │    互不干扰，无共享状态              │
│       │ │       │ │       │                                      │
│ 节点1  │ │ 节点1  │ │ 节点1  │    每域内部:                       │
│  ├─data─┤ │  ├─data─┤ │  ├─data─┤    节点 → 条件边求值 → 下一跳   │
│ 节点2  │ │ 节点2  │ │ 节点2  │    失败 → 降级边 → 备选路径        │
│  ├─cond─┤ │  ├─cond─┤ │  ├─cond─┤                                  │
│ 节点3  │ │ 节点3  │ │ 节点3  │                                      │
│  ├─data─┤ │  ├─data─┤ │  ├─data─┤                                  │
│ 节点N  │ │ 节点N  │ │ 节点N  │                                      │
└───┬───┘ └───┬───┘ └───┬───┘                                      │
    │         │         │                                           │
    └────┬────┴────┬────┘                                           │
         │  汇总 DomainResult[]                                      │
         ▼                                                          │
  ┌──────────────────┐                                              │
  │  cross_fusion     │  多域结果融合为 MergedSet                     │
  │  (聚合层节点)      │  方法: weighted_rrf / weighted_sum           │
  └──────┬───────────┘                                              │
         │                                                          │
         ▼                                                          │
  ┌──────────────────┐                                              │
  │  cross_dedup      │  跨域去重 DedupedSet                          │
  │  (聚合层节点)      │                                              │
  └──────┬───────────┘                                              │
         │                                                          │
         ▼                                                          │
  ┌──────────────────┐                                              │
  │  conflict_detect  │  冲突检测 ConflictReport                      │
  │  (聚合层节点)      │                                              │
  └──────┬───────────┘                                              │
         │                                                          │
         │        ◄──── 单域快捷路径直接跳转 ────┘                    │
         │                                                          │
         ▼                                                          │
  ┌──────────────────┐                                              │
  │  unified_generate │  统一答案合成 → Answer                        │
  │  (聚合层节点)      │  输入: DedupedSet + ConflictReport           │
  └──────────────────┘                                              │
         │
         ▼
   [最终答案: Answer]
   {answer, citations, conflict_report?, shortcut_activated}
```

### 5.2 单域快捷路径

```
[查询] → query_analyzer → 检测到只有 1 个域 →
        跳过 domain_dispatch, cross_fusion, cross_dedup, conflict_detect →
        域管道执行 → unified_generate → [答案]
        
响应标记: shortcut_activated = true
```

### 5.3 条件边求值流程

```
节点执行完毕 → 遍历该节点的 conditional_edges
    ├── condition == "cache_hit" → NodeResult.output == CachedResult → true 分支
    ├── condition == "cache_miss" → NodeResult.output == None → false 分支
    └── condition == "intent_route:label" → 匹配 output 中的标签 → 对应分支

命中条件 → 路由到 condition edge 的 target 节点
未命中 → 继续沿 data edge 走主路径
```

### 5.4 降级链流程

```
节点执行抛出异常或超时 →
    ├── 有 degradation_edge 且 strategy != abort →
    │   ├── skip_node: 上游输出直传下游，记录降级事件
    │   ├── reroute: 路由到备选同类型节点（需配置 target 节点）
    │   ├── degrade_cache: 取最近一次成功缓存结果，记录降级事件
    │   └── abort (或无边): 直接返回错误，管道终止
    │
    降级记录写入 PipelineState.degradation_events → 异步上报 Tracing 系统
    连续降级次数超过阈值 (默认 10) → 触发 Prometheus 告警指标 + 通知
```

---

## 6. 测试策略

### 6.1 目录结构

```
backend/tests/
├── unit/
│   └── pipeline/
│       ├── nodes/
│       │   ├── test_query_rewrite.py
│       │   ├── test_synonym_expand.py
│       │   ├── test_vector_search.py
│       │   ├── test_hybrid_search.py
│       │   ├── test_result_fusion.py
│       │   ├── test_sensitive_filter.py
│       │   ├── test_pii_mask.py
│       │   ├── test_content_audit.py
│       │   ├── test_rerank.py
│       │   ├── test_dedup.py
│       │   ├── test_hallucination_check.py
│       │   ├── test_citation_verify.py
│       │   ├── test_semantic_cache.py
│       │   ├── test_rate_limiter.py
│       │   ├── test_structured_output.py
│       │   ├── test_query_analyzer.py
│       │   ├── test_domain_dispatch.py
│       │   ├── test_cross_fusion.py
│       │   ├── test_cross_dedup.py
│       │   ├── test_conflict_detect.py
│       │   └── test_unified_generate.py
│       ├── test_node_registry.py
│       ├── test_pipeline_validator.py
│       └── test_pipeline_compiler.py
├── integration/
│   └── pipeline/
│       ├── test_pipeline_compile_and_execute.py
│       ├── test_pipeline_shortcut.py
│       ├── test_pipeline_conditional_routing.py
│       ├── test_pipeline_degradation.py
│       ├── test_pipeline_version_management.py
│       └── test_compound_node_expansion.py
└── fixtures/
    └── pipeline/
        ├── sample_pipeline_config.py    # 预定义测试用管道配置
        └── mock_node_executors.py       # 通用 mock 执行器
```

### 6.2 单元测试：逐节点执行器测试

每个节点执行器测试覆盖三个维度：

```python
# 示例：test_query_rewrite.py

class TestQueryRewriteExecutor:
    """查询改写节点单元测试"""

    @pytest.fixture
    def executor(self):
        return QueryRewriteExecutor()

    @pytest.fixture
    def mock_llm(self):
        """Mock LLM 服务，返回预设改写结果"""
        ...

    # ── 配置校验 ──────────────────────

    def test_validate_config_valid(self, executor):
        """合法配置应返回空错误列表"""
        errors = executor.validate_config({"model": "gpt-4", "max_retries": 3})
        assert errors == []

    def test_validate_config_invalid_max_retries(self, executor):
        """max_retries 为负数应报错"""
        errors = executor.validate_config({"max_retries": -1})
        assert len(errors) > 0
        assert "max_retries" in errors[0]

    def test_validate_config_missing_required(self, executor):
        """缺少必填参数报告为 warning（因有 L0 默认值）"""
        ...

    # ── 正常执行 ──────────────────────

    @pytest.mark.asyncio
    async def test_execute_rewrites_query(self, executor, mock_llm):
        """正常输入应返回改写变体列表"""
        context = NodeContext(
            node_id="n1", node_type="query_rewrite",
            config={"model": "gpt-4", "max_retries": 2},
            input_data="2岁宝宝还不会走路怎么办",
            pipeline_id="p1", pipeline_version=1, tenant_id="t1", trace_id="tr1"
        )
        mock_llm.set_response(["2岁幼儿步行发育迟缓咨询", "2岁仍无法独立行走原因"])
        result = await executor.execute(context)
        assert result.output == ["2岁幼儿步行发育迟缓咨询", "2岁仍无法独立行走原因"]
        assert result.error is None

    # ── 异常处理 ──────────────────────

    @pytest.mark.asyncio
    async def test_execute_llm_timeout_retries(self, executor, mock_llm):
        """LLM 超时后按 max_retries 重试"""
        mock_llm.set_fail_then_succeed(fail_count=1, response=["重试后结果"])
        result = await executor.execute(context)
        assert result.output is not None

    @pytest.mark.asyncio
    async def test_execute_all_retries_exhausted(self, executor, mock_llm):
        """所有重试失败后返回 error"""
        mock_llm.set_always_fail()
        result = await executor.execute(context)
        assert result.error is not None
```

### 6.3 集成测试：PipelineCompiler 编译与执行

```python
# test_pipeline_compile_and_execute.py

class TestPipelineCompileAndExecute:
    """编译 + 执行端到端测试"""

    @pytest.fixture
    def registry(self):
        """使用全部已注册的 mock 执行器"""
        reg = NodeRegistry()
        # 注册全部 28 种 mock 执行器
        return reg

    @pytest.fixture
    def compiler(self, registry):
        return PipelineCompiler(registry)

    @pytest.fixture
    def simple_pipeline_config(self):
        """单域简单管道配置"""
        return PipelineSnapshot(
            domains=[
                DomainConfig(
                    id="d1", name="测试域", knowledge_base_id="kb_1", weight=1.0,
                    activation_rules=ActivationRules(keywords=["测试"], min_confidence=0.5),
                    pipeline=DomainPipelineConfig(
                        nodes=[
                            NodeConfig(id="n1", type="term_normalize", config={}),
                            NodeConfig(id="n2", type="vector_search", config={"top_k": 5}),
                        ],
                        edges=[EdgeConfig(id="e1", source="n1", target="n2", type=EdgeType.DATA)]
                    )
                )
            ],
            aggregation=AggregationConfig(
                nodes=[
                    NodeConfig(id="agg1", type="query_analyzer", config={}),
                    NodeConfig(id="agg2", type="domain_dispatch", config={}),
                    NodeConfig(id="agg3", type="cross_fusion", config={}),
                    NodeConfig(id="agg4", type="cross_dedup", config={}),
                    NodeConfig(id="agg5", type="conflict_detect", config={}),
                    NodeConfig(id="agg6", type="unified_generate", config={}),
                ],
                edges=[
                    EdgeConfig(id="ae1", source="agg1", target="agg2", type=EdgeType.DATA),
                    EdgeConfig(id="ae2", source="agg2", target="agg3", type=EdgeType.DATA),
                    EdgeConfig(id="ae3", source="agg3", target="agg4", type=EdgeType.DATA),
                    EdgeConfig(id="ae4", source="agg4", target="agg5", type=EdgeType.DATA),
                    EdgeConfig(id="ae5", source="agg5", target="agg6", type=EdgeType.DATA),
                ],
                shortcut_edge=ShortcutEdge(source="agg1", target="agg6")
            )
        )

    @pytest.mark.asyncio
    async def test_compile_success(self, compiler, simple_pipeline_config):
        """合法配置编译成功"""
        compiled = compiler.compile(simple_pipeline_config, "测试查询", {})
        assert compiled.pipeline_id is not None
        assert len(compiled.aggregation_nodes) == 6

    @pytest.mark.asyncio
    async def test_compile_unregistered_node_type(self, compiler):
        """未注册节点类型 → 抛出 PipelineCompileError"""
        bad_config = ...  # 含未注册的 type
        with pytest.raises(PipelineCompileError, match="未注册"):
            compiler.compile(bad_config, "查询", {})

    @pytest.mark.asyncio
    async def test_execute_returns_state(self, compiler, simple_pipeline_config):
        """执行成功返回填充的 PipelineState"""
        compiled = compiler.compile(simple_pipeline_config, "测试查询", {})
        state = PipelineState(
            pipeline_id="p1", pipeline_version=1, tenant_id="t1",
            query="测试查询", params={}
        )
        result = await compiler.execute(compiled, state)
        assert result.final_answer is not None
        assert len(result.node_results) > 0

    @pytest.mark.asyncio
    async def test_execute_shortcut_activated(self, compiler):
        """单域查询应触发快捷路径，跳过 4 个聚合中间节点"""
        single_domain_config = ...  # 仅 1 个域匹配
        compiled = compiler.compile(single_domain_config, "查询", {})
        state = PipelineState(...)
        result = await compiler.execute(compiled, state)
        assert result.shortcut_activated is True
        # 验证跳过的节点未执行
        assert "domain_dispatch" not in result.node_results

    @pytest.mark.asyncio
    async def test_execute_conditional_routing_cache_hit(self, compiler):
        """语义缓存命中 → 跳过检索链，直通答案合成"""
        ...

    @pytest.mark.asyncio
    async def test_execute_conditional_routing_cache_miss(self, compiler):
        """语义缓存未命中 → 走完整检索链"""
        ...

    @pytest.mark.asyncio
    async def test_execute_degradation_skip_node(self, compiler):
        """节点失败 → 降级 skip_node，上游输出直传下游"""
        ...

    @pytest.mark.asyncio
    async def test_domain_parallel_execution(self, compiler):
        """3 域管道并发执行，总耗时 ≈ max(单域耗时) + 聚合开销"""
        import time
        start = time.monotonic()
        result = await compiler.execute(compiled, state)
        elapsed = time.monotonic() - start
        single_domain_time = 0.5  # mock 单域耗时
        assert elapsed < single_domain_time * 3 * 0.8  # 明显小于串行

    @pytest.mark.asyncio
    async def test_compound_node_expansion(self, compiler):
        """复合节点正确展开，内部节点按 internal_edges 顺序执行"""
        ...

    @pytest.mark.asyncio
    async def test_degradation_event_recorded_in_state(self, compiler):
        """降级事件正确记录到 PipelineState.degradation_events"""
        ...
```

### 6.4 关键测试场景列表（≥8）

| # | 场景 | 测试类型 | 覆盖 AC |
|---|------|---------|---------|
| S1 | 合法管道配置编译成功，所有 28 种节点类型可编译 | 集成 | AC-1.1 |
| S2 | 管道配置引用未注册节点类型 → 编译失败，返回具体错误 | 集成 | AC-1.1 |
| S3 | 语义缓存命中 → 条件路由跳过检索链直达 `unified_generate` | 集成 | AC-1.2 |
| S4 | 语义缓存未命中 → 条件路由进入检索链 | 集成 | AC-1.2 |
| S5 | 节点执行超时 → 降级 skip_node → 上游输出直传下游 | 集成 | AC-1.3 |
| S6 | 降级事件写入 PipelineState → 追踪系统记录降级 Span | 集成 | AC-1.3 |
| S7 | 连续降级超过阈值 → Prometheus 告警指标递增 | 集成 | AC-1.4 |
| S8 | 复合节点展开后修改内部参数 → 其他管道实例不受影响 | 集成 | AC-1.5 |
| S9 | 管道保存 → 版本号自增（v1→v2） | 集成 | AC-1.6 |
| S10 | 回滚到 v2 → 创建新版本 v5（不覆盖 v2/v3/v4） | 集成 | AC-1.6 |
| S11 | 单域查询 → 跳过 4 个聚合节点，`shortcut_activated: true` | 集成 | AC-1.7 |
| S12 | 聚合层 edges 配置为 "先冲突检测再融合" 拓扑 → 按配置顺序执行 | 集成 | AC-1.8 |
| S13 | `validate` 端点返回具体错误（节点 id、参数名、问题描述） | 集成 | AC-1.9 |
| S14 | 3 域管道 → 域并发执行，总耗时 ≈ max(域耗时) + 聚合开销 | 集成 | AC-1.10 |
| S15 | 验证每个节点的 `validate_config()` 对合法/不合法配置的正确响应 | 单元 | AC-1.1 |
| S16 | 节点执行器 mock 依赖隔离，独立可测 | 单元 | — |

---

## 7. 验收标准映射

| AC | 描述 | 关联测试 | 验证方法 |
|----|------|---------|---------|
| AC-1.1 | 全部 28 种节点可编译执行，类型标识注册完整 | S1, S2, S15 | `test_compile_success` 验证所有 type_id 可查；`test_compile_unregistered_node_type` 验证未注册类型被拒绝；S15 验证所有执行器的配置校验 |
| AC-1.2 | 条件路由正确求值 | S3, S4 | `test_execute_conditional_routing_cache_hit` 与 `_cache_miss`，验证 `_evaluate_condition()` 对每种条件类型的求值 |
| AC-1.3 | 降级路径触发 + 追踪写入 | S5, S6 | `test_execute_degradation_skip_node` 验证降级策略执行；`test_degradation_event_recorded_in_state` 验证事件收集 |
| AC-1.4 | 降级频率超阈值触发告警 | S7 | Mock 触发多次降级 → 验证 Prometheus Counter 指标 `pipeline_degradation_total` 超过阈值后 `pipeline_degradation_alert` 置 1 |
| AC-1.5 | 复合节点修改不影响已部署实例 | S8 | 修改复合节点配置 → 验证之前使用该复合节点的管道版本 `config_snapshot` 未变（实例持有独立副本） |
| AC-1.6 | 版本号自增 + 回滚创建新版本 | S9, S10 | `test_pipeline_version_management`：保存验证 version_number 递增；回滚验证创建新记录而非覆盖 |
| AC-1.7 | 单域快捷路径 | S11 | `test_execute_shortcut_activated`：仅 1 域时 domain_dispatch/cross_fusion/cross_dedup/conflict_detect 不执行，`shortcut_activated=true` |
| AC-1.8 | edges 决定聚合层节点顺序 | S12 | 构造两种不同 edges 数组的管道配置，验证执行顺序与 edges 一致（拓扑排序结果匹配） |
| AC-1.9 | 校验端点返回具体错误位置 | S13 | `test_pipeline_validator`：传入多种错误配置 → 验证返回的 errors 数组包含 `location`（节点路径）、`field`（参数名）、`message`（问题描述） |
| AC-1.10 | 域并发执行性能 | S14 | `test_domain_parallel_execution`：mock 单域耗时 0.5s → 3 域总耗时 < 0.8s（0.5s + 聚合开销），远小于串行 1.5s |
