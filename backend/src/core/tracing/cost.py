"""LLM 调用成本计算

从 ConfigManager 动态加载模型定价表，禁止硬编码。
"""

from decimal import Decimal
from typing import Optional


def _get_model_pricing() -> dict:
    """从配置动态加载模型定价表"""
    from src.config import settings

    pricing = {}
    for model_name, pricing_config in settings.model_pricing.items():
        pricing[model_name] = {
            "input_per_million": pricing_config.input_per_million,
            "output_per_million": pricing_config.output_per_million,
        }
    return pricing


def calculate_cost(
    model: str, input_tokens: int, output_tokens: int
) -> Optional[Decimal]:
    """计算单次 LLM 调用成本

    Args:
        model: 模型名称
        input_tokens: 输入 Token 数
        output_tokens: 输出 Token 数

    Returns:
        成本 (Decimal)，未配置定价的模型返回 None
    """
    pricing_table = _get_model_pricing()
    if model not in pricing_table:
        return None

    pricing = pricing_table[model]
    input_cost = (input_tokens / 1_000_000) * pricing["input_per_million"]
    output_cost = (output_tokens / 1_000_000) * pricing["output_per_million"]

    return Decimal(str(input_cost + output_cost))
