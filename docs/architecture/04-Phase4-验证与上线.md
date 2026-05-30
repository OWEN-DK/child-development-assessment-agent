# Phase 4: 验证与上线

> **工期**: 2 人天 | **风险**: 中 | **依赖**: Phase 3（Agent 引擎改造完成）  
> **目标**: 回归测试通过、降级路径验证、灰度上线、监控上线
> **实施状态**: ✅ 测试脚本和监控配置已部署（2026-05-30）。执行验证待全链路就绪。
>
> **后端端口**: 51002，健康检查: `http://localhost:51002/health/`

---

## 4.1 回归测试

### 4.1.1 测试 Case

| Case | 问题 | 验证重点 |
|------|------|---------|
| A | "注意力不集中…推荐运动改善方案"（指定书名） | S4 运动名称在 Neo4j Exercise 列表中 |
| B | "社交能力偏弱，有什么方法可以改善？"（未指定书名） | match_books 覆盖、S4 完整性 |
| C | "3岁儿童的大运动发展里程碑是什么？" | S3/S4 正确跳过、S5 边界声明 |
| D | "学龄前儿童注意力训练和运动方案" | 跨书冲突检测、共识标注 |

### 4.1.2 测试执行

```bash
# 1. NEO4J_ENABLED=False 基线
NEO4J_ENABLED=False uv run pytest tests/e2e/test_knowledge_qa_e2e.py -v

# 2. NEO4J_ENABLED=True 新架构
NEO4J_ENABLED=True uv run pytest tests/e2e/test_knowledge_qa_e2e.py -v

# 3. 对比输出
```

### 4.1.3 对比指标

| 指标 | 目标 | 测量方式 |
|------|------|---------|
| **source_coverage** | ≥ 60% 已索引书籍 | `generation_metadata.source_coverage` |
| **S4 运动名称合法率** | ≥ 95% | 运动名称在 Neo4j Exercise 列表中 |
| **S4 structured_data 填充率** | ≥ 95% | `phases` / `plan_summary` / `caution` 非空 |
| **contradiction 召回率** | ≥ 70% | 已知矛盾 case 检出率 |
| **S5 边界声明** | 包含"超出知识库范围" | 人工评审 |
| **端到端耗时增量** | ≤ 30s | 同 case 对比 |

---

## 4.2 降级路径验证

| # | 场景 | 操作 | 预期 |
|---|------|------|------|
| 1 | Neo4j 宕机 | `docker compose stop neo4j` | 流水线不中断，降级到 Chroma |
| 2 | NEO4J_ENABLED=False | 环境变量设为 False | 行为与当前完全一致 |
| 3 | 无匹配运动 | 查询不存在的年龄组合 | 降级到 LLM 生成 + 标记"待提炼" |
| 4 | 无跨书关系 | 仅有一本书时 | LLM 全量审计 |
| 5 | 查询超时 | 设置 `NEO4J_QUERY_TIMEOUT=1` | 返回空，继续流水线 |

### 降级测试脚本

```python
# tests/e2e/test_neo4j_degradation.py

import os
import pytest
from unittest.mock import patch

@pytest.mark.asyncio
async def test_neo4j_unavailable_degradation():
    """Neo4j 不可用时流水线不中断。"""
    os.environ["NEO4J_ENABLED"] = "False"
    result = await run_qa_pipeline("注意力不集中怎么办")
    assert result.status == "completed"
    assert len(result.sections) == 5

@pytest.mark.asyncio
async def test_neo4j_connection_timeout_graceful():
    """Neo4j 连接超时时优雅降级。"""
    with patch("neo4j.AsyncGraphDatabase.driver") as mock_driver:
        from neo4j.exceptions import ServiceUnavailable
        mock_driver.side_effect = ServiceUnavailable("Connection refused")
        result = await run_qa_pipeline("注意力不集中怎么办")
        assert result.neo4j_knowledge == {}
        assert result.status == "completed"
```

---

## 4.3 灰度上线

```bash
# 阶段 1: 1% 流量（观察 1 天）
NEO4J_ENABLED=True
NEO4J_ROLLOUT_PERCENTAGE=1

# 阶段 2: 10% 流量（观察 1 天）
NEO4J_ROLLOUT_PERCENTAGE=10

# 阶段 3: 100% 流量
NEO4J_ROLLOUT_PERCENTAGE=100
```

灰度逻辑：

```python
# backend/src/service/knowledge_qa_service.py
import hashlib

def _should_use_neo4j(question_id: str) -> bool:
    """根据灰度百分比决定是否使用 Neo4j（hash 稳定路由）。

    同一 question_id 始终走同一路径，避免重试时行为不一致。
    """
    if not config_manager.get("neo4j.enabled", False):
        return False
    percentage = config_manager.get("neo4j.rollout_percentage", 0)
    if percentage >= 100:
        return True
    if percentage <= 0:
        return False
    hash_val = int(hashlib.md5(question_id.encode()).hexdigest()[:8], 16)
    return (hash_val % 100) < percentage
```

---

## 4.4 监控

### Prometheus 告警

```yaml
# prometheus/alerts/neo4j.yml

groups:
  - name: neo4j_alerts
    rules:
      - alert: Neo4jDegradationRateHigh
        expr: rate(neo4j_degradation_total[10m]) / rate(knowledge_qa_requests_total[10m]) > 0.1
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Neo4j 降级率超过 10%"

      - alert: Neo4jP99LatencyHigh
        expr: histogram_quantile(0.99, neo4j_query_duration_seconds) > 0.5
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Neo4j P99 查询延迟超过 500ms"

      - alert: PendingQueueGrowing
        expr: pending_queue_length > 50
        for: 1d
        labels:
          severity: info
        annotations:
          summary: "待提炼队列超过 50 项"
```

### Grafana 仪表盘

| Panel | 指标 |
|-------|------|
| 来源分布 | 每本书被引用次数、convergence_score 趋势 |
| 知识覆盖 | Neo4j 节点/关系总数、已提炼书籍数、待提炼队列长度 |
| Neo4j 健康 | 查询延迟 P50/P99、错误率、连接池状态 |
| 降级事件 | 降级次数（按原因分类）、降级率 |

---

## 4.5 回滚方案

```bash
# 全量回滚（紧急）
export NEO4J_ENABLED=False
export NEO4J_ROLLOUT_PERCENTAGE=0
docker compose restart backend  # 容器名: child-dev-backend

# 部分回滚（非紧急）
export NEO4J_ROLLOUT_PERCENTAGE=1
docker compose restart backend
```

---

## 4.6 验证清单

- [ ] 四份 e2e 测试全部通过（NEO4J_ENABLED=True/False）
- [ ] 对比指标全部达标
- [ ] 5 个降级场景全部通过
- [ ] Neo4j P99 < 500ms（100 并发）
- [ ] 灰度: 1% → 10% → 100%，每阶段观察 ≥ 1 天
- [ ] 监控仪表盘正常显示
- [ ] 告警规则已配置

---

## 4.7 预计产出

| 文件 | 操作 | 说明 |
|------|------|------|
| `tests/e2e/test_neo4j_degradation.py` | 新增 | 降级路径测试 |
| `scripts/neo4j_perf_test.py` | 新增 | Neo4j 性能测试 |
| `prometheus/alerts/neo4j.yml` | 新增 | 告警规则 |
| `backend/src/config/modules/neo4j.py` | 修改 | 新增 `NEO4J_ROLLOUT_PERCENTAGE` |
| `backend/src/service/knowledge_qa_service.py` | 修改 | 新增 `_should_use_neo4j()` |
