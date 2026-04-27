# 02 - 后端五引擎架构

## 需求

将当前混杂的 RAG 评估后端代码（~9,900行）重构为 5 个独立引擎 + 1 个统一编排器，每个引擎 < 500 行。

## 当前问题

1. `draft_service.py` 1157行，包含 6+ 职责（生成/验证/去重/分类/CRUD/导入）
2. `rag_test_controller.py` 996行，45 个端点混杂 7 个领域
3. `facade.py` 494行，ORM-to-Pydantic 转换重复 6 次
4. 双服务层共存（`rag_test_manager` + `facade`）
5. 双报告服务共存（`rag_report_service.py` + `report/`）
6. Singleton `__new__` 反模式，sync/async 混用
7. 内联 SQL 绕过 Repository 层

## 目录结构

```
backend/src/
├── controller/
│   └── rag_eval_controller.py          # ~400行，统一控制器
│
├── service/
│   └── rag_eval/
│       ├── __init__.py
│       ├── orchestrator.py              # ~150行，跨引擎编排
│       │
│       ├── draft/                       # 草稿引擎
│       │   ├── __init__.py
│       │   ├── facade.py                # ~120行，门面
│       │   ├── generator.py             # ~200行，LLM QA生成
│       │   ├── faithfulness_checker.py  # ~150行，忠实度验证
│       │   ├── deduplicator.py          # ~100行，去重
│       │   └── book_analyzer.py         # ~120行，书籍元数据分析
│       │
│       ├── metrics/                     # 指标引擎
│       │   ├── __init__.py
│       │   ├── facade.py                # ~100行，门面
│       │   ├── registry.py              # ~60行，指标注册表
│       │   ├── base.py                  # ~40行，MetricCalculator接口
│       │   ├── retrieval_quality.py     # ~200行，L1指标
│       │   ├── generation_quality.py    # ~180行，L2指标
│       │   ├── system_quality.py        # ~150行，L3指标
│       │   └── calculators/             # 原子计算器
│       │       ├── __init__.py
│       │       ├── precision_recall.py  # ~80行
│       │       ├── mrr_ndcg.py          # ~100行
│       │       ├── faithfulness_calc.py # ~120行
│       │       └── groundedness_calc.py # ~100行
│       │
│       ├── run/                         # 运行引擎
│       │   ├── __init__.py
│       │   ├── facade.py                # ~120行，门面
│       │   ├── executor.py              # ~120行，单用例执行
│       │   ├── batch_runner.py          # ~180行，批量并发
│       │   ├── result_processor.py      # ~100行，结果聚合
│       │   └── snapshot_manager.py      # ~120行，快照管理
│       │
│       ├── report/                      # 报告引擎
│       │   ├── __init__.py
│       │   ├── facade.py                # ~80行，门面
│       │   ├── builder.py               # ~150行，报告构建
│       │   ├── markdown_renderer.py     # ~80行，Markdown渲染
│       │   ├── trend_analyzer.py        # ~100行，趋势分析
│       │   └── exporter.py              # ~80行，导出
│       │
│       └── tuning/                      # 调优引擎
│           ├── __init__.py
│           ├── facade.py                # ~80行，门面
│           ├── advisor.py               # ~120行，建议生成
│           ├── conflict_detector.py     # ~80行，冲突检测
│           └── impact_analyzer.py       # ~100行，影响分析
│
├── schemas/
│   └── rag_eval/                        # 实体类集中管理
│       ├── __init__.py
│       ├── source_document.py
│       ├── draft.py
│       ├── test_case.py
│       ├── test_set.py
│       ├── test_run.py
│       ├── metrics.py
│       ├── report.py
│       ├── snapshot.py
│       └── tuning.py
│
└── utils/
    ├── orm_mapper.py                    # ORM→Pydantic统一映射
    ├── embedding_helper.py              # Embedding缓存+计算
    └── similarity.py                    # cosine/欧氏距离
```

## 编排器设计

