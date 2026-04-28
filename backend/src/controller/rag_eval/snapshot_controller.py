"""快照管理控制器"""

from fastapi import APIRouter, Body, Path

from src.schemas.common import APIResponse
from src.schemas.rag_eval.snapshot import SnapshotCreate
from src.service.rag_eval.run.snapshot_manager import SnapshotManager


class SnapshotController:
    """知识库快照管理端点"""

    def __init__(self, snapshot_manager: SnapshotManager):
        self._snapshot = snapshot_manager

    def register(self, router: APIRouter) -> None:
        router.add_api_route("/snapshots", self.create_snapshot, methods=["POST"])
        router.add_api_route("/snapshots", self.list_snapshots, methods=["GET"])
        router.add_api_route("/snapshots/{snapshot_id}", self.get_snapshot, methods=["GET"])
        router.add_api_route("/snapshots/{snapshot_id}/restore", self.restore_snapshot, methods=["POST"])

    async def create_snapshot(self, body: SnapshotCreate = Body(default_factory=SnapshotCreate)):
        result = await self._snapshot.create_snapshot(
            name=body.name, description=body.description,
        )
        return APIResponse.success(result.model_dump(mode="json"))

    async def list_snapshots(self):
        result = await self._snapshot.list_snapshots()
        return APIResponse.success([r.model_dump(mode="json") for r in result])

    async def get_snapshot(self, snapshot_id: str = Path(...)):
        result = await self._snapshot.get_snapshot(snapshot_id)
        return APIResponse.success(result.model_dump(mode="json"))

    async def restore_snapshot(self, snapshot_id: str = Path(...)):
        await self._snapshot.restore_snapshot(snapshot_id)
        return APIResponse.success(None)
