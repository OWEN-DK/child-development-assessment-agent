# P0 级别修复：阻断性 Bug + RAG 流水线接入

**优先级**: 🔴 最高  
**工作量**: 4.5h  

---

## 一、P0-1：修复提示词系统阻断性 Bug

### 1.1 问题描述

**问题文件**：`backend/src/service/config_health_service.py:28`

**错误代码**：
```python
from src.core.prompts import PromptManager  # 错误！不存在 src.core.prompts 模块
```

**实际模块路径**：`src.core.prompt_impl.facade`（PromptManager 定义在此）

**根因分析**：
- 开发者误以为 `src.core.prompts` 存在（实际是 `prompts_fallback.py` 文件，非模块）
- 正确的导入路径应为 `from src.core.prompt_impl.facade import prompt_manager`（全局单例）
- 或使用 `from src.core.prompt_impl.manager import PromptManager`（类定义）

### 1.2 修复方案

**修改内容**：
```python
# 修正后（使用全局单例）
from src.core.prompt_impl.facade import prompt_manager

# 或使用类定义（如需自行实例化）
from src.core.prompt_impl.manager import PromptManager
```

**推荐方案**：使用 `prompt_manager` 全局单例（已在 `prompt_impl/facade.py:99` 定义），避免重复实例化。

### 1.3 验证方式

- 启动后端服务：`cd backend && uv run start`
- 访问健康检查端点：`GET /api/v1/system/health`
- 确认无 `ModuleNotFoundError` 异常

### 1.4 影响范围

| 影响 | 说明 |
|------|------|
| 阻断性 | 系统启动时即报错，无法正常运行 |
| 修复风险 | 极低（仅修改导入路径） |

---

## 二、P0-2：RAG 查询流水线接入实际调用链路

### 2.1 问题描述

**现状**：
- `PipelineOrchestrator`、YAML 配置、10 个步骤类**全部已实现**
- 但 `KnowledgeRetriever.retrieve_knowledge()` 仍走**硬编码流程**
- `PipelineOrchestrator` 在整个 `src/` 目录下**零调用**

**硬编码链路**（`knowledge_retriever.py:243-360`）：
```
缓存检查 → A/B测试变体分配 → 查询重写 → 同义词扩展 → 年龄过滤构建 
→ _execute_retrieval(混合检索/重排序) → 精确年龄二次过滤 
→ _convert_to_knowledge_items → 缓存写入 → 监控埋点
```

### 2.2 根因分析

**问题**：为何 `PipelineOrchestrator` 实现完整但零调用？

**根因**：
1. 开发优先级：先实现硬编码链路保证功能可用，Pipeline 作为后续优化
2. 缺少配置开关：无法灰度切换，不敢直接接入生产
3. 测试不足：Pipeline 步骤类未充分测试

**决策**：直接接入 Pipeline，删除硬编码链路（遵循"零迁移原则"，不保留双模式）。

### 2.3 修复目标

```
目标状态：
直接接入 PipelineOrchestrator 声明式流水线
删除硬编码检索链路（knowledge_retriever.py）
Pipeline 执行失败 → 抛出异常（便于发现根因）
```

### 2.4 详细修复方案

#### Step 1：新增 `RAG_PIPELINE_ENABLED` 配置

**文件**：`backend/src/config/modules/rag/pipeline.py`

**新增字段**：
```python
class RagPipelineSettings(BaseSettings):
    rag_pipeline_enabled: bool = Field(
        default=True,
        description="是否启用声明式流水线"
    )
```

**注意**：默认启用 Pipeline，不保留双模式开关。

---

#### Step 2：修改 `RetrievalFacade.retrieve_knowledge()`

**文件**：`backend/src/service/retrieval/facade.py`

**修改策略**：
```python
def retrieve_knowledge(
    self, 
    query: str, 
    age_range: Optional[str] = None,
    top_k: int = 5,
    ...
) -> List[KnowledgeItem]:
    """检索知识（声明式流水线）"""
    
    # 直接接入 Pipeline，失败时抛出异常
    return self._retrieve_via_pipeline(query, age_range, top_k, ...)
```

**注意**：删除原有硬编码链路代码，不保留双模式。

---

#### Step 3：新增 `_retrieve_via_pipeline()` 方法

**文件**：`backend/src/service/retrieval/facade.py`

**⚠️ 重要：PipelineOrchestrator 实际签名与方案初稿不同**

