# 向量后端扩展策略

> **定位**：定义 Chroma / Elasticsearch / Milvus 三种向量后端的统一适配架构、分阶段实施计划和迁移流程。所有后端都必须支持，但可以分阶段交付。
> **关联需求**：[03-knowledge-base.md](../../requirements/03-knowledge-base.md) §1.5、[core-objectives.md](../../core-objectives.md) §2
> **创建日期**：2026-05-14

---

## 1. 设计目标

- **统一接口**：业务代码（检索节点、分块引擎、Embedding 引擎）不感知具体后端，通过抽象层切换
- **全部支持**：Chroma / ES / Milvus 三种后端均需实现，不做阉割
- **分阶段交付**：一期实现一种，后续扩展，但架构从第一天就为三种后端设计
- **可迁移**：知识库创建后支持切换后端，自动触发全量重建

---

## 2. 统一适配架构

### 2.1 抽象层设计

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class SearchQuery:
    """统一的检索查询"""
    embedding: list[float] | None = None   # 向量检索时提供
    text: str | None = None                 # BM25 检索时提供
    top_k: int = 10
    filters: dict[str, Any] | None = None   # ACL 过滤条件（已由 ACLFilterBuilder 构建）
    score_threshold: float = 0.0


@dataclass
class SearchResult:
    """统一的检索结果"""
    chunk_id: str
    content: str
    score: float
    metadata: dict[str, Any]
    doc_id: str
    kb_id: str


class VectorStoreAdapter(ABC):
    """向量存储后端统一接口"""

    @abstractmethod
    async def create_collection(self, kb_id: str, config: dict) -> None:
        """创建集合/索引"""
        ...

    @abstractmethod
    async def delete_collection(self, kb_id: str) -> None:
        """删除集合/索引"""
        ...

    @abstractmethod
    async def upsert(self, kb_id: str, chunks: list[dict]) -> None:
        """写入/更新分块向量"""
        ...

    @abstractmethod
    async def delete_by_doc(self, kb_id: str, doc_id: str) -> None:
        """删除某文档的所有分块"""
        ...

    @abstractmethod
    async def search(self, kb_id: str, query: SearchQuery) -> list[SearchResult]:
        """统一检索入口"""
        ...

    @abstractmethod
    async def count(self, kb_id: str) -> int:
        """返回分块数量"""
        ...

    @abstractmethod
    async def health_check(self) -> bool:
        """后端健康检查"""
        ...


class BM25IndexAdapter(ABC):
    """BM25 关键词索引统一接口（仅 Chroma/Milvus 需要，ES 内置）"""

    @abstractmethod
    async def create_index(self, kb_id: str) -> None:
        """创建 BM25 索引"""
        ...

    @abstractmethod
    async def add_documents(self, kb_id: str, chunks: list[dict]) -> None:
        """添加文档到索引"""
        ...

    @abstractmethod
    async def search(self, kb_id: str, query: str, top_k: int,
                     filters: dict | None = None) -> list[SearchResult]:
        """BM25 检索"""
        ...

    @abstractmethod
    async def delete_by_doc(self, kb_id: str, doc_id: str) -> None:
        """删除某文档的所有索引条目"""
        ...

    @abstractmethod
    async def delete_index(self, kb_id: str) -> None:
        """删除整个索引"""
        ...
```

### 2.2 ACL 过滤器统一接口

```python
class ACLFilterBuilder(ABC):
    """根据用户角色构建向量存储的 ACL 过滤条件"""

    @abstractmethod
    def build_filter(self, user_roles: list[str]) -> dict:
        """将用户角色列表转换为当前后端的过滤条件
        - Chroma: 返回 where 条件 dict
        - Elasticsearch: 返回 filter clause list
        - Milvus: 返回 expr 字符串
        """
        ...
```

### 2.3 工厂模式

```python
class VectorStoreFactory:
    """根据知识库的向量后端配置创建对应的适配器实例"""

    _registry: dict[str, type[VectorStoreAdapter]] = {}

    @classmethod
    def register(cls, backend: str, adapter_class: type[VectorStoreAdapter]):
        cls._registry[backend] = adapter_class

    @classmethod
    def create(cls, backend: str, config: dict) -> VectorStoreAdapter:
        if backend not in cls._registry:
            raise ValueError(f"不支持的向量后端: {backend}")
        return cls._registry[backend](**config)


