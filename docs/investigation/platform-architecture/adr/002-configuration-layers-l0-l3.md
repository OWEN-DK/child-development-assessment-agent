# ADR-002：L0-L3 四层配置架构

> 日期：2026-05-14
> 状态：已决定

## 背景

多租户平台需要灵活的参数管理：平台提供出厂默认值、租户全局覆盖、单资源配置、API 调用方临时覆盖。需要一个统一的配置分层模型。

## 决策

采用四层配置层级，覆盖优先级从高到低：**L3 > L2 > L1 > L0**。

```
L3: API 参数       ← 调用方单次请求覆盖（仅白名单参数）
L2: 资源配置        ← 管道/知识库/评估的独立配置
L1: 租户覆盖        ← 租户 admin 的全局默认配置
L0: 平台默认        ← 超管/系统内置 + .env 兜底
```

### 各模块的 L0 来源

| 模块 | L0 来源 |
|------|--------|
| 01-管道 | `core/pipeline/defaults.py` 中的 `NODE_DEFAULTS` dict |
| 03-知识库 | `core/knowledge_base/defaults.py` 中的 `CHUNK_DEFAULTS`、`EMBEDDING_DEFAULTS` |
| 04-权限 | 内置角色定义（admin/editor/viewer）+ `core/auth/defaults.py` |
| 05-搜索 | `MAX_QUERY_LENGTH=2000`、`MAX_BODY_SIZE=1MB` 等常量 |
| 06-评估 | `_DEFAULT_THRESHOLDS` dict + `DEFAULT_WEIGHTS` |
| 07-基础设施 | `.env` 中的 DATABASE_URL、REDIS_URL、JWT_SECRET 等 |

### Fallback 链

```
ConfigCache.get(key)
  → L3: 请求上下文中的 params（如有）
    → L2: 资源配置表中的值（如 pipeline_versions.config_snapshot）
      → L1: MySQL 全局配置表（tenant_id 维度）
        → L0: 代码常量 / .env 兜底
```

## 理由

1. **为什么 L0 不统一走 `.env`**：`.env` 不区分租户，无法在多租户场景下提供租户级默认值。L0 是"租户未配置时的系统全局兜底"，适合放代码常量；`.env` 仅用于基础设施凭证和环境变量。
2. **为什么 L1 走 MySQL 而非 `.env`**：`.env` 修改需重启服务，MySQL 修改支持热重载（ConfigCache + Redis Pub/Sub），满足不停机调整租户配置的需求。
3. **为什么 L3 需要白名单**：防止 API 调用方覆盖安全关键参数（如 `acl_filter`、`max_concurrency`）。
4. **为什么 L2 是主要配置层**：管道和知识库是业务核心单元，它们的独立配置是平台可组合性的基础。

## 后果

- 每个模块的所有参数必须在需求文档中标注允许的配置层级（`[L0]`/`[L1]`/`[L2]`/`[L3]`）
- `ConfigCache` 需要支持分层优先级的 `get(key, tenant_id, resource_id, request_params)` 查询
- L2 参数变更（如管道节点参数）不触发热重载——管道执行时动态读取最新配置
- L1 变更（如租户默认 LLM 模型）通过 Redis Pub/Sub 通知所有实例刷新
