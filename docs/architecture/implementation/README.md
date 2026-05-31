# 实施方案代码

> 本目录包含各阶段实施方案的完整代码。代码设计为可直接放置到项目对应路径中使用。
>
> **📊 实施进度**: [PROGRESS.md](PROGRESS.md)

## 目录结构

```
implementation/
├── README.md                              ← 本文件
├── phase1_infrastructure/                 ← Phase 1: 基础设施
│   ├── schema.cypher                      ← Neo4j Schema 约束和索引
│   ├── neo4j_driver.py                    ← Driver 单例管理
│   ├── import_exercises.py                ← 运动数据导入脚本
│   └── health_check.py                    ← 健康检查冒烟测试
│
├── phase2_md_toolchain/                   ← Phase 2: MD 工具链
│   ├── chapter_parser.py                  ← EPUB 章节解析
│   ├── md_generator.py                    ← AI MD 生成器（四阶段流水线）
│   ├── aggregator.py                      ← 跨章聚合 + 矛盾检测
│   ├── md_renderer.py                     ← MD 草稿渲染
│   ├── md_parser.py                       ← MD → Cypher 解析器
│   ├── cross_relation.py                  ← 跨书关系检测
│   ├── synonym_registry.py                ← 同义词注册表
│   ├── pending_queue.py                   ← 待提炼队列管理
│   ├── md_diff_analyzer.py                ← 增量 Diff 引擎
│   ├── delta_cypher.py                    ← Delta Cypher 生成器
│   ├── md_metadata.py                     ← MD 元数据 ORM
│   ├── md_version.py                      ← MD 版本 ORM
│   ├── generate_draft.py                  ← MD 草稿生成 CLI
│   └── import_md.py                       ← MD 入库 CLI
│
├── phase3_agent_engine/                   ← Phase 3: Agent 引擎改造
│   ├── query_neo4j_graph.py               ← Layer 1 查询节点
│   ├── query_dispatcher.py                ← 多模式查询调度
│   └── diversity_rerank.py                ← 来源多样性重排
│
└── phase4_verification/                   ← Phase 4: 验证与上线
    ├── test_degradation.py                ← 降级路径测试
    ├── perf_test.py                       ← Neo4j 性能测试
    ├── grayscale_rollout.py               ← 灰度上线逻辑
    └── alerts_neo4j.yml                   ← Prometheus 告警规则
```

## 代码放置映射

| 本目录文件 | 项目目标路径 |
|-----------|------------|
| `phase1_infrastructure/schema.cypher` | `neo4j/init/schema.cypher` |
| `phase1_infrastructure/neo4j_driver.py` | `backend/src/core/knowledge_qa/neo4j/driver.py` |
| `phase1_infrastructure/import_exercises.py` | `backend/src/scripts/import_exercises_to_neo4j.py` |
| `phase1_infrastructure/health_check.py` | `backend/src/scripts/neo4j_health_check.py` |
| `phase2_md_toolchain/chapter_parser.py` | `backend/src/core/knowledge_qa/neo4j/chapter_parser.py` |
| `phase2_md_toolchain/md_generator.py` | `backend/src/core/knowledge_qa/neo4j/md_generator.py` |
| `phase2_md_toolchain/aggregator.py` | `backend/src/core/knowledge_qa/neo4j/aggregator.py` |
| `phase2_md_toolchain/md_renderer.py` | `backend/src/core/knowledge_qa/neo4j/md_renderer.py` |
| `phase2_md_toolchain/md_parser.py` | `backend/src/core/knowledge_qa/neo4j/md_parser.py` |
| `phase2_md_toolchain/cross_relation.py` | `backend/src/core/knowledge_qa/neo4j/cross_relation.py` |
| `phase2_md_toolchain/synonym_registry.py` | `backend/src/core/knowledge_qa/neo4j/synonym_registry.py` |
| `phase2_md_toolchain/pending_queue.py` | `backend/src/core/knowledge_qa/neo4j/pending_queue.py` |
| `phase2_md_toolchain/md_diff_analyzer.py` | `backend/src/core/knowledge_qa/neo4j/md_diff_analyzer.py` |
| `phase2_md_toolchain/delta_cypher.py` | `backend/src/core/knowledge_qa/neo4j/delta_cypher.py` |
| `phase2_md_toolchain/md_metadata.py` | `backend/src/models/md_metadata.py` |
| `phase2_md_toolchain/md_version.py` | `backend/src/models/md_version.py` |
| `phase2_md_toolchain/generate_draft.py` | `backend/src/scripts/generate_draft.py` |
| `phase2_md_toolchain/import_md.py` | `backend/src/scripts/import_md.py` |
| `phase3_agent_engine/query_neo4j_graph.py` | `backend/src/core/knowledge_qa/nodes_v2/query_neo4j_graph.py` |
| `phase3_agent_engine/query_dispatcher.py` | `backend/src/core/knowledge_qa/neo4j/query_dispatcher.py` |
| `phase3_agent_engine/diversity_rerank.py` | `backend/src/core/knowledge_qa/neo4j/diversity_rerank.py` |
| `phase4_verification/test_degradation.py` | `backend/tests/e2e/test_neo4j_degradation.py` |
| `phase4_verification/perf_test.py` | `backend/scripts/neo4j_perf_test.py` |
| `phase4_verification/grayscale_rollout.py` | `backend/src/service/knowledge_qa_service.py` (补充) |
| `phase4_verification/alerts_neo4j.yml` | `prometheus/alerts/neo4j.yml` |

