"""诊断层共享工具函数

提供各层复用的评分计算和状态判定逻辑。
"""

from src.schemas.rag_eval.diagnosis import LayerIssue


def calculate_layer_score(issues: list[LayerIssue], total_cases: int) -> float:
    """按通过率计算健康度分数 0-1

    通过率 = (总用例数 - 受影响用例数) / 总用例数
    一个用例触发多条规则只算 1 个受影响用例。
    """
    if total_cases <= 0:
        return 1.0
    if not issues:
        return 1.0
    affected_cases = len({item for issue in issues for item in issue.affected_items})
    return round(max(0.0, (total_cases - affected_cases) / total_cases), 4)


def count_affected_cases(issues: list[LayerIssue]) -> int:
    """统计受影响的唯一用例/实体数"""
    return len({item for issue in issues for item in issue.affected_items})


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