```python
class RagEvalOrchestrator:
    """跨引擎协调器，处理跨引擎的工作流"""
    
    def __init__(self, ...):
        self.draft_engine = DraftEngineFacade(...)
        self.metric_engine = MetricEngineFacade(...)
        self.run_engine = RunEngineFacade(...)
        self.report_engine = ReportEngineFacade(...)
        self.tuning_engine = TuningEngineFacade(...)
    
    async def run_full_evaluation(self, test_set_id: str, config: EvalConfig) -> str:
        """完整评估流程：快照→执行→计算指标→生成报告→调优建议"""
        snapshot_id = await self.run_engine.create_snapshot()
        run_id = await self.run_engine.execute_batch(test_set_id, snapshot_id, config)
        metrics = await self.metric_engine.calculate_all(run_id)
        report = await self.report_engine.build(run_id, metrics)
        suggestions = await self.tuning_engine.analyze(run_id, metrics)
        return run_id
    
    async def generate_and_review_drafts(self, doc_id: str, config: DraftConfig) -> str:
        """草稿全流程：生成→去重→验证"""
        task_id = await self.draft_engine.start_generation(doc_id, config)
        return task_id
```

## 控制器设计

```python
class RagEvalController:
    """统一控制器，路由前缀 /rag/eval/"""
    
    def __init__(self, orchestrator: RagEvalOrchestrator):
        self._orch = orchestrator
    
    # 草稿路由组
    def register_draft_routes(self, router: APIRouter): ...
    
    # 测试用例/集路由组
    def register_test_case_routes(self, router: APIRouter): ...
    
    # 运行路由组
    def register_run_routes(self, router: APIRouter): ...
    
    # 报告路由组
    def register_report_routes(self, router: APIRouter): ...
    
    # 调优路由组
    def register_tuning_routes(self, router: APIRouter): ...
    
    # 快照路由组
    def register_snapshot_routes(self, router: APIRouter): ...
```

每个 `register_xxx_routes` 方法 ~60-70 行，控制器总计 ~400 行。

## 关键设计决策

### 1. 删除旧代码（零迁移原则）

以下文件/目录在重构完成后直接删除：
- `backend/src/service/rag_test/` （整个旧目录）
- `backend/src/service/rag_test_manager.py`
- `backend/src/service/rag_report_service.py`
- `backend/src/controller/rag_test_controller.py`
- `backend/src/schemas/test_case.py`（合并到 `rag_eval/test_case.py`）
- `backend/src/schemas/rag_eval.py`（拆分到 `rag_eval/` 目录）

### 2. 统一使用 Repository 层

所有数据访问通过 Repository 层，禁止内联 SQL：

```python
# 禁止 ❌
async with self.db_session_factory() as session:
    result = await session.execute(select(TestCase))

# 正确 ✅
cases = await self.test_case_repo.list(filters)
```

### 3. 依赖注入替代 Singleton

```python
# 禁止 ❌
class DraftService:
    _instance = None
    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

# 正确 ✅ — 通过 DI 容器注入
class DraftEngineFacade:
    def __init__(
        self,
        generator: DraftGenerator,
        faithfulness_checker: FaithfulnessChecker,
        deduplicator: DraftDeduplicator,
        draft_repo: DraftRepository,
    ):
        self._generator = generator
        self._faithfulness_checker = faithfulness_checker
        self._deduplicator = deduplicator
        self._repo = draft_repo
```

### 4. ORM-to-Pydantic 统一映射

```python
# utils/orm_mapper.py
class OrmMapper:
    @staticmethod
    def to_pydantic(orm_obj, pydantic_class: Type[T]) -> T:
        """通用 ORM → Pydantic 转换"""
        data = {}
        for field in pydantic_class.model_fields:
            if hasattr(orm_obj, field):
                data[field] = getattr(orm_obj, field)
        return pydantic_class(**data)
    
    @staticmethod
    def to_pydantic_list(orm_objs: List, pydantic_class: Type[T]) -> List[T]:
        return [OrmMapper.to_pydantic(obj, pydantic_class) for obj in orm_objs]
```

### 5. 全异步

所有 Service 方法统一为 `async`，消除 sync/async 混用问题。快照操作通过 `asyncio.to_thread()` 包装同步底层调用。

## 验收标准

1. 所有文件 < 500 行
2. 无 Singleton `__new__` 模式
3. 无内联 SQL（全部通过 Repository）
4. 无 sync/async 混用
5. ORM-to-Pydantic 转换通过 `OrmMapper` 统一处理
6. 旧的 `rag_test/` 目录完全删除
7. 所有硬编码值迁移到 ConfigManager
