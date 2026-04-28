"""调优建议控制器"""

from fastapi import APIRouter, Body, Path, Query

from src.schemas.common import APIResponse
from src.service.rag_eval.tuning.config_changer import ConfigChanger
from src.service.rag_eval.tuning.facade import TuningEngineFacade
from src.utils.exceptions import AppException
from src.utils.orm_mapper import OrmMapper


class TuningController:
    """调优建议与配置版本管理端点"""

    def __init__(
        self,
        tuning_engine: TuningEngineFacade,
        config_changer: ConfigChanger,
    ):
        self._engine = tuning_engine
        self._changer = config_changer

    def register(self, router: APIRouter) -> None:
        router.add_api_route("/runs/{run_id}/tuning", self.get_suggestions, methods=["GET"])
        router.add_api_route("/tuning/{suggestion_id}/adopt", self.adopt, methods=["POST"])
        router.add_api_route("/tuning/{suggestion_id}/reject", self.reject, methods=["POST"])
        router.add_api_route("/tuning/{suggestion_id}/ignore", self.ignore, methods=["POST"])
        router.add_api_route("/config-versions", self.list_config_versions, methods=["GET"])
        router.add_api_route("/config-versions/{version_id}/rollback", self.rollback, methods=["POST"])

    async def get_suggestions(self, run_id: str = Path(...)):
        result = await self._engine.get_suggestions(run_id)
        return APIResponse.success([r.model_dump(mode="json") for r in result])

    async def adopt(self, suggestion_id: str = Path(...)):
        result = await self._engine.adopt(suggestion_id)
        return APIResponse.success(result.model_dump(mode="json"))

    async def reject(
        self,
        suggestion_id: str = Path(...),
        body: dict = Body(default_factory=dict),
    ):
        reason = body.get("reason")
        await self._engine.reject(suggestion_id, reason)
        return APIResponse.success(None)

    async def ignore(self, suggestion_id: str = Path(...)):
        await self._engine.ignore(suggestion_id)
        return APIResponse.success(None)

    async def list_config_versions(
        self,
        page: int = Query(1, ge=1),
        page_size: int = Query(20, ge=1, le=100),
    ):
        from src.repository.rag_eval.config_version_repository import ConfigVersionRepository
        from src.schemas.rag_eval.tuning import ConfigVersionRead
        repo = ConfigVersionRepository()
        skip = (page - 1) * page_size
        orms = await repo.get_version_history(skip, page_size)
        return APIResponse.success(OrmMapper.to_read_list(orms, ConfigVersionRead))

    async def rollback(
        self,
        version_id: str = Path(...),
        body: dict = Body(default_factory=dict),
    ):
        """回滚至指定配置版本

        通过 change_set_id 回滚，需要变更集中记录目标版本号。
        如果没有变更集，直接创建新的 ConfigVersion 快照恢复。
        """
        reason = body.get("reason", "手动回滚")
        await self._changer.rollback(version_id, reason)
        return APIResponse.success(None)