class BM25IndexFactory:
    """BM25 索引工厂（ES 后端返回 NoopBM25Adapter）"""

    @classmethod
    def create(cls, backend: str, config: dict) -> BM25IndexAdapter:
        if backend == "es":
            return NoopBM25Adapter()  # ES 内置 BM25，不需要独立索引
        # Chroma/Milvus 返回独立 BM25 索引实现
        ...
```

---

## 3. 三种后端实现对照

### 3.1 向量存储实现

| 能力 | Chroma | Elasticsearch | Milvus |
|------|--------|---------------|--------|
| **Collection/Index** | Collection | Index | Collection |
| **命名约定** | `{tenant_id}_{kb_id}` | `rag_{tenant_id}_{kb_id}` | `rag_{tenant_id}_{kb_id}` |
| **向量字段** | `embedding` | `embedding` | `vector` |
| **标量字段** | metadata dict | fields | scalar fields |
| **距离度量** | cosine / l2 / ip | cosine / dot_product / l2 | cosine / L2 / IP |
| **ACL 过滤语法** | `where: {"$and": [...]}` | `filter: [{term: ...}]` | `expr: "role in [...]"` |
| **批量写入** | `collection.add()` | `bulk()` API | `collection.insert()` |
| **检索 API** | `collection.query()` | `search()` + `knn` | `collection.search()` |
| **依赖库** | `chromadb` | `elasticsearch[async]` | `pymilvus` |
| **Docker 服务** | 无（本地持久化） | Elasticsearch 8.15+ | Milvus 2.3+ + etcd + minio |

### 3.2 BM25 索引实现

| 能力 | Chroma | Elasticsearch | Milvus |
|------|--------|---------------|--------|
| **需要独立 BM25** | 是 | 否（内置） | 是 |
| **BM25 实现** | `rank_bm25` 库 + pickle 持久化 | ES `match` 查询 | `rank_bm25` 库 + pickle 持久化 |
| **存储位置** | `storage/bm25/{kb_id}/` | — | `storage/bm25/{kb_id}/` |
| **更新策略** | 增量（文档增删时） | — | 增量（文档增删时） |

### 3.3 ACL 过滤器实现

```python
class ChromaACLFilterBuilder(ACLFilterBuilder):
    def build_filter(self, user_roles: list[str]) -> dict:
        if not user_roles:
            return {}
        return {"doc_acl": {"$in": user_roles}}


class ESACLFilterBuilder(ACLFilterBuilder):
    def build_filter(self, user_roles: list[str]) -> dict:
        if not user_roles:
            return {}
        return {"terms": {"doc_acl": user_roles}}


class MilvusACLFilterBuilder(ACLFilterBuilder):
    def build_filter(self, user_roles: list[str]) -> str:
        if not user_roles:
            return ""
        roles_str = ", ".join(f'"{r}"' for r in user_roles)
        return f'doc_acl in [{roles_str}]'
