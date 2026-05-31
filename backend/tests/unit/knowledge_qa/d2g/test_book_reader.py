"""Phase 0 全书阅读单元测试

测试工具函数: _extract_section, _extract_list, _extract_terminology。
"""

import pytest

from src.core.knowledge_qa.d2g.book_reader import (
    _extract_section,
    _extract_list,
    _extract_terminology,
)


# ──────────────────────────────────────────────────────────────
# _extract_section 测试
# ──────────────────────────────────────────────────────────────


class TestExtractSection:
    """_extract_section 函数测试"""

    def test_extract_h3_section(self):
        """应能提取 ### 标题下的内容"""
        text = """### 全书主旨
这是一本关于儿童发展的书。

### 核心论点
论点1
论点2
"""
        result = _extract_section(text, "全书主旨")
        assert "儿童发展" in result

    def test_extract_h2_section(self):
        """应能提取 ## 标题下的内容"""
        text = """## 全书主旨
核心内容在这里。

## 其他
其他内容。
"""
        result = _extract_section(text, "全书主旨")
        assert "核心内容" in result

    def test_missing_section(self):
        """不存在的标题应返回空字符串"""
        text = """### 全书主旨
内容
"""
        result = _extract_section(text, "不存在的标题")
        assert result == ""

    def test_empty_text(self):
        """空文本应返回空字符串"""
        result = _extract_section("", "标题")
        assert result == ""


# ──────────────────────────────────────────────────────────────
# _extract_list 测试
# ──────────────────────────────────────────────────────────────


class TestExtractList:
    """_extract_list 函数测试"""

    def test_extract_dash_list(self):
        """应能提取 - 开头的列表"""
        text = """### 核心论点
- 论点一：发展是动态过程
- 论点二：环境影响大脑
- 论点三：早期干预关键
"""
        items = _extract_list(text, "核心论点")
        assert len(items) == 3
        assert "发展是动态过程" in items[0]

    def test_extract_numbered_list(self):
        """应能提取数字开头的列表"""
        text = """### 核心论点
1. 论点一
2. 论点二
"""
        items = _extract_list(text, "核心论点")
        assert len(items) == 2

    def test_extract_empty_list(self):
        """不存在的标题应返回空列表"""
        items = _extract_list("### 标题\n内容", "其他")
        assert items == []


# ──────────────────────────────────────────────────────────────
# _extract_terminology 测试
# ──────────────────────────────────────────────────────────────


class TestExtractTerminology:
    """_extract_terminology 函数测试"""

    def test_extract_bold_terms(self):
        """应能提取 **术语**：定义 格式"""
        text = """### 关键术语
- **敏感期**：特定能力发展的最佳窗口期
- **感觉统合**：大脑整合多种感觉信息的能力
"""
        terms = _extract_terminology(text)
        assert len(terms) == 2
        assert "敏感期" in terms
        assert terms["敏感期"] == "特定能力发展的最佳窗口期"
        assert "感觉统合" in terms

    def test_extract_colon_separator(self):
        """应支持中文冒号分隔"""
        text = """### 关键术语
- **术语A**：定义A
"""
        terms = _extract_terminology(text)
        assert "术语A" in terms

    def test_missing_terminology_section(self):
        """不存在术语表时应返回空字典"""
        terms = _extract_terminology("### 其他\n内容")
        assert terms == {}

    def test_empty_terminology(self):
        """空术语表应返回空字典"""
        terms = _extract_terminology("")
        assert terms == {}
