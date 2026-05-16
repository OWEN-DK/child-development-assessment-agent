"""提示词占位符校验器

校验提示词模板中的实际占位符与声明的 variables 是否一致。
"""
import re
from dataclasses import dataclass, field


@dataclass
class ValidationResult:
    """占位符校验结果"""
    is_valid: bool
    missing: list[str] = field(default_factory=list)
    extra: list[str] = field(default_factory=list)


class PromptValidator:
    """提示词占位符校验器"""

    @staticmethod
    def validate_variables(
        prompt_key: str, template: str, declared_variables: list[str]
    ) -> ValidationResult:
        """校验模板中的占位符与声明的 variables 是否一致

        Args:
            prompt_key: 提示词 key（用于日志）
            template: 提示词模板字符串
            declared_variables: 声明的变量列表

        Returns:
            ValidationResult
        """
        # 提取 {variable} 占位符，排除 {{}} JSON 转义
        actual_variables = set(re.findall(r"(?<!\{)\{(\w+)\}(?!\})", template))
        declared_set = set(declared_variables)

        missing = list(actual_variables - declared_set)
        extra = list(declared_set - actual_variables)
        is_valid = len(missing) == 0 and len(extra) == 0

        return ValidationResult(is_valid=is_valid, missing=missing, extra=extra)
