"""复合节点 Repository"""
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from src.models.compound_node import CompoundNode
from src.utils.id_generator import generate_id
from src.utils.logger import logger


class CompoundNodeRepository:
    """复合节点数据访问"""

    def __init__(self, session_factory: async_sessionmaker):
        self._session_factory = session_factory

    async def create(self, tenant_id: str, owner_id: str, name: str,
                     description: str, expanded_nodes: list[dict],
                     internal_edges: list[dict], exposed_ports: dict,
                     is_shared: bool = False) -> CompoundNode:
        """创建复合节点"""
        import json
        config = json.dumps({
            "expanded_nodes": expanded_nodes,
            "internal_edges": internal_edges,
            "exposed_ports": exposed_ports,
        }, ensure_ascii=False)

        async with self._session_factory() as session:
            node = CompoundNode(
                id=generate_id(prefix="cn"),
                tenant_id=tenant_id,
                owner_id=owner_id,
                name=name,
                description=description,
                config_snapshot=config,
                is_shared=is_shared,
            )
            session.add(node)
            await session.commit()
            await session.refresh(node)
            return node

    async def get_by_id(self, node_id: str, tenant_id: str) -> Optional[CompoundNode]:
        """按 ID 查询"""
        async with self._session_factory() as session:
            stmt = select(CompoundNode).where(
                CompoundNode.id == node_id,
                CompoundNode.tenant_id == tenant_id,
            )
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def list_by_tenant(self, tenant_id: str) -> list[CompoundNode]:
        """按租户列出所有复合节点"""
        async with self._session_factory() as session:
            stmt = (
                select(CompoundNode)
                .where(CompoundNode.tenant_id == tenant_id)
                .order_by(CompoundNode.created_at.desc())
            )
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def update(self, node_id: str, tenant_id: str, **kwargs) -> Optional[CompoundNode]:
        """更新复合节点"""
        async with self._session_factory() as session:
            stmt = select(CompoundNode).where(
                CompoundNode.id == node_id,
                CompoundNode.tenant_id == tenant_id,
            )
            result = await session.execute(stmt)
            node = result.scalar_one_or_none()
            if not node:
                return None

            for field, value in kwargs.items():
                if hasattr(node, field):
                    setattr(node, field, value)

            await session.commit()
            await session.refresh(node)
            return node

    async def delete(self, node_id: str, tenant_id: str) -> bool:
        """删除复合节点"""
        from sqlalchemy import delete
        async with self._session_factory() as session:
            stmt = delete(CompoundNode).where(
                CompoundNode.id == node_id,
                CompoundNode.tenant_id == tenant_id,
            )
            result = await session.execute(stmt)
            await session.commit()
            return result.rowcount > 0

    async def export_to_dict(self, node_id: str, tenant_id: str) -> Optional[dict]:
        """导出为字典（供 JSON 导入导出）"""
        import json
        node = await self.get_by_id(node_id, tenant_id)
        if not node:
            return None
        return json.loads(node.config_snapshot)

    async def import_from_dict(self, tenant_id: str, owner_id: str,
                               name: str, config: dict,
                               description: str = "") -> CompoundNode:
        """从字典导入"""
        return await self.create(
            tenant_id=tenant_id,
            owner_id=owner_id,
            name=name,
            description=description,
            expanded_nodes=config.get("expanded_nodes", []),
            internal_edges=config.get("internal_edges", []),
            exposed_ports=config.get("exposed_ports", {}),
        )
