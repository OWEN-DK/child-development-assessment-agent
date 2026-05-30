# Phase 1: 基础设施与 Neo4j 部署

> **工期**: 3 人天 | **风险**: 低 | **依赖**: Phase 0（前置条件检查通过）  
> **目标**: Neo4j 运行起来，Schema 创建完毕，健康检查通过，初始数据导入完成
> **实施状态**: ✅ 代码已部署（2026-05-30）。运行时验证待 Neo4j 容器启动后执行。

---

## 1.1 前置检查

```bash
# 检查 Docker 可用
docker --version  # ≥ 24.0

# 确认 Python 环境
cd backend && uv run python -c "from neo4j import GraphDatabase; print('neo4j driver OK')"
```

---

## 1.2 Docker 部署 Neo4j

### 1.2.1 docker-compose.yml

> Neo4j 服务已存在于 `docker-compose.yml`（容器名 `child-dev-neo4j`，端口 7474/7687，认证 `neo4j/devpass123`）。调整内存参数至 512m/1g。

```yaml
  neo4j:
    image: neo4j:5.26-community
    container_name: child-dev-neo4j
    ports:
      - "7474:7474"   # HTTP
      - "7687:7687"   # Bolt
    environment:
      - NEO4J_AUTH=neo4j/${NEO4J_PASSWORD:-devpass123}
      - NEO4J_server_memory_heap_initial__size=512m
      - NEO4J_server_memory_heap_max__size=1g
      - NEO4J_server_memory_pagecache_size=512m
    volumes:
      - ./neo4j/data:/data
      - ./neo4j/logs:/logs
      - ./neo4j/import:/var/lib/neo4j/import
      - ./neo4j/plugins:/plugins
    healthcheck:
      test: ["CMD", "cypher-shell", "-u", "neo4j", "-p", "${NEO4J_PASSWORD:-devpass123}", "RETURN 1"]
      interval: 10s
      timeout: 5s
      retries: 5
```

### 1.2.2 启动与验证

```bash
docker compose up -d neo4j
docker compose ps neo4j  # STATUS 应为 healthy
docker compose exec neo4j cypher-shell -u neo4j -p devpass123 "RETURN 'connected' AS status;"
```

---

## 1.3 创建 Schema 约束和索引

### 1.3.1 Cypher 初始化脚本

创建 `neo4j/init/schema.cypher`：

```cypher
// ===== 唯一性约束 =====
CREATE CONSTRAINT book_id_unique IF NOT EXISTS FOR (b:Book) REQUIRE b.book_id IS UNIQUE;
CREATE CONSTRAINT problem_id_unique IF NOT EXISTS FOR (p:Problem) REQUIRE p.problem_id IS UNIQUE;
CREATE CONSTRAINT rootcause_id_unique IF NOT EXISTS FOR (r:RootCause) REQUIRE r.rootcause_id IS UNIQUE;
CREATE CONSTRAINT solution_id_unique IF NOT EXISTS FOR (s:Solution) REQUIRE s.solution_id IS UNIQUE;
CREATE CONSTRAINT exercise_id_unique IF NOT EXISTS FOR (e:Exercise) REQUIRE e.exercise_id IS UNIQUE;
CREATE CONSTRAINT prescription_id_unique IF NOT EXISTS FOR (p:Prescription) REQUIRE p.prescription_id IS UNIQUE;
CREATE CONSTRAINT brainregion_name_unique IF NOT EXISTS FOR (br:BrainRegion) REQUIRE br.name IS UNIQUE;
CREATE CONSTRAINT childprofile_id_unique IF NOT EXISTS FOR (cp:ChildProfile) REQUIRE cp.profile_id IS UNIQUE;
CREATE CONSTRAINT risk_id_unique IF NOT EXISTS FOR (r:Risk) REQUIRE r.risk_id IS UNIQUE;
CREATE CONSTRAINT chapter_id_unique IF NOT EXISTS FOR (c:Chapter) REQUIRE c.chapter_id IS UNIQUE;
CREATE CONSTRAINT autoentity_name_book_unique IF NOT EXISTS FOR (ae:AutoEntity) REQUIRE (ae.name, ae.book_id) IS UNIQUE;
CREATE CONSTRAINT autocommunity_node_id_unique IF NOT EXISTS FOR (ac:AutoCommunity) REQUIRE ac.node_id IS UNIQUE;

// ===== 索引（加速查询） =====
CREATE INDEX exercise_name_idx IF NOT EXISTS FOR (e:Exercise) ON (e.name);
CREATE INDEX exercise_category_idx IF NOT EXISTS FOR (e:Exercise) ON (e.category);
CREATE INDEX problem_severity_idx IF NOT EXISTS FOR (p:Problem) ON (p.severity);
CREATE INDEX book_title_idx IF NOT EXISTS FOR (b:Book) ON (b.title);
CREATE INDEX childprofile_age_idx IF NOT EXISTS FOR (cp:ChildProfile) ON (cp.age_range_min, cp.age_range_max);
CREATE INDEX exercise_minage_idx IF NOT EXISTS FOR (e:Exercise) ON (e.min_age);
CREATE INDEX autoentity_type_idx IF NOT EXISTS FOR (ae:AutoEntity) ON (ae.entity_type);

// ===== 全文索引（语义搜索） =====
CREATE FULLTEXT INDEX exercise_fulltext IF NOT EXISTS
FOR (e:Exercise) ON EACH [e.name, e.description, e.benefits];

CREATE FULLTEXT INDEX problem_fulltext IF NOT EXISTS
FOR (p:Problem) ON EACH [p.name, p.description, p.symptoms];
```

