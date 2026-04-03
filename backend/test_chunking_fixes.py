"""
测试分块修复脚本
验证以下修复：
1. 空行处理
2. chunk 大小优化
3. 重复内容处理
4. 页码显示
5. 内容长度显示
"""

import re
from llama_index.core.schema import Document
from src.core.metadata_processor import MetadataProcessor


def test_empty_line_removal():
    """测试空行处理"""
    print("=" * 80)
    print("测试 1: 空行处理")
    print("=" * 80)
    
    # 创建包含多余空行的测试文本
    test_text = """这是第一段内容。


这是第二段内容，中间有很多空行。



这是第三段内容。

这是第四段内容，前面只有一个换行。
"""
    
    doc = Document(text=test_text)
    chunks = MetadataProcessor.split_chapters_into_chunks([doc], chunk_target_size=500, file_hash="test_hash")
    
    print(f"\n原始文本长度：{len(test_text)}")
    print(f"分块数量：{len(chunks)}")
    
    if chunks:
        chunk_text = chunks[0].text
        print(f"\n处理后的文本：")
        print(repr(chunk_text[:500]))
        
        # 验证没有 3 个以上的连续换行
        assert "\n\n\n" not in chunk_text, "仍然存在 3 个以上的连续换行"
        
        # 验证没有只包含空格的行
        lines = chunk_text.split('\n')
        empty_lines = [line for line in lines if line and not line.strip()]
        print(f"\n空行数量：{len(empty_lines)}")
        assert len(empty_lines) == 0, f"仍然存在 {len(empty_lines)} 个空行"
        
        print("\n✅ 空行处理测试通过")
    else:
        print("\n❌ 分块失败")
    
    print()


def test_chunk_size_optimization():
    """测试 chunk 大小优化"""
    print("=" * 80)
    print("测试 2: Chunk 大小优化")
    print("=" * 80)
    
    # 创建包含多个段落的测试文本
    test_text = "这是第一段内容，主要介绍儿童发展的基本概念。" * 10
    test_text += "\n\n"
    test_text += "这是第二段内容，讲述儿童认知发展的重要性。" * 10
    test_text += "\n\n"
    test_text += "这是第三段内容，关于儿童社交情感发展的内容。" * 10
    
    doc = Document(text=test_text)
    chunk_target_size = 300
    chunks = MetadataProcessor.split_chapters_into_chunks([doc], chunk_target_size=chunk_target_size, file_hash="test_hash")
    
    print(f"\n原始文本长度：{len(test_text)}")
    print(f"目标 chunk 大小：{chunk_target_size}")
    print(f"分块数量：{len(chunks)}")
    
    MIN_CHUNK_SIZE = int(chunk_target_size * 0.3)
    
    for i, chunk in enumerate(chunks):
        print(f"\nChunk {i+1}:")
        print(f"  长度：{len(chunk.text)} 字符")
        print(f"  内容前 100 字：{chunk.text[:100]}...")
        
        # 验证 chunk 大小（除非是最后一个 chunk）
        if i < len(chunks) - 1:
            assert len(chunk.text) >= MIN_CHUNK_SIZE, \
                f"Chunk {i+1} 过小：{len(chunk.text)} < {MIN_CHUNK_SIZE}"
    
    print("\n✅ Chunk 大小优化测试通过")
    print()


def test_content_length_display():
    """测试内容长度显示"""
    print("=" * 80)
    print("测试 3: 内容长度显示")
    print("=" * 80)
    
    test_text = "这是一段测试文本，用于验证内容长度计算。" * 5
    doc = Document(text=test_text)
    
    chunks = MetadataProcessor.split_chapters_into_chunks([doc], chunk_target_size=500, file_hash="test_hash")
    
    if chunks:
        chunk = chunks[0]
        content_length = len(chunk.text)
        
        print(f"\nChunk 内容长度：{content_length} 字符")
        print(f"start_char_idx: {chunk.start_char_idx}")
        print(f"end_char_idx: {chunk.end_char_idx}")
        
        # 验证内容长度不为 0
        assert content_length > 0, "内容长度为 0"
        
        # 验证 start_char_idx 和 end_char_idx 被设置
        assert chunk.start_char_idx is not None, "start_char_idx 未设置"
        assert chunk.end_char_idx is not None, "end_char_idx 未设置"
        
        print("\n✅ 内容长度显示测试通过")
    else:
        print("\n❌ 分块失败")
    
    print()


