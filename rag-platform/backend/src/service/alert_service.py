"""LLM 监控告警服务"""

from dataclasses import dataclass
from typing import Callable

from src.utils.logger import logger


@dataclass
class AlertRule:
    name: str
    condition: Callable[[dict], bool]
    message: str
    severity: str = "warning"


class AlertService:
    """LLM 监控告警服务"""

    _rules: list[AlertRule] = []

    @classmethod
    def add_rule(cls, rule: AlertRule):
        cls._rules.append(rule)

    @classmethod
    def check_alerts(cls, metrics: dict) -> list[AlertRule]:
        """检查是否触发告警"""
        triggered = []
        for rule in cls._rules:
            if rule.condition(metrics):
                triggered.append(rule)
                logger.warning(
                    f"[{rule.severity.upper()}] 告警触发: {rule.name} - {rule.message}"
                )
        return triggered


AlertService.add_rule(
    AlertRule(
        name="high_error_rate",
        condition=lambda m: m.get("error_rate", 0) > 0.1,
        message="LLM 调用错误率超过 10%",
        severity="critical",
    )
)

AlertService.add_rule(
    AlertRule(
        name="slow_response",
        condition=lambda m: m.get("avg_duration_ms", 0) > 10000,
        message="LLM 平均响应时间超过 10 秒",
        severity="warning",
    )
)

AlertService.add_rule(
    AlertRule(
        name="token_spike",
        condition=lambda m: m.get("total_tokens", 0) > 1000000,
        message="Token 消耗突增超过 100 万",
        severity="warning",
    )
)
