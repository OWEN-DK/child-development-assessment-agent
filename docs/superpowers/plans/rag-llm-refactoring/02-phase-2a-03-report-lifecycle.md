# Phase 2A.2: 报告生命周期管理

> **前置文档:** [Overview](./02-phase-2a-00-overview.md) | [执行路径统一](./02-phase-2a-02-execution-path.md)
> **状态:** ⏳ 完全待实现
> **预计工期:** 1人天

### 🔴 2.3 报告生命周期管理（⏳ 完全待实现，1人天）
> 存储方案：元数据存MySQL，静态报告文件存本地磁盘 `/app_data/reports/`，按日期分目录存储
> 删除策略：测试阶段直接物理删除，不保留软删除机制

#### Task 2.3.1: 实现报告生成服务
**Files:**
- Create: `src/service/rag_report_service.py`
- Test: `tests/service/test_rag_report_service.py`

- [ ] **Step 1: 编写测试用例**
```python
import pytest

@pytest.mark.asyncio
async def test_generate_report():
    from src.service.rag_report_service import rag_report_service
    
    report = await rag_report_service.generate_report(run_id=1)
    assert report is not None
    assert "## 整体指标" in report.content
    assert "## 分领域统计" in report.content
    assert "## Bad Case 列表" in report.content
```

- [ ] **Step 2: 运行测试验证失败**
Run: `pytest tests/service/test_rag_report_service.py::test_generate_report -v`
Expected: FAIL - 服务未实现

