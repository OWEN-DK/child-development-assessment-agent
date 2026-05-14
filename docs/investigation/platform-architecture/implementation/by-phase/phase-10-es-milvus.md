# Phase 10：ES/Milvus 后端扩展——阶段实施文档

> **上游依赖**：Phase 2（知识库管理）——三个向量存储适配器（Chroma/ES/Milvus）的代码框架已在 Phase 2 中实现，Phase 10 对其进行验证和调优。
> **下游被依赖**：无。此阶段为横向验证阶段，对已实现的后端扩展进行集成级别的端到端校验。
> **关联文档**：
> - [实施清单](../implementation-checklist.md) §Phase 10
> - [代码级实施计划](../implementation-plan-detail.md) §二 知识库管理（ES/Milvus 适配器、ACL 过滤器、BM25 索引、迁移服务）
> - [知识库模块完整规范](../by-module/03-knowledge-base.md) §附录 A（BM25 独立索引规范）
> - [基础设施模块完整规范](../by-module/07-infrastructure.md) §1（Docker Compose profiles 配置）、§ADR-007-03
> - [核心目标文档](../../core-objectives.md)
> **最后更新**：2026-05-14

---

## 1. 阶段目标

验证 ElasticsearchAdapter 和 MilvusAdapter 作为 Chroma 的替代向量后端在生产级条件下的正确性、一致性和可靠性。开发阶段默认只用 Chroma，ES/Milvus 按需通过 Docker Compose `profiles` 启用。

核心验证维度：

| 验证维度 | 目标 |
|---------|------|
| **向量检索正确性** | ES knn 查询和 Milvus 向量搜索返回与 Chroma 语义一致的结果（top-10 重叠率 ≥ 80%） |
| **BM25 检索正确性** | ES 内置 BM25（match query）和独立 BM25 索引管理器在 Chroma/Milvus 后端的结果一致 |
| **混合检索正确性** | BM25 + 向量 → RRF 融合在三后端下的结果语义等价 |
| **ACL 过滤一致性** | 同一用户、同一 KB、同一文档子集 → 三后端返回完全相同的文档子集 |
| **BM25 索引维护** | Chroma/Milvus 后端下独立 BM25 索引的增量更新、全量重建、删除级联均正确 |
| **后端迁移可靠性** | Chroma → ES、ES → Milvus 迁移流程完整可逆，失败时原子回滚 |
| **Docker Compose 配置** | 验证 profiles 启动/停止弹性搜索和 Milvus 的行为正确性 |

---

## 2. 任务清单

> 每项任务对应 [implementation-checklist.md](../implementation-checklist.md) §Phase 10 的可勾选项。勾选 `[ ]` 标记未完成，`[~]` 标记进行中，`[x]` 标记已完成。

### 2.1 ElasticsearchAdapter 验证

| # | 验证对象 | 验证内容 | 关键要点 |
|---|---------|---------|---------|
| 2.1.1 | ES 向量检索 | 通过 `knn` query 检索，验证返回结果的 cosine 分数和排序正确性 | `num_candidates = top_k × 10`，`field: embedding` (dense_vector)，filter clause 注入 ACL |
| 2.1.2 | ES BM25 检索 | 通过 `match` query 检索，验证文本字段的全文搜索能力 | ES 内置 BM25 无需独立索引，`field: content` (text)，支持 `multi_match` 多字段 |
| 2.1.3 | ES 混合检索 | BM25 + 向量并行检索 → RRF 融合，验证融合结果的有效性 | 并行调用 knn + match → 本地 RRF 融合，融合结果同时含语义匹配和关键词匹配的 chunk |
| 2.1.4 | ES index 映射验证 | 创建 index 时验证 mapping 字段定义正确 | `embedding: {type: dense_vector, dims, similarity: cosine}`, `content: {type: text}`, `doc_acl: {type: keyword}` |

- [ ] 2.1.1 — ES 向量检索（knn query）通过
- [ ] 2.1.2 — ES BM25 检索（match query）通过
- [ ] 2.1.3 — ES 混合检索（knn + match → RRF）通过
- [ ] 2.1.4 — ES index mapping 验证通过

### 2.2 MilvusAdapter 验证