**实际代码**（`orchestrator.py:106`）：
```python
async def execute(self, query: str, age: float, limit: int = 5) -> list[Any]:
    """返回 context.results（原始检索结果列表）"""
```

**不是**：接收 `PipelineContext` 对象，返回 `dict`

**核心逻辑**：
```python
async def _retrieve_via_pipeline(
    self, 
    query: str, 
    age_range: Optional[str] = None,
    top_k: int = 5,
    ...
) -> List[KnowledgeItem]:
    """通过声明式流水线执行检索"""
    
    # 1. 解析 age_range 为 float（如 "3-4岁" → 3.5）
    age = self._parse_age_range(age_range) if age_range else 0.0
    
    # 2. 执行流水线（返回原始检索结果列表）
    raw_results = await self.pipeline_orchestrator.execute(
        query=query,
        age=age,
        limit=top_k
    )
    
    # 3. 转换为 KnowledgeItem 格式
    return self._convert_to_knowledge_items(raw_results)
```

**缺失能力补充**：

| 能力 | 现状 | 补充方案 |
|------|------|----------|
| A/B 测试变体分配 | 内嵌在 `_execute_retrieval` | 在 `PipelineContext.metadata` 中传递 `ab_test_variant` |
| 监控埋点 | 内嵌在 `retrieve_knowledge` 末尾 | 在 `PipelineOrchestrator.execute()` 末尾添加日志记录（暂不接入 Prometheus） |
| KnowledgeItem 转换 | `_convert_to_knowledge_items` | 在 Facade 层转换，不新增步骤类（保持 Pipeline 返回原始结果） |

---

#### Step 4：修改 `_classify_query()` 逻辑

**文件**：`backend/src/core/pipeline/orchestrator.py:150-153`

**当前问题**：硬编码返回 `"complex"`

**修复方案 A**（推荐）：基于规则分类
```python
def _classify_query(self, query: str) -> str:
    """基于规则简单/复杂查询分类"""
    
    # 复杂查询关键词
    complex_keywords = ["区别", "对比", "差异", "比较", "如何", "为什么", "原因"]
    
    for keyword in complex_keywords:
        if keyword in query:
            return "complex"
    
    # 长度阈值
    if len(query) > 20:
        return "complex"
    
    return "simple"
```

**修复方案 B**（进阶）：使用 `QueryRouterStep`（已实现）
```python
async def _classify_query(self, query: str) -> str:
    """使用 LLM 分类查询"""
    router_step = QueryRouterStep(name="query_router", config={})
    context = PipelineContext(query=query, age=0.0, limit=1)
    context = await router_step.execute(context)
    return context.metadata.get("query_type", "complex")
```

---

#### Step 5：补充监控埋点

**文件**：`backend/src/core/pipeline/orchestrator.py`

**在 `execute()` 方法末尾添加**：
```python
async def execute(self, query: str, age: float, limit: int = 5) -> list[Any]:
    # ... 现有执行逻辑
    
    # 记录监控指标
    self._record_metrics(context, query_type)
    
    return context.results

def _record_metrics(self, context: PipelineContext, query_type: str):
    """记录 Pipeline 执行指标"""
    elapsed_ms = (time.time() - context.start_time) * 1000
    
    # 记录总耗时
    logger.info(
        f"RAG 流水线 [{query_type}] 执行完成："
        f"{len(context.results)} 个结果，耗时 {elapsed_ms:.0f}ms"
    )
    
    # 记录错误
    if context.errors:
        logger.warning(f"流水线执行错误：{', '.join(context.errors)}")
```

**注意**：Prometheus 暂未集成，仅记录到日志，后续统一接入

---

### 2.4 验收标准

- [ ] 请求走 PipelineOrchestrator（`orchestrator.py:106` 的 `execute(query, age, limit)` 签名）
- [ ] 硬编码链路代码已删除
- [ ] Pipeline 执行失败时，抛出异常（不静默降级，便于发现根因）
- [ ] 监控日志正常记录（执行耗时、结果数量、错误信息）
- [ ] A/B 测试变体分配正常工作（通过 `PipelineContext.metadata` 传递）
- [ ] 查询分类逻辑准确（simple/complex 路由正确）

---

### 2.5 影响分析

| 影响维度 | 说明 |
|----------|------|
| **破坏性变更** | 硬编码链路已删除，无法回退 |
| **性能影响** | Pipeline 增加约 5-10ms 开销（YAML 解析 + 步骤调度） |
| **风险等级** | 中（需充分测试 Pipeline 稳定性） |


