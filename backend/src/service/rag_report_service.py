"""RAG测试报告服务

负责报告生成、删除、导出和定时清理
"""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.config import settings
from src.core.database import db_session_factory
from src.core.rag.metrics_calculator import (calculate_mrr, calculate_ndcg,
                                             calculate_precision,
                                             calculate_recall)
from src.core.redis_client import RedisClient
from src.repository.test_case_repository import (TestRunRepository,
                                                 TestRunResultRepository)
from src.schemas import ReportExportFormat, TestRunStatus
from src.utils.logger import logger


class RagReportService:
    """RAG测试报告服务"""

    def __init__(self):
        self.test_run_repo = TestRunRepository(db_session_factory)
        self.test_run_result_repo = TestRunResultRepository(db_session_factory)
        self.redis_client = RedisClient.get_client()
        self.report_dir = (
            Path(getattr(settings, "rag_storage_dir", "./app_data/rag_storage"))
            / "reports"
        )
        self.report_dir.mkdir(parents=True, exist_ok=True)

    async def generate_report(self, run_id: str) -> dict:
        """生成测试报告（带分布式锁防止并发生成）"""
        lock_key = f"report:generate:{run_id}"

        try:
            acquired = await self.redis_client.set(lock_key, "1", nx=True, ex=60)
            if not acquired:
                raise RuntimeError(f"报告 {run_id} 正在生成中，请勿重复提交")

            async with db_session_factory() as session:
                # 获取测试运行
                test_run = await self.test_run_repo.get_by_id(run_id)
                if not test_run:
                    raise ValueError(f"测试运行 {run_id} 不存在")

                # 获取所有结果
                results = await self.test_run_result_repo.get_by_run_id(run_id)

                if not results:
                    raise ValueError(f"测试运行 {run_id} 无结果数据")

                total_cases = len(results)

                # 计算整体指标
                mrr_values = [float(r.mrr) for r in results if r.mrr is not None]
                avg_mrr = sum(mrr_values) / len(mrr_values) if mrr_values else 0.0

                ndcg_values = [float(r.ndcg) for r in results if r.ndcg is not None]
                avg_ndcg = sum(ndcg_values) / len(ndcg_values) if ndcg_values else 0.0

                precision_values = [
                    float(r.precision) for r in results if r.precision is not None
                ]
                avg_precision = (
                    sum(precision_values) / len(precision_values)
                    if precision_values
                    else 0.0
                )

                recall_values = [
                    float(r.recall) for r in results if r.recall is not None
                ]
                avg_recall = (
                    sum(recall_values) / len(recall_values) if recall_values else 0.0
                )

                hit_rate_1_values = [
                    float(r.hit_rate_1) for r in results if r.hit_rate_1 is not None
                ]
                avg_hit_rate_1 = (
                    sum(hit_rate_1_values) / len(hit_rate_1_values)
                    if hit_rate_1_values
                    else 0.0
                )

                hit_rate_3_values = [
                    float(r.hit_rate_3) for r in results if r.hit_rate_3 is not None
                ]
                avg_hit_rate_3 = (
                    sum(hit_rate_3_values) / len(hit_rate_3_values)
                    if hit_rate_3_values
                    else 0.0
                )

                hit_rate_5_values = [
                    float(r.hit_rate_5) for r in results if r.hit_rate_5 is not None
                ]
                avg_hit_rate_5 = (
                    sum(hit_rate_5_values) / len(hit_rate_5_values)
                    if hit_rate_5_values
                    else 0.0
                )

                # 按领域统计
                domain_stats = {}
                for result in results:
                    # 从test_case获取domain（需要关联查询）
                    # 这里简化处理，实际应该JOIN test_cases表
                    domain = getattr(result, "domain", "未知")

                    if domain not in domain_stats:
                        domain_stats[domain] = {
                            "count": 0,
                            "total_mrr": 0.0,
                            "total_ndcg": 0.0,
                            "ndcg_count": 0,
                            "total_precision": 0.0,
                            "precision_count": 0,
                            "total_recall": 0.0,
                            "recall_count": 0,
                        }

                    stats = domain_stats[domain]
                    stats["count"] += 1

                    if result.mrr is not None:
                        stats["total_mrr"] += float(result.mrr)
                    if result.ndcg is not None:
                        stats["total_ndcg"] += float(result.ndcg)
                        stats["ndcg_count"] += 1
                    if result.precision is not None:
                        stats["total_precision"] += float(result.precision)
                        stats["precision_count"] += 1
                    if result.recall is not None:
                        stats["total_recall"] += float(result.recall)
                        stats["recall_count"] += 1

                # 计算平均值
                for domain in domain_stats:
                    stats = domain_stats[domain]
                    stats["avg_mrr"] = (
                        stats["total_mrr"] / stats["count"]
                        if stats["count"] > 0
                        else 0.0
                    )
                    stats["avg_ndcg"] = (
                        stats["total_ndcg"] / stats["ndcg_count"]
                        if stats["ndcg_count"] > 0
                        else 0.0
                    )
                    stats["avg_precision"] = (
                        stats["total_precision"] / stats["precision_count"]
                        if stats["precision_count"] > 0
                        else 0.0
                    )
                    stats["avg_recall"] = (
                        stats["total_recall"] / stats["recall_count"]
                        if stats["recall_count"] > 0
                        else 0.0
                    )

                # 找出Bad Case（MRR < 0.3）
                bad_cases = [
                    r for r in results if r.mrr is not None and float(r.mrr) < 0.3
                ]

                # 生成Markdown报告
                content = self._generate_markdown_report(
                    test_run=test_run,
                    total_cases=total_cases,
                    avg_mrr=avg_mrr,
                    avg_ndcg=avg_ndcg,
                    avg_precision=avg_precision,
                    avg_recall=avg_recall,
                    avg_hit_rate_1=avg_hit_rate_1,
                    avg_hit_rate_3=avg_hit_rate_3,
                    avg_hit_rate_5=avg_hit_rate_5,
                    domain_stats=domain_stats,
                    bad_cases=bad_cases,
                )

                # 保存报告文件
                date_str = datetime.now(timezone.utc).strftime("%Y%m%d")
                report_path = (
                    self.report_dir
                    / date_str
                    / f"run_{run_id}_{datetime.now(timezone.utc).strftime('%H%M%S')}.md"
                )
                report_path.parent.mkdir(parents=True, exist_ok=True)

                with open(report_path, "w", encoding="utf-8") as f:
                    f.write(content)

                # 更新数据库记录
                from sqlalchemy import update

                stmt = (
                    update(test_run.__class__)
                    .where(test_run.__class__.id == run_id)
                    .values(report_storage_path=str(report_path))
                )
                await session.execute(stmt)
                await session.commit()

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
                        "avg_hit_rate_5": avg_hit_rate_5,
                    },
                    "domain_stats": domain_stats,
                    "bad_case_count": len(bad_cases),
                }

        finally:
            try:
                await self.redis_client.delete(lock_key)
            except Exception:
                pass

    def _generate_markdown_report(
        self,
        test_run,
        total_cases: int,
        avg_mrr: float,
        avg_ndcg: float,
        avg_precision: float,
        avg_recall: float,
        avg_hit_rate_1: float,
        avg_hit_rate_3: float,
        avg_hit_rate_5: float,
        domain_stats: dict,
        bad_cases: list,
    ) -> str:
        """生成Markdown格式报告"""
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
            content += f"{idx + 1}. 用例ID: {case.test_case_id}, 查询: {case.query}, MRR: {float(case.mrr):.4f}\n"

        return content

    async def delete_report(self, run_id: str):
        """物理删除报告"""
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

    async def export_report(self, run_id: str, format: ReportExportFormat) -> Any:
        """导出报告"""
        test_run = await self.test_run_repo.get_by_id(run_id)
        if not test_run:
            raise ValueError(f"测试运行 {run_id} 不存在")

        if format == ReportExportFormat.MARKDOWN:
            if (
                not test_run.report_storage_path
                or not Path(test_run.report_storage_path).exists()
            ):
                # 如果报告不存在，重新生成
                report = await self.generate_report(run_id)
                return report["content"]
            with open(test_run.report_storage_path, "r", encoding="utf-8") as f:
                return f.read()

        elif format == ReportExportFormat.JSON:
            results = await self.test_run_result_repo.get_by_run_id(run_id)
            total_cases = len(results)

            mrr_values = [float(r.mrr) for r in results if r.mrr is not None]
            avg_mrr = sum(mrr_values) / len(mrr_values) if mrr_values else 0.0

            ndcg_values = [float(r.ndcg) for r in results if r.ndcg is not None]
            avg_ndcg = sum(ndcg_values) / len(ndcg_values) if ndcg_values else 0.0

            precision_values = [
                float(r.precision) for r in results if r.precision is not None
            ]
            avg_precision = (
                sum(precision_values) / len(precision_values)
                if precision_values
                else 0.0
            )

            recall_values = [float(r.recall) for r in results if r.recall is not None]
            avg_recall = (
                sum(recall_values) / len(recall_values) if recall_values else 0.0
            )

            data = {
                "run_id": run_id,
                "name": test_run.name,
                "completed_at": test_run.completed_at.isoformat()
                if test_run.completed_at
                else None,
                "overall_metrics": {
                    "avg_precision": avg_precision,
                    "avg_recall": avg_recall,
                    "avg_mrr": avg_mrr,
                    "avg_ndcg": avg_ndcg,
                },
                "results": [
                    {
                        "test_case_id": r.test_case_id,
                        "query": r.query,
                        "mrr": float(r.mrr) if r.mrr is not None else None,
                        "ndcg": float(r.ndcg) if r.ndcg is not None else None,
                        "precision": float(r.precision)
                        if r.precision is not None
                        else None,
                        "recall": float(r.recall) if r.recall is not None else None,
                        "hit_rate_1": float(r.hit_rate_1)
                        if r.hit_rate_1 is not None
                        else 0.0,
                        "hit_rate_3": float(r.hit_rate_3)
                        if r.hit_rate_3 is not None
                        else 0.0,
                        "hit_rate_5": float(r.hit_rate_5)
                        if r.hit_rate_5 is not None
                        else 0.0,
                        "retrieved_docs": r.retrieved_doc_ids or [],
                        "relevant_docs": r.relevant_doc_ids or [],
                    }
                    for r in results
                ],
            }
            return json.dumps(data, ensure_ascii=False, indent=2)

        elif format == ReportExportFormat.PDF:
            try:
                from weasyprint import CSS, HTML

                md_content = await self.export_report(
                    run_id, ReportExportFormat.MARKDOWN
                )
                import markdown

                html_content = markdown.markdown(
                    md_content, extensions=["tables", "fenced_code"]
                )

                chinese_css = CSS(
                    string="""
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
                    @page {
                        size: A4;
                        margin: 2cm;
                    }
                """
                )

                pdf_bytes = HTML(string=html_content).write_pdf(
                    stylesheets=[chinese_css]
                )
                return pdf_bytes
            except ImportError:
                raise RuntimeError("PDF导出依赖未安装，请安装weasyprint和相关依赖")

        else:
            raise ValueError(f"不支持的导出格式: {format}")

    async def cleanup_expired_reports(self, retention_days: int = 30):
        """清理过期报告"""
        lock_key = "scheduler:cleanup_reports"

        try:
            acquired = await self.redis_client.set(lock_key, "1", nx=True, ex=3600)
            if not acquired:
                logger.info("其他实例正在执行清理任务，跳过")
                return

            cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)

            # 查询过期报告
            from sqlalchemy import select

            async with db_session_factory() as session:
                from src.schemas import TestRun

                stmt = select(TestRun).where(
                    TestRun.status == TestRunStatus.COMPLETED,
                    TestRun.completed_at < cutoff,
                )
                result = await session.execute(stmt)
                old_runs = result.scalars().all()

                cleaned_count = 0
                for run in old_runs:
                    try:
                        if run.report_storage_path:
                            path = Path(run.report_storage_path)
                            if path.exists():
                                path.unlink()
                                logger.info(
                                    f"已删除过期报告文件: {run.report_storage_path}"
                                )

                        await self.test_run_repo.delete(run.id)
                        cleaned_count += 1
                    except Exception as e:
                        logger.error(f"清理报告 {run.id} 失败: {e}")

                logger.info(f"清理完成，共删除 {cleaned_count} 个过期报告")

        finally:
            try:
                await self.redis_client.delete(lock_key)
            except Exception:
                pass


# 全局单例
rag_report_service = RagReportService()