```

---

## 4. 分阶段实施计划

### Phase 2（一期）：Chroma 适配器

**范围**：仅实现 Chroma 后端，但架构从第一天支持三种后端。

| 交付物 | 说明 |
|--------|------|
| `VectorStoreAdapter` 抽象接口 | 定义统一接口，业务代码仅依赖此接口 |
| `BM25IndexAdapter` 抽象接口 | 定义 BM25 索引接口 |
| `ACLFilterBuilder` 抽象接口 | 定义 ACL 过滤器接口 |
| `ChromaVectorStoreAdapter` | Chroma 向量存储实现 |
| `ChromaBM25IndexAdapter` | Chroma 的独立 BM25 索引实现 |
| `ChromaACLFilterBuilder` | Chroma ACL 过滤器实现 |
| `VectorStoreFactory` | 工厂模式，注册 Chroma |
| `BM25IndexFactory` | 工厂模式，注册 Chroma |

**验证标准**：
- [ ] 知识库创建 → Chroma Collection 成功生成
- [ ] 文档上传 → 分块 → 向量化 → 写入 Chroma
- [ ] 向量检索 + BM25 检索 + 混合检索正常工作
- [ ] ACL 过滤生效（不同角色看到不同文档子集）
- [ ] 分块策略变更 → 全量重建 → Chroma Collection 更新

### Phase 10（二期）：ES + Milvus 适配器

**范围**：实现 ES 和 Milvus 适配器，验证迁移流程。

| 交付物 | 说明 |
|--------|------|
| `ESVectorStoreAdapter` | Elasticsearch 向量存储实现 |
| `ESACLFilterBuilder` | Elasticsearch ACL 过滤器实现 |
| `NoopBM25Adapter` | ES 不需要独立 BM25 的空实现 |
| `MilvusVectorStoreAdapter` | Milvus 向量存储实现 |
| `MilvusBM25IndexAdapter` | Milvus 的独立 BM25 索引实现 |
| `MilvusACLFilterBuilder` | Milvus ACL 过滤器实现 |
| 后端迁移流程 | Chroma → ES / Chroma → Milvus / ES ↔ Milvus |
| Docker profiles | ES 和 Milvus 的 docker-compose profiles |

**验证标准**：
- [ ] ES 后端：知识库创建 → ES Index 成功生成 → 检索正常
- [ ] ES 后端：BM25 检索自动使用 ES 内置 `match` 查询（不走独立索引）
- [ ] Milvus 后端：知识库创建 → Milvus Collection 成功生成 → 检索正常
- [ ] Milvus 后端：独立 BM25 索引正常工作
- [ ] 迁移：Chroma → ES 迁移完成后可正常检索
- [ ] 迁移：Chroma → Milvus 迁移完成后可正常检索
- [ ] 迁移失败：回滚到旧后端，知识库状态恢复 ready
- [ ] ACL 一致性：同一用户同一知识库，三种后端返回相同文档子集
- [ ] Docker：`docker compose --profile elasticsearch up` 正常启动 ES
- [ ] Docker：`docker compose --profile milvus up` 正常启动 Milvus

---

## 5. 后端迁移流程

### 5.1 迁移触发

用户在知识库设置页选择新后端 → 系统显示预计迁移时间（基于文档量）→ 确认后开始。

### 5.2 迁移步骤

```
1. 知识库状态 → `migrating`
2. 创建新后端的 Collection/Index
3. 从旧后端读取所有分块（含向量、metadata）
4. 写入新后端
5. 验证：新后端分块数 == 旧后端分块数
6. 切换知识库的 vector_backend 配置
7. 清理旧后端数据
8. 知识库状态 → `ready`
```

### 5.3 迁移约束

| 约束 | 说明 |
|------|------|
| **可读不可写** | 迁移期间知识库可读（用旧索引），不可上传文档或修改分块策略 |
| **异步执行** | 迁移是后台异步任务，前端 SSE 推送进度 |
| **失败回滚** | 迁移失败时保留旧数据，知识库状态恢复 `ready`，vector_backend 不变 |
| **快照失效** | 引用旧后端路径的知识库快照自动标记为 `invalid` |

### 5.4 迁移路径矩阵

| 源 → 目标 | 复杂度 | 需要迁移的内容 |
|-----------|--------|---------------|
| Chroma → ES | 中 | 向量 + metadata → ES documents |
| Chroma → Milvus | 中 | 向量 + metadata → Milvus entities |
| ES → Chroma | 中 | ES documents → 向量 + metadata |
| ES → Milvus | 中 | ES documents → Milvus entities |
| Milvus → Chroma | 中 | Milvus entities → 向量 + metadata |
| Milvus → ES | 中 | Milvus entities → ES documents |

所有迁移路径的复杂度相同——都是"从源后端读取全部分块 → 写入目标后端"。向量数据本身不变，只是存储格式不同。

---

## 6. BM25 独立索引设计（Chroma/Milvus 适用）

### 6.1 存储结构

```
storage/bm25/{kb_id}/
├── index.pkl          # BM25 模型 pickle 文件
├── chunks.jsonl       # chunk_id → content 映射（用于检索后回查内容）
└── doc_map.json       # doc_id → [chunk_ids] 映射（用于删除文档时清理）
```

### 6.2 更新策略

| 事件 | BM25 索引操作 |
|------|-------------|
| 文档上传 + 分块 | 增量添加新分块到索引 |
| 文档删除 | 从索引中移除该文档的所有分块 |
| 分块策略变更 | 全量重建索引 |
| Embedding 变更 | BM25 不受影响（BM25 不依赖向量） |
| 后端迁移 | 目标后端如果是 ES 则不需要 BM25；如果是 Chroma/Milvus 则保留 BM25 索引 |

### 6.3 BM25 参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `k1` | 1.5 | 词频饱和度 |
| `b` | 0.75 | 文档长度归一化 |
| `field_weights` | `{"title": 2.0, "body": 1.0}` | 字段权重（如有标题） |

---

## 7. Docker 部署配置

### 7.1 核心服务（始终启动）

```yaml
services:
  rag-platform:
    build: ./backend
    ports: ["51002:51002"]
    depends_on:
      mysql: { condition: service_healthy }
      redis: { condition: service_healthy }

  mysql:
    image: mysql:5.7
    # ...

  redis:
    image: redis:7.0-alpine
    # ...