## 关键依赖

| 包 | 版本 | 用途 |
|----|------|------|
| `neo4j` | ≥ 5.0 | Neo4j Python Driver |
| `ebooklib` | ≥ 0.18 | EPUB 解析 |
| `beautifulsoup4` | ≥ 4.12 | HTML 清洗 |
| `tiktoken` | ≥ 0.5 | Token 估算 |
| `scikit-learn` | ≥ 1.3 | Embedding 相似度 |
| `pyyaml` | ≥ 6.0 | YAML 解析 |
| `sqlalchemy` | ≥ 2.0 | ORM (md_metadata / md_version) |

## 使用方式

```bash
# Phase 1: 部署 Neo4j
docker compose up -d neo4j
cat phase1_infrastructure/schema.cypher | docker compose exec -T neo4j cypher-shell -u neo4j -p devpass123
python phase1_infrastructure/import_exercises.py
python phase1_infrastructure/health_check.py

# Phase 2: 生成并入库 MD
python phase2_md_toolchain/generate_draft.py --book-id exercise_book_001 --epub-path /path/to/book.epub
python phase2_md_toolchain/import_md.py --file reviewed.md --dry-run
python phase2_md_toolchain/import_md.py --file reviewed.md

# Phase 4: 验证
pytest phase4_verification/test_degradation.py -v
python phase4_verification/perf_test.py --concurrency 100
```

---

## D2G 流水线（替换原 phase2_md_toolchain）

> **设计文档**: [`../07-知识图谱直提方案-D2G.md`](../07-知识图谱直提方案-D2G.md)

```
phase2_d2g_pipeline/                   ← D2G: 书→知识图谱直提
├── models.py                          ← Pydantic 数据模型（实体/关系/图质量/配置）
├── book_reader.py                     ← Phase 0: 全书深度阅读
├── chapter_extractor.py               ← Phase 1: 逐章 3 轮聚焦提取
├── long_chapter.py                    ← 长章节分段处理（滑窗 + 合并）
├── entity_resolver.py                 ← Phase 2: 增量实体消歧
├── master_graph.py                    ← 内存主图（NetworkX 封装）
├── review_md_generator.py             ← 审核 MD 生成（从图反向生成）
├── graph_quality.py                   ← Phase 3: 图质量审计（纯程序化）
├── graph_committer.py                 ← Phase 4: 入库 Neo4j
└── book_pipeline.py                   ← 流水线编排（端到端流程）
```

### 代码放置映射

| 本目录文件 | 项目目标路径 |
|-----------|------------|
| `phase2_d2g_pipeline/models.py` | `backend/src/core/knowledge_qa/d2g/models.py` |
| `phase2_d2g_pipeline/book_reader.py` | `backend/src/core/knowledge_qa/d2g/book_reader.py` |
| `phase2_d2g_pipeline/chapter_extractor.py` | `backend/src/core/knowledge_qa/d2g/chapter_extractor.py` |
| `phase2_d2g_pipeline/long_chapter.py` | `backend/src/core/knowledge_qa/d2g/long_chapter.py` |
| `phase2_d2g_pipeline/entity_resolver.py` | `backend/src/core/knowledge_qa/d2g/entity_resolver.py` |
| `phase2_d2g_pipeline/master_graph.py` | `backend/src/core/knowledge_qa/d2g/master_graph.py` |
| `phase2_d2g_pipeline/review_md_generator.py` | `backend/src/core/knowledge_qa/d2g/review_md_generator.py` |
| `phase2_d2g_pipeline/graph_quality.py` | `backend/src/core/knowledge_qa/d2g/graph_quality.py` |
| `phase2_d2g_pipeline/graph_committer.py` | `backend/src/core/knowledge_qa/d2g/graph_committer.py` |
| `phase2_d2g_pipeline/book_pipeline.py` | `backend/src/core/knowledge_qa/d2g/book_pipeline.py` |

