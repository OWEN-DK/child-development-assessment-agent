# 实施方案代码

> 本目录包含各阶段实施方案的完整代码。代码设计为可直接放置到项目对应路径中使用。

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
