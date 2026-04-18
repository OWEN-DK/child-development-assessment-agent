"""成本计算单元测试"""

from decimal import Decimal
from unittest.mock import patch

import pytest


def test_cost_calculation_known_model():
    from src.core.tracing.cost import calculate_cost

    mock_pricing = {
        "qwen-plus": {
            "input_per_million": 4.0,
            "output_per_million": 12.0,
        }
    }

    with patch("src.core.tracing.cost._get_model_pricing", return_value=mock_pricing):
        cost = calculate_cost(model="qwen-plus", input_tokens=1000, output_tokens=500)
        assert cost is not None
        expected = Decimal(str((1000 / 1_000_000) * 4.0 + (500 / 1_000_000) * 12.0))
        assert cost == expected


def test_cost_calculation_unknown_model():
    from src.core.tracing.cost import calculate_cost

    mock_pricing = {
        "qwen-plus": {
            "input_per_million": 4.0,
            "output_per_million": 12.0,
        }
    }

    with patch("src.core.tracing.cost._get_model_pricing", return_value=mock_pricing):
        cost = calculate_cost(
            model="unknown-model", input_tokens=1000, output_tokens=500
        )
        assert cost is None


def test_cost_calculation_zero_tokens():
    from src.core.tracing.cost import calculate_cost

    mock_pricing = {
        "qwen-plus": {
            "input_per_million": 4.0,
            "output_per_million": 12.0,
        }
    }

    with patch("src.core.tracing.cost._get_model_pricing", return_value=mock_pricing):
        cost = calculate_cost(model="qwen-plus", input_tokens=0, output_tokens=0)
        assert cost == Decimal("0.0")