### 替换关系（原 phase2_md_toolchain → D2G）

| 原文件 | D2G 替换 | 变更说明 |
|--------|---------|---------|
| `md_generator.py` | `chapter_extractor.py` | 单次 LLM → 3 轮聚焦提取 |
| `md_parser.py` | `graph_builder.py`（内置 `master_graph.py`） | MD 解析 → Pydantic 直接建图 |
| `aggregator.py` | `entity_resolver.py` | 同名合并 → embedding + LLM 消歧 |
| `md_renderer.py` | `review_md_generator.py` | 渲染 MD → 从图反向生成审核 MD |
| `generate_draft.py` | `book_pipeline.py` | 新 5 阶段流程编排 |


---

## 自定义知识 + 三层综合（Phase 3）

> **设计文档**: [`../09-自定义知识匹配方案.md`](../09-自定义知识匹配方案.md)

```
phase3_custom_knowledge/               ← 自定义知识匹配 + 三层知识综合
├── custom_knowledge_repository.py     ← MySQL 索引 CRUD + Neo4j CustomRule 双写
├── custom_knowledge_service.py        ← 三通道匹配引擎 + 上传解析 + LLM 关键词生成
├── custom_knowledge_controller.py     ← REST API（6 端点）
├── fast_knowledge_match.py            ← LangGraph 节点: 自定义知识快速匹配
├── knowledge_synthesis_v2.py          ← LangGraph 节点: 三层知识综合
├── schema_changes.py                  ← State + Assembly + 现有节点修改参考
└── migration.sql                      ← MySQL migration
```

### 代码放置映射

| 本目录文件 | 项目目标路径 |
|-----------|------------|
| `phase3_custom_knowledge/custom_knowledge_repository.py` | `backend/src/repository/custom_knowledge_repository.py` |
| `phase3_custom_knowledge/custom_knowledge_service.py` | `backend/src/service/custom_knowledge_service.py` |
| `phase3_custom_knowledge/custom_knowledge_controller.py` | `backend/src/controller/custom_knowledge_controller.py` |
| `phase3_custom_knowledge/fast_knowledge_match.py` | `backend/src/core/knowledge_qa/nodes/fast_knowledge_match.py` |
| `phase3_custom_knowledge/knowledge_synthesis_v2.py` | `backend/src/core/knowledge_qa/nodes_v2/knowledge_synthesis_v2.py` |
| `phase3_custom_knowledge/migration.sql` | `backend/migrations/20260531_create_custom_knowledge_index.sql` |
| `phase3_custom_knowledge/schema_changes.py` | 仅作参考，按注释修改对应文件 |

### 需修改的现有文件

| 文件 | 变更 | 参考 |
|------|------|------|
| `backend/src/schemas/knowledge_qa.py` | 新增 4 个 State 字段 | `schema_changes.py` §1 |
| `backend/src/core/knowledge_qa/_assembly_v2.py` | 新增 2 节点 + 路由变更 | `schema_changes.py` §2 |
| `backend/src/core/knowledge_qa/nodes/prefetch_context.py` | 删除 skip + 增强 question | `schema_changes.py` §3 |
| `backend/src/core/knowledge_qa/nodes_v2/query_neo4j_graph.py` | 增强 s2_problems | `schema_changes.py` §4 |
| `backend/src/core/knowledge_qa/nodes/base.py` | 新增 custom_knowledge_context 参数 | `schema_changes.py` §5 |
| `backend/src/core/knowledge_qa/nodes/conclusion.py` | 注入三层综合 | `schema_changes.py` §6 |
| `backend/src/server.py` | 注册 CustomKnowledgeController | — |

### 使用方式

```bash
# 1. 执行 migration
mysql -u root -p < phase3_custom_knowledge/migration.sql

# 2. 部署新文件（按放置映射复制到 backend/src/）

# 3. 修改现有文件（按 schema_changes.py 逐项修改）

# 4. 重启服务

# 5. 测试上传
curl -X POST http://localhost:8000/api/v1/custom-knowledge/upload \
  -F "files=@ADHD运动干预原则.md"

# 6. 测试匹配
curl -X POST http://localhost:8000/api/v1/custom-knowledge/match \
  -H "Content-Type: application/json" \
  -d '{"question": "我家孩子注意力不集中，适合什么运动？"}'
```