| # | 验证对象 | 验证内容 | 关键要点 |
|---|---------|---------|---------|
| 2.2.1 | Milvus 向量检索 | 通过 `search()` 检索，验证返回 cosine 距离和排序正确性 | IVF_FLAT/HNSW 索引，`metric_type: COSINE`，expr filter 注入 ACL |
| 2.2.2 | Milvus + 独立 BM25 | Milvus Collection 仅存向量 → BM25 检索通过独立 `BM25IndexManager` 完成 | 验证 BM25 返回的 chunk_id 在 Milvus Collection 中存在且向量可查询 |
| 2.2.3 | Milvus Collection schema 验证 | 创建 Collection 时验证 schema 定义正确 | `chunk_id: VARCHAR(PK)`, `embedding: FLOAT_VECTOR(dim)`, `doc_acl: ARRAY VARCHAR`, `content: VARCHAR`（可选，用于调试） |

- [ ] 2.2.1 — Milvus 向量检索通过
- [ ] 2.2.2 — Milvus + 独立 BM25 联合检索通过
- [ ] 2.2.3 — Milvus Collection schema 验证通过

### 2.3 ACL 过滤器三后端一致性

| # | 验证对象 | 验证内容 | 关键要点 |
|---|---------|---------|---------|
| 2.3.1 | ACL 一致：restricted 文档 | 同一用户（editor 角色），同一 KB（含 5 个 inherit 文档 + 3 个 restricted to admin 文档），三后端搜索 | 三后端均返回 5 个 inherit 文档，0 个 restricted 文档 |
| 2.3.2 | ACL 一致：admin vs editor | admin 角色 → 三后端均返回全部 8 个；editor 角色 → 三后端均返回 5 个 inherit 文档 | 角色权限在三后端下效果完全一致 |
| 2.3.3 | ACL 一致：God Mode | user_roles=[] → 三后端均返回空 filter（全部文档可见） | God Mode 下三 Builder 统一返回空条件 |

- [ ] 2.3.1 — ACL 一致：restricted 文档不可见（三后端）
- [ ] 2.3.2 — ACL 一致：admin 可见全部 / editor 仅 inherit（三后端）
- [ ] 2.3.3 — ACL 一致：God Mode 全量可见（三后端）

### 2.4 BM25 索引维护验证

| # | 验证对象 | 验证内容 | 关键要点 |
|---|---------|---------|---------|
| 2.4.1 | BM25 增量更新 | Chroma KB 上传 3 篇文档 → 验证 `storage/bm25/{tenant_id}/{kb_id}/` 下 index.json 和 id_map.json 已生成 | 增量添加后索引文件含 3 个文档的分块 |
| 2.4.2 | BM25 增量删除 | 上传后删除 1 篇文档 → 验证 BM25 索引文件减少 | `remove_chunks()` 后 search 不再返回已删文档的 chunk |
| 2.4.3 | BM25 全量重建 | 分块策略变更触发重建 → 验证重建后 BM25 搜索正常 | `rebuild_from_chunks()` 全量重写 index.json |
| 2.4.4 | BM25 ES 后端禁止 | 创建 ES 后端 KB → 验证 `storage/bm25/` 下无对应目录 | ES 后端不维护独立 BM25 索引 |
| 2.4.5 | BM25 迁移联动 | Chroma→ES 迁移完成后 → BM25 索引目录已删除；ES→Chroma 迁移完成后 → BM25 索引已重建 | 迁移时正确处理索引的创建/删除 |

- [ ] 2.4.1 — BM25 增量更新（add_chunks）
- [ ] 2.4.2 — BM25 增量删除（remove_chunks）
- [ ] 2.4.3 — BM25 全量重建（rebuild）
- [ ] 2.4.4 — ES 后端不创建独立 BM25 索引
- [ ] 2.4.5 — BM25 迁移联动（创建/删除）

### 2.5 后端迁移流程验证

| # | 验证对象 | 验证内容 | 关键要点 |
|---|---------|---------|---------|
| 2.5.1 | Chroma → ES 迁移 | 100 文档 KB 从 Chroma 迁移到 ES → 验证 ES index 分块数 == kb_chunks 记录数 | 6 步完整流程：创建 target → 读取旧 chunks → 写入新后端 → 验证数量 → 切换 backend → 清理 source |
| 2.5.2 | ES → Milvus 迁移 | 同上 ES → Milvus → 验证 Milvus Collection 分块数 == kb_chunks 记录数 | 迁移过程中 KB status=rebuilding，旧索引只读可用 |
| 2.5.3 | 迁移幂等性 | 已完成 Chroma→ES 迁移 → 再次请求 Chroma→ES | 400 "ALREADY_SAME_BACKEND" |
| 2.5.4 | 迁移失败回滚 | Mock ES 写入第 50/100 文档时失败 → 验证回滚 | KB status 恢复 ready, KB vector_backend 保持 chroma, Chroma 旧数据完好, task status=failed |
| 2.5.5 | 迁移后数据完整性 | 迁移完成后随机抽样 20 篇文档 → 三后端搜索语义对比 | top-10 结果与迁移前一致（重叠率 ≥ 80%） |

