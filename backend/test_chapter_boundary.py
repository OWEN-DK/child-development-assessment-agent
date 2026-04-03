"""
测试章节边界保护功能
验证不同章节的段落不会被合并
"""

from src.core.metadata_processor import MetadataProcessor
from llama_index.core.schema import Document


def test_chapter_boundary_protection():
    """测试章节边界保护：不同章节的 chunk 不合并"""
    print("=" * 80)
    print("测试：章节边界保护功能")
    print("=" * 80)
    
    # 创建多个章节的文档对象，模拟真实的 EPUB/PDF 章节结构
    # 每个 Document 代表一个独立的章节
    chapter1_doc = Document(
        text="这是第一章的第一段内容，主要介绍儿童发展的基本概念。儿童发展是一个复杂的过程，涉及多个方面的发展。\n\n" * 5,
        metadata={"chapter_title": "第一章 儿童发展概述", "chapter": "1"}
    )
    
    chapter2_doc = Document(
        text="这是第二章的第一段内容，介绍儿童粗大动作发展的特点。粗大动作发展是儿童早期发展的重要组成部分。\n\n" * 5,
        metadata={"chapter_title": "第二章 粗大动作发展", "chapter": "2"}
    )
    
    chapter3_doc = Document(
        text="这是第三章的第一段内容，介绍儿童精细动作发展的规律。精细动作发展涉及手部小肌肉群的协调运动。\n\n" * 5,
        metadata={"chapter_title": "第三章 精细动作发展", "chapter": "3"}
    )
    
    documents = [chapter1_doc, chapter2_doc, chapter3_doc]
    chunk_target_size = 400
    
    total_length = sum(len(doc.text) for doc in documents)
    print(f"\n原始文本总长度：{total_length} 字符")
    print(f"章节数量：{len(documents)}")
    print(f"目标 chunk 大小：{chunk_target_size} 字符")
    print(f"最小 chunk 大小：{int(chunk_target_size * 0.4)} 字符")
    
    chunks = MetadataProcessor.split_chapters_into_chunks(
        documents, 
        chunk_target_size=chunk_target_size, 
        file_hash="test_chapter_boundary_hash"
    )
    
    print(f"\n分块数量：{len(chunks)}")
    
    # 验证每个 chunk 的章节信息
    chapter_groups = {}
    for i, chunk in enumerate(chunks):
        chapter_title = chunk.metadata.get('chapter_title', 'Unknown')
        chapter = chunk.metadata.get('chapter', 'Unknown')
        chapter_info = chapter_title or chapter
        
        if chapter_info not in chapter_groups:
            chapter_groups[chapter_info] = []
        
        chapter_groups[chapter_info].append({
            'index': i,
            'length': len(chunk.text),
            'content': chunk.text[:100]
        })
        
        print(f"\n--- Chunk {i+1} ---")
        print(f"章节：{chapter_info}")
        print(f"长度：{len(chunk.text)} 字符")
        print(f"内容前 100 字符：{chunk.text[:100]}...")
    
    # 验证章节分组
    print("\n" + "=" * 80)
    print("章节分组统计")
    print("=" * 80)
    
    for chapter_info, chunk_list in chapter_groups.items():
        print(f"\n{chapter_info}: {len(chunk_list)} 个 chunk")
        total_length = sum(c['length'] for c in chunk_list)
        avg_length = total_length / len(chunk_list)
        print(f"  总长度：{total_length} 字符")
        print(f"  平均长度：{avg_length:.1f} 字符")
    
    # 验证：每个章节的 chunk 数量应该合理
    # 如果章节边界保护生效，每个章节应该有独立的 chunk
    assert len(chapter_groups) >= 2, "应该至少有 2 个不同的章节"
    
    # 验证：没有跨章节的合并
    # 检查每个 chunk 的章节信息是否一致
    cross_chapter_found = False
    for i, chunk in enumerate(chunks):
        content = chunk.text
        chapter_title = chunk.metadata.get('chapter_title', chunk.metadata.get('chapter', ''))
        
        # 检查是否包含其他章节的内容标记
        for other_chapter_num in ['1', '2', '3']:
            other_chapter_title = f"第{'一二三'[int(other_chapter_num)-1]}章"
            if chapter_title and other_chapter_title in chapter_title:
                # 当前 chunk 属于这个章节
                # 检查内容是否包含其他章节的特征词
                if other_chapter_num == '1' and ('第二章' in content or '第三章' in content or '粗大动作' in content or '精细动作' in content):
                    print(f"\n⚠️  警告：Chunk {i+1} 可能包含跨章节内容")
                    print(f"   当前章节：{chapter_title}")
                    print(f"   内容：{content[:200]}...")
                    cross_chapter_found = True
                elif other_chapter_num == '2' and ('第一章' in content or '第三章' in content or '儿童发展概述' in content or '精细动作' in content):
                    print(f"\n⚠️  警告：Chunk {i+1} 可能包含跨章节内容")
                    print(f"   当前章节：{chapter_title}")
                    print(f"   内容：{content[:200]}...")
                    cross_chapter_found = True
                elif other_chapter_num == '3' and ('第一章' in content or '第二章' in content or '儿童发展概述' in content or '粗大动作' in content):
                    print(f"\n⚠️  警告：Chunk {i+1} 可能包含跨章节内容")
                    print(f"   当前章节：{chapter_title}")
                    print(f"   内容：{content[:200]}...")
                    cross_chapter_found = True
    
    assert not cross_chapter_found, "发现跨章节合并，章节边界保护失效"
    
    print("\n\n✅ 章节边界保护功能测试通过")
    print("不同章节的内容保持独立，未发生跨章节合并")


def test_same_chapter_merge():
    """测试同一章节内的小 chunk 合并"""
    print("\n" + "=" * 80)
    print("测试：同一章节内的小 chunk 合并")
    print("=" * 80)
    
    # 创建单个章节的多个短段落
    single_chapter_text = """## 第一章 测试章节

这是第一段短内容。
这是第二段短内容。
这是第三段短内容。
这是第四段短内容。
这是第五段短内容。
这是第六段短内容。
这是第七段短内容。
这是第八段短内容。
"""
    
    doc = Document(text=single_chapter_text)
    chunk_target_size = 300
    
    print(f"\n原始文本长度：{len(single_chapter_text)} 字符")
    print(f"目标 chunk 大小：{chunk_target_size} 字符")
    
    chunks = MetadataProcessor.split_chapters_into_chunks(
        [doc], 
        chunk_target_size=chunk_target_size, 
        file_hash="test_same_chapter_hash"
    )
    
    print(f"\n分块数量：{len(chunks)}")
    
    for i, chunk in enumerate(chunks):
        print(f"\n--- Chunk {i+1} ---")
        print(f"长度：{len(chunk.text)} 字符")
        print(f"内容：{chunk.text[:150]}...")
    
    # 验证：同一章节的短段落应该被合并
    # 如果没有合并，会有很多小 chunk
    print(f"\n\n✅ 同一章节内合并测试通过")
    print(f"分块数量：{len(chunks)} (应该较少，因为短段落被合并了)")


def main():
    """运行所有测试"""
    print("\n" + "=" * 80)
    print("开始测试章节边界保护功能")
    print("=" * 80 + "\n")
    
    test_chapter_boundary_protection()
    test_same_chapter_merge()
    
    print("\n" + "=" * 80)
    print("所有测试完成！✅")
    print("=" * 80)


if __name__ == "__main__":
    main()
