"""年龄→年龄段标签映射工具

DraftEngine / CaseEngine 共用。
"""


def calculate_age_stage_label(age: float) -> str:
    """根据年龄计算年龄段标签

    映射规则：
    - 0-0.5   → "0-6m"
    - 0.5-1   → "6-12m"
    - 1-2     → "1-2y"
    - 2-3     → "2-3y"
    - 3-4     → "3-4y"
    - 4-6     → "4-6y"
    - 6+      → "6+y"

    Args:
        age: 年龄（岁，如 1.5）

    Returns:
        年龄段标签字符串
    """
    if age < 0.5:
        return "0-6m"
    if age < 1:
        return "6-12m"
    if age < 2:
        return "1-2y"
    if age < 3:
        return "2-3y"
    if age < 4:
        return "3-4y"
    if age < 6:
        return "4-6y"
    return "6+y"