- [ ] 2.5.1 — Chroma → ES 迁移成功
- [ ] 2.5.2 — ES → Milvus 迁移成功
- [ ] 2.5.3 — 迁移幂等性（同后端拒绝）
- [ ] 2.5.4 — 迁移失败回滚原子性
- [ ] 2.5.5 — 迁移后数据完整性（抽样验证）

### 2.6 Docker Compose profiles 配置

| # | 验证对象 | 验证内容 | 关键要点 |
|---|---------|---------|---------|
| 2.6.1 | ES profile 启动 | `docker compose --profile elasticsearch up -d` → 验证 ES 健康检查通过 | ES 容器运行，`:9200` 可访问，healthcheck 通过 |
| 2.6.2 | Milvus profile 启动 | `docker compose --profile milvus up -d` → 验证 Milvus + etcd + MinIO 健康检查通过 | 三个容器全部运行，`:19530` 可访问，healthcheck 通过 |
| 2.6.3 | 双 profile 启动 | `docker compose --profile elasticsearch --profile milvus up -d` → 验证全部服务就绪 | 后端可同时连接 ES 和 Milvus |
| 2.6.4 | 默认不启动 | `docker compose up -d`（无 profile）→ ES/Milvus 不启动 | 后端启动无报错，VectorStoreAdapterFactory 对 ES/Milvus 的访问正常抛 `ConfigurationError` |
| 2.6.5 | profile 停止 | `docker compose --profile elasticsearch stop` → ES 容器停止 | 后端优雅降级，已有 ES KB 返回 `not_configured` 而非 500 |

- [ ] 2.6.1 — ES profile 启动正常
- [ ] 2.6.2 — Milvus profile 启动正常
- [ ] 2.6.3 — 双 profile 同时启动正常
- [ ] 2.6.4 — 默认不启动 ES/Milvus
- [ ] 2.6.5 — profile 停止后优雅降级

---

## 3. 关键实现细节

### 3.1 Elasticsearch 索引映射 (Index Mapping)

ES 后端为每个知识库创建一个独立 Index，命名规则：`rag_{tenant_id}_{kb_id}`（全小写，ES 要求 index 名必须小写）。

```json
{
  "settings": {
    "number_of_shards": 1,
    "number_of_replicas": 0,
    "refresh_interval": "5s"
  },
  "mappings": {
    "properties": {
      "chunk_id":      { "type": "keyword" },
      "doc_id":        { "type": "keyword" },
      "kb_id":         { "type": "keyword" },
      "tenant_id":     { "type": "keyword" },
      "content":       { "type": "text", "analyzer": "standard" },
      "embedding":     { "type": "dense_vector", "dims": 1024, "index": true, "similarity": "cosine" },
      "doc_acl":       { "type": "keyword" },
      "chunk_index":   { "type": "integer" },
      "created_at":    { "type": "date" }
    }
  }
}
```

**字段说明**：

| 字段 | 类型 | 说明 |
|------|------|------|
| `chunk_id` | keyword | 分块唯一标识，精确匹配 |
| `doc_id` | keyword | 所属文档 ID，精确匹配 |
| `content` | text | 分块原文，用于 ES 内置 BM25 全文搜索（`match` query） |
| `embedding` | dense_vector | 向量嵌入，维度在创建时动态设置（从 EmbeddingConfig 读取），`similarity: cosine` |
| `doc_acl` | keyword | 文档 ACL 数组，用于权限过滤（`terms` query） |

**向量检索流程（knn query）**：
```python
body = {
    "knn": {
        "field": "embedding",
        "query_vector": query_vector,
        "k": top_k,
        "num_candidates": top_k * 10
    },
    "size": top_k,
    "_source": ["chunk_id", "doc_id", "content", "chunk_index"]
}
if acl_filter:
    body["knn"]["filter"] = acl_filter  # ES filter clause (terms + must_not)
```

**BM25 检索流程（match query）**：
```python
body = {
    "query": {
        "match": {
            "content": {
                "query": query_text,
                "operator": "or"
            }
        }
    },
    "size": top_k,
    "_source": ["chunk_id", "doc_id", "content", "chunk_index"]
}
```

### 3.2 Milvus Collection Schema

Milvus 后端为每个知识库创建一个独立 Collection，命名规则：`rag_{tenant_id}_{kb_id}`（全小写，Milvus 要求 Collection 名必须小写且仅含字母/数字/下划线）。

