"""MD → Cypher 解析器测试。"""

import pytest
from src.core.knowledge_qa.neo4j.md_parser import parse_md, MDParseResult, CypherStatement


SAMPLE_MD = """---
book_id: "test_book_001"
book_title: "测试书籍"
status: "draft"
version: 1
---

# 测试书籍 — 结构化知识

## 概念

### 注意力缺陷 (ADHD)
- **entity_type**: Problem
- **severity**: high
- **symptoms**: 注意力不集中、多动
- **brain_regions**: ["前额叶皮层", "基底核"]
- **source**: 第二章

### 有氧运动
- **entity_type**: Solution
- **category**: 运动干预
- **mechanism**: 提升 BDNF 水平
- **source**: 第三章

## 主张

### 有氧运动改善 ADHD 注意力
- **claim_type**: causal
- **confidence**: high
- **source_problem**: "注意力缺陷 (ADHD)"
- **source_solution**: "有氧运动"
- **evidence**: "30分钟中等强度有氧运动后，前额叶皮层激活增强"

## 运动处方

### 中等强度有氧运动 — ADHD
- **exercise**: "有氧运动"
- **frequency**: "每天1次"
- **duration**: "30分钟"
- **intensity**: "中等"
- **age_range**: "6-18岁"
- **contraindications**: ["严重心脏病", "急性哮喘发作"]
"""


class TestParseMd:
    """parse_md() 测试。"""

    def test_parse_valid_md(self):
        result = parse_md(SAMPLE_MD)
        assert result.book_id == "test_book_001"
        assert result.book_title == "测试书籍"
        assert result.status == "draft"
        assert result.version == 1

    def test_parse_generates_cypher_statements(self):
        result = parse_md(SAMPLE_MD)
        assert len(result.cypher_statements) > 0

    def test_parse_missing_frontmatter_raises(self):
        with pytest.raises(ValueError, match="YAML front matter"):
            parse_md("# 没有 front matter 的文档")

    def test_parse_minimal_valid_md(self):
        md = """---
book_id: b1
book_title: "T"
---
## 概念

### 测试实体
- **entity_type**: Problem
- **severity**: low
"""
        result = parse_md(md)
        assert result.book_id == "b1"
        assert result.book_title == "T"

    def test_cypher_statement_structure(self):
        result = parse_md(SAMPLE_MD)
        for stmt in result.cypher_statements:
            assert isinstance(stmt, CypherStatement)
            assert stmt.query
            assert isinstance(stmt.params, dict)

    def test_parse_prescriptions(self):
        result = parse_md(SAMPLE_MD)
        # 应该包含处方相关的 Cypher
        descriptions = [s.description for s in result.cypher_statements]
        assert any("PRESCRIPTION" in d or "prescription" in d.lower() or "处方" in d for d in descriptions)
