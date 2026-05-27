"""单元测试：实体提取器 (extractor.py)

覆盖：JSON 解析（正常/修复/markdown 包裹）、提示词构建、chunk_id 分配、异常数据过滤
"""

import json
from unittest.mock import MagicMock

import pytest

from src.core.knowledge_qa.graph.extractor import (
    ENTITY_TYPES,
    RELATION_TYPES,
    Entity,
    Relation,
    _assign_chunk_ids_by_topics,
    _build_extraction_prompt,
    _parse_extraction_result,
)


# ==================== 共享测试数据 ====================

VALID_EXTRACTION_JSON = {
    "entities": [
        {
            "name": "前庭觉失调",
            "type": "symptom_behavior",
            "description": "前庭系统功能异常",
            "aliases": ["前庭功能失调"],
        },
        {
            "name": "注意力训练",
            "type": "intervention_method",
            "description": "提升注意力的训练方法",
        },
    ],
    "relations": [
        {
            "source": "前庭觉失调",
            "target": "注意力训练",
            "type": "treats",
            "description": "前庭觉训练改善注意力",
        },
    ],
}


class TestParseExtractionResult:
    """LLM 返回结果解析测试"""

    def test_parse_extraction_result_valid_json(self):
        """合法 JSON 应正确解析为 Entity 和 Relation 列表"""
        raw = json.dumps(VALID_EXTRACTION_JSON, ensure_ascii=False)

        entities, relations = _parse_extraction_result(raw, book_id="book-001")

        assert len(entities) == 2
        assert len(relations) == 1

        # 验证第一个实体
        e1 = entities[0]
        assert e1.name == "前庭觉失调"
        assert e1.entity_type == "symptom_behavior"
        assert e1.description == "前庭系统功能异常"
        assert e1.aliases == ["前庭功能失调"]
        assert e1.book_id == "book-001"

        # 验证第二个实体
        e2 = entities[1]
        assert e2.name == "注意力训练"
        assert e2.entity_type == "intervention_method"

        # 验证关系
        r = relations[0]
        assert r.source == "前庭觉失调"
        assert r.target == "注意力训练"
        assert r.relation_type == "treats"

    def test_parse_extraction_result_json_repair_fallback(self):
        """畸形 JSON（缺少逗号）应通过 json_repair 修复后解析"""
        # 缺少逗号和括号
        malformed = '{"entities": [{"name": "测试实体" "type": "development_concept"}], "relations": []}'
        entities, relations = _parse_extraction_result(malformed, book_id="b1")

        assert len(entities) == 1
        assert entities[0].name == "测试实体"

    def test_parse_extraction_result_markdown_wrapped(self):
        """被 ```json...``` 包裹的返回应去除标记后解析"""
        raw_json = json.dumps(VALID_EXTRACTION_JSON, ensure_ascii=False)
        wrapped = f"```json\n{raw_json}\n```"

        entities, relations = _parse_extraction_result(wrapped, book_id="book-002")

        assert len(entities) == 2
        assert len(relations) == 1
        assert entities[0].name == "前庭觉失调"

    def test_parse_skips_entities_without_name(self):
        """name 为空或缺失的实体应被跳过"""
        data = {
            "entities": [
                {"name": "", "type": "symptom_behavior", "description": "空名实体"},
                {"name": "有效实体", "type": "development_concept", "description": "正常"},
                {"type": "brain_region", "description": "无名字段"},
            ],
            "relations": [],
        }
        raw = json.dumps(data, ensure_ascii=False)

        entities, relations = _parse_extraction_result(raw, book_id="b1")

        # 只有 "有效实体" 应保留
        assert len(entities) == 1
        assert entities[0].name == "有效实体"

    def test_parse_skips_relations_unknown_source_target(self):
        """关系引用不存在的实体名时应被跳过"""
        data = {
            "entities": [
                {"name": "实体A", "type": "development_concept"},
            ],
            "relations": [
                {"source": "实体A", "target": "不存在的实体", "type": "causes"},
                {"source": "幽灵", "target": "实体A", "type": "treats"},
                {"source": "", "target": "实体A", "type": "related_to"},
            ],
        }
        raw = json.dumps(data, ensure_ascii=False)

        entities, relations = _parse_extraction_result(raw, book_id="b1")

        assert len(entities) == 1
        # 所有关系都引用了不存在的实体，应全部跳过
        assert len(relations) == 0


class TestBuildExtractionPrompt:
    """提示词构建测试"""

    def test_build_extraction_prompt_structure(self):
        """提示词应包含实体类型、关系类型和用户传入的主题"""
        topics = ["前庭觉", "注意力", "感觉统合"]
        sample_texts = ["前庭系统是平衡的基础。", "注意力训练有多种方法。"]

        system, user = _build_extraction_prompt(topics, sample_texts)

        # system prompt 应包含实体类型列表
        for et in ENTITY_TYPES:
            assert et in system

        # system prompt 应包含关系类型列表
        for rt in RELATION_TYPES:
            assert rt in system

        # user prompt 应包含主题标签
        for topic in topics:
            assert topic in user

        # user prompt 应包含样本文本
        assert "前庭系统" in user
        assert "注意力训练" in user


class TestAssignChunkIdsByTopics:
    """chunk_id 分配测试"""

    def test_assign_chunk_ids_by_topics_matching(self):
        """实体名匹配 chunk 的 topic 时，chunk_ids 应被填充"""
        entities = [
            Entity(name="前庭觉失调", entity_type="symptom_behavior", description="测试"),
            Entity(name="注意力训练", entity_type="intervention_method", description="测试"),
        ]

        # 模拟 chunk 对象
        mock_chunk = MagicMock()
        mock_chunk.node_id = "chunk_0"
        mock_chunk.get_content = MagicMock(return_value="前庭觉失调的文本内容")

        chunks = [mock_chunk]
        # chunk_0 的 topic 包含 "前庭觉失调"，匹配第一个实体
        topics_per_chunk = [["前庭觉失调", "平衡能力"]]

        _assign_chunk_ids_by_topics(entities, chunks, topics_per_chunk)

        # 第一个实体应匹配到 chunk_0
        assert "chunk_0" in entities[0].chunk_ids
        # 第二个实体无匹配
        assert len(entities[1].chunk_ids) == 0