- [ ] **Step 3: 实现报告生成逻辑**
创建`src/service/rag_report_service.py`:
```python
from injector import inject
from pathlib import Path
from datetime import datetime, timezone
import json
from src.config import settings
from src.repository.test_run_repository import test_run_repo
from src.repository.test_run_result_repository import test_run_result_repo
from src.core.rag.metrics_calculator import calculate_mrr, calculate_ndcg, calculate_precision, calculate_recall
from src.utils.logger import logger
from redis.asyncio import Redis

@inject
class RagReportService:
    def __init__(
        self, 
        test_run_repo: TestRunRepository, 
        test_run_result_repo: TestRunResultRepository,
        redis_client: Redis
    ):
        self.test_run_repo = test_run_repo
        self.test_run_result_repo = test_run_result_repo
        self.redis_client = redis_client
        self.report_dir = Path(settings.paths.rag_report_dir)
        self.report_dir.mkdir(parents=True, exist_ok=True)
    
    async def generate_report(self, run_id: int) -> dict:
        """生成测试报告（带分布式锁防止并发生成）"""
        lock_key = f"report:generate:{run_id}"
        acquired = await self.redis_client.set(lock_key, "1", nx=True, ex=60)  # 修正为实例属性
        if not acquired:
            raise RuntimeError(f"报告 {run_id} 正在生成中，请勿重复提交")
        
        try:
            test_run = await self.test_run_repo.get_by_id(run_id)
            results = await self.test_run_result_repo.list_by_test_run_id(run_id)
            
            if not test_run or not results:
                raise ValueError(f"测试运行 {run_id} 不存在或无结果")
            
            total_cases = len(results)
            avg_mrr = sum(r.mrr for r in results) / total_cases
            
            # NDCG 过滤 None 值（空期望文档的用例）
            ndcg_values = [float(r.ndcg) for r in results if r.ndcg is not None]
            avg_ndcg = sum(ndcg_values) / len(ndcg_values) if ndcg_values else 0.0
            
            # Precision/Recall@K 过滤 None 值
            precision_values = [float(r.precision) for r in results if r.precision is not None]
            recall_values = [float(r.recall) for r in results if r.recall is not None]
            avg_precision = sum(precision_values) / len(precision_values) if precision_values else 0.0
            avg_recall = sum(recall_values) / len(recall_values) if recall_values else 0.0
            
            avg_hit_rate_1 = sum(r.hit_rate_1 for r in results) / total_cases
            avg_hit_rate_3 = sum(r.hit_rate_3 for r in results) / total_cases
            avg_hit_rate_5 = sum(r.hit_rate_5 for r in results) / total_cases
            
            domain_stats = {}
            for result in results:
                domain = result.test_case.domain
                if domain not in domain_stats:
                    domain_stats[domain] = {
                        "count": 0, "total_mrr": 0, "total_ndcg": 0, "ndcg_count": 0,
                        "total_precision": 0, "precision_count": 0,
                        "total_recall": 0, "recall_count": 0
                    }
                domain_stats[domain]["count"] += 1
                domain_stats[domain]["total_mrr"] += result.mrr
                if result.ndcg is not None:
                    domain_stats[domain]["total_ndcg"] += float(result.ndcg)
                    domain_stats[domain]["ndcg_count"] += 1
                if result.precision is not None:
                    domain_stats[domain]["total_precision"] += float(result.precision)
                    domain_stats[domain]["precision_count"] += 1
                if result.recall is not None:
                    domain_stats[domain]["total_recall"] += float(result.recall)
                    domain_stats[domain]["recall_count"] += 1
            
            for domain in domain_stats:
                stats = domain_stats[domain]
                stats["avg_mrr"] = stats["total_mrr"] / stats["count"]
                stats["avg_ndcg"] = stats["total_ndcg"] / stats["ndcg_count"] if stats["ndcg_count"] > 0 else 0.0
                stats["avg_precision"] = stats["total_precision"] / stats["precision_count"] if stats["precision_count"] > 0 else 0.0
                stats["avg_recall"] = stats["total_recall"] / stats["recall_count"] if stats["recall_count"] > 0 else 0.0
            
            bad_cases = [r for r in results if r.mrr < 0.3]
            
            content = f"""# RAG测试报告
## 基本信息
- 测试运行ID: {test_run.id}
- 测试名称: {test_run.name or "未命名"}
- 执行时间: {test_run.completed_at or datetime.now(timezone.utc)}
- 总测试用例数: {total_cases}

## 整体指标
| 指标 | 值 |
|------|----|
| 平均MRR | {avg_mrr:.4f} |
| 平均NDCG | {avg_ndcg:.4f} |
| 平均精确率(Precision) | {avg_precision:.4f} |
| 平均召回率(Recall) | {avg_recall:.4f} |
| 平均命中率@1 | {avg_hit_rate_1:.4f} |
| 平均命中率@3 | {avg_hit_rate_3:.4f} |
| 平均命中率@5 | {avg_hit_rate_5:.4f} |

## 分领域统计
| 领域 | 用例数 | 平均MRR | 平均NDCG | 平均Precision | 平均Recall |
|------|--------|---------|----------|---------------|------------|
"""
            for domain, stats in domain_stats.items():
                content += f"| {domain} | {stats['count']} | {stats['avg_mrr']:.4f} | {stats['avg_ndcg']:.4f} | {stats['avg_precision']:.4f} | {stats['avg_recall']:.4f} |\n"
            
            content += f"""
## Bad Case 列表
共 {len(bad_cases)} 个Bad Case（MRR < 0.3）

"""
            for idx, case in enumerate(bad_cases[:20]):
                content += f"{idx+1}. 用例ID: {case.test_case_id}, 查询: {case.test_case.query}, MRR: {case.mrr:.4f}\n"
            
            date_str = datetime.now(timezone.utc).strftime("%Y%m%d")
            report_path = self.report_dir / date_str / f"run_{run_id}_{datetime.now(timezone.utc).strftime('%H%M%S')}.md"
            report_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(report_path, "w", encoding="utf-8") as f:
                f.write(content)
            
            await self.test_run_repo.update(run_id, {"report_storage_path": str(report_path)})
            
            return {
                "run_id": run_id,
                "content": content,
                "storage_path": str(report_path),
                "overall_metrics": {
                    "avg_mrr": avg_mrr,
                    "avg_ndcg": avg_ndcg,
                    "avg_precision": avg_precision,
                    "avg_recall": avg_recall,
                    "avg_hit_rate_1": avg_hit_rate_1,
                    "avg_hit_rate_3": avg_hit_rate_3,
                    "avg_hit_rate_5": avg_hit_rate_5
                },
                "domain_stats": domain_stats,
                "bad_case_count": len(bad_cases)
            }
        finally:
            await self.redis_client.delete(lock_key)
```

- [ ] **Step 4: 运行测试验证通过**
Run: `pytest tests/service/test_rag_report_service.py::test_generate_report -v`
Expected: PASS

---

#### Task 2.3.2: 实现报告删除功能
**Files:**
- Modify: `src/service/rag_report_service.py` (新增删除方法)
- Test: `tests/service/test_rag_report_service.py::test_delete_report`

- [ ] **Step 1: 编写删除测试用例**
```python
@pytest.mark.asyncio
async def test_delete_report():
    from src.service.rag_report_service import rag_report_service
    
    # 删除报告
    await rag_report_service.delete_report(run_id=1)
    
    # 验证数据库记录已删除
    test_run = await rag_test_service.get_test_run(1)
    assert test_run is None
```