```

### 7.2 ES 服务（按需启动）

```yaml
  elasticsearch:
    image: docker.elastic.co/elasticsearch/elasticsearch:8.15.0
    profiles: ["elasticsearch"]
    environment:
      - discovery.type=single-node
      - xpack.security.enabled=false
    ports: ["9200:9200"]
    volumes:
      - rag-platform-es:/usr/share/elasticsearch/data
```

启动命令：`docker compose --profile elasticsearch up -d`

### 7.3 Milvus 服务（按需启动）

```yaml
  etcd:
    image: quay.io/coreos/etcd:v3.5.5
    profiles: ["milvus"]
    # ...

  minio:
    image: minio/minio
    profiles: ["milvus"]
    # ...

  milvus:
    image: milvusdb/milvus:v2.3.4
    profiles: ["milvus"]
    depends_on: [etcd, minio]
    ports: ["19530:19530"]
    volumes:
      - rag-platform-milvus:/var/lib/milvus
```

启动命令：`docker compose --profile milvus up -d`

### 7.4 同时启动 ES + Milvus

```bash
docker compose --profile elasticsearch --profile milvus up -d
```

---

## 8. 配置层级

| 配置项 | 层级 | 说明 |
|--------|------|------|
| 向量后端类型 | L2（知识库配置） | 创建时选择，后续可迁移 |
| Chroma 持久化路径 | L0（平台默认） | `storage/chroma/` |
| ES 连接地址 | L0（`.env`） | `ES_URL=http://localhost:9200` |
| Milvus 连接地址 | L0（`.env`） | `MILVUS_HOST=localhost`、`MILVUS_PORT=19530` |
| BM25 索引路径 | L0（平台默认） | `storage/bm25/` |
| 相似度度量 | L2（知识库配置） | cosine / euclidean / dot_product |
| 向量维度 | L2（知识库配置） | 模型默认 / 256 / 512 / 768 / 1024 |

---

## 9. 错误码

| error_code | HTTP | 说明 |
|------------|------|------|
| `KB_VECTOR_BACKEND_UNAVAILABLE` | 503 | 向量后端不可用（ES/Milvus 未启动） |
| `KB_MIGRATION_IN_PROGRESS` | 409 | 迁移进行中，不接受写操作 |
| `KB_MIGRATION_FAILED` | 500 | 迁移失败，已回滚 |
| `KB_SNAPSHOT_INVALID` | 400 | 快照引用的后端已变更，快照失效 |
| `KB_BM25_INDEX_ERROR` | 500 | BM25 索引操作失败 |

---

## 10. 与其他模块的接口

| 消费方 | 接口 |
|--------|------|
| 检索节点（Phase 3） | 通过 `VectorStoreFactory.create(backend)` 获取适配器，调用 `search()` |
| BM25 检索节点（Phase 3） | 通过 `BM25IndexFactory.create(backend)` 获取适配器，调用 `search()` |
| PipelineCompiler（Phase 3） | 域分发时根据知识库 `vector_backend` 选择适配器 |
| ACL 过滤（Phase 1） | 通过 `ACLFilterBuilder` 子类构建过滤条件，注入检索查询 |
| 知识库管理（Phase 2） | 创建/删除/迁移知识库时调用适配器的 `create_collection` / `delete_collection` |
| 评估系统（Phase 7） | 知识库快照记录 `vector_backend_type`，恢复时使用对应适配器 |
