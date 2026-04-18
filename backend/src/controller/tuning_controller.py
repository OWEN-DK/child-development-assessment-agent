"""调参建议 API 控制器"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
from src.config import config_manager
from src.utils.logger import logger
from src.models.rag_eval.enums import RagEvalIgnoreScope
from src.core.database import async_session_factory
from src.service.config_change_set_service import config_change_set_service
from src.core.config.cache import ConfigCache

router = APIRouter(prefix="/api/v1/rag/test", tags=["调参建议"])


class PreviewRequest(BaseModel):
    run_id: str
    param_name: str
    suggested_value: float


class PreviewResponse(BaseModel):
    predicted_metrics: Optional[dict] = None
    based_on_history: bool = False
    message: str


class ApplyRequest(BaseModel):
    run_id: str
    suggestion_ids: Optional[List[str]] = None


class ApplyResponse(BaseModel):
    new_config_version_id: str
    applied_params: dict


class IgnoreSuggestionRequest(BaseModel):
    """忽略调优建议请求"""

    scope: RagEvalIgnoreScope
    reason: Optional[str] = None
    test_set_id: str
    report_id: Optional[str] = None
    param_name: str


class SuggestionResponse(BaseModel):
    """调优建议响应"""

    id: str
    param_name: str
    current_value: Optional[dict] = None
    suggested_value: Optional[dict] = None
    action: Optional[str] = None
    reason: Optional[str] = None
    expected_effect: Optional[dict] = None
    priority: Optional[str] = None
    source: Optional[str] = None
    applied: bool = False


class IgnoreSuggestionResponse(BaseModel):
    """忽略建议响应"""

    message: str
    suggestion_id: str


class IgnoredSuggestionItem(BaseModel):
    """已忽略建议项"""

    id: str
    param_name: str
    name_zh: Optional[str] = None
    suggestion_type: str
    ignore_scope: str
    ignored_at: Optional[datetime] = None
    ignored_by: Optional[str] = None
    ignore_reason: Optional[str] = None
    restored: bool
    restored_at: Optional[datetime] = None


class IgnoredSuggestionsResponse(BaseModel):
    """已忽略建议列表响应"""

    items: List[IgnoredSuggestionItem]
    total: int


class RestoreIgnoredSuggestionResponse(BaseModel):
    """恢复忽略建议响应"""

    id: str
    restored: bool
    restored_at: Optional[datetime] = None
    message: str


class DeleteIgnoredSuggestionResponse(BaseModel):
    """删除忽略建议响应"""

    id: str
    message: str


class PromptItem(BaseModel):
    """提示词变更项"""

    key: str
    version_string: str
    content: str
    summary: Optional[str] = None


class ConfigChangeSetRequest(BaseModel):
    """创建配置变更集请求"""

    config_snapshot: dict
    prompts: List[PromptItem] = []
    change_summary: Optional[str] = None


class ConfigChangeSetResponse(BaseModel):
    """配置变更集响应"""

    id: str
    change_set_label: str
    config_version_id: Optional[str] = None
    status: str
    created_at: datetime


class TuningController:
    """调参建议 API 控制器"""

    def __init__(self, tuning_engine, suggestion_service=None):
        """初始化控制器"""
        self.tuning_engine = tuning_engine
        self.config_mgr = config_manager
        self.test_run_repo = tuning_engine.test_run_repo
        self.suggestion_service = suggestion_service

    def register_routes(self, app):
        """注册路由"""

        @router.get("/run/{run_id}/tuning-suggestions")
        async def get_tuning_suggestions(run_id: str):
            """获取指定测试运行的调参建议"""
            try:
                response = await self.tuning_engine.generate_suggestions(run_id)
                return response
            except ValueError as e:
                raise HTTPException(status_code=404, detail=str(e))
            except Exception as e:
                logger.error(f"获取调参建议失败: {e}")
                raise HTTPException(status_code=500, detail="内部服务器错误")

        @router.post("/tuning-suggestions/preview")
        async def preview_suggestion(req: PreviewRequest):
            """预览应用某条建议后的预期指标变化"""
            history_runs = await self.test_run_repo.get_completed_runs(limit=50)
            matching_changes = []

            for run in history_runs:
                old_snap = await self.config_mgr.get_version_config(
                    getattr(run, "previous_config_version_id", None)
                )
                new_snap = await self.config_mgr.get_version_config(
                    run.config_version_id
                )

                if old_snap and new_snap:
                    old_val = old_snap.get(req.param_name)
                    new_val = new_snap.get(req.param_name)

                    if old_val is not None and new_val is not None:
                        matching_changes.append(
                            {
                                "from": old_val,
                                "to": new_val,
                                "recall": getattr(run, "overall_recall", 0),
                                "precision": getattr(run, "overall_precision", 0),
                            }
                        )

            if matching_changes:
                recalls = sorted([c["recall"] for c in matching_changes])
                precisions = sorted([c["precision"] for c in matching_changes])

                def median(values: list) -> float:
                    n = len(values)
                    if n % 2 == 0:
                        return (values[n // 2 - 1] + values[n // 2]) / 2
                    return values[n // 2]

                predicted = {
                    "overall_recall": round(median(recalls), 4),
                    "overall_precision": round(median(precisions), 4),
                }
                return PreviewResponse(
                    predicted_metrics=predicted,
                    based_on_history=True,
                    message=f"基于 {len(matching_changes)} 次历史变更的中位数预测",
                )

            return PreviewResponse(
                predicted_metrics=None,
                based_on_history=False,
                message="基于规则的预期效果",
            )

        @router.post("/tuning-suggestions/apply")
        async def apply_suggestions(req: ApplyRequest):
            """一键应用建议参数到当前配置版本"""
            suggestions_response = await self.tuning_engine.generate_suggestions(
                req.run_id
            )

            applied_params = {}
            all_suggestions = suggestions_response.rule_engine_suggestions + (
                suggestions_response.llm_diagnosis.recommendations
                if suggestions_response.llm_diagnosis
                else []
            )

            for s in all_suggestions:
                if req.suggestion_ids and s.id not in req.suggestion_ids:
                    continue

                if s.safe_range:
                    min_val, max_val = s.safe_range
                    if not (min_val <= s.suggested_value <= max_val):
                        logger.warning(
                            f"建议值 {s.suggested_value} 超出安全范围 [{min_val}, {max_val}],跳过"
                        )
                        continue

                applied_params[s.param_name] = s.suggested_value

            if not applied_params:
                raise HTTPException(status_code=400, detail="无有效参数可应用")

            current_config = self.config_mgr.get_full_config()
            new_config = {**current_config, **applied_params}

            try:
                new_version_id = await self.config_mgr.create_version(
                    config_data=new_config,
                    description=f"调参建议应用 (run_id={req.run_id})",
                )
            except Exception as e:
                logger.error(f"创建配置版本失败: {e}")
                raise HTTPException(status_code=500, detail="创建配置版本失败")

            return ApplyResponse(
                new_config_version_id=new_version_id,
                applied_params=applied_params,
            )

        @router.get(
            "/reports/{report_id}/suggestions", response_model=List[SuggestionResponse]
        )
        async def get_report_suggestions(report_id: str, test_set_id: str):
            """获取指定报告的未忽略调优建议"""
            if not self.suggestion_service:
                raise HTTPException(status_code=501, detail="建议服务未初始化")

            try:
                from src.core.database import async_session_factory

                async with async_session_factory() as session:
                    suggestions = await self.suggestion_service.get_active_suggestions(
                        report_id=report_id,
                        test_set_id=test_set_id,
                        session=session,
                    )

                    return [
                        SuggestionResponse(
                            id=s.id,
                            param_name=s.param_name,
                            current_value=s.current_value,
                            suggested_value=s.suggested_value,
                            action=s.action,
                            reason=s.reason,
                            expected_effect=s.expected_effect,
                            priority=s.priority,
                            source=s.source.value if s.source else None,
                            applied=s.applied,
                        )
                        for s in suggestions
                    ]
            except ValueError as e:
                raise HTTPException(status_code=404, detail=str(e))
            except Exception as e:
                logger.error(f"获取报告建议失败: {e}")
                raise HTTPException(status_code=500, detail="内部服务器错误")

        @router.post(
            "/suggestions/{suggestion_id}/ignore",
            response_model=IgnoreSuggestionResponse,
        )
        async def ignore_suggestion(suggestion_id: str, req: IgnoreSuggestionRequest):
            """忽略调优建议"""
            if not self.suggestion_service:
                raise HTTPException(status_code=501, detail="建议服务未初始化")

            try:
                from src.core.database import async_session_factory

                async with async_session_factory() as session:
                    await self.suggestion_service.ignore_suggestion(
                        suggestion_id=suggestion_id,
                        scope=req.scope,
                        reason=req.reason,
                        session=session,
                        test_set_id=req.test_set_id,
                        report_id=req.report_id,
                        param_name=req.param_name,
                    )

                    return IgnoreSuggestionResponse(
                        message="建议已忽略",
                        suggestion_id=suggestion_id,
                    )
            except Exception as e:
                logger.error(f"忽略建议失败: {e}")
                raise HTTPException(status_code=500, detail="内部服务器错误")

        @router.get(
            "/ignored-suggestions",
            response_model=IgnoredSuggestionsResponse,
        )
        async def get_ignored_suggestions(
            test_set_id: str, report_id: Optional[str] = None
        ):
            """获取已忽略建议列表"""
            if not self.suggestion_service:
                raise HTTPException(status_code=501, detail="建议服务未初始化")

            try:
                from src.core.database import async_session_factory
                from src.service.ignored_suggestion_service import (
                    IgnoredSuggestionService,
                )

                ignored_service = IgnoredSuggestionService()

                async with async_session_factory() as session:
                    ignored_list = await ignored_service.get_ignored_suggestions(
                        test_set_id=test_set_id,
                        report_id=report_id,
                        session=session,
                    )

                    items = [
                        IgnoredSuggestionItem(
                            id=item.id,
                            param_name=item.param_name,
                            suggestion_type=item.suggestion_type.value,
                            ignore_scope=item.ignore_scope.value,
                            ignored_at=item.ignored_at,
                            ignored_by=item.ignored_by,
                            ignore_reason=item.ignore_reason,
                            restored=item.restored,
                            restored_at=item.restored_at,
                        )
                        for item in ignored_list
                    ]

                    return IgnoredSuggestionsResponse(
                        items=items,
                        total=len(items),
                    )
            except Exception as e:
                logger.error(f"获取忽略建议列表失败: {e}")
                raise HTTPException(status_code=500, detail="内部服务器错误")

        @router.post(
            "/ignored-suggestions/{suggestion_id}/restore",
            response_model=RestoreIgnoredSuggestionResponse,
        )
        async def restore_ignored_suggestion(suggestion_id: str):
            """恢复已忽略建议"""
            if not self.suggestion_service:
                raise HTTPException(status_code=501, detail="建议服务未初始化")

            try:
                from src.core.database import async_session_factory
                from src.service.ignored_suggestion_service import (
                    IgnoredSuggestionService,
                )

                ignored_service = IgnoredSuggestionService()

                async with async_session_factory() as session:
                    restored_record = await ignored_service.restore_ignored_suggestion(
                        suggestion_id=suggestion_id,
                        session=session,
                    )

                    return RestoreIgnoredSuggestionResponse(
                        id=restored_record.id,
                        restored=restored_record.restored,
                        restored_at=restored_record.restored_at,
                        message="已恢复，推荐将重新出现在推荐列表中",
                    )
            except ValueError as e:
                raise HTTPException(status_code=404, detail=str(e))
            except Exception as e:
                logger.error(f"恢复忽略建议失败: {e}")
                raise HTTPException(status_code=500, detail="内部服务器错误")

        @router.delete(
            "/ignored-suggestions/{suggestion_id}",
            response_model=DeleteIgnoredSuggestionResponse,
        )
        async def delete_ignored_suggestion(suggestion_id: str):
            """删除忽略记录"""
            if not self.suggestion_service:
                raise HTTPException(status_code=501, detail="建议服务未初始化")

            try:
                from src.core.database import async_session_factory
                from src.service.ignored_suggestion_service import (
                    IgnoredSuggestionService,
                )

                ignored_service = IgnoredSuggestionService()

                async with async_session_factory() as session:
                    await ignored_service.delete_ignored_suggestion(
                        suggestion_id=suggestion_id,
                        session=session,
                    )

                    return DeleteIgnoredSuggestionResponse(
                        id=suggestion_id,
                        message="已删除",
                    )
            except ValueError as e:
                raise HTTPException(status_code=404, detail=str(e))
            except Exception as e:
                logger.error(f"删除忽略记录失败: {e}")
                raise HTTPException(status_code=500, detail="内部服务器错误")

        @router.post(
            "/config-change-sets",
            response_model=ConfigChangeSetResponse,
        )
        async def create_config_change_set(
            req: ConfigChangeSetRequest,
            user=Depends(lambda: None),  # 占位，实际应从认证中间件获取
        ):
            """创建配置变更集（原子保存配置 + 提示词版本）

            事务提交后发布 Redis 事件，通知其他实例刷新缓存。
            """
            if not req.config_snapshot:
                raise HTTPException(status_code=400, detail="配置快照不能为空")

            user_id = getattr(user, "id", "system") if user else "system"

            try:
                async with async_session_factory() as session:
                    change_set = await config_change_set_service.save_config_change_set(
                        config_data=req.config_snapshot,
                        prompt_data=[p.model_dump() for p in req.prompts],
                        user_id=user_id,
                        session=session,
                        change_summary=req.change_summary,
                    )

                    # 事务已提交，发布 Redis 事件
                    try:
                        from src.core.redis_client import RedisClient

                        redis_client = RedisClient.get_client()
                        await redis_client.publish(
                            "config_changed",
                            f"change_set_id={change_set.id}",
                        )
                        logger.info(
                            f"已发布 config_changed 事件: change_set_id={change_set.id}"
                        )
                    except Exception as e:
                        logger.warning(f"发布 Redis 事件失败（不影响主流程）: {e}")

                    # 刷新本地缓存
                    try:
                        cache = ConfigCache.get_instance()
                        await cache.reload()
                    except Exception as e:
                        logger.warning(f"刷新 ConfigCache 失败: {e}")

                    return ConfigChangeSetResponse(
                        id=change_set.id,
                        change_set_label=change_set.change_set_label,
                        config_version_id=change_set.config_version_id,
                        status=change_set.status.value,
                        created_at=change_set.created_at,
                    )
            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"创建配置变更集失败: {e}")
                raise HTTPException(status_code=500, detail="创建配置变更集失败")

        app.include_router(router)