- [ ] **Step 2: 实现删除逻辑**
在`RagReportService`中新增方法：
```python
async def delete_report(self, run_id: int):
    """物理删除报告（测试阶段直接删除，不保留软删除）"""
    test_run = await self.test_run_repo.get_by_id(run_id)
    if not test_run:
        raise ValueError(f"测试运行 {run_id} 不存在")
    
    try:
        # 删除报告文件
        if test_run.report_storage_path:
            path = Path(test_run.report_storage_path)
            if path.exists():
                path.unlink()
                logger.info(f"已删除报告文件: {test_run.report_storage_path}")
        
        # 物理删除数据库记录（级联删除结果）
        await self.test_run_repo.delete(run_id)
        logger.info(f"已物理删除报告 {run_id}")
    except Exception as e:
        logger.error(f"删除报告 {run_id} 失败: {e}")
        raise
```

---

#### Task 2.3.3: 配置定时任务（APScheduler）
**Files:**
- Create: `src/core/scheduler/rag_report_scheduler.py`
- Modify: `src/app.py` (注册调度器)

- [ ] **Step 1: 实现定时任务调度器**
```python
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from injector import inject

@inject
class RagReportScheduler:
    def __init__(self, report_service: RagReportService):
        self.scheduler = AsyncIOScheduler()
        self.report_service = report_service
    
    def start(self):
        # 每天凌晨 2 点清理过期报告（保留 30 天）
        self.scheduler.add_job(
            self.report_service.cleanup_expired_reports,
            CronTrigger(hour=2, minute=0),
            id="cleanup_reports",
            replace_existing=True,
            max_instances=1
        )
        
        # 每天凌晨 3 点清理 orphaned 草稿（状态=draft 且超过 7 天未审核）
        self.scheduler.add_job(
            self.report_service.cleanup_orphaned_drafts,
            CronTrigger(hour=3, minute=0),
            id="cleanup_drafts",
            replace_existing=True,
            max_instances=1
        )
        
        self.scheduler.start()
    
    def shutdown(self):
        self.scheduler.shutdown()
```

- [ ] **Step 2: 在 app.py 中注册调度器（使用 FastAPI lifespan）**
```python
from contextlib import asynccontextmanager
from fastapi import FastAPI
from src.core.scheduler.rag_report_scheduler import rag_report_scheduler

@asynccontextmanager
async def lifespan(app: FastAPI):
    rag_report_scheduler.start()
    yield
    rag_report_scheduler.shutdown()

app = FastAPI(lifespan=lifespan)
```

- [ ] **Step 3: 实现清理方法**
在`RagReportService`中新增方法：
```python
from datetime import timedelta, datetime, timezone

async def cleanup_expired_reports(self, retention_days: int = 30):
    """清理过期报告（多实例部署防重复执行：分布式锁）"""
    lock_key = "scheduler:cleanup_reports"
    acquired = await self.redis_client.set(lock_key, "1", nx=True, ex=3600)  # 锁1小时过期
    if not acquired:
        logger.info("其他实例正在执行清理任务，跳过")
        return

    try:
        cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
        old_runs = await self.test_run_repo.get_completed_before(cutoff)

        cleaned_count = 0
        for run in old_runs:
            try:
                if run.report_storage_path:
                    path = Path(run.report_storage_path)
                    if path.exists():
                        path.unlink()
                        logger.info(f"已删除过期报告文件: {run.report_storage_path}")

                await self.test_run_repo.delete(run.id)
                cleaned_count += 1
            except Exception as e:
                logger.error(f"清理报告 {run.id} 失败: {e}")

        logger.info(f"清理完成，共删除 {cleaned_count} 个过期报告")
    finally:
        await self.redis_client.delete(lock_key)

async def cleanup_orphaned_drafts(self, orphan_days: int = 7):
    """清理超过 orphan_days 天未审核的草稿（多实例部署防重复执行：分布式锁）"""
    lock_key = "scheduler:cleanup_drafts"
    acquired = await self.redis_client.set(lock_key, "1", nx=True, ex=3600)
    if not acquired:
        logger.info("其他实例正在执行草稿清理任务，跳过")
        return

    try:
        cutoff = datetime.now(timezone.utc) - timedelta(days=orphan_days)
        old_drafts = await self.test_case_draft_repo.get_unreviewed_before(cutoff)

        cleaned_count = 0
        for draft in old_drafts:
            try:
                await self.test_case_draft_repo.delete(draft.id)
                cleaned_count += 1
            except Exception as e:
                logger.error(f"清理草稿 {draft.id} 失败: {e}")

        logger.info(f"清理完成，共删除 {cleaned_count} 个过期草稿")
    finally:
        await self.redis_client.delete(lock_key)
```

