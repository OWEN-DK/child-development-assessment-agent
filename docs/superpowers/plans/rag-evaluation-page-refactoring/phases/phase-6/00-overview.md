# Phase 6: 趋势追踪 + 导出功能 — 总览

> **需求来源**: spec 文档 `04-frontend-pages.md` 4.9-4.10 节
> **需求点数量**: 8 个
> **优先级**: P2

## 目标

实现指标趋势图、配置版本对比与回滚、PDF/CSV/JSON 导出功能。

## 前置依赖

```bash
cd backend && uv add weasyprint
```

## 需求点清单

### 趋势追踪 (2 个) - P0 核心功能

| # | 需求点 | 实施文件 | 优先级 | 说明 |
|---|--------|---------|--------|------|
| 1 | 趋势图组件（均值 + 误差线） | `01-trend-chart-component.md` | P0 | 按配置版本分组，均值数据点，min~max 误差线 |
| 2 | 多指标叠加展示 | `02-multi-metric-overlay.md` | P1 | 独立 Y 轴，图例可点击切换 |

### 配置版本管理 (2 个) - P0 核心功能

| # | 需求点 | 实施文件 | 优先级 | 说明 |
|---|--------|---------|--------|------|
| 3 | 配置版本对比 | `03-config-version-comparison.md` | P0 | 展示变更项，✨ 标记 |
| 4 | 配置版本回滚 | `04-config-version-rollback.md` | P0 | 原子回滚配置 + 提示词，创建 rolled_back 变更集 |

### 导出功能 (4 个) - P1 次要功能

| # | 需求点 | 实施文件 | 优先级 | 实现方式 | 内容 |
|---|--------|---------|--------|---------|------|
| 5 | PDF 导出（后端异步） | `05-pdf-export-async.md` | P1 | weasyprint + Jinja2 模板 | 报告摘要 + 指标 + 校验结果 + 调优建议 |
| 6 | CSV 导出（前端） | `06-csv-export-frontend.md` | P1 | papaparse 前端生成 | 用例执行明细 |
| 7 | JSON 导出（前端） | `07-json-export-frontend.md` | P1 | 前端直接下载 | 完整报告数据 |
| 8 | 导出任务并发限制 | `08-export-task-concurrency-limit.md` | P2 | 最多 2 个并行 PDF 导出，超时 60 秒 | 任务队列管理 |

## 验收标准

- [ ] 趋势图按配置版本分组展示（均值 + 误差线）
- [ ] 误差线、多指标叠加、hover 详情正常
- [ ] 配置版本对比展示变更项
- [ ] 配置版本回滚功能正常（原子回滚配置 + 提示词）
- [ ] PDF 导出异步任务完成（weasyprint + Jinja2）
- [ ] CSV/JSON 前端导出正常
- [ ] 导出任务限制（最多 2 个并行 PDF 导出，超时 60 秒）

## 趋势图交互细节

- X 轴按配置版本分组展示，每个版本一个数据点
- 同一配置版本多次运行时，以均值±误差线展示
- 误差线 = min~max 范围，1px 细线，50% 透明度
- hover 时展示：版本号、运行次数、每次运行具体值、运行时间
- 配置版本 hover 展示 config_snapshot 摘要（仅变更项）

---

**文档索引**: 
- 上一节: [Phase 5 总览](../phase-5/00-overview.md)
- 下一节: [01-trend-chart-component.md](./01-trend-chart-component.md) — 需求点 1
