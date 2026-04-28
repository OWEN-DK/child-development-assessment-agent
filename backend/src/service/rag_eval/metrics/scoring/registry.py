"""指标注册表——动态注册和查找计算器"""

from src.core.config.cache import ConfigCache
from src.service.rag_eval.metrics.scoring.base import MetricCalculator


class MetricRegistry:
    """指标注册表

    支持按名称和层级查找计算器，扩展新指标只需 register() 即可，无需修改核心代码。
    """

    def __init__(self, config_cache: ConfigCache = None):
        self._config_cache = config_cache or ConfigCache.get_instance()
        self._calculators: dict[str, MetricCalculator] = {}
        self._by_layer: dict[int, list[MetricCalculator]] = {}

    def register(self, calculator: MetricCalculator) -> None:
        """注册计算器，按 layer 分组并更新名称索引"""
        name = calculator.name
        layer = calculator.layer

        if name in self._calculators:
            raise ValueError(f"指标计算器已注册: {name}")

        self._calculators[name] = calculator
        if layer not in self._by_layer:
            self._by_layer[layer] = []
        self._by_layer[layer].append(calculator)

    def get_by_name(self, name: str) -> MetricCalculator:
        """按名称获取计算器，不存在则抛 AppException"""
        calc = self._calculators.get(name)
        if calc is None:
            from src.utils.exceptions import AppException

            raise AppException(
                status_code=404,
                code=13007,
                message=f"指标计算器不存在: {name}",
                error_code="METRIC_NOT_FOUND",
                details={"metric_name": name},
            )
        return calc

    def get_by_layer(self, layer: int) -> list[MetricCalculator]:
        """获取指定层的所有已注册计算器"""
        return list(self._by_layer.get(layer, []))

    def get_all(self) -> list[MetricCalculator]:
        """获取所有已注册计算器"""
        return list(self._calculators.values())