**补充 Repository 方法:**
```python
# src/repository/test_run_repository.py
from datetime import datetime
from typing import List
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.models.rag import TestRun, TestRunStatus

async def get_completed_before(self, session: AsyncSession, cutoff: datetime) -> List[TestRun]:
    result = await session.execute(
        select(TestRun).where(
            TestRun.status == TestRunStatus.COMPLETED,
            TestRun.completed_at < cutoff
        )
    )
    return list(result.scalars().all())

# src/repository/test_case_draft_repository.py
async def get_unreviewed_before(self, session: AsyncSession, cutoff: datetime) -> List[TestCaseDraft]:
    result = await session.execute(
        select(TestCaseDraft).where(
            TestCaseDraft.status == "draft",
            TestCaseDraft.created_at < cutoff,
            TestCaseDraft.reviewed_at == None
        )
    )
    return list(result.scalars().all())
```

---

#### Task 2.3.4: 实现报告导出功能
**Files:**
- Modify: `src/service/rag_report_service.py` (新增导出方法)
- Modify: `Dockerfile` (新增PDF依赖)
- Test: `tests/service/test_rag_report_service.py::test_export_report`

- [ ] **Step 1: 编写导出测试用例**
```python
@pytest.mark.asyncio
async def test_export_report():
    from src.service.rag_report_service import rag_report_service
    from src.models.rag import ReportExportFormat
    
    # Markdown导出
    md_content = await rag_report_service.export_report(run_id=1, format=ReportExportFormat.MARKDOWN)
    assert md_content.startswith("# RAG测试报告")
    
    # JSON导出
    json_content = await rag_report_service.export_report(run_id=1, format=ReportExportFormat.JSON)
    assert "overall_metrics" in json.loads(json_content)
```

- [ ] **Step 2: 实现导出逻辑**
在`RagReportService`中新增方法：
```python
from src.models.rag import ReportExportFormat
import json

async def export_report(self, run_id: int, format: ReportExportFormat) -> str:
    """导出报告"""
    test_run = await self.test_run_repo.get_by_id(run_id)
    if not test_run:
        raise ValueError(f"测试运行 {run_id} 不存在")
    
    if format == ReportExportFormat.MARKDOWN:
        if not test_run.report_storage_path or not Path(test_run.report_storage_path).exists():
            # 如果报告不存在，重新生成
            report = await self.generate_report(run_id)
            return report["content"]
        with open(test_run.report_storage_path, "r", encoding="utf-8") as f:
            return f.read()
    
    elif format == ReportExportFormat.JSON:
        results = await self.test_run_result_repo.list_by_test_run_id(run_id)
        # 重新计算聚合指标（export_report 为独立方法作用域）
        total_cases = len(results)
        avg_mrr = sum(r.mrr for r in results) / total_cases if total_cases > 0 else 0.0
        ndcg_values = [float(r.ndcg) for r in results if r.ndcg is not None]
        avg_ndcg = sum(ndcg_values) / len(ndcg_values) if ndcg_values else 0.0
        precision_values = [float(r.precision) for r in results if r.precision is not None]
        avg_precision = sum(precision_values) / len(precision_values) if precision_values else 0.0
        recall_values = [float(r.recall) for r in results if r.recall is not None]
        avg_recall = sum(recall_values) / len(recall_values) if recall_values else 0.0

        data = {
            "run_id": run_id,
            "name": test_run.name,
            "completed_at": test_run.completed_at.isoformat() if test_run.completed_at else None,
            "overall_metrics": {
                "avg_precision": avg_precision,
                "avg_recall": avg_recall,
                "avg_mrr": avg_mrr,
                "avg_ndcg": avg_ndcg
            },
            "results": [
                {
                    "test_case_id": r.test_case_id,
                    "query": r.test_case.query,
                    "mrr": float(r.mrr),
                    "ndcg": float(r.ndcg) if r.ndcg is not None else None,
                    "precision": float(r.precision) if r.precision is not None else None,
                    "recall": float(r.recall) if r.recall is not None else None,
                    "hit_rate_1": float(r.hit_rate_1),
                    "hit_rate_3": float(r.hit_rate_3),
                    "hit_rate_5": float(r.hit_rate_5),
                    "retrieved_docs": r.retrieved_doc_ids,
                    "relevant_docs": r.relevant_doc_ids
                } for r in results
            ]
        }
        return json.dumps(data, ensure_ascii=False, indent=2)
    
    elif format == ReportExportFormat.PDF:
        try:
            from weasyprint import HTML, CSS
            import markdown
            
            md_content = await self.export_report(run_id, ReportExportFormat.MARKDOWN)
            html_content = markdown.markdown(md_content, extensions=['tables', 'fenced_code'])
            
            # 注入中文字体 CSS，确保 WeasyPrint 正确渲染中文
            chinese_css = CSS(string='''
                @font-face {
                    font-family: "Noto Sans CJK SC";
                    src: local("Noto Sans CJK SC"), local("Noto Sans SC"), local("Microsoft YaHei"), local("SimHei");
                }
                body {
                    font-family: "Noto Sans CJK SC", "Noto Sans SC", "Microsoft YaHei", "SimHei", sans-serif;
                    font-size: 12pt;
                    line-height: 1.6;
                }
                table {
                    border-collapse: collapse;
                    width: 100%;
                    margin: 1em 0;
                }
                th, td {
                    border: 1px solid #ddd;
                    padding: 8px;
                    text-align: left;
                }
                th {
                    background-color: #f5f5f5;
                    font-weight: bold;
                }
                code {
                    font-family: "Courier New", monospace;
                    background-color: #f5f5f5;
                    padding: 2px 4px;
                    border-radius: 3px;
                }
                pre {
                    background-color: #f5f5f5;
                    padding: 12px;
                    border-radius: 4px;
                    overflow-x: auto;
                }
                @page {
                    size: A4;
                    margin: 2cm;
                }
            ''')
            
            pdf_bytes = HTML(string=html_content).write_pdf(stylesheets=[chinese_css])
            return pdf_bytes
        except ImportError:
            raise RuntimeError("PDF导出依赖未安装，请安装weasyprint和相关依赖")
```

