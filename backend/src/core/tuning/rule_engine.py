"""规则引擎:根据测试指标生成参数调整建议"""

from typing import Any, Dict, List

from src.schemas import TuningSuggestion
from src.utils.logger import logger


class RuleEngine:
    """规则引擎:指标驱动的参数诊断"""

    OPERATORS = {
        "<": lambda a, b: a < b,
        ">": lambda a, b: a > b,
        "<=": lambda a, b: a <= b,
        ">=": lambda a, b: a >= b,
        "==": lambda a, b: a == b,
    }

    def __init__(self, config_mgr=None):
        """初始化规则引擎"""
        from src.config import config_manager

        self.config_mgr = config_mgr or config_manager
        self._current_config_cache: Dict[str, Any] = {}

    def _load_rules(self) -> Dict[str, Any]:
        """从 ConfigManager 加载调参规则"""
        full_config = self.config_mgr.get_full_config()
        return full_config.get("rag_tuning_rules", {})

    def _refresh_config_cache(self):
        """刷新当前配置缓存(热配置场景下每次评估前调用)"""
        self._current_config_cache = self.config_mgr.get_full_config()

    def _get_current_value(self, param_name: str) -> Any:
        """根据参数名从 ConfigManager 当前配置中读取当前值(热配置兼容)"""
        value = self._current_config_cache.get(param_name)
        if value is not None:
            return value
        parts = param_name.split(".")
        current = self._current_config_cache
        for part in parts:
            if isinstance(current, dict):
                current = current.get(part)
            else:
                return None
        return current

    def _check_trigger(self, trigger: Dict, metrics: Dict[str, float]) -> bool:
        """检查触发条件是否满足"""
        if "or" in trigger:
            return any(self._check_condition(cond, metrics) for cond in trigger["or"])
        if "and" in trigger:
            return all(self._check_condition(cond, metrics) for cond in trigger["and"])
        return self._check_condition(trigger, metrics)

    def _check_condition(self, condition: Dict, metrics: Dict[str, float]) -> bool:
        """检查单一条件"""
        metric = condition["metric"]
        operator = condition["operator"]
        threshold = condition["threshold"]

        actual_value = metrics.get(metric)
        if actual_value is None:
            return False

        op_func = self.OPERATORS.get(operator)
        if op_func is None:
            logger.warning(f"未知操作符: {operator}")
            return False

        return op_func(actual_value, threshold)

    async def evaluate(self, metrics: Dict[str, float]) -> List[TuningSuggestion]:
        """根据指标评估生成调参建议"""
        self._refresh_config_cache()

        rules = self._load_rules()
        suggestions = []

        for rule_name, rule in rules.items():
            trigger = rule.get("trigger", {})
            if not self._check_trigger(trigger, metrics):
                continue

            priority = rule.get("priority", "medium")
            for suggestion_template in rule.get("suggestions", []):
                param_name = suggestion_template["param"]
                suggestion = TuningSuggestion(
                    id=f"rule_{rule_name}_{param_name}",
                    param_name=param_name,
                    current_value=self._get_current_value(param_name),
                    suggested_value=suggestion_template["suggested_value"],
                    action=suggestion_template["action"],
                    reason=f"{rule_name} 规则触发: 指标不达标",
                    expected_effect=suggestion_template.get("expected_effect", ""),
                    priority=priority,
                    source="rule_engine",
                    safe_range=tuple(suggestion_template.get("safe_range", []))
                    if suggestion_template.get("safe_range")
                    else None,
                )
                suggestions.append(suggestion)

        logger.info(f"规则引擎评估完成: 生成 {len(suggestions)} 条建议")
        return suggestions