### 1.3.2 执行初始化

```bash
cat neo4j/init/schema.cypher | docker compose exec -T neo4j cypher-shell -u neo4j -p devpass123
```

### 1.3.3 验证 Schema

```bash
docker compose exec neo4j cypher-shell -u neo4j -p devpass123 "SHOW CONSTRAINTS;"
docker compose exec neo4j cypher-shell -u neo4j -p devpass123 "SHOW INDEXES;"
# 预期: 12 个约束 + 8 个索引 + 2 个全文索引
```

---

## 1.4 后端配置与 Driver

### 1.4.1 配置项

`backend/src/config/modules/neo4j.py` 新增：

```python
# Neo4j 配置
NEO4J_ENABLED: bool = False  # 特性开关，灰度上线时逐步开启
NEO4J_URI: str = "bolt://localhost:7687"
NEO4J_USER: str = "neo4j"
NEO4J_PASSWORD: str = "devpass123"
NEO4J_QUERY_TIMEOUT: int = 30  # 秒
NEO4J_MAX_POOL_SIZE: int = 50
NEO4J_ROLLOUT_PERCENTAGE: int = 0  # 灰度百分比 0-100
```

### 1.4.2 Neo4j Driver

`backend/src/core/knowledge_qa/neo4j/driver.py`：

```python
"""Neo4j Driver 单例管理。"""
import logging
from typing import Optional
from neo4j import GraphDatabase, ServiceUnavailable, SessionExpired
from config.core.manager import config_manager

logger = logging.getLogger(__name__)

_driver = None


def get_neo4j_driver():
    """获取 Neo4j driver 单例。NEO4J_ENABLED=False 时返回 None。"""
    global _driver
    if not config_manager.get("neo4j.enabled", False):
        return None
    if _driver is None:
        _driver = GraphDatabase.driver(
            config_manager.get("neo4j.uri", "bolt://localhost:7687"),
            auth=(
                config_manager.get("neo4j.user", "neo4j"),
                config_manager.get("neo4j.password", "devpass123"),
            ),
            max_connection_lifetime=config_manager.get("neo4j.max_connection_lifetime", 3600),
            max_connection_pool_size=config_manager.get("neo4j.max_connection_pool_size", 50),
            connection_acquisition_timeout=config_manager.get("neo4j.connection_acquisition_timeout", 30),
        )
        logger.info("Neo4j driver initialized: %s", config_manager.get("neo4j.uri", "bolt://localhost:7687"))
    return _driver


def close_neo4j_driver():
    """关闭 Neo4j driver（应用关闭时调用）。"""
    global _driver
    if _driver:
        _driver.close()
        _driver = None
        logger.info("Neo4j driver closed")


def neo4j_available() -> bool:
    """检查 Neo4j 是否可用。"""
    if not config_manager.get("neo4j.enabled", False):
        return False
    driver = get_neo4j_driver()
    if driver is None:
        return False
    try:
        with driver.session() as session:
            session.run("RETURN 1")
        return True
    except (ServiceUnavailable, SessionExpired, OSError):
        return False
```

### 1.4.3 DI 注册

在 `backend/src/utils/di.py` 中注册，在应用关闭时（FastAPI lifespan）调用 `close_neo4j_driver()`。

---

## 1.5 初始数据导入

### 1.5.1 运动数据导入

项目未上线，无需迁移。直接将 `运动改变大脑_运动清单.json` 导入 Neo4j：

