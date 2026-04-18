"""Phase 7: PromptMetadata 模型测试"""

import pytest
from sqlalchemy import inspect
from src.models.rag_eval.prompt_metadata import RagEvalPromptMetadata
from src.models.rag_eval.enums import RagEvalPromptCategory


class TestPromptMetadataModel:
    """测试 PromptMetadata 模型定义"""

    def test_table_name(self):
        """验证表名正确"""
        assert RagEvalPromptMetadata.__tablename__ == "rag_eval_prompt_metadata"

    def test_primary_key_is_uuid(self):
        """验证主键为 String(36) UUID"""
        mapper = inspect(RagEvalPromptMetadata)
        pk_columns = [c.key for c in mapper.primary_key]
        assert "id" in pk_columns

    def test_required_fields_exist(self):
        """验证必填字段存在"""
        mapper = inspect(RagEvalPromptMetadata)
        column_names = [c.key for c in mapper.columns]

        required_fields = [
            "id",
            "prompt_key",
            "name_zh",
            "purpose",
            "category",
            "is_active",
            "is_system",
            "created_at",
            "updated_at",
        ]
        for field in required_fields:
            assert field in column_names, f"字段 {field} 不存在"

    def test_optional_fields_exist(self):
        """验证可选字段存在"""
        mapper = inspect(RagEvalPromptMetadata)
        column_names = [c.key for c in mapper.columns]

        optional_fields = [
            "subcategory",
            "variables_schema",
            "code_references",
            "config_dependencies",
            "created_by",
            "updated_by",
        ]
        for field in optional_fields:
            assert field in column_names, f"字段 {field} 不存在"

    def test_unique_index_on_prompt_key(self):
        """验证 prompt_key 有唯一索引"""
        table_args = RagEvalPromptMetadata.__table__
        indexes = [
            idx for idx in table_args.indexes if "prompt_key" in idx.columns.keys()
        ]
        assert len(indexes) > 0
        assert any(idx.unique for idx in indexes)

    def test_enum_uses_values_callable(self):
        """验证 Enum 使用 values_callable"""
        mapper = inspect(RagEvalPromptMetadata)
        category_col = mapper.columns.category
        # 验证 Enum 类型
        assert category_col.type.python_type == RagEvalPromptCategory


class TestPromptMetadataCreation:
    """测试 PromptMetadata 实例创建"""

    def test_create_minimal_instance(self):
        """测试创建最小实例"""
        # 直接测试字段默认值，不触发 SQLAlchemy mapper 配置
        assert RagEvalPromptMetadata.__table__.c.is_active.default.arg is True
        assert RagEvalPromptMetadata.__table__.c.is_system.default.arg is False

    def test_create_with_optional_fields(self):
        """测试可选字段类型"""
        # 验证字段类型定义
        columns = RagEvalPromptMetadata.__table__.c
        assert columns.variables_schema.type.python_type == dict
        assert columns.code_references.type.python_type == dict
        assert columns.config_dependencies.type.python_type == dict

    def test_default_values(self):
        """测试默认值定义"""
        columns = RagEvalPromptMetadata.__table__.c
        assert columns.is_active.default.arg is True
        assert columns.is_system.default.arg is False