```python
from pymilvus import CollectionSchema, FieldSchema, DataType

fields = [
    FieldSchema(name="chunk_id", dtype=DataType.VARCHAR, is_primary=True, max_length=64),
    FieldSchema(name="doc_id", dtype=DataType.VARCHAR, max_length=64),
    FieldSchema(name="kb_id", dtype=DataType.VARCHAR, max_length=64),
    FieldSchema(name="tenant_id", dtype=DataType.VARCHAR, max_length=64),
    FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=configuration.embedding_dimension),
    FieldSchema(name="doc_acl", dtype=DataType.ARRAY, element_type=DataType.VARCHAR, max_capacity=100, max_length=64),
    FieldSchema(name="chunk_index", dtype=DataType.INT64),
]

schema = CollectionSchema(fields, description=f"KB {kb_id} vector store")
```

**索引创建**：
```python
index_params = {
    "metric_type": "COSINE",
    "index_type": "IVF_FLAT",  # 或 HNSW（可通过配置切换）
    "params": {"nlist": 128}
}
collection.create_index("embedding", index_params)
collection.load()
```

**ACL 过滤（expr 表达式）**：
```python
# MilvusACLFilterBuilder 构建的 expr 字符串示例
# admin/editor 角色：
#   array_contains_any(doc_acl, ["admin", "editor"])
# 含 inherit 文档兜底（doc_acl 为空或 null 的文档对所有角色可见）：
#   array_contains_any(doc_acl, ["editor"]) or len(doc_acl) == 0 or doc_acl is null
# God Mode（user_roles=[] 或超管）：
#   不传 expr（全量返回）
```

### 3.3 BM25 独立索引

Chroma 和 Milvus 不提供内置 BM25 全文搜索能力，需要独立的文件系统级 BM25 索引。

**触发条件**：`knowledge_bases.vector_backend ∈ {"chroma", "milvus"}` 时，`KnowledgeBaseService.create()` 调用 `BM25IndexManager` 初始化索引目录。ES 后端不创建独立 BM25 索引（使用 ES 内置 BM25）。

**索引结构**：
```
storage/bm25/{tenant_id}/{kb_id}/
├── index.json       # BM25Okapi 序列化索引（rank_bm25 库）
├── id_map.json      # 内部 ID → chunk_id 映射
└── metadata.json    # 创建时间、文档数、k1=1.5, b=0.75
```

**分词**：所有中文文本通过 `jieba` 精确模式分词后加入 BM25 索引，英文按空格分词。

**参数**：k1=1.5, b=0.75，系统固定默认值，不接受用户配置。

**增量更新策略**：
- 文件级写锁（`asyncio.Lock`，per KB per tenant），避免并发增量更新导致索引损坏
- `add_chunks()`：读取现有索引 → 分词 → 追加到 BM25Okapi → 序列化写回
- `remove_chunks()`：通过 BM25 class 的 `remove()` 方法删除（rank_bm25 库限制：BM25Okapi 不支持直接删除，实际上必须全量重建；因此 `remove_chunks()` 实现为从 DB 获取当前全部 chunks → 全量重建）
- `rebuild()`：从 `kb_chunks` 表获取所有 chunks → 全量重建

**锁控制实现**：
```python
class BM25IndexManager:
    def __init__(self, storage_root: str = "storage/bm25"):
        self._storage_root = storage_root
        self._locks: dict[str, asyncio.Lock] = {}  # key: "{tenant_id}/{kb_id}"

    def _get_lock(self, kb_id: str, tenant_id: str) -> asyncio.Lock:
        key = f"{tenant_id}/{kb_id}"
        if key not in self._locks:
            self._locks[key] = asyncio.Lock()
        return self._locks[key]
```

### 3.4 后端迁移流程

`MigrationService.migrate()` 实现 6 步完整迁移流程，支持任意方向迁移（Chroma↔ES↔Milvus）。

**前置条件检查**：
- 知识库 status != rebuilding（重建期间禁止迁移）
- 目标后端可连接（`VectorStoreAdapterFactory.get_adapter(target).health_check()`）
- 目标后端 != 源后端（幂等性检查，相同时返回 400 "ALREADY_SAME_BACKEND"）

**6 步迁移流程**：

