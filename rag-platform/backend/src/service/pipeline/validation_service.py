"""管道校验服务

提供管道配置校验和干运行能力。
校验流程：结构校验 → 节点配置校验 → 边合法性校验 → 编译验证。
干运行：编译但不实际执行检索，验证管道可运行性。
"""
from typing import Any

from src.core.pipeline.compiler import PipelineCompiler
from src.core.pipeline.defaults import NODE_DEFAULTS
from src.core.pipeline.registry import registry
from src.schemas.pipeline.validation import (
    DryRunResult,
    NodeTypeInfo,
    NodeTypeCategory,
    NodeTypeListResponse,
    ValidationError,
    ValidationResult,
)
from src.utils.logger import logger


# 节点类别中文名称映射
_CATEGORY_LABELS: dict[str, dict[str, str]] = {
    "query": {"name": "查询理解", "icon": "SearchOutlined"},
    "retrieval": {"name": "检索策略", "icon": "CloudSearchOutlined"},
    "security": {"name": "安全合规", "icon": "SafetyOutlined"},
    "quality": {"name": "质量增强", "icon": "StarOutlined"},
    "performance": {"name": "性能优化", "icon": "ThunderboltOutlined"},
    "synthesis": {"name": "答案合成", "icon": "FileTextOutlined"},
    "aggregation": {"name": "聚合层", "icon": "ApartmentOutlined"},
}


class PipelineValidationService:
    """管道校验服务"""

    def __init__(self) -> None:
        self.compiler = PipelineCompiler()

    async def validate(self, pipeline_config: dict[str, Any]) -> ValidationResult:
        """校验管道配置

        流程：结构校验 → 节点配置校验 → 编译验证。

        Args:
            pipeline_config: 管道完整 JSON 配置

        Returns:
            ValidationResult 校验结果
        """
        errors: list[ValidationError] = []
        node_count = 0
        edge_count = 0
        domain_count = len(pipeline_config.get("domains", []))

        # 1. 结构校验
        structure_errors = self.compiler._validate_structure(pipeline_config)
        for msg in structure_errors:
            errors.append(ValidationError(
                location="pipeline",
                error_type="structure",
                message=msg,
            ))

        # 如果结构校验失败，跳过后续校验
        if errors:
            return ValidationResult(
                valid=False,
                errors=errors,
                node_count=0,
                edge_count=0,
                domain_count=domain_count,
            )

        # 2. 节点配置校验
        node_errors = self.compiler._validate_nodes(pipeline_config)
        for msg in node_errors:
            # 从错误消息中提取节点位置
            location = "node"
            if msg.startswith("[") and "]" in msg:
                location = msg[1:msg.index("]")]
            errors.append(ValidationError(
                location=location,
                error_type="node",
                message=msg,
            ))

        # 统计节点和边数
        for domain in pipeline_config.get("domains", []):
            domain_pipeline = domain.get("pipeline", {})
            node_count += len(domain_pipeline.get("nodes", []))
            edge_count += len(domain_pipeline.get("edges", []))
        agg_config = pipeline_config.get("aggregation", {})
        node_count += len(agg_config.get("nodes", []))
        edge_count += len(agg_config.get("edges", []))

        # 3. 编译验证（如果前两步无错误）
        if not errors:
            try:
                compiled = self.compiler.compile(pipeline_config)
                logger.debug(f"管道编译验证通过: {node_count} 节点, {edge_count} 边")
            except Exception as e:
                errors.append(ValidationError(
                    location="compiler",
                    error_type="compilation",
                    message=str(e),
                ))

        return ValidationResult(
            valid=len(errors) == 0,
            errors=errors,
            node_count=node_count,
            edge_count=edge_count,
            domain_count=domain_count,
        )

    async def dry_run(self, pipeline_config: dict[str, Any]) -> DryRunResult:
        """干运行：验证管道可编译性，不实际执行检索

        Args:
            pipeline_config: 管道完整 JSON 配置

        Returns:
            DryRunResult 干运行结果
        """
        errors: list[ValidationError] = []
        registered_types: set[str] = set()
        unregistered_types: set[str] = set()

        # 收集所有涉及的节点类型
        for domain in pipeline_config.get("domains", []):
            for node in domain.get("pipeline", {}).get("nodes", []):
                node_type = node.get("type", "")
                if node_type:
                    self._check_node_type(node_type, registered_types, unregistered_types)

        for node in pipeline_config.get("aggregation", {}).get("nodes", []):
            node_type = node.get("type", "")
            if node_type:
                self._check_node_type(node_type, registered_types, unregistered_types)

        # 尝试编译
        execution_plan_summary = None
        compilable = False
        try:
            compiled = self.compiler.compile(pipeline_config)
            compilable = True

            # 构建执行计划摘要
            plan = compiled.execution_plan
            execution_plan_summary = {
                "sorted_node_ids": plan.sorted_ids,
                "parallel_groups": plan.parallel_groups,
                "domain_plans": {
                    domain_id: node_ids
                    for domain_id, node_ids in plan.domain_plans.items()
                },
                "conditional_routes": plan.conditional_routes,
                "degradation_routes": plan.degradation_routes,
            }
        except Exception as e:
            errors.append(ValidationError(
                location="compiler",
                error_type="compilation",
                message=str(e),
            ))

        return DryRunResult(
            compilable=compilable,
            errors=errors,
            execution_plan_summary=execution_plan_summary,
            registered_node_types=sorted(registered_types),
            unregistered_node_types=sorted(unregistered_types),
        )

    def get_node_types(self) -> NodeTypeListResponse:
        """获取所有已注册节点类型信息

        Returns:
            NodeTypeListResponse 按类别分组的节点类型列表
        """
        categories: dict[str, list[NodeTypeInfo]] = {}

        for node_type in registry.list_types():
            try:
                executor = registry.create_executor(node_type)
                cat = executor.category

                if cat not in categories:
                    categories[cat] = []

                # 从 NODE_DEFAULTS 获取默认配置
                default_config = NODE_DEFAULTS.get(node_type, {})

                categories[cat].append(NodeTypeInfo(
                    type=node_type,
                    category=cat,
                    label=node_type,  # 使用类型标识作为标签
                    description=f"{cat}/{node_type} 节点",
                    default_config=default_config,
                    input_ports=[executor.input_type],
                    output_ports=[executor.output_type],
                ))
            except Exception as e:
                logger.warning(f"获取节点类型信息失败: {node_type} - {e}")

        # 构建分类列表
        category_list: list[NodeTypeCategory] = []
        for cat_name, cat_info in _CATEGORY_LABELS.items():
            if cat_name in categories:
                category_list.append(NodeTypeCategory(
                    name=cat_info["name"],
                    icon=cat_info["icon"],
                    types=categories[cat_name],
                ))

        # 添加未分类的节点
        known_categories = set(_CATEGORY_LABELS.keys())
        for cat_name, types in categories.items():
            if cat_name not in known_categories:
                category_list.append(NodeTypeCategory(
                    name=cat_name,
                    icon="QuestionOutlined",
                    types=types,
                ))

        total = sum(len(cat.types) for cat in category_list)
        return NodeTypeListResponse(categories=category_list, total=total)

    def _check_node_type(
        self,
        node_type: str,
        registered: set[str],
        unregistered: set[str],
    ) -> None:
        """检查节点类型是否已注册"""
        try:
            registry.get(node_type)
            registered.add(node_type)
        except KeyError:
            unregistered.add(node_type)
