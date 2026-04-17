# 01 - 趋势图组件（均值 + 误差线） Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 01 - 趋势图组件（均值 + 误差线）

**Architecture:** 参考下方原文档的实现方案和数据模型

**Tech Stack:** Python, FastAPI, TypeScript, React

---

### Task 1: 实现核心逻辑与测试

**Files:**
- Test: `tests/test_placeholder.py`

- [ ] **Step 1: Write the failing test**
  - 根据下方的验收标准和测试方案，编写对应的测试用例
- [ ] **Step 2: Run test to verify it fails**
  - 执行测试并确保看到预期失败信息 (Red)
- [ ] **Step 3: Write minimal implementation**
  - 根据下方"实现方案"中的步骤，编写或修改业务代码
- [ ] **Step 4: Run test to verify it passes**
  - 执行测试确保通过 (Green)
- [ ] **Step 5: Commit**
  - `git add` 相关文件并提交 commit

---

## 原始需求与设计细节 (供参考)

> **Phase**: 6
> **需求点**: 1
> **需求来源**: spec `04-frontend-pages.md` §4.9

## 目标

实现按配置版本分组的指标趋势图，展示均值数据和 min~max 误差线。

## 方案设计

### 组件结构

```
src/features/rag-eval/components/TrendChart/
├── index.tsx                    # 入口组件
├── ChartCanvas.tsx              # 图表画布（基于 recharts）
├── ErrorBar.tsx                 # 误差线组件
├── VersionTooltip.tsx           # 版本详情 tooltip
└── types.ts                     # 类型定义
```

### 数据聚合策略

后端按 `config_version_id` 分组，返回每组指标的平均值、最小值、最大值、运行次数：

```python
# backend/src/service/trend_service.py

async def get_trend_data(
    test_set_id: str,
    metric: str,
    days: int = 7,
    session: AsyncSession = None
) -> list[dict]:
    """获取趋势数据"""
    cutoff_date = datetime.utcnow() - timedelta(days=days)
    
    # 查询指定时间范围内的 ConfigVersion
    result = await session.execute(
        select(ConfigVersion)
        .where(ConfigVersion.created_at >= cutoff_date)
        .order_by(ConfigVersion.created_at)
    )
    versions = result.scalars().all()
    
    trend_data = []
    for version in versions:
        # 查询该配置版本的所有 TestRun 结果
        runs = await get_runs_by_config_version(version.id, session)
        if not runs:
            continue
        
        # 计算指标统计
        values = [getattr(run.metrics, metric) for run in runs if hasattr(run.metrics, metric)]
        if not values:
            continue
        
        trend_data.append({
            "version_id": str(version.id),
            "version_label": version.version_label,
            "created_at": version.created_at.isoformat(),
            "run_count": len(runs),
            "mean": sum(values) / len(values),
            "min": min(values),
            "max": max(values),
            "runs": [
                {
                    "run_id": str(run.id),
                    "value": getattr(run.metrics, metric),
                    "started_at": run.started_at.isoformat()
                }
                for run in runs
            ]
        })
    
    return trend_data
```

### 图表展示规则

| 规则 | 说明 |
|------|------|
| **X 轴** | 按配置版本分组展示，标签为版本号（如 v2.3） |
| **数据点** | 使用均值作为中心，实心圆（6px） |
| **误差线** | min~max 范围，1px 细线，50% 透明度 |
| **单次运行** | 不显示误差线，仅显示单个数据点 |
| **颜色** | P@5 蓝色、R@5 绿色、F1 橙色、MRR 紫色、NDCG 红色 |

### Tooltip 展示内容

鼠标悬停数据点时，展示：

```
版本: v2.3
创建时间: 2026-04-16
运行次数: 3
---
运行 1: 0.53 (2026-04-16 10:30:15)
运行 2: 0.58 (2026-04-16 14:20:30)
运行 3: 0.61 (2026-04-17 09:15:00)
---
均值: 0.57
范围: 0.53 ~ 0.61
```

### 配置版本 hover 详情

鼠标悬停 X 轴版本号时，弹出浮层展示：

```
版本: v2.3
创建时间: 2026-04-16
变更项:
• bm25_top_k: 10 → 15
• reranker_initial_k: 30 → 40
关联提示词变更:
• query_rewrite: v3 → v4
```

### API 端点

```
GET /api/reports/{test_set_id}/trends?metric={metric}&days={days}
Response:
{
  "metric": "p_at_5",
  "data": [
    {
      "version_id": "uuid",
      "version_label": "v2.3",
      "created_at": "2026-04-16T10:00:00Z",
      "run_count": 3,
      "mean": 0.57,
      "min": 0.53,
      "max": 0.61,
      "runs": [...]
    }
  ],
  "config_changes": {
    "v2.3": {
      "config_changes": {"bm25_top_k": {"old": 10, "new": 15}},
      "prompt_changes": {"query_rewrite": {"old": "v3", "new": "v4"}}
    }
  }
}
```

### 验收标准

- [ ] X 轴按配置版本分组展示
- [ ] 均值数据点正确展示
- [ ] 误差线展示 min~max 范围
- [ ] 单次运行不显示误差线
- [ ] Tooltip 展示每次运行的具体值和时间
- [ ] 配置版本 hover 展示变更项摘要
