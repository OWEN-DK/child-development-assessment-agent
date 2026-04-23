"""报告查询 API 控制器

提供报告详情、校验结果查询、版本对比等接口
"""

from typing import Optional

from fastapi import APIRouter, Query
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from src.core.database import db_session_factory
from src.models.rag_eval.test_report import RagEvalTestReport
from src.models.rag_eval.test_run import RagEvalTestRun
from src.schemas.common import APIResponse
from src.utils.exceptions import ResourceNotFoundException
from src.utils.serializers import create_serializer, safe_isoformat

router = APIRouter(prefix="/api/v1/rag/test", tags=["RAG Eval Reports"])

serialize_report = create_serializer(
    object,
    {
        "id": None,
        "run_id": None,
        "test_set_id": None,
        "config_version_id": None,
        "status": None,
        "overall_score": None,
        "precision": None,
        "recall": None,
        "f1": None,
        "mrr": None,
        "ndcg": None,
        "validation_results": None,
        "tuning_suggestion_summary": None,
        "created_by": None,
        "created_at": safe_isoformat,
    },
)


@router.get("/reports/{report_id}")
async def get_report(report_id: str):
    """获取报告详情（含6层校验结果）"""
    async with db_session_factory() as session:
        stmt = select(RagEvalTestReport).where(
            RagEvalTestReport.id == report_id
        )
        result = await session.execute(stmt)
        report = result.scalar_one_or_none()

        if not report:
            raise ResourceNotFoundException(message=f"报告不存在: {report_id}")

        return APIResponse.success(data=serialize_report(report))


@router.get("/reports")
async def list_reports(
    test_run_id: Optional[str] = Query(None, description="按测试运行ID查询"),
    test_set_id: Optional[str] = Query(None, description="按测试集ID查询"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """查询报告列表"""
    async with db_session_factory() as session:
        stmt = select(RagEvalTestReport)

        if test_run_id:
            stmt = stmt.where(RagEvalTestReport.run_id == test_run_id)
        if test_set_id:
            stmt = stmt.where(RagEvalTestReport.test_set_id == test_set_id)

        stmt = stmt.order_by(RagEvalTestReport.created_at.desc())

        # 分页
        offset = (page - 1) * page_size
        stmt_page = stmt.offset(offset).limit(page_size)
        result = await session.execute(stmt_page)
        reports = result.scalars().all()

        # 统计总数
        from sqlalchemy import func
        count_stmt = select(func.count()).select_from(RagEvalTestReport)
        if test_run_id:
            count_stmt = count_stmt.where(RagEvalTestReport.run_id == test_run_id)
        if test_set_id:
            count_stmt = count_stmt.where(RagEvalTestReport.test_set_id == test_set_id)
        count_result = await session.execute(count_stmt)
        total = count_result.scalar() or 0

        return APIResponse.success(data={
            "items": [serialize_report(r) for r in reports],
            "total": total,
            "page": page,
            "page_size": page_size,
        })


@router.get("/reports/by-run/{run_id}")
async def get_report_by_run_id(run_id: str):
    """按测试运行ID获取报告"""
    async with db_session_factory() as session:
        stmt = select(RagEvalTestReport).where(
            RagEvalTestReport.run_id == run_id
        )
        result = await session.execute(stmt)
        report = result.scalar_one_or_none()

        if not report:
            raise ResourceNotFoundException(message=f"报告不存在: run_id={run_id}")

        return APIResponse.success(data=serialize_report(report))


@router.get("/reports/{report_id}/validation/{layer}")
async def get_validation_layer(report_id: str, layer: str):
    """获取单层校验详情

    layer: layer1/layer2/layer3/layer4/layer5/layer6
    """
    async with db_session_factory() as session:
        stmt = select(RagEvalTestReport).where(
            RagEvalTestReport.id == report_id
        )
        result = await session.execute(stmt)
        report = result.scalar_one_or_none()

        if not report:
            raise ResourceNotFoundException(message=f"报告不存在: {report_id}")

        validation_results = report.validation_results or []
        layer_key_map = {
            "layer1": 1,
            "layer2": 2,
            "layer3": 3,
            "layer4": 4,
            "layer5": 5,
            "layer6": 6,
        }
        target_layer = layer_key_map.get(layer)

        if not target_layer:
            raise ResourceNotFoundException(message=f"未知校验层: {layer}")

        for vr in validation_results:
            if vr.get("layer") == target_layer:
                return APIResponse.success(data=vr)

        raise ResourceNotFoundException(message=f"校验层结果不存在: {layer}")


@router.get("/reports/compare")
async def compare_reports(
    report_id_1: str = Query(..., description="第一个报告ID"),
    report_id_2: str = Query(..., description="第二个报告ID"),
):
    """对比两个版本的报告"""
    async with db_session_factory() as session:
        stmt = select(RagEvalTestReport).where(
            RagEvalTestReport.id.in_([report_id_1, report_id_2])
        )
        result = await session.execute(stmt)
        reports = result.scalars().all()

        if len(reports) != 2:
            raise ResourceNotFoundException(message="一个或两个报告不存在")

        r1, r2 = reports[0], reports[1]

        # 指标对比
        metrics_diff = {
            "precision": {
                "report_1": r1.precision,
                "report_2": r2.precision,
                "delta": (r2.precision or 0) - (r1.precision or 0),
            },
            "recall": {
                "report_1": r1.recall,
                "report_2": r2.recall,
                "delta": (r2.recall or 0) - (r1.recall or 0),
            },
            "f1": {
                "report_1": r1.f1,
                "report_2": r2.f1,
                "delta": (r2.f1 or 0) - (r1.f1 or 0),
            },
            "mrr": {
                "report_1": r1.mrr,
                "report_2": r2.mrr,
                "delta": (r2.mrr or 0) - (r1.mrr or 0),
            },
            "ndcg": {
                "report_1": r1.ndcg,
                "report_2": r2.ndcg,
                "delta": (r2.ndcg or 0) - (r1.ndcg or 0),
            },
            "overall_score": {
                "report_1": r1.overall_score,
                "report_2": r2.overall_score,
                "delta": (r2.overall_score or 0) - (r1.overall_score or 0),
            },
        }

        # 配置对比
        config_diff = {}
        if r1.config_version and r2.config_version:
            config1 = r1.config_version.config_snapshot or {}
            config2 = r2.config_version.config_snapshot or {}
            all_keys = set(config1.keys()) | set(config2.keys())
            for key in all_keys:
                if config1.get(key) != config2.get(key):
                    config_diff[key] = {
                        "report_1": config1.get(key),
                        "report_2": config2.get(key),
                    }

        # 校验结果对比
        suggestions_diff = {
            "report_1_count": len(r1.tuning_suggestion_summary or []),
            "report_2_count": len(r2.tuning_suggestion_summary or []),
        }

        return APIResponse.success(data={
            "report_1": {
                "id": r1.id,
                "created_at": r1.created_at.isoformat() if r1.created_at else None,
                "config_version_id": r1.config_version_id,
            },
            "report_2": {
                "id": r2.id,
                "created_at": r2.created_at.isoformat() if r2.created_at else None,
                "config_version_id": r2.config_version_id,
            },
            "metrics_diff": metrics_diff,
            "config_diff": config_diff,
            "suggestions_diff": suggestions_diff,
        })
