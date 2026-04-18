"""提示词影响分析引擎 - Phase 7"""

import re
import ast
from pathlib import Path
from typing import Optional
from pydantic import BaseModel, Field


class CodeReference(BaseModel):
    """代码引用位置"""

    file: str
    line: int
    function: Optional[str] = None


class VariableChanges(BaseModel):
    """变量变更"""

    added: list[str] = Field(default_factory=list)
    removed: list[str] = Field(default_factory=list)
    modified: list[str] = Field(default_factory=list)


class ConfigDependency(BaseModel):
    """配置依赖"""

    param: str
    category: str
    description: str = ""
    current_value: Optional[str] = None


class ImpactAnalysisResult(BaseModel):
    """影响分析结果"""

    code_references: list[CodeReference] = Field(default_factory=list)
    variable_changes: VariableChanges = Field(default_factory=VariableChanges)
    config_dependencies: list[ConfigDependency] = Field(default_factory=list)
    affected_files: list[str] = Field(default_factory=list)
    risk_level: str = "low"  # low, medium, high


class CodeReferenceScanner:
    """代码引用扫描器 - 扫描代码中 prompt_manager.get_prompt(key) 调用位置"""

    def __init__(self, root_dir: str = "backend/src"):
        self._root_dir = root_dir

    async def scan(self, prompt_key: str) -> list[CodeReference]:
        """扫描代码中引用指定提示词的位置"""
        references = []
        root_path = Path(self._root_dir)

        if not root_path.exists():
            return references

        for py_file in root_path.rglob("*.py"):
            refs = await self._scan_file(py_file, prompt_key)
            references.extend(refs)

        return references

    async def _scan_file(self, file_path: Path, prompt_key: str) -> list[CodeReference]:
        """扫描单个文件"""
        try:
            content = file_path.read_text(encoding="utf-8")
            tree = ast.parse(content)
        except (SyntaxError, UnicodeDecodeError):
            return []

        references = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and self._is_get_prompt_call(
                node, prompt_key
            ):
                func_name = self._get_enclosing_function(tree, node)
                rel_path = str(file_path.relative_to(self._root_dir))
                references.append(
                    CodeReference(
                        file=rel_path,
                        line=node.lineno,
                        function=func_name,
                    )
                )

        return references

    def _is_get_prompt_call(self, node: ast.Call, prompt_key: str) -> bool:
        """检查是否是 get_prompt(prompt_key) 调用"""
        if isinstance(node.func, ast.Attribute) and node.func.attr == "get_prompt":
            if node.args and isinstance(node.args[0], ast.Constant):
                return node.args[0].value == prompt_key
        return False

    def _get_enclosing_function(
        self, tree: ast.Module, target_node: ast.Call
    ) -> Optional[str]:
        """获取包含调用的函数名"""
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for child in ast.walk(node):
                    if child is target_node:
                        return node.name
        return None


class VariableValidator:
    """变量校验器 - 校验提示词变量新增/删除/修改"""

    async def validate(
        self,
        prompt_key: str,
        new_content: str,
        current_variables: list[str] | None = None,
    ) -> VariableChanges:
        """校验提示词变量变更"""
        current_vars = set(current_variables or [])
        new_vars = set(re.findall(r"\{(\w+)\}", new_content))

        added = sorted(list(new_vars - current_vars))
        removed = sorted(list(current_vars - new_vars))
        modified = []  # 变量名相同但类型/必填变化的情况（需要 variables_schema 支持）

        return VariableChanges(
            added=added,
            removed=removed,
            modified=modified,
        )

    @staticmethod
    def extract_variables(content: str) -> list[str]:
        """从提示词内容中提取变量 {variable}"""
        return sorted(list(set(re.findall(r"\{(\w+)\}", content))))


class ConfigDependencyDetector:
    """配置参数依赖检测器 - 检测提示词中引用的配置参数"""

    def __init__(self, config_params: list[dict] | None = None):
        self._config_params = config_params or []

    async def detect(self, prompt_key: str, new_content: str) -> list[ConfigDependency]:
        """检测提示词中引用的配置参数"""
        dependencies = []
        for param in self._config_params:
            pattern = r"\{" + re.escape(param["key"]) + r"\}"
            if re.search(pattern, new_content):
                dependencies.append(
                    ConfigDependency(
                        param=param["key"],
                        category=param.get("category", ""),
                        description=param.get("description_zh", ""),
                        current_value=str(param.get("current_value", "")),
                    )
                )
        return dependencies


class PromptImpactAnalyzer:
    """提示词影响分析引擎 - 综合分析代码引用、变量变更、配置依赖"""

    def __init__(self, config_params: list[dict] | None = None):
        self._code_scanner = CodeReferenceScanner()
        self._variable_validator = VariableValidator()
        self._config_detector = ConfigDependencyDetector(config_params or [])

    async def analyze(
        self,
        prompt_key: str,
        new_content: str,
        current_variables: list[str] | None = None,
    ) -> ImpactAnalysisResult:
        """综合分析提示词修改的影响"""
        # 1. 扫描代码引用
        code_refs = await self._code_scanner.scan(prompt_key)

        # 2. 校验变量变更
        variable_changes = await self._variable_validator.validate(
            prompt_key, new_content, current_variables
        )

        # 3. 检测配置依赖
        config_deps = await self._config_detector.detect(prompt_key, new_content)

        # 4. 计算风险等级
        risk_level = self._calculate_risk_level(variable_changes, config_deps)

        return ImpactAnalysisResult(
            code_references=code_refs,
            variable_changes=variable_changes,
            config_dependencies=config_deps,
            affected_files=list(set(ref.file for ref in code_refs)),
            risk_level=risk_level,
        )

    def _calculate_risk_level(
        self, variable_changes: VariableChanges, config_deps: list[ConfigDependency]
    ) -> str:
        """计算风险等级"""
        if variable_changes.removed or config_deps:
            return "high"
        if variable_changes.added or variable_changes.modified:
            return "medium"
        return "low"