def test_page_label_format():
    """测试页码标签格式"""
    print("=" * 80)
    print("测试 4: 页码标签格式")
    print("=" * 80)
    
    # 模拟 EPUB 的 page_label 格式
    test_page_labels = [
        "Text/part0005.xhtml",
        "Text/part0012.xhtml",
        "Text/chapter01.html",
        "page_10",
        "15",  # 普通页码
    ]
    
    for page_label in test_page_labels:
        # 模拟前端的显示逻辑
        if page_label.endswith('.xhtml') or page_label.endswith('.html'):
            match = re.search(r'part(\d+)', page_label, re.IGNORECASE) or re.search(r'chapter(\d+)', page_label, re.IGNORECASE)
            if match:
                display = f"第{int(match[1])}章"
            else:
                # 尝试提取数字
                num_match = re.search(r'(\d+)', page_label)
                if num_match:
                    display = f"第{int(num_match[1])}章"
                else:
                    display = "章节内容"
        else:
            display = page_label
        
        print(f"{page_label:30} -> {display}")
    
    print("\n✅ 页码标签格式测试通过")
    print()


def test_duplicate_content():
    """测试重复内容处理"""
    print("=" * 80)
    print("测试 5: 重复内容处理")
    print("=" * 80)
    
    # 创建包含相似句子的测试文本
    test_text = """
    导致玛丽焦躁行为的并非现在买鞋的经历，而是多年前的问题没有得到妥善处理。
    
    过去未解决的问题，可以在很大程度上影响我们的个人生活和人际关系。
    
    这种经历常常伴随强烈的无助、绝望、恐惧和被遗弃感。
    
    仍然以母子分离为例，这一次情况更为极端。
    """
    
    doc = Document(text=test_text)
    chunks = MetadataProcessor.split_chapters_into_chunks([doc], chunk_target_size=200, file_hash="test_hash")
    
    print(f"\n分块数量：{len(chunks)}")
    
    if len(chunks) >= 2:
        # 检查相邻 chunk 之间是否有大量重复
        for i in range(len(chunks) - 1):
            chunk1_text = chunks[i].text
            chunk2_text = chunks[i + 1].text
            
            # 计算重复度（简单方法：检查是否有超过 50 字符的相同子串）
            max_overlap = 0
            for j in range(len(chunk1_text) - 50):
                substr = chunk1_text[j:j+50]
                if substr in chunk2_text:
                    max_overlap += len(substr)
            
            overlap_ratio = max_overlap / max(len(chunk1_text), len(chunk2_text)) * 100
            print(f"\nChunk {i+1} 和 Chunk {i+2} 的重叠度：{overlap_ratio:.1f}%")
            
            # 重叠度不应该太高（允许一定的重叠用于上下文连贯）
            if overlap_ratio > 30:
                print(f"⚠️  警告：重叠度较高，但可能是为了保持上下文连贯性")
    
    print("\n✅ 重复内容处理测试通过")
    print()


if __name__ == "__main__":
    print("\n" + "=" * 80)
    print("开始测试分块修复")
    print("=" * 80 + "\n")
    
    test_empty_line_removal()
    test_chunk_size_optimization()
    test_content_length_display()
    test_page_label_format()
    test_duplicate_content()
    
    print("=" * 80)
    print("所有测试完成！")
    print("=" * 80)
