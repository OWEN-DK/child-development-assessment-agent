import pytest
from src.core.metadata_processor import MetadataProcessor

def test_semantic_chunker_basic():
    """测试基本语义分块功能"""
    text = """
## 第一章 儿童发展概述

儿童发展是指个体从出生到成熟的成长过程，包括生理、认知、情感、社会等多个方面的发展。
儿童发展具有阶段性和连续性的特点，每个阶段都有其独特的发展任务和特征。

### 1.1 生理发展
生理发展是儿童发展的基础，包括身体发育、运动能力发展等方面。
0-3岁是儿童生理发展最迅速的时期，身高、体重都在快速增长。
3-6岁儿童的大肌肉和小肌肉能力逐渐发展，可以完成跑、跳、画画等复杂动作。

### 1.2 认知发展
认知发展包括感知、记忆、思维、语言等方面的发展。
皮亚杰的认知发展理论将儿童认知发展分为四个阶段：感知运动阶段、前运算阶段、具体运算阶段和形式运算阶段。
"""
    # 模拟Document对象
    from llama_index.core.schema import Document
    doc = Document(text=text, metadata={"chapter_title": "第一章 儿童发展概述"})
    
    chunks = MetadataProcessor.split_chapters_into_chunks([doc], chunk_target_size=200)
    
    # 验证分块结果
    assert len(chunks) > 1
    # 验证块语义完整性
    for chunk in chunks:
        assert len(chunk.text) > 50
        assert "儿童发展" in chunk.text or "发展" in chunk.text

def test_semantic_chunker_overlap():
    """测试分块重叠逻辑，确保上下文连续性"""
    text = "这是第一段内容，主要介绍儿童粗大动作发展的特点。" * 20
    text += "\n\n"
    text += "这是第二段内容，主要介绍儿童精细动作发展的训练方法。" * 20
    
    from llama_index.core.schema import Document
    doc = Document(text=text)
    
    chunks = MetadataProcessor.split_chapters_into_chunks([doc], chunk_target_size=300)
    
    # 验证至少有2个块
    assert len(chunks) >= 2
    # 验证块之间有重叠内容
    chunk_texts = [chunk.text for chunk in chunks]
    # 第一个块的结尾应该和第二个块的开头有重叠
    assert chunk_texts[0][-50:] in chunk_texts[1] or chunk_texts[1][:50] in chunk_texts[0]

def test_semantic_chunker_special_characters():
    """测试特殊字符和全角空格处理"""
    text = """这是包含　全角空格　的文本。
还有很多特殊字符：\x00\x01\x02测试内容。
连续的换行符\n\n\n\n也是需要处理的。
"""
    from llama_index.core.schema import Document
    doc = Document(text=text)
    
    chunks = MetadataProcessor.split_chapters_into_chunks([doc], chunk_target_size=100)
    
    assert len(chunks) >= 1
    processed_text = chunks[0].text
    # 验证全角空格被替换
    assert "　" not in processed_text
    # 验证不可见字符被清理
    assert "\x00" not in processed_text
    assert "\x01" not in processed_text
    # 验证连续换行被处理
    assert "\n\n\n\n" not in processed_text

def test_semantic_chunker_short_text():
    """测试短文本分块"""
    text = "这是一段非常短的文本。"
    
    from llama_index.core.schema import Document
    doc = Document(text=text)
    
    chunks = MetadataProcessor.split_chapters_into_chunks([doc], chunk_target_size=200)
    
    # 短文本应该只有一个块
    assert len(chunks) == 1
    assert chunks[0].text == text.strip()

def test_semantic_chunker_empty_text():
    """测试空文本处理"""
    text = ""
    
    from llama_index.core.schema import Document
    doc = Document(text=text)
    
    chunks = MetadataProcessor.split_chapters_into_chunks([doc], chunk_target_size=200)
    
    # 空文本应该返回空列表或处理后的结果
    assert len(chunks) == 0 or all(len(chunk.text.strip()) == 0 for chunk in chunks)