```
[1] 创建目标存储
    ├─ 目标后端创建 Collection/Index（如 ES: PUT /rag_{tenant_id}_{kb_id}）
    ├─ 如需独立 BM25：创建目标 BM25 索引目录
    └─ KB status → "rebuilding"

[2] 从源后端读取所有 chunks
    ├─ 从 kb_chunks 表分批读取（batch_size=500）
    ├─ 从源后端获取 embedding 向量
    └─ 进度：progress_pct 0% → 30%

[3] 写入目标后端
    ├─ 分批写入目标后端（batch_size=200）
    ├─ 如需独立 BM25：同步写入目标 BM25 索引
    └─ 进度：progress_pct 30% → 70%

[4] 验证数据完整性
    ├─ 目标后端 chunk 数量 == kb_chunks 记录数
    ├─ 随机抽样 20 个 chunk 搜索验证
    ├─ 数量不一致 → 触发回滚
    └─ 进度：progress_pct 70% → 85%

[5] 切换后端
    ├─ 更新 knowledge_bases.vector_backend = target
    ├─ 更新 knowledge_bases.status = "ready"
    └─ 进度：progress_pct 85% → 95%

[6] 清理源存储
    ├─ 删除源 Collection/Index
    ├─ 如需独立 BM25：删除或重建源 BM25 索引
    └─ 进度：progress_pct 95% → 100%
```

**回滚策略**：保持源存储完整可用，直到步骤 [4] 验证通过后才执行 [5] 切换。如果 [1]-[4] 任一阶段失败：

```python
async def _rollback_on_failure(self, kb_id: str, target_backend: str, error: Exception):
    """迁移失败原子回滚。"""
    # 1. 删除目标存储（清理垃圾）
    await self._cleanup_target(kb_id, target_backend)

    # 2. 恢复 KB 状态
    await self._kb_repo.update(kb_id, status="ready")

    # 3. 标记任务失败
    await self._rebuild_repo.update(task_id, status="failed", error=str(error))

    # 注意：源存储从未修改或删除，无需恢复
```

**迁移时间预估**（基于 1000 文档基准测试）：

| 场景 | 预估时间 | 主要耗时分布 |
|------|---------|-------------|
| 1000 chunks, Chroma → ES | ≤ 3 分钟 | 写入 ES 60%，验证 20% |
| 1000 chunks, ES → Milvus | ≤ 5 分钟 | 写入 Milvus 70%，索引构建 20% |
| 10000 chunks, Chroma → ES | ≤ 30 分钟 | 写入 ES 50%，读取 Chroma 30% |

### 3.5 Docker Compose profiles 设计

