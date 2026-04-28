"""诊断层共享工具函数

提供各层复用的评分计算和状态判定逻辑。
"""

from src.schemas.rag_eval.diagnosis import LayerIssue

_PENALTY_MAP = {"critical": 0.3, "warning": 0.15, "info": 0.05}


def calculate_layer_score(issues: list[LayerIssue]) -> float:
    """根据 issue 严重程度计算健康度分数 0-1"""
    if not issues:
        return 1.0
    penalty = sum(_PENALTY_MAP.get(i.severity, 0.05) for i in issues)
    return round(max(0.0, 1.0 - penalty), 4)


def determine_layer_status(issues: list[LayerIssue]) -> str:
    """根据 issue 严重程度判定状态: pass/warn/fail"""
    critical = sum(1 for i in issues if i.severity == "critical")
    warning = sum(1 for i in issues if i.severity == "warning")
    if critical > 0:
        return "fail"
    if warning > 0:
        return "warn"
    return "pass"


def count_by_severity(
    issues: list[LayerIssue],
) -> tuple[int, int, int]:
    """统计各严重程度的 issue 数量: (critical, warning, info)"""
    critical = sum(1 for i in issues if i.severity == "critical")
    warning = sum(1 for i in issues if i.severity == "warning")
    info = sum(1 for i in issues if i.severity == "info")
    return critical, warning, info
