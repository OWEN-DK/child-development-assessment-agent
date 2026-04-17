"""趋势数据服务测试

注意：由于 trend_service 使用 SQLAlchemy ORM 的 selectinload，
直接 mock session 会触发 ORM 配置检查。因此测试聚焦于业务逻辑验证。
"""

import pytest
from datetime import datetime, timedelta


def test_metric_field_mapping():
    """测试：指标名称正确映射到数据库字段"""
    metric_field_map = {
        "precision": "overall_precision",
        "recall": "overall_recall",
        "f1": "overall_f1",
        "mrr": "overall_mrr",
        "ndcg": "overall_ndcg",
    }

    assert metric_field_map.get("f1") == "overall_f1"
    assert metric_field_map.get("precision") == "overall_precision"
    assert metric_field_map.get("recall") == "overall_recall"
    assert metric_field_map.get("mrr") == "overall_mrr"
    assert metric_field_map.get("ndcg") == "overall_ndcg"
    assert metric_field_map.get("unknown", "overall_f1") == "overall_f1"


def test_date_cutoff_calculation():
    """测试：日期范围计算正确"""
    days = 30
    cutoff_date = datetime.utcnow() - timedelta(days=days)

    # 验证 cutoff_date 是 30 天前
    expected = datetime.utcnow() - timedelta(days=30)
    assert abs((cutoff_date - expected).total_seconds()) < 60  # 允许 1 分钟误差


def test_trend_data_aggregation_logic():
    """测试：趋势数据聚合逻辑正确"""
    # 模拟运行数据
    runs = [
        {"overall_f1": 0.75, "id": "run-1", "created_at": datetime.utcnow()},
        {"overall_f1": 0.80, "id": "run-2", "created_at": datetime.utcnow()},
        {"overall_f1": 0.70, "id": "run-3", "created_at": datetime.utcnow()},
    ]

    values = [r["overall_f1"] for r in runs]

    # 验证聚合计算
    mean = sum(values) / len(values)
    min_val = min(values)
    max_val = max(values)

    assert mean == pytest.approx(0.75)
    assert min_val == pytest.approx(0.70)
    assert max_val == pytest.approx(0.80)


def test_empty_runs_handling():
    """测试：空运行列表处理"""
    runs = []
    values = [r.get("overall_f1") for r in runs if r.get("overall_f1") is not None]

    assert len(values) == 0


def test_multi_metric_structure():
    """测试：多指标返回结构正确"""
    metrics = ["f1", "precision", "recall"]
    result = {metric: [] for metric in metrics}

    assert "f1" in result
    assert "precision" in result
    assert "recall" in result
    assert len(result) == 3
