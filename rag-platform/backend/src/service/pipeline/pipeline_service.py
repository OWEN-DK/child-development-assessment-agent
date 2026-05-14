"""管道服务

管道 CRUD、版本管理、校验、回滚。
"""
import json
import uuid
from typing import Optional

from sqlalchemy.ext.asyncio import async_sessionmaker

from src.core.pipeline.compiler import PipelineCompiler
from src.models.pipeline import Pipeline
from src.repository.pipeline.pipeline_repo import PipelineRepository
from src.repository.pipeline.version_repo import PipelineVersionRepository
from src.schemas.pipeline.pipeline import (
    PipelineCreate,
    PipelineList,
    PipelineRead,
    PipelineUpdate,
)
from src.schemas.pipeline.version import (
    PipelineVersionListItem,
    PipelineVersionRead,
    VersionCompareResult,
)
from src.utils.logger import logger


class PipelineService:
    """管道服务"""

    def __init__(self, db_session_factory: async_sessionmaker):
        self.db_session_factory = db_session_factory
        self.pipeline_repo = PipelineRepository(db_session_factory)
        self.version_repo = PipelineVersionRepository(db_session_factory)
        self.compiler = PipelineCompiler()

    async def create(
        self, data: PipelineCreate, tenant_id: str, user_id: str
    ) -> PipelineRead:
        """创建管道"""
        pipeline_id = self._generate_id()

        # 创建管道记录
        pipeline_data = {
            "id": pipeline_id,
            "tenant_id": tenant_id,
            "name": data.name,
            "description": data.description,
            "type": data.type,
            "status": "draft",
            "active_version": 1,
        }
        pipeline = await self.pipeline_repo.create(pipeline_data)

        # 创建初始版本
        version_data = {
            "id": self._generate_id(),
            "pipeline_id": pipeline_id,
            "tenant_id": tenant_id,
            "version_number": 1,
            "change_log": "初始版本",
            "config_snapshot": json.dumps({"pipeline": {"id": pipeline_id, "type": data.type}, "domains": [], "aggregation": {}}),
        }
        await self.version_repo.create(version_data)

        logger.info(f"管道创建成功: {pipeline_id} ({data.name})")
        return self._to_read(pipeline)

    async def get(self, pipeline_id: str, tenant_id: str) -> PipelineRead:
        """获取管道详情"""
        pipeline = await self.pipeline_repo.get_by_id(pipeline_id, tenant_id)
        if not pipeline:
            raise ValueError(f"管道不存在: {pipeline_id}")
        return self._to_read(pipeline)

    async def list(
        self,
        tenant_id: str,
        status: Optional[str] = None,
        keyword: Optional[str] = None,
        skip: int = 0,
        limit: int = 20,
    ) -> PipelineList:
        """列出管道"""
        items = await self.pipeline_repo.list_by_tenant(
            tenant_id=tenant_id,
            status=status,
            keyword=keyword,
            skip=skip,
            limit=limit,
        )
        total = await self.pipeline_repo.count_by_tenant(tenant_id)
        return PipelineList(
            items=[self._to_read(p) for p in items],
            total=total,
        )

    async def update(
        self, pipeline_id: str, data: PipelineUpdate, tenant_id: str
    ) -> PipelineRead:
        """更新管道配置（触发版本递增）"""
        pipeline = await self.pipeline_repo.get_by_id(pipeline_id, tenant_id)
        if not pipeline:
            raise ValueError(f"管道不存在: {pipeline_id}")

        # 更新基本信息
        update_data = data.model_dump(exclude_unset=True, exclude={"config", "change_log"})
        if update_data:
            await self.pipeline_repo.update(pipeline_id, update_data, tenant_id)

        # 如果有新配置，校验并创建新版本
        if data.config is not None:
            # 校验管道配置
            try:
                self.compiler.compile(data.config)
            except Exception as e:
                raise ValueError(f"管道配置校验失败: {e}")

            new_version = await self.version_repo.get_next_version_number(pipeline_id, tenant_id)
            version_data = {
                "id": self._generate_id(),
                "pipeline_id": pipeline_id,
                "tenant_id": tenant_id,
                "version_number": new_version,
                "change_log": data.change_log or f"版本 {new_version}",
                "config_snapshot": json.dumps(data.config),
            }
            await self.version_repo.create(version_data)
            await self.pipeline_repo.update_active_version(pipeline_id, new_version, tenant_id)
            logger.info(f"管道版本递增: {pipeline_id} → v{new_version}")

        return await self.get(pipeline_id, tenant_id)

    async def delete(self, pipeline_id: str, tenant_id: str) -> None:
        """删除管道"""
        # TODO: 检查发布 URL 引用
        pipeline = await self.pipeline_repo.get_by_id(pipeline_id, tenant_id)
        if not pipeline:
            raise ValueError(f"管道不存在: {pipeline_id}")

        # 删除所有版本
        versions = await self.version_repo.list_by_pipeline(pipeline_id, tenant_id)
        for v in versions:
            await self.version_repo.delete(v.id, tenant_id)

        # 删除管道
        await self.pipeline_repo.delete(pipeline_id, tenant_id)
        logger.info(f"管道删除成功: {pipeline_id}")

    async def get_versions(
        self, pipeline_id: str, tenant_id: str
    ) -> list[PipelineVersionListItem]:
        """获取版本列表"""
        versions = await self.version_repo.list_by_pipeline(pipeline_id, tenant_id)
        return [
            PipelineVersionListItem(
                id=v.id,
                version_number=v.version_number,
                change_log=v.change_log,
                created_at=v.created_at,
            )
            for v in versions
        ]

    async def get_version(
        self, pipeline_id: str, version_number: int, tenant_id: str
    ) -> PipelineVersionRead:
        """获取指定版本"""
        version = await self.version_repo.get_by_version(
            pipeline_id, version_number, tenant_id
        )
        if not version:
            raise ValueError(f"版本不存在: v{version_number}")

        return PipelineVersionRead(
            id=version.id,
            pipeline_id=version.pipeline_id,
            version_number=version.version_number,
            change_log=version.change_log,
            config_snapshot=json.loads(version.config_snapshot),
            created_at=version.created_at,
        )

    async def rollback(
        self, pipeline_id: str, target_version: int, tenant_id: str
    ) -> PipelineVersionRead:
        """回滚到指定版本"""
        target = await self.version_repo.get_by_version(
            pipeline_id, target_version, tenant_id
        )
        if not target:
            raise ValueError(f"目标版本不存在: v{target_version}")

        # 创建新版本（复制目标版本的配置）
        new_version = await self.version_repo.get_next_version_number(pipeline_id, tenant_id)
        version_data = {
            "id": self._generate_id(),
            "pipeline_id": pipeline_id,
            "tenant_id": tenant_id,
            "version_number": new_version,
            "change_log": f"回滚到 v{target_version}",
            "config_snapshot": target.config_snapshot,
        }
        await self.version_repo.create(version_data)
        await self.pipeline_repo.update_active_version(pipeline_id, new_version, tenant_id)

        logger.info(f"管道回滚: {pipeline_id} v{target_version} → v{new_version}")
        return await self.get_version(pipeline_id, new_version, tenant_id)

    async def compare(
        self, pipeline_id: str, v1: int, v2: int, tenant_id: str
    ) -> VersionCompareResult:
        """对比两个版本"""
        version1 = await self.version_repo.get_by_version(pipeline_id, v1, tenant_id)
        version2 = await self.version_repo.get_by_version(pipeline_id, v2, tenant_id)

        if not version1 or not version2:
            raise ValueError(f"版本不存在: v{v1} 或 v{v2}")

        config1 = json.loads(version1.config_snapshot)
        config2 = json.loads(version2.config_snapshot)

        # 简化对比：比较节点列表
        nodes1 = {n["id"] for d in config1.get("domains", []) for n in d.get("pipeline", {}).get("nodes", [])}
        nodes2 = {n["id"] for d in config2.get("domains", []) for n in d.get("pipeline", {}).get("nodes", [])}

        return VersionCompareResult(
            v1=v1,
            v2=v2,
            added_nodes=list(nodes2 - nodes1),
            removed_nodes=list(nodes1 - nodes2),
        )

    def _generate_id(self) -> str:
        return str(uuid.uuid4()).replace("-", "")[:24]

    def _to_read(self, pipeline: Pipeline) -> PipelineRead:
        return PipelineRead(
            id=pipeline.id,
            tenant_id=pipeline.tenant_id,
            name=pipeline.name,
            description=pipeline.description,
            type=pipeline.type,
            active_version=pipeline.active_version,
            status=pipeline.status,
            domain_count=0,  # TODO: 从配置中统计
            created_at=pipeline.created_at,
            updated_at=pipeline.updated_at,
        )
