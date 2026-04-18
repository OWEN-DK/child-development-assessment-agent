"""调参建议 API 控制器"""

from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends

from src.config import config_manager
from src.core.config.cache import ConfigCache
from src.core.database import async_session_factory
from src.models.rag_eval.enums import RagEvalIgnoreScope
from src.schemas import (ApplyRequest, ApplyResponse, ConfigChangeSetRequest,
                         ConfigChangeSetResponse,
                         DeleteIgnoredSuggestionResponse,
                         IgnoredSuggestionItem, IgnoredSuggestionsResponse,
                         IgnoreSuggestionRequest, IgnoreSuggestionResponse,
                         PreviewRequest, PreviewResponse, PromptItem,
                         RestoreIgnoredSuggestionResponse, SuggestionResponse)
from src.service.config_change_set_service import config_change_set_service
from src.utils.exceptions import (ForbiddenException, InvalidParamsException,
                                    ResourceNotFoundException,
                                    ServiceUnavailableException)
from src.utils.logger import logger
from src.utils.response import api_handler

router = APIRouter(prefix="/api/v1/rag/test", tags=["调参建议"])


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
        @api_handler("获取调参建议", exception_map={ValueError: ResourceNotFoundException})
        async def get_tuning_suggestions(run_id: str):
            """获取指定测试运行的调参建议"""
            response = await self.tuning_engine.generate_suggestions(run_id)
            return response

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
        @api_handler("应用调参建议")
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
                raise InvalidParamsException(message="无有效参数可应用")

            current_config = self.config_mgr.get_full_config()
            new_config = {**current_config, **applied_params}

            new_version_id = await self.config_mgr.create_version(
                config_data=new_config,
                description=f"调参建议应用 (run_id={req.run_id})",
            )

            return ApplyResponse(
                new_config_version_id=new_version_id,
                applied_params=applied_params,
            )

        @router.get(
            "/reports/{report_id}/suggestions", response_model=List[SuggestionResponse]
        )
        @api_handler("获取报告建议", exception_map={ValueError: ResourceNotFoundException})
        async def get_report_suggestions(report_id: str, test_set_id: str):
            """获取指定报告的未忽略调优建议"""
            if not self.suggestion_service:
                raise ServiceUnavailableException(message="建议服务未初始化")

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

        @router.post(
            "/suggestions/{suggestion_id}/ignore",
            response_model=IgnoreSuggestionResponse,
        )
        @api_handler("忽略调优建议")
        async def ignore_suggestion(suggestion_id: str, req: IgnoreSuggestionRequest):
            """忽略调优建议"""
            if not self.suggestion_service:
                raise ServiceUnavailableException(message="建议服务未初始化")

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

        @router.get(
            "/ignored-suggestions",
            response_model=IgnoredSuggestionsResponse,
        )
        @api_handler("获取忽略建议列表")
        async def get_ignored_suggestions(
            test_set_id: str, report_id: Optional[str] = None
        ):
            """获取已忽略建议列表"""
            if not self.suggestion_service:
                raise ServiceUnavailableException(message="建议服务未初始化")

            from src.core.database import async_session_factory
            from src.service.ignored_suggestion_service import \
                IgnoredSuggestionService

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

        @router.post(
            "/ignored-suggestions/{suggestion_id}/restore",
            response_model=RestoreIgnoredSuggestionResponse,
        )
        @api_handler("恢复忽略建议", exception_map={ValueError: ResourceNotFoundException})
        async def restore_ignored_suggestion(suggestion_id: str):
            """恢复已忽略建议"""
            if not self.suggestion_service:
                raise ServiceUnavailableException(message="建议服务未初始化")

            from src.core.database import async_session_factory
            from src.service.ignored_suggestion_service import \
                IgnoredSuggestionService

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

        @router.delete(
            "/ignored-suggestions/{suggestion_id}",
            response_model=DeleteIgnoredSuggestionResponse,
        )
        @api_handler("删除忽略记录", exception_map={ValueError: ResourceNotFoundException})
        async def delete_ignored_suggestion(suggestion_id: str):
            """删除忽略记录"""
            if not self.suggestion_service:
                raise ServiceUnavailableException(message="建议服务未初始化")

            from src.core.database import async_session_factory
            from src.service.ignored_suggestion_service import \
                IgnoredSuggestionService

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

        @router.post(
            "/config-change-sets",
            response_model=ConfigChangeSetResponse,
        )
        @api_handler("创建配置变更集")
        async def create_config_change_set(
            req: ConfigChangeSetRequest,
            user=Depends(lambda: None),  # 占位，实际应从认证中间件获取
        ):
            """创建配置变更集（原子保存配置 + 提示词版本）

            事务提交后发布 Redis 事件，通知其他实例刷新缓存。
            """
            if not req.config_snapshot:
                raise InvalidParamsException(message="配置快照不能为空")

            user_id = getattr(user, "id", "system") if user else "system"

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

        app.include_router(router)
