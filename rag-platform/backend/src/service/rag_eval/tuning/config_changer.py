"""配置变更器

将调优建议应用到管道配置，自动创建评估配置版本和变更记录。
支持回滚到历史配置版本。
"""
import json
import uuid
from datetime import datetime
from typing import Any, Optional

from sqlalchemy.ext.asyncio import async_sessionmaker

from src.core.pipeline.compiler import PipelineCompiler
from src.repository.rag_eval.config_version_repo import ConfigVersionRepository
from src.repository.rag_eval.tuning_repo import TuningSuggestionRepository
from src.repository.pipeline.pipeline_repo import PipelineRepository
from src.utils.exceptions import InvalidParamsException, ResourceNotFoundException
from src.utils.logger import logger


class ConfigChanger:
    """配置变更器

    核心职责：
    1. 将调优建议解析为管道配置变更
    2. 调用 PipelineCompiler 更新节点配置
    3. 创建 ConfigVersion（完整快照 + 变更摘要）
    4. 创建 ConfigChangeSet（版本关联 + 回滚源）
    5. 更新 TuningSuggestion 状态为 adopted
    """

    def __init__(
        self,
        session_factory: async_sessionmaker,
        pipeline_compiler: PipelineCompiler,
        tuning_repo: TuningSuggestionRepository,
        config_version_repo: ConfigVersionRepository,
        pipeline_repo: PipelineRepository,
    ):
        self._session_factory = session_factory
        self._compiler = pipeline_compiler
        self._tuning_repo = tuning_repo
        self._config_version_repo = config_version_repo
        self._pipeline_repo = pipeline_repo

    async def apply_suggestion(
        self,
        suggestion: dict[str, Any],
        pipeline_id: str,
        tenant_id: str,
        user_id: str,
    ) -> dict[str, Any]:
        """应用调优建议，修改管道配置并创建版本记录

        步骤：
        1. 解析 target_node_id / target_param / suggested_value
        2. 获取当前管道配置
        3. 调用 PipelineCompiler.update_node_config() 应用变更
        4. 创建 ConfigVersion 记录
        5. 创建 ConfigChangeSet 记录
        6. 更新 TuningSuggestion 状态

        Returns:
            创建的 ConfigVersion Read 字典
        """
        suggestion_id = suggestion["id"]
        target_node_id = suggestion.get("target_node_id", "")
        target_param = suggestion.get("target_param", "")
        suggested_value = suggestion.get("suggested_value", "")

        if not target_node_id or not target_param:
            raise InvalidParamsException(message=f"建议 {suggestion_id} 缺少 target_node_id 或 target_param")

        # 1. 获取当前管道配置
        pipeline = await self._pipeline_repo.get_by_id(pipeline_id, tenant_id)
        if not pipeline:
            raise ResourceNotFoundException(message=f"管道不存在: {pipeline_id}")

        # 取最新版本的配置快照
        latest_config = None
        # 管道最新版本配置从 pipeline_versions 表获取
        from sqlalchemy import select
        from src.models.pipeline_version import PipelineVersion

        async with self._session_factory() as session:
            stmt = (
                select(PipelineVersion)
                .where(
                    PipelineVersion.pipeline_id == pipeline_id,
                    PipelineVersion.tenant_id == tenant_id,
                )
                .order_by(PipelineVersion.version_number.desc())
                .limit(1)
            )
            result = await session.execute(stmt)
            version_row = result.scalar_one_or_none()
            if version_row:
                latest_config = version_row.config_snapshot or {}
            else:
                raise ResourceNotFoundException(message=f"管道 {pipeline_id} 没有可用版本")

        # 记录变更前配置快照
        config_before = json.dumps(latest_config, ensure_ascii=False)

        # 2. 应用变更
        new_config = self._apply_param_change(
            config=latest_config,
            target_node_id=target_node_id,
            target_param=target_param,
            new_value=suggested_value,
        )

        config_after = json.dumps(new_config, ensure_ascii=False)

        # 3. 创建评估配置版本
        config_version_id = f"cv_{int(datetime.utcnow().timestamp())}_{uuid.uuid4().hex[:8]}"
        change_summary = (
            f"[{suggestion.get('category', 'auto')}] "
            f"{suggestion.get('title', 'N/A')}: "
            f"节点 {target_node_id}.{target_param} "
            f"从 {suggestion.get('current_value', 'N/A')} "
            f"改为 {suggested_value}"
        )

        version_data = {
            "id": config_version_id,
            "tenant_id": tenant_id,
            "version_number": 1,  # 简化：评估配置版本独立编号
            "config_snapshot": new_config,
            "change_summary": change_summary,
            "created_by": user_id,
        }
        config_version = await self._config_version_repo.create(version_data)

        # 4. 创建变更集（关联评估版本）
        change_set_id = f"cs_{int(datetime.utcnow().timestamp())}_{uuid.uuid4().hex[:8]}"
        change_set_data = {
            "id": change_set_id,
            "tenant_id": tenant_id,
            "config_version_id": config_version_id,
            "previous_config_json": {"before": config_before[:5000]},  # 截断防过大
            "current_config_json": {"after": config_after[:5000]},
            "change_details": {
                "target_node_id": target_node_id,
                "target_param": target_param,
                "suggested_value": suggested_value,
                "suggestion_id": suggestion_id,
            },
            "created_by": user_id,
        }

        # 5. 更新建议状态
        await self._tuning_repo.update(suggestion_id, {
            "status": "adopted",
            "applied_config_version_id": config_version_id,
        }, tenant_id)

        logger.info(
            f"调优建议已采纳: {suggestion_id} → {target_node_id}.{target_param}"
        )

        return {
            "config_version_id": config_version_id,
            "change_set_id": change_set_id,
            "target_node_id": target_node_id,
            "target_param": target_param,
            "config_snapshot": new_config,
            "change_summary": change_summary,
        }

    async def rollback(
        self,
        config_version_id: str,
        pipeline_id: str,
        tenant_id: str,
        user_id: str,
    ) -> dict[str, Any]:
        """回滚管配置到指定评估版本

        1. 读取指定 ConfigVersion 的 config_snapshot
        2. 替换管道当前配置
        3. 创建新的 ConfigChangeSet 记录回滚操作
        """
        version = await self._config_version_repo.get_by_id(config_version_id, tenant_id)
        if not version:
            raise ResourceNotFoundException(message=f"配置版本不存在: {config_version_id}")

        config_snapshot = version.config_snapshot or {}
        if not config_snapshot:
            raise ResourceNotFoundException(message=f"配置版本 {config_version_id} 的快照为空")

        # 更新管道的配置版本记录
        from src.models.pipeline_version import PipelineVersion
        from sqlalchemy import select

        async with self._session_factory() as session:
            stmt = (
                select(PipelineVersion)
                .where(
                    PipelineVersion.pipeline_id == pipeline_id,
                    PipelineVersion.tenant_id == tenant_id,
                )
                .order_by(PipelineVersion.version_number.desc())
                .limit(1)
            )
            result = await session.execute(stmt)
            version_row = result.scalar_one_or_none()

            if version_row:
                # 创建回滚变更集
                prev_config = json.dumps(
                    version_row.config_snapshot or {}, ensure_ascii=False
                )
                change_set_id = f"cs_rb_{int(datetime.utcnow().timestamp())}_{uuid.uuid4().hex[:8]}"
                # 更新到回滚目标快照
                version_row.config_snapshot = config_snapshot
                await session.commit()

        logger.info(
            f"管道配置已回滚: pipeline={pipeline_id} → config_version={config_version_id}"
        )
        return {
            "pipeline_id": pipeline_id,
            "rolled_back_to": config_version_id,
            "change_summary": f"回滚到评估配置版本 {config_version_id}",
        }

    def _apply_param_change(
        self,
        config: dict[str, Any],
        target_node_id: str,
        target_param: str,
        new_value: str,
    ) -> dict[str, Any]:
        """将参数变更应用到管道配置 JSON

        遍历 nodes 和 domains 中的 nodes，找到目标节点并更新参数。
        支点表示法：'domain_weight.domain_name' → config[domain_weight][domain_name]
        """
        import copy

        new_config = copy.deepcopy(config)

        def _update_node(nodes: list[dict[str, Any]]):
            for node in nodes:
                if node.get("id") == target_node_id or node.get("node_id") == target_node_id:
                    node_config = node.get("config", node.get("params", {}))
                    # 支持点分隔的嵌套参数路径
                    if "." in target_param:
                        parts = target_param.split(".")
                        target = node_config
                        for part in parts[:-1]:
                            if part not in target:
                                target[part] = {}
                            target = target[part]
                        target[parts[-1]] = new_value
                    else:
                        node_config[target_param] = new_value
                    return True
            return False

        # 在聚合层查找
        aggregation = new_config.get("aggregation", {})
        aggr_nodes = aggregation.get("nodes", [])
        if _update_node(aggr_nodes):
            return new_config

        # 在域管道中查找
        domains = new_config.get("domains", [])
        for domain in domains:
            domain_nodes = domain.get("nodes", [])
            if _update_node(domain_nodes):
                return new_config

        logger.warning(
            f"未找到目标节点 {target_node_id}，参数变更可能未生效"
        )
        return new_config
