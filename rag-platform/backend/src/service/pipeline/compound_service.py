"""复合节点服务

复合节点是将固定节点组合保存为可复用单元（拖一次 = 部署一组节点）。
展开态显示内部节点，折叠态显示为节点块。
"""
import json
from typing import Optional

from sqlalchemy.ext.asyncio import async_sessionmaker

from src.repository.pipeline.compound_repo import CompoundNodeRepository
from src.schemas.pipeline.compound import (
    CompoundNodeCreate,
    CompoundNodeImport,
    CompoundNodeRead,
)
from src.core.auth.exceptions import AuthorizationError
from src.utils.logger import logger


class CompoundNodeService:
    """复合节点服务"""

    def __init__(self, session_factory: async_sessionmaker):
        self._repo = CompoundNodeRepository(session_factory)

    async def create(
        self, data: CompoundNodeCreate,
        tenant_id: str, owner_id: str,
    ) -> CompoundNodeRead:
        """创建复合节点"""
        node = await self._repo.create(
            tenant_id=tenant_id,
            owner_id=owner_id,
            name=data.name,
            description=data.description or "",
            expanded_nodes=data.expanded_nodes,
            internal_edges=data.internal_edges,
            exposed_ports=data.exposed_ports,
        )
        return self._to_read(node)

    async def list_nodes(self, tenant_id: str) -> list[CompoundNodeRead]:
        """列出复合节点"""
        nodes = await self._repo.list_by_tenant(tenant_id)
        return [self._to_read(n) for n in nodes]

    async def get(self, node_id: str, tenant_id: str) -> Optional[CompoundNodeRead]:
        """获取复合节点详情"""
        node = await self._repo.get_by_id(node_id, tenant_id)
        return self._to_read(node) if node else None

    async def update(
        self, node_id: str, tenant_id: str,
        data: dict,
    ) -> Optional[CompoundNodeRead]:
        """更新复合节点"""
        node = await self._repo.update(node_id, tenant_id, **data)
        return self._to_read(node) if node else None

    async def delete(self, node_id: str, tenant_id: str) -> bool:
        """删除复合节点"""
        return await self._repo.delete(node_id, tenant_id)

    async def export_to_json(self, node_id: str, tenant_id: str) -> Optional[dict]:
        """导出复合节点为 JSON"""
        return await self._repo.export_to_dict(node_id, tenant_id)

    async def import_from_json(
        self, data: CompoundNodeImport,
        tenant_id: str, owner_id: str,
    ) -> CompoundNodeRead:
        """从 JSON 导入复合节点"""
        config = data.data
        name = config.get("name", "导入的复合节点")
        description = config.get("description", "")
        node = await self._repo.import_from_dict(
            tenant_id=tenant_id,
            owner_id=owner_id,
            name=name,
            config=config,
            description=description,
        )
        return self._to_read(node)

    def _to_read(self, node) -> CompoundNodeRead:
        """模型 → 响应实体"""
        config = {}
        node_count = 0
        try:
            config = json.loads(node.config_snapshot) if node.config_snapshot else {}
            node_count = len(config.get("expanded_nodes", []))
        except (json.JSONDecodeError, TypeError):
            pass

        return CompoundNodeRead(
            id=node.id,
            name=node.name,
            description=node.description,
            node_count=node_count,
            is_shared=node.is_shared,
            created_at=node.created_at,
        )