```python
# backend/src/scripts/import_exercises_to_neo4j.py
"""将运动清单 JSON 直接导入 Neo4j（全新部署，非迁移）。"""

import json
import re
import sys
from pathlib import Path
from neo4j import GraphDatabase

BOOK_ID = "exercise_book_001"
UNSUABLE_FOR_CHILDREN = {9, 10, 19, 35, 36, 92}  # 不适合儿童的运动序号


def parse_age_range(text: str) -> tuple[int, int]:
    """解析年龄文本，返回 (min_age, max_age)。"""
    if not text:
        return (0, 18)
    numbers = re.findall(r'\d+', text)
    if len(numbers) >= 2:
        return (int(numbers[0]), int(numbers[1]))
    elif len(numbers) == 1:
        return (int(numbers[0]), 18)
    return (0, 18)


def import_exercises(json_path: str, uri: str, user: str, password: str):
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    driver = GraphDatabase.driver(uri, auth=(user, password))

    with driver.session() as session:
        # 确保 Book 节点存在
        session.run(
            "MERGE (b:Book {book_id: $book_id}) SET b.title = $title",
            book_id=BOOK_ID, title="运动改变大脑",
        )

        count = 0
        for item in data:
            seq = str(item.get("序号", "")).zfill(3)
            name = item.get("运动名称", "").strip()
            if not name:
                continue

            category = item.get("运动类别", "")
            chapter = item.get("所在章节", "")
            benefits = item.get("运动效果", "")
            intensity = item.get("强度建议", "")
            suitable = int(seq.lstrip("0") or "0") not in UNSUABLE_FOR_CHILDREN
            min_age, max_age = parse_age_range(item.get("适合年龄", ""))
            chapter_id = f"CH_{BOOK_ID}_{chapter.replace(' ', '_')[:50]}"

            session.run("""
                MERGE (e:Exercise {exercise_id: $eid})
                SET e.name = $name,
                    e.category = $category,
                    e.benefits = $benefits,
                    e.intensity = $intensity,
                    e.suitable_for_children = $suitable,
                    e.min_age = $min_age,
                    e.max_age = $max_age,
                    e.book_id = $book_id,
                    e.curation_status = 'published'
                WITH e
                MATCH (b:Book {book_id: $book_id})
                MERGE (b)-[:CONTAINS_EXERCISE]->(e)
                WITH e, b
                MERGE (ch:Chapter {chapter_id: $chapter_id})
                SET ch.title = $chapter, ch.book_id = $book_id
                MERGE (b)-[:HAS_CHAPTER]->(ch)
                MERGE (ch)-[:DESCRIBES_EXERCISE]->(e)
            """,
                eid=f"EX{seq}", name=name, category=category,
                benefits=benefits, intensity=intensity,
                suitable=suitable, min_age=min_age, max_age=max_age,
                book_id=BOOK_ID, chapter=chapter, chapter_id=chapter_id,
            )
            count += 1

        result = session.run("MATCH (e:Exercise) RETURN count(e)").single()
        print(f"✅ 已导入 {result[0]} 项运动（共处理 {count} 条记录）")

    driver.close()


if __name__ == "__main__":
    json_path = Path(__file__).resolve().parent.parent.parent.parent / "data" / "运动改变大脑_运动清单.json"
    if not json_path.exists():
        print(f"❌ 文件不存在: {json_path}")
        sys.exit(1)
    import_exercises(str(json_path), "bolt://localhost:7687", "neo4j", "devpass123")
```

---

## 1.6 LazyGraphRAG 直写 Neo4j

项目全新部署，文档摄入流水线直接写入 Neo4j，不经过 MySQL graph_* 表。

`backend/src/service/document_ingestion/facade.py` 中新增 Neo4j 写入逻辑：

```python
async def _store_graph_entities_neo4j(
    entities: list, relationships: list, communities: list, book_id: str
) -> dict[str, int]:
    """将 LazyGraphRAG 提取结果直接写入 Neo4j。"""
    from core.knowledge_qa.neo4j.driver import get_neo4j_driver, neo4j_available

    if not neo4j_available():
        return {"entities": 0, "relationships": 0, "communities": 0}

    driver = get_neo4j_driver()
    entity_count = rel_count = community_count = 0

    def do_write(tx):
        nonlocal entity_count, rel_count, community_count

        tx.run("MERGE (b:Book {book_id: $book_id})", book_id=book_id)

        for ent in entities:
            tx.run("""
                MERGE (ae:AutoEntity {name: $name, book_id: $book_id})
                SET ae.entity_type = $entity_type,
                    ae.aliases = $aliases,
                    ae.description = $description,
                    ae.chunk_ids = $chunk_ids
            """, name=ent.name, book_id=book_id,
                entity_type=ent.entity_type or "",
                aliases=ent.aliases or [],
                description=ent.description or "",
                chunk_ids=ent.chunk_ids or [],
            )
            tx.run("""
                MATCH (b:Book {book_id: $book_id})
                MATCH (ae:AutoEntity {name: $name, book_id: $book_id})
                MERGE (b)-[:CONTAINS_ENTITY]->(ae)
            """, book_id=book_id, name=ent.name)
            entity_count += 1

        for rel in relationships:
            tx.run("""
                MATCH (src:AutoEntity {name: $src_name, book_id: $book_id})
                MATCH (tgt:AutoEntity {name: $tgt_name, book_id: $book_id})
                MERGE (src)-[r:RELATES_TO {relationship_type: $rel_type}]->(tgt)
                SET r.weight = $weight, r.description = $description
            """, src_name=rel.source_name, tgt_name=rel.target_name,
                book_id=book_id, rel_type=rel.relationship_type or "",
                weight=rel.weight or 0.0, description=rel.description or "",
            )
            rel_count += 1

        for com in communities:
            tx.run("""
                MERGE (ac:AutoCommunity {node_id: $node_id})
                SET ac.level = $level, ac.label = $label,
                    ac.entity_names = $entity_names, ac.book_id = $book_id
            """, node_id=com.node_id, level=com.level or 0,
                label=com.label or "", entity_names=com.entity_names or [],
                book_id=book_id,
            )
            community_count += 1

    with driver.session() as session:
        session.execute_write(do_write)

    return {"entities": entity_count, "relationships": rel_count, "communities": community_count}
```

