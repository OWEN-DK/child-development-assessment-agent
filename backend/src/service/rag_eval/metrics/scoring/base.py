"""指标计算器抽象基类"""

from abc import ABC, abstractmethod

from src.core.config.cache import ConfigCache
from src.schemas.rag_eval.metrics import MetricInput, MetricOutput


class MetricCalculator(ABC):
    """指标计算器抽象基类

    所有三层指标计算器必须继承此类并实现 calculate、name、layer、description。
    阈值统一从 ConfigCache 读取，兜底使用默认值。
    """

    # 各指标默认阈值（ConfigCache 无配置时兜底）
    _DEFAULT_THRESHOLDS: dict[str, float] = {
        "context_precision": 0.7,
        "context_recall": 0.6,
        "noise_sensitivity": 0.3,
        "mrr": 0.5,
        "ndcg": 0.6,
        "faithfulness": 0.8,
        "answer_relevancy": 0.7,
        "groundedness": 0.75,
        "rule_compliance": 1.0,
        "regression_score": 0.9,
        "cost_efficiency": 0.5,
        "config_stability": 0.95,
    }

    def __init__(self, config_cache: ConfigCache = None):
        self._config_cache = config_cache or ConfigCache.get_instance()

    @abstractmethod
    async def calculate(self, input_data: MetricInput) -> MetricOutput:
        """计算指标并返回 MetricOutput"""

    @property
    @abstractmethod
    def name(self) -> str:
        """指标名称，如 'context_precision'"""

    @property
    @abstractmethod
    def layer(self) -> int:
        """所属层级 1/2/3"""

    @property
    @abstractmethod
    def description(self) -> str:
        """指标描述"""

    async def _get_threshold(self) -> float:
        """从 ConfigCache 获取阈值

        key: rag.eval.threshold.{self.name}
        若无配置则从 _DEFAULT_THRESHOLDS 兜底。
        """
        config_key = f"rag.eval.threshold.{self.name}"
        config = self._config_cache.get_latest_config()
        if config:
            return float(config.get(config_key, self._DEFAULT_THRESHOLDS.get(self.name, 0.5)))
        return self._DEFAULT_THRESHOLDS.get(self.name, 0.5)
