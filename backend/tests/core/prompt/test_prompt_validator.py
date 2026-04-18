"""
PromptValidator 占位符校验器测试
"""

import pytest
from src.core.prompt.validator import PromptValidator, ValidationResult


class TestPromptValidator:
    """测试 PromptValidator 占位符校验功能"""

    def test_validate_variables_perfect_match(self):
        """测试占位符完全匹配的情况"""
        template = "你好 {name}，你的年龄是 {age} 岁"
        declared_variables = ["name", "age"]

        result = PromptValidator.validate_variables(
            "test_prompt", template, declared_variables
        )

        assert result.is_valid is True
        assert result.missing == []
        assert result.extra == []

    def test_validate_variables_missing_variable(self):
        """测试模板使用了未声明的变量"""
        template = "你好 {name}，你的年龄是 {age} 岁"
        declared_variables = ["name"]  # 缺少 age

        result = PromptValidator.validate_variables(
            "test_prompt", template, declared_variables
        )

        assert result.is_valid is False
        assert "age" in result.missing
        assert result.extra == []

    def test_validate_variables_extra_variable(self):
        """测试声明了但模板未使用的变量"""
        template = "你好 {name}"
        declared_variables = ["name", "age", "gender"]  # age 和 gender 未使用

        result = PromptValidator.validate_variables(
            "test_prompt", template, declared_variables
        )

        assert result.is_valid is False
        assert result.missing == []
        assert "age" in result.extra
        assert "gender" in result.extra

    def test_validate_variables_both_missing_and_extra(self):
        """测试同时存在缺失和多余的变量"""
        template = "你好 {name}，来自 {city}"
        declared_variables = ["name", "age"]  # 缺少 city，多余 age

        result = PromptValidator.validate_variables(
            "test_prompt", template, declared_variables
        )

        assert result.is_valid is False
        assert "city" in result.missing
        assert "age" in result.extra

    def test_validate_variables_empty_template(self):
        """测试模板没有占位符"""
        template = "这是一个固定提示词，没有变量"
        declared_variables = []

        result = PromptValidator.validate_variables(
            "test_prompt", template, declared_variables
        )

        assert result.is_valid is True
        assert result.missing == []
        assert result.extra == []

    def test_validate_variables_empty_declared(self):
        """测试声明了变量但模板没有使用"""
        template = "这是一个固定提示词"
        declared_variables = ["name", "age"]

        result = PromptValidator.validate_variables(
            "test_prompt", template, declared_variables
        )

        assert result.is_valid is False
        assert result.missing == []
        assert "name" in result.extra
        assert "age" in result.extra

    def test_validate_variables_json_template(self):
        """测试 JSON 模板中的占位符（需要排除 {{}} 转义）"""
        template = """
        {
            "name": "{name}",
            "age": {age},
            "escaped_braces": "{{this_should_be_ignored}}"
        }
        """
        declared_variables = ["name", "age"]

        result = PromptValidator.validate_variables(
            "test_prompt", template, declared_variables
        )

        assert result.is_valid is True
        assert result.missing == []
        assert result.extra == []

    def test_validate_variables_complex_template(self):
        """测试复杂模板（多个相同变量）"""
        template = """
        你好 {name}，
        你的年龄是 {age} 岁。
        {name}，请确认你的信息：
        - 年龄：{age}
        - 城市：{city}
        """
        declared_variables = ["name", "age", "city"]

        result = PromptValidator.validate_variables(
            "test_prompt", template, declared_variables
        )

        assert result.is_valid is True
        assert result.missing == []
        assert result.extra == []

    def test_validate_variables_underscore_in_name(self):
        """测试变量名包含下划线"""
        template = "你好 {user_name}，你的邮箱是 {user_email}"
        declared_variables = ["user_name", "user_email"]

        result = PromptValidator.validate_variables(
            "test_prompt", template, declared_variables
        )

        assert result.is_valid is True

    def test_validate_variables_case_sensitive(self):
        """测试变量名大小写敏感"""
        template = "你好 {Name}，你的年龄是 {age}"
        declared_variables = ["name", "age"]  # Name vs name

        result = PromptValidator.validate_variables(
            "test_prompt", template, declared_variables
        )

        assert result.is_valid is False
        assert "Name" in result.missing
        assert "name" in result.extra
