"""Phase 7: 提示词影响分析引擎测试"""

import pytest
import tempfile
import os
from pathlib import Path

from src.service.prompt_impact_analyzer import (
    CodeReferenceScanner,
    VariableValidator,
    ConfigDependencyDetector,
    PromptImpactAnalyzer,
    CodeReference,
    VariableChanges,
    ConfigDependency,
    ImpactAnalysisResult,
)


class TestCodeReferenceScanner:
    """测试代码引用扫描器"""

    def test_scan_finds_get_prompt_calls(self):
        """测试扫描到 get_prompt 调用"""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test_service.py"
            test_file.write_text("""
from src.core.prompt.manager import prompt_manager

async def process_query(query: str):
    prompt = await prompt_manager.get_prompt("rag_query_rewrite", variables={"query": query})
    return prompt
""")
            scanner = CodeReferenceScanner(root_dir=tmpdir)
            import asyncio

            refs = asyncio.get_event_loop().run_until_complete(
                scanner.scan("rag_query_rewrite")
            )

            assert len(refs) == 1
            assert refs[0].file == "test_service.py"
            assert refs[0].line == 5
            assert refs[0].function == "process_query"

    def test_scan_no_matches(self):
        """测试无匹配时返回空列表"""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test_service.py"
            test_file.write_text("""
def some_function():
    return "hello"
""")
            scanner = CodeReferenceScanner(root_dir=tmpdir)
            import asyncio

            refs = asyncio.get_event_loop().run_until_complete(
                scanner.scan("nonexistent_prompt")
            )

            assert len(refs) == 0

    def test_scan_invalid_python_file(self):
        """测试无效 Python 文件返回空列表"""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "invalid.py"
            test_file.write_text("this is not valid python syntax {{{")

            scanner = CodeReferenceScanner(root_dir=tmpdir)
            import asyncio

            refs = asyncio.get_event_loop().run_until_complete(scanner.scan("test"))

            assert len(refs) == 0


class TestVariableValidator:
    """测试变量校验器"""

    def test_extract_variables(self):
        """测试提取变量"""
        content = "你好 {query}，年龄是 {age}，姓名是 {name}"
        variables = VariableValidator.extract_variables(content)
        assert variables == ["age", "name", "query"]

    def test_validate_added_variables(self):
        """测试检测新增变量"""
        validator = VariableValidator()
        import asyncio

        changes = asyncio.get_event_loop().run_until_complete(
            validator.validate("test", "你好 {new_var}", current_variables=["old_var"])
        )
        assert changes.added == ["new_var"]
        assert changes.removed == ["old_var"]

    def test_validate_no_changes(self):
        """测试无变量变更"""
        validator = VariableValidator()
        import asyncio

        changes = asyncio.get_event_loop().run_until_complete(
            validator.validate("test", "你好 {var}", current_variables=["var"])
        )
        assert changes.added == []
        assert changes.removed == []

    def test_validate_empty_current(self):
        """测试当前无变量"""
        validator = VariableValidator()
        import asyncio

        changes = asyncio.get_event_loop().run_until_complete(
            validator.validate("test", "你好 {new_var}", current_variables=[])
        )
        assert changes.added == ["new_var"]
        assert changes.removed == []


class TestConfigDependencyDetector:
    """测试配置依赖检测器"""

    def test_detect_config_dependency(self):
        """测试检测配置依赖"""
        config_params = [
            {
                "key": "rag_similarity_threshold",
                "category": "rag.retrieval",
                "description_zh": "相似度阈值",
                "current_value": "0.7",
            },
        ]
        detector = ConfigDependencyDetector(config_params=config_params)
        import asyncio

        deps = asyncio.get_event_loop().run_until_complete(
            detector.detect("test", "阈值设置为 {rag_similarity_threshold}")
        )
        assert len(deps) == 1
        assert deps[0].param == "rag_similarity_threshold"
        assert deps[0].category == "rag.retrieval"

    def test_no_config_dependency(self):
        """测试无配置依赖"""
        config_params = [
            {
                "key": "rag_similarity_threshold",
                "category": "rag.retrieval",
                "description_zh": "相似度阈值",
            },
        ]
        detector = ConfigDependencyDetector(config_params=config_params)
        import asyncio

        deps = asyncio.get_event_loop().run_until_complete(
            detector.detect("test", "这是一个普通提示词")
        )
        assert len(deps) == 0


class TestPromptImpactAnalyzer:
    """测试提示词影响分析引擎"""

    def test_analyze_low_risk(self):
        """测试低风险分析（无变更）"""
        analyzer = PromptImpactAnalyzer()
        import asyncio

        result = asyncio.get_event_loop().run_until_complete(
            analyzer.analyze("test", "你好 {query}", current_variables=["query"])
        )
        assert result.risk_level == "low"

    def test_analyze_medium_risk(self):
        """测试中等风险分析（新增变量）"""
        analyzer = PromptImpactAnalyzer()
        import asyncio

        result = asyncio.get_event_loop().run_until_complete(
            analyzer.analyze(
                "test", "你好 {query} {new_var}", current_variables=["query"]
            )
        )
        assert result.risk_level == "medium"
        assert result.variable_changes.added == ["new_var"]

    def test_analyze_high_risk(self):
        """测试高风险分析（删除变量）"""
        analyzer = PromptImpactAnalyzer()
        import asyncio

        result = asyncio.get_event_loop().run_until_complete(
            analyzer.analyze("test", "你好", current_variables=["query"])
        )
        assert result.risk_level == "high"
        assert result.variable_changes.removed == ["query"]

    def test_analyze_returns_affected_files(self):
        """测试返回受影响文件列表"""
        analyzer = PromptImpactAnalyzer()
        import asyncio

        result = asyncio.get_event_loop().run_until_complete(
            analyzer.analyze("test", "你好 {query}", current_variables=["query"])
        )
        assert isinstance(result.affected_files, list)
