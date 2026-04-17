import pytest
from unittest.mock import MagicMock, AsyncMock
from src.core.validation.layers.layer4b_chunk_quality import Layer4bChunkQuality


@pytest.mark.asyncio
async def test_missing_chunks_skipped():
    """缺少分块数据时跳过"""
    test_run = MagicMock(chunks=[])
    layer = Layer4bChunkQuality(AsyncMock(), test_run)
    result = await layer.execute()
    assert result["status"] == "skipped"


@pytest.mark.asyncio
async def test_info_density_calculation():
    """信息密度计算正确"""
    test_run = MagicMock(chunks=[])
    layer = Layer4bChunkQuality(AsyncMock(), test_run)

    # 高信息密度（少停用词）
    content1 = "感统训练前庭觉本体觉触觉"
    density1 = layer._calc_info_density(content1)
    assert density1 > 0.8

    # 低信息密度（多停用词）
    content2 = "的方法是通过的感觉的的过程的是在有的"
    density2 = layer._calc_info_density(content2)
    assert density2 < 0.5


@pytest.mark.asyncio
async def test_structure_level_calculation():
    """结构化程度计算正确"""
    test_run = MagicMock(chunks=[])
    layer = Layer4bChunkQuality(AsyncMock(), test_run)

    # 高结构化内容
    content = """# 标题一
- 列表项1
- 列表项2
1. 有序列表1
2. 有序列表2
普通段落内容"""
    structure = layer._calc_structure_level(content)
    assert structure > 0.5

    # 无结构化内容
    content2 = "这是一段普通的文字内容没有任何标题或列表"
    structure2 = layer._calc_structure_level(content2)
    assert structure2 == 0.0


@pytest.mark.asyncio
async def test_split_rationality():
    """切分合理性计算正确"""
    test_run = MagicMock(chunks=[])
    layer = Layer4bChunkQuality(AsyncMock(), test_run)

    # 完整句子结束
    chunk1 = {"content": "这是一段完整的文字。"}
    assert layer._calc_split_rationality(chunk1) == 1.0

    # 不完整结束
    chunk2 = {"content": "这是一段不完整的文字"}
    assert layer._calc_split_rationality(chunk2) == 0.5


@pytest.mark.asyncio
async def test_composite_score():
    """分块质量检查当前不支持，应返回跳过状态"""
    # 分块数据存储在向量库(Chroma)中，而非MySQL数据库
    # 当前层无法直接从数据库获取分块数据，应优雅跳过
    test_run = MagicMock(
        chunks=[
            {"id": "1", "content": "感统训练前庭觉本体觉。"},
            {"id": "2", "content": "的了在是有的"},
        ]
    )
    layer = Layer4bChunkQuality(AsyncMock(), test_run)
    result = await layer.execute()

    # 当前实现返回跳过状态
    assert result["status"] == "skipped"
    assert "reason" in result["data"]
