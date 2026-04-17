# 00 - 项目概览

> **本文档包含**: 项目背景、核心目标、验收标准、整体架构、核心工作流、依赖管理、配置管理

---

## 项目背景

用户核心任务：诊断 RAG 检索质量 → 调优参数 → 验证效果 → 循环。

当前工作流断裂：
```
期望工作流：
导入书籍 → 生成测试用例 → 运行诊断 → 查看问题 → 调参 → 验证效果 → 循环

当前工作流：
导入书籍 → ❌ 失败 → 无法生成用例 → 无法运行诊断 → 页面空白
```

---

## 核心目标

| # | 目标 | 验收标准 | 所属 Phase |
|---|------|---------|-----------|
| 1 | 修复 12 个核心工作流根因 | 书籍导入/批量测试全部正常 | Phase 0 |
| 2 | 建立 18 个数据模型 | UUID 主键 String(36)，MySQL 存储，22 个索引（⚠️ Phase 1 文档目标行误写为 17 个） | Phase 1 |
| 3 | 实现 SSE 实时推送工作流 | 10 种事件，断线重连，心跳无泄漏 | Phase 2 |
| 4 | 构建 6 层校验引擎 | 13 种校验，分层递进诊断 | Phase 4 |
| 5 | 实现推荐模式面板 | 三种模式，采纳→审查→保存三步分离 | Phase 5 |
| 6 | 实现配置/提示词版本管理 | 原子保存，热重载，回滚 | Phase 5 |
| 7 | 实现趋势追踪与导出 | PDF/CSV/JSON，误差线，多指标叠加 | Phase 6 |
| 8 | 重构提示词管理 | 中文说明，影响分析，测试沙箱 | Phase 7 |
| 9 | 优化配置管理 | 分组展示，实时校验，冲突检测 | Phase 8 |

---

## 验收标准总览

### Phase 0 验收
- 书籍导入：PDF/EPUB/TXT 三类文件均能正确提取文本
- SSE 连接：开发环境和生产环境均成功
- 批量测试：前端实时显示进度，不等待 HTTP 响应
- 单个用例测试：严格只运行该用例
- 长时间任务不静默终止

### Phase 1 验收
- 17 个数据模型全部创建，MySQL 表结构正确
- UUID 主键统一，所有关联采用弱引用（无外键约束）
- 22 个索引全部创建
- Enum 映射正确（values_callable）

### Phase 2 验收
- 10 种 SSE 事件定义完整（严格按 spec 字段格式）
- 前端能接收并展示实时进度
- 断线重连机制工作正常
- 心跳队列无内存泄漏

### Phase 3 验收
- 前端路由 `/rag-eval/*` 全部可用
- 评估报告页展示 6 层校验结果
- 测试集管理（列表/详情/用例管理/草稿审核）
- 运行历史列表与详情页
- 旧路由 `/rag-evaluation` 直接删除

### Phase 4 验收
- 6 层校验引擎全部实现（13 种校验）
- 校验总耗时 < 5 分钟
- 降级策略正确执行
- 并发限制正确（最多 3 个并行）

### Phase 5 验收
- 推荐模式面板三种模式切换正常
- 采纳→审查→保存三步分离
- 配置/提示词原子保存
- 热重载机制工作正常
- 对比视图展示 diff

### Phase 6 验收
- 趋势图按配置版本分组展示
- 误差线、多指标叠加、hover 详情正常
- PDF 导出异步任务完成
- CSV/JSON 前端导出正常
- 配置版本回滚功能正常

### Phase 7 验收
- 提示词列表展示中文名称和用途
- 编辑页展示变量可视化面板
- 版本对比 diff 可视化
- 测试沙箱可预览 LLM 输出
- 影响分析引擎正确扫描代码引用

### Phase 8 验收
- 配置主页按功能域分组展示
- 所有配置项有中文名称和用途说明
- 输入时实时校验取值范围
- 修改时展示影响范围和重载方式
- 配置冲突检测正确

---

## 整体架构

```
┌─────────────────────────────────────────────────────────────┐
│                      前端 (React + Ant Design)                │
│  /rag-eval/test-sets  /rag-eval/runs  /rag-eval/reports/{id} │
│  /rag-eval/prompts    /system-config                         │
└──────────────────────────┬────────────────────────────────────┘
                           │ REST API + SSE
┌──────────────────────────▼────────────────────────────────────┐
│                      后端 (FastAPI)                            │
│  Controller 层 → Service 层 → ValidationEngine (6 层校验)     │
│  SSE Pub/Redis → ConfigCache (热重载) → LLM (DashScope)       │
└──────────────────────────┬────────────────────────────────────┘
                           │
┌──────────────────────────▼────────────────────────────────────┐
│                      数据层                                    │
│  MySQL 5.7 (17+ 张表) → Redis 7.0 (Pub/Sub) → Chroma (向量库) │
└─────────────────────────────────────────────────────────────┘
```

### 核心工作流

```
创建/选择测试集 → 运行测试集 → 生成评估报告 → 6 层校验诊断
    → 输出调优建议 → 推荐模式面板展示 → 用户采纳 → 审查 → 保存为新版本
    → 复测验证 → 趋势追踪 → 循环
```

---

## 依赖管理

### 新增依赖

```toml
# Phase 6: PDF 导出
weasyprint = "^60.0"

# Phase 4: JSON 修复（LLM 输出解析）
json-repair = "^0.30.0"
```

---

## 配置管理

### 新增配置项

```python
# Phase 4: 校验引擎
rag_validation_timeout_total: int = 300
rag_validation_timeout_per_layer: dict = {1: 30, 2: 30, 3: 120, 4: 30, 5: 30, 6: 60}
rag_validation_max_concurrent: int = 3
rag_validation_queue_max: int = 10
rag_bad_case_llm_threshold: int = 5
rag_bad_case_sample_max: int = 50
# Layer 1 规则引擎阈值（禁止硬编码，从配置中心读取）
rag_validation_threshold_p_at_5: float = 0.70
rag_validation_threshold_r_at_5: float = 0.85
rag_validation_threshold_f1: float = 0.75
rag_validation_threshold_mrr: float = 0.70
rag_validation_threshold_short_query_failure_rate: float = 0.30
rag_validation_threshold_cross_domain_failure_rate: float = 0.20

# Phase 5: 配置热重载
rag_config_cache_ttl: int = 300
rag_config_redis_channel: str = "config_changed"

# Phase 6: 导出
rag_export_pdf_timeout: int = 60
rag_export_pdf_max_concurrent: int = 2
rag_export_redis_ttl: int = 86400
```

---

**文档索引**: 
- 下一步: [Phase 0 总览](./phases/phase-0/00-overview.md)
- 需求映射: [DOCUMENT_STRUCTURE.md](./DOCUMENT_STRUCTURE.md)
- 进度追踪: [PROGRESS.md](./PROGRESS.md)
