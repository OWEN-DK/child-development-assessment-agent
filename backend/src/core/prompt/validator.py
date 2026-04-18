"""提示词占位符校验器

校验提示词模板中的实际占位符与声明的 variables 是否一致
"""

import re
from dataclasses import dataclass
from typing import List

from src.utils.logger import logger


@dataclass
class ValidationResult:
    """占位符校验结果"""

    is_valid: bool
    missing: List[str]  # 模板中使用了但未声明的变量
    extra: List[str]  # 声明了但模板中未使用的变量


class PromptValidator:
    """提示词占位符校验器"""

    @staticmethod
    def validate_variables(
        prompt_key: str, template: str, declared_variables: List[str]
    ) -> ValidationResult:
        """
        校验模板中的实际占位符与声明的 variables 是否一致

        Args:
            prompt_key: 提示词 key
            template: 提示词模板字符串
            declared_variables: 声明的变量列表

        Returns:
            ValidationResult: 校验结果
        """
        # 提取模板中所有的 {variable} 占位符
        # 注意：需要排除 JSON 模板中的 {{}} 转义符号
        actual_variables = set(re.findall(r"(?<!\{)\{(\w+)\}(?!\})", template))
        declared_set = set(declared_variables)

        # 找出缺失和多余的变量
        missing = list(actual_variables - declared_set)
        extra = list(declared_set - actual_variables)

        is_valid = len(missing) == 0 and len(extra) == 0

        if not is_valid:
            logger.warning(
                f"提示词 '{prompt_key}' 占位符不匹配: missing={missing}, extra={extra}"
            )

        return ValidationResult(is_valid=is_valid, missing=missing, extra=extra)