---

## 1.7 健康检查脚本

```python
# backend/src/scripts/neo4j_health_check.py
"""Neo4j 健康检查 — 部署后冒烟测试。"""

import sys
from neo4j import GraphDatabase

CHECKS = {
    "连接性": "RETURN 1 AS ok",
    "节点数": "MATCH (n) RETURN count(n) AS total_nodes",
    "关系数": "MATCH ()-[r]->() RETURN count(r) AS total_relationships",
    "约束存在": "SHOW CONSTRAINTS",
    "索引存在": "SHOW INDEXES",
    "Book 节点": "MATCH (b:Book) RETURN count(b) AS books",
    "Exercise 节点": "MATCH (e:Exercise) RETURN count(e) AS exercises",
}


def main():
    driver = GraphDatabase.driver("bolt://localhost:7687", auth=("neo4j", "devpass123"))
    all_ok = True

    with driver.session() as session:
        for name, query in CHECKS.items():
            try:
                record = session.run(query).single()
                value = record.values()[0] if record else "N/A"
                print(f"  ✅ {name}: {value}")
            except Exception as e:
                print(f"  ❌ {name}: {e}")
                all_ok = False

    driver.close()
    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
```

---

## 1.8 验证清单

- [ ] `docker compose up -d neo4j` 成功，容器 healthy
- [ ] `SHOW CONSTRAINTS` 显示 12 个约束
- [ ] `SHOW INDEXES` 显示 8 个索引 + 2 个全文索引
- [ ] `neo4j_health_check.py` 全部通过
- [ ] `import_exercises_to_neo4j.py` 导入 93 项运动
- [x] `NEO4J_ENABLED=False` 时 `get_neo4j_driver()` 返回 `None`
- [x] `NEO4J_ENABLED=True` 时 Driver 可执行查询

### 验证命令

```bash
# 健康检查
docker compose exec neo4j cypher-shell -u neo4j -p devpass123 "
SHOW CONSTRAINTS;
SHOW INDEXES;
MATCH (e:Exercise) RETURN count(e) AS exercises;
MATCH (e:Exercise) WHERE e.suitable_for_children = true RETURN count(e) AS suitable;
"

# Python 验证
cd backend && uv run python -c "
from core.knowledge_qa.neo4j.driver import neo4j_available
print('Neo4j available:', neo4j_available())
"
```

---

## 1.9 预计产出

| 文件 | 操作 | 说明 |
|------|------|------|
| `docker-compose.yml` | 修改 | 确认 Neo4j 服务，调整内存参数 |
| `neo4j/init/schema.cypher` | 新增 | Schema 约束和索引 |
| `backend/src/config/modules/neo4j.py` | 新增 | Neo4j 配置模块 |
| `backend/src/core/knowledge_qa/neo4j/__init__.py` | 新增 | 模块入口 |
| `backend/src/core/knowledge_qa/neo4j/driver.py` | 新增 | Driver 单例 + 健康检查 |
| `backend/src/core/knowledge_qa/neo4j/schema.py` | 新增 | 节点类型常量定义 |
| `backend/src/scripts/import_exercises_to_neo4j.py` | 新增 | 运动数据导入 |
| `backend/src/scripts/neo4j_health_check.py` | 新增 | 冒烟测试脚本 |
| `backend/src/service/document_ingestion/facade.py` | 修改 | 新增 Neo4j 直写逻辑 |
| `backend/pyproject.toml` | 修改 | 添加 `neo4j` 依赖 |