> **FastAPI导出接口适配示例**:
> ```python
> from fastapi.responses import StreamingResponse, Response
> from io import BytesIO
> 
> @router.get("/reports/{run_id}/export")
> async def export_report(
>     run_id: int,
>     format: ReportExportFormat = Query(ReportExportFormat.MARKDOWN),
>     service: RagReportService = Depends(rag_report_service)
> ):
>     content = await service.export_report(run_id, format)
>     
>     if format == ReportExportFormat.PDF:
>         return StreamingResponse(
>             BytesIO(content),
>             media_type="application/pdf",
>             headers={"Content-Disposition": f"attachment; filename=rag_report_{run_id}.pdf"}
>         )
>     elif format == ReportExportFormat.JSON:
>         return Response(content, media_type="application/json")
>     else:
>         return Response(content, media_type="text/markdown", headers={"Content-Disposition": f"attachment; filename=rag_report_{run_id}.md"})
> ```

- [ ] **Step 3: Dockerfile新增PDF依赖（含中文字体）**
```dockerfile
# PDF导出系统依赖 + 中文字体
RUN apt-get update && apt-get install -y \
    libpango-1.0-0 \
    libcairo2 \
    libgirepository1.0-dev \
    fonts-noto-cjk \
    fontconfig \
    && fc-cache -fv \
    && rm -rf /var/lib/apt/lists/*

# 验证中文字体安装
RUN fc-list :lang=zh | grep -i "noto" && echo "✅ 中文字体安装成功" || echo "⚠️ 中文字体未找到"

# Python依赖
RUN pip install weasyprint markdown
```

> **Alpine镜像依赖兼容**:
> ```dockerfile
> RUN apk add --no-cache \
>     pango \
>     cairo \
>     gobject-introspection-dev \
>     font-noto-cjk \
>     fontconfig \
>     && fc-cache -fv \
>     && fc-list :lang=zh | grep -i "noto" || echo "⚠️ 中文字体未找到"
> ```

> **PDF导出字体回退策略**:
> 若中文字体未正确安装，WeasyPrint 将按以下顺序回退：
> 1. `Noto Sans CJK SC` (首选)
> 2. `Noto Sans SC` (备选)
> 3. `Microsoft YaHei` (Windows 系统字体)
> 4. `SimHei` (黑体，常见中文字体)
> 5. `sans-serif` (系统默认无衬线字体)

---

**上一阶段：** [执行路径统一](./02-phase-2a-02-execution-path.md)  
**下一阶段：** [测试用例生成优化](./02-phase-2a-04-test-case-generation.md)