**ADR 决策**：ES 和 Milvus 通过 Docker Compose `profiles` 实现可选启用，默认不启动（参考 [ADR-007-03](../by-module/07-infrastructure.md#adr-007-03-es-和-milvus-作为可选-profile)）。

**使用方式**：
```bash
# 仅 Chroma（默认开发环境）
docker compose up -d

# 启用 ES
docker compose --profile elasticsearch up -d

# 启用 Milvus（含 etcd + MinIO 依赖）
docker compose --profile milvus up -d

# 完全体（三后端全部可用）
docker compose --profile elasticsearch --profile milvus up -d
```

**profiles 映射**：
| 服务 | profiles | 端口 | 依赖 |
|------|----------|------|------|
| `elasticsearch` | `elasticsearch` | 9200 | 无 |
| `etcd` | `milvus` | —（内部） | 无 |
| `minio` | `milvus` | 9000, 9001 | 无 |
| `milvus-standalone` | `milvus` | 19530, 9091 | etcd, minio |

**环境变量传递**：
```yaml
# docker-compose.yml 中 rag-platform 服务的环境变量
ES_URL: "http://elasticsearch:9200"
MILVUS_HOST: "milvus-standalone"
MILVUS_PORT: "19530"
```

即使 ES/Milvus 容器未启动，后端也不会因这些环境变量存在而报错。`VectorStoreAdapterFactory` 在 `get_adapter("elasticsearch")` 时才检查连接可用性，未配置时抛出 `ConfigurationError`。

---

## 4. 测试策略

### 4.1 集成测试

| # | 测试对象 | 测试内容 | 验证点 |
|---|---------|---------|--------|
| IT-10.1 | ES 向量搜索 | 上传 20 个文档到 ES KB → 向量查询 "儿童运动能力发展" | 返回结果按 cosine 分数降序，top-5 语义相关，score ∈ [-1,1] |
| IT-10.2 | ES BM25 搜索 | 上传 20 个文档到 ES KB → match query "前庭觉" | 返回结果含 keyword 匹配的分块，无嵌入字段依赖 |
| IT-10.3 | ES 混合搜索 | 并行 knn + match → RRF(k=60) 融合 | 融合结果同时含语义相关和关键词匹配的结果，融合后分数在 RRF 范围内 |
| IT-10.4 | Milvus 向量搜索 | 上传 20 个文档到 Milvus KB → 向量查询 | 返回结果按 cosine 距离排序（越小越相关），符合 Milvus 输出格式 |
| IT-10.5 | Milvus + BM25 联合 | Milvus KB 上传文档 → 验证 BM25 独立索引可用 → BM25 查询 | BM25 search 返回合理结果，返回的 chunk_id 在 Milvus Collection 中存在 |
| IT-10.6 | ACL 三后端一致性 | 同一 KB（含 inherit + restricted 文档），admin/editor/空角色 → 分别三后端查询 | 相同角色下三后端返回的 doc_id 集合完全一致 |
| IT-10.7 | Chroma → ES 迁移 | 100 文档 KB Chroma→ES 迁移 → 验证完整性 | ES index 分块数 == kb_chunks 记录数，迁移后搜索正常 |
| IT-10.8 | ES → Milvus 迁移 | 同上 ES→Milvus → 随机抽样验证 | Milvus Collection 分块数 == kb_chunks 记录数，迁移后搜索正常 |
| IT-10.9 | 迁移回滚 | Mock ES 写入第 50/100 文档时抛出异常 | KB status 恢复 ready, vector_backend 保持原值, 源数据完好, task status=failed |
| IT-10.10 | Docker Compose profiles | 分别用 4 种 profile 组合启动 → 验证健康检查和 API 可用 | 对应容器运行/不运行，后端正确响应 |

### 4.2 性能测试

| # | 测试对象 | 测试内容 | 基准指标 |
|---|---------|---------|---------|
| PT-10.1 | 向量搜索延迟对比 | 1000 chunks KB → 相同查询 → Chroma/ES/Milvus 各跑 100 次 | P50 ≤ 100ms (Chroma), P50 ≤ 150ms (ES), P50 ≤ 200ms (Milvus) |
| PT-10.2 | BM25 搜索延迟对比 | 同上 → ES match vs 独立 BM25 | P50 ≤ 50ms (ES match), P50 ≤ 100ms (独立 BM25) |
| PT-10.3 | 混合搜索延迟对比 | 1000 chunks → 向量 + BM25 并行 → 融合 | P50 ≤ 300ms 全部后端 |
| PT-10.4 | 批量写入吞吐量 | 1000 chunks → embed_batch(32) + 批量写入 | ≥ 200 chunks/s (ES), ≥ 100 chunks/s (Milvus) |

### 4.3 关键测试场景（≥ 6）

1. **TS-10.1 — 端到端多后端平等能力**：同一文档集分别导入 Chroma/ES/Milvus 三个 KB → 同一查询 → 验证三后端返回结果语义一致（top-10 重叠率 ≥ 80%）。

2. **TS-10.2 — ACL 过滤器全矩阵测试**：
   - 知识库可见性 = `role_scoped`，`visible_roles = ["admin", "editor", "viewer"]`
   - 上传 10 篇文档：4 篇 inherit，3 篇 restricted to admin，2 篇 restricted to editor，1 篇 restricted to viewer
   - admin 角色搜索 → 三后端均返回 10/10
   - editor 角色搜索 → 三后端均返回 6/10（4 inherit + 2 editor-restricted）
   - viewer 角色搜索 → 三后端均返回 5/10（4 inherit + 1 viewer-restricted）
   - God Mode → 三后端均返回 10/10

3. **TS-10.3 — 大型迁移不丢数据**：10000 文档 KB → Chroma→ES 迁移 → ES→Milvus 迁移 → 每步验证目标存储 chunk 数 == kb_chunks 记录数 → 随机抽样 100 篇综合搜索对比。

4. **TS-10.4 — 迁移中断恢复**：Chroma→ES 迁移 → 写入 50/100 chunks 后强制 kill 容器 → 重启后检查：
   - KB status 是否为 `error`（而非 `rebuilding`）
   - KB vector_backend 是否仍为 `chroma`
   - 旧 Chroma Collection 数据是否完好
   - 是否可重新发起迁移

5. **TS-10.5 — BM25 索引生命周期全流程**：Chroma KB 创建 → 上传文档（增量更新） → 删除 1 篇文档（索引减少） → 修改分块策略（全量重建） → 迁移到 ES（索引删除） → 迁回 Chroma（索引重建） → 删除 KB（索引级联删除）。

6. **TS-10.6 — 三后端混合环境并发搜索**：同时运行 1 个 Chroma KB + 1 个 ES KB + 1 个 Milvus KB → 每个 KB 并发 20 次搜索 → 全部返回正确结果，无后端串扰。

7. **TS-10.7 — ES/Milvus 优雅降级**：Docker Compose 默认 mode（无 profile）→ 尝试创建 ES KB → 400 "ELASTICSEARCH_NOT_CONFIGURED"；已创建的 ES KB 查询时 → 500 "backend_unavailable"，前端显示友好错误提示而非空白页。

8. **TS-10.8 — 迁移幂等性与并发保护**：Chroma→ES 迁移完成后 → 再次请求 Chrome→ES → 400 "ALREADY_SAME_BACKEND"。两并发迁移请求 → 第一个成功，第二个 409 "REBUILD_IN_PROGRESS"。

---

## 5. 验收检查点

### 5.1 ElasticsearchAdapter

- [ ] ES 索引创建后 mapping 字段定义完整：`embedding (dense_vector, cosine)`, `content (text)`, `doc_acl (keyword)`
- [ ] `search()` knn query 正确注入 `num_candidates`，`query_vector` 维度匹配
- [ ] BM25 检索通过 `match` query 正确返回关键词匹配结果
- [ ] 混合检索：knn + match 并行 → RRF 融合结果正确性
- [ ] ACL filter 通过 `knn.filter` 或 `bool.filter` 正确注入
- [ ] ES 客户端连接失败时抛 `ConfigurationError` 而非 `ConnectionError`（区分未配置 vs 不可用）
- [ ] Index 命名 `rag_{tenant_id}_{kb_id}` 全小写
- [ ] `add_embeddings()` 支持批量写入（bulk API）
- [ ] `delete_by_filter()` 支持按 `doc_id` 批量删除
- [ ] `get_collection_info()` 返回分块数、存储大小

### 5.2 MilvusAdapter

- [ ] Collection 创建后 schema 字段定义完整：`chunk_id (VARCHAR PK)`, `embedding (FLOAT_VECTOR)`, `doc_acl (ARRAY)`
- [ ] 向量索引创建：IVF_FLAT，`metric_type: COSINE`，`nlist=128`
- [ ] `search()` 正确注入 `expr` 过滤条件
- [ ] `add_embeddings()` 支持批量 insert
- [ ] `delete_by_filter()` 支持按 `chunk_id` 或 `doc_id` 表达式删除
- [ ] Milvus 连接失败时抛 `ConfigurationError`
- [ ] Collection 命名 `rag_{tenant_id}_{kb_id}` 全小写，仅含字母/数字/下划线
- [ ] `get_collection_info()` 返回分块数

### 5.3 ACL 过滤器一致性

- [ ] 同一用户角色 + 同一 KB + 同一文档集 → Chroma/ES/Milvus 三后端返回的 `chunk_id` 列表完全一致
- [ ] ChromaACLFilterBuilder 输出 `$or` 语法正确，含 `{"doc_acl": {"$size": 0}}` inherit 兜底
- [ ] ESACLFilterBuilder 输出 `{"terms": {"doc_acl": roles}}` 语法正确，含 `must_not exists` 或空数组 inherit 兜底
- [ ] MilvusACLFilterBuilder 输出 `array_contains_any(doc_acl, [...]) or len(doc_acl) == 0 or doc_acl is null` 正确
- [ ] God Mode（user_roles=[] 或超管）下三 Builder 均返回空条件
- [ ] 知识库 visibility=public 时 ACL filter 不过滤任何文档
- [ ] 知识库 visibility=private 仅 owner 可见（通过 Repository 层 `tenant_id` + `created_by` 过滤，不经过 ACL builder）

### 5.4 BM25 索引维护

- [ ] Chroma/Milvus KB 创建时自动初始化 `storage/bm25/{tenant_id}/{kb_id}/` 目录及文件
- [ ] ES KB 创建时 `storage/bm25/` 下无对应目录
- [ ] 文档上传后 `add_chunks()` 增量更新索引，搜索结果包含新增文档的分块
- [ ] 文档删除后 `remove_chunks()` 搜索结果不再包含已删文档的分块
- [ ] 分块策略变更触发 `rebuild()` 全量重建，重建后搜索结果正确
- [ ] 单 KB 单写锁 (`asyncio.Lock`) 防止并发增量更新损坏
- [ ] 索引文件可在进程重启后正确恢复加载
- [ ] BM25 参数 k1=1.5, b=0.75 固定，不接受用户配置
- [ ] Chroma→ES 迁移完成后 BM25 索引目录已删除
- [ ] ES→Chroma 迁移完成后 BM25 索引已从 kb_chunks 全量重建

### 5.5 后端迁移

- [ ] Chroma → ES 迁移 6 步流程全部执行，最终 `vector_backend=elasticsearch`，ES 分块数正确
- [ ] ES → Milvus 迁移同上，最终 `vector_backend=milvus`
- [ ] Milvus → Chroma 迁移同上，最终 `vector_backend=chroma`
- [ ] 目标后端 == 源后端 → 400 "ALREADY_SAME_BACKEND"
- [ ] 迁移中 KB `status=rebuilding`，旧索引只读可用
- [ ] 迁移失败 → 目标存储已清理，源数据完好，KB status 恢复 "ready"
- [ ] 迁移进度通过 SSE 实时推送（progress 含 progress_pct + status_message）
- [ ] 迁移完成后随机抽样 20 篇文档语义搜索验证（top-10 重叠率 ≥ 80%）
- [ ] `migrate_backend` API 返回 `MigrationStatus` 含 `source_backend` + `target_backend` + `estimated_minutes` + `rebuild_task_id`
- [ ] 并发迁移互斥：同一 KB 同时两个迁移请求 → 第二个返回 409 "REBUILD_IN_PROGRESS"

### 5.6 Docker Compose profiles

- [ ] `docker compose up -d`（无 profile）→ ES/Milvus 容器不启动，后端无报错
- [ ] `docker compose --profile elasticsearch up -d` → ES 容器健康检查通过（green/yellow），API 路径 `/api/v1/knowledge-bases` 可选 `elasticsearch` 后端
- [ ] `docker compose --profile milvus up -d` → etcd/MinIO/Milvus 全部健康，API 可选 `milvus` 后端
- [ ] `docker compose --profile elasticsearch --profile milvus up -d` → 三后端全部可用
- [ ] ES/Milvus 容器停止后，后端对已创建的 ES/Milvus KB 搜索返回 503 "backend_unavailable" 而非 500
- [ ] `docker-compose.dev.yml` 覆盖开发环境正常工作，含源码热重载
- [ ] `.env` 文件中 ES_URL/MILVUS_HOST/MILVUS_PORT 有兜底默认值（对应容器名称）

### 5.7 非功能需求

- [ ] 三后端向量搜索响应 P50 延迟 ≤ 各自基准（Chroma ≤ 100ms, ES ≤ 150ms, Milvus ≤ 200ms）— 1000 chunks 规模
- [ ] 混合搜索 P50 延迟 ≤ 300ms — 1000 chunks 规模
- [ ] ES 批量写入吞吐量 ≥ 200 chunks/s
- [ ] Milvus 批量写入吞吐量 ≥ 100 chunks/s
- [ ] 10000 chunks 迁移 Chroma→ES ≤ 30 分钟
- [ ] ACL 过滤不显著增加搜索延迟（增加 ≤ 10%）
- [ ] ES/Milvus 未配置时所有相关 API 优雅降级（返回 `not_configured`），不阻塞 Chroma 功能
- [ ] ES 索引和 Milvus Collection 的命名规则严格遵循规范（全小写、rag_ 前缀、含 tenant_id）
- [ ] 三后端搜索接口统一：`VectorStoreAdapter.search()` 的输入输出格式一致，上层调用无需区分后端

---

## 附录：验证文件清单

| 文件路径 | 类型 | 说明 |
|---------|------|------|
| `core/knowledge_base/vector_store/elasticsearch.py` | Phase 2 实现 | ElasticsearchAdapter，Phase 10 验证 |
| `core/knowledge_base/vector_store/milvus.py` | Phase 2 实现 | MilvusAdapter，Phase 10 验证 |
| `core/knowledge_base/vector_store/factory.py` | Phase 2 实现 | VectorStoreAdapterFactory，Phase 10 验证降级逻辑 |
| `core/knowledge_base/acl_filter.py` | Phase 2 实现 | ACLFilterBuilder + 三个后端实现，Phase 10 验证一致性 |
| `core/knowledge_base/bm25_index.py` | Phase 2 实现 | BM25IndexManager，Phase 10 验证生命周期 |
| `service/knowledge/migration_service.py` | Phase 2 实现 | MigrationService，Phase 10 验证迁移流程+回滚 |
| `docker-compose.yml` | Phase 0 实现 | Docker Compose profiles 配置，Phase 10 验证启动/停止 |

Phase 10 的验证结果若发现 Phase 2 代码缺陷，应直接在 Phase 2 对应的源文件中修复，而非在 Phase 10 中打补丁。
