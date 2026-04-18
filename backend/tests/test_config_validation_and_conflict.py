"""Phase 8: 配置校验引擎和冲突检测测试"""

import pytest

from src.service.config_validation_engine import (
    ConfigValidationEngine,
    ValidationResult,
)
from src.service.config_conflict_detector import ConfigConflictDetector, Conflict


class TestConfigValidationEngine:
    """测试配置校验引擎"""

    def test_validate_type_number_valid(self):
        """测试数字类型校验 - 有效"""
        metadata_store = {
            "test_config": {
                "name_zh": "测试配置",
                "value_type": "number",
                "min_value": 0,
                "max_value": 100,
            }
        }
        engine = ConfigValidationEngine(metadata_store=metadata_store)
        import asyncio

        result = asyncio.get_event_loop().run_until_complete(
            engine.validate({"test_config": 50})
        )
        assert result.valid is True
        assert result.errors == []

    def test_validate_type_number_invalid(self):
        """测试数字类型校验 - 无效"""
        metadata_store = {
            "test_config": {
                "name_zh": "测试配置",
                "value_type": "number",
            }
        }
        engine = ConfigValidationEngine(metadata_store=metadata_store)
        import asyncio

        result = asyncio.get_event_loop().run_until_complete(
            engine.validate({"test_config": "not_a_number"})
        )
        assert result.valid is False
        assert len(result.errors) == 1
        assert "值必须为数字" in result.errors[0]

    def test_validate_type_boolean(self):
        """测试布尔类型校验"""
        metadata_store = {
            "test_config": {
                "name_zh": "测试配置",
                "value_type": "boolean",
            }
        }
        engine = ConfigValidationEngine(metadata_store=metadata_store)
        import asyncio

        result = asyncio.get_event_loop().run_until_complete(
            engine.validate({"test_config": "not_a_bool"})
        )
        assert result.valid is False
        assert "值必须为布尔类型" in result.errors[0]

    def test_validate_range(self):
        """测试取值范围校验"""
        metadata_store = {
            "test_config": {
                "name_zh": "测试配置",
                "value_type": "number",
                "min_value": 0,
                "max_value": 100,
            }
        }
        engine = ConfigValidationEngine(metadata_store=metadata_store)
        import asyncio

        result = asyncio.get_event_loop().run_until_complete(
            engine.validate({"test_config": 150})
        )
        assert result.valid is False
        assert "值不能大于 100" in result.errors[0]

    def test_validate_recommended_range(self):
        """测试推荐范围警告"""
        metadata_store = {
            "test_config": {
                "name_zh": "测试配置",
                "value_type": "number",
                "min_value": 0,
                "max_value": 100,
                "recommended_min": 10,
                "recommended_max": 90,
            }
        }
        engine = ConfigValidationEngine(metadata_store=metadata_store)
        import asyncio

        result = asyncio.get_event_loop().run_until_complete(
            engine.validate({"test_config": 5})
        )
        assert result.valid is True  # 在取值范围内，所以 valid
        assert len(result.warnings) == 1
        assert "推荐值不低于 10" in result.warnings[0]

    def test_validate_nonexistent_key(self):
        """测试不存在的配置项"""
        engine = ConfigValidationEngine(metadata_store={})
        import asyncio

        result = asyncio.get_event_loop().run_until_complete(
            engine.validate({"nonexistent": 50})
        )
        assert result.valid is False
        assert "配置项 nonexistent 不存在" in result.errors[0]


class TestConfigConflictDetector:
    """测试配置冲突检测器"""

    def test_bm25_vector_ratio_warning(self):
        """测试 BM25 TopK 比例警告"""
        detector = ConfigConflictDetector()
        import asyncio

        conflicts = asyncio.get_event_loop().run_until_complete(
            detector.detect({"bm25_top_k": 5, "vector_top_k": 20}, {})
        )
        assert len(conflicts) >= 1
        assert any(c.rule == "bm25_vector_ratio" for c in conflicts)

    def test_fusion_threshold_error(self):
        """测试融合阈值错误"""
        detector = ConfigConflictDetector()
        import asyncio

        conflicts = asyncio.get_event_loop().run_until_complete(
            detector.detect(
                {"fusion_threshold": 1.5, "bm25_weight": 0.5, "vector_weight": 0.5}, {}
            )
        )
        assert any(c.rule == "fusion_threshold" for c in conflicts)
        assert any(c.level == "error" for c in conflicts)

    def test_reranker_k_order_error(self):
        """测试重排序 K 值顺序错误"""
        detector = ConfigConflictDetector()
        import asyncio

        conflicts = asyncio.get_event_loop().run_until_complete(
            detector.detect({"reranker_initial_k": 5, "reranker_final_k": 30}, {})
        )
        assert any(c.rule == "reranker_k_order" for c in conflicts)

    def test_chunk_overlap_warning(self):
        """测试分块重叠警告"""
        detector = ConfigConflictDetector()
        import asyncio

        conflicts = asyncio.get_event_loop().run_until_complete(
            detector.detect({"chunk_size": 500, "chunk_overlap": 300}, {})
        )
        assert any(c.rule == "chunk_overlap" for c in conflicts)

    def test_llm_sampling_warning(self):
        """测试 LLM 采样警告"""
        detector = ConfigConflictDetector()
        import asyncio

        conflicts = asyncio.get_event_loop().run_until_complete(
            detector.detect({"llm_temperature": 0.9, "llm_top_p": 0.9}, {})
        )
        assert any(c.rule == "llm_sampling" for c in conflicts)

    def test_db_pool_error(self):
        """测试数据库连接池错误"""
        detector = ConfigConflictDetector()
        import asyncio

        conflicts = asyncio.get_event_loop().run_until_complete(
            detector.detect({"db_pool_size": 5, "max_concurrent_tasks": 10}, {})
        )
        assert any(c.rule == "db_pool_size" for c in conflicts)
        assert any(c.level == "error" for c in conflicts)

    def test_no_conflicts(self):
        """测试无冲突"""
        detector = ConfigConflictDetector()
        import asyncio

        conflicts = asyncio.get_event_loop().run_until_complete(
            detector.detect(
                {
                    "bm25_top_k": 10,
                    "vector_top_k": 10,
                    "reranker_initial_k": 30,
                    "reranker_final_k": 5,
                    "chunk_size": 500,
                    "chunk_overlap": 50,
                    "llm_temperature": 0.7,
                    "llm_top_p": 0.9,
                    "db_pool_size": 10,
                    "max_concurrent_tasks": 5,
                },
                {},
            )
        )
        # 应该没有严重冲突
        error_conflicts = [c for c in conflicts if c.level == "error"]
        assert len(error_conflicts) == 0
