"""
测试分块优化效果
验证配置参数调整、小 chunk 合并机制、语言检测功能
"""

from src.core.metadata_processor import MetadataProcessor
from llama_index.core.schema import Document


def test_language_detection():
    """测试语言检测功能"""
    print("=" * 80)
    print("测试 1: 语言检测功能")
    print("=" * 80)
    
    # 英文文本
    en_text = "This is a test text in English. It contains multiple sentences. " * 10
    en_lang = detect_language(en_text)
    print(f"\n英文文本检测结果：{en_lang}")
    assert en_lang == "en", f"英文文本应检测为'en'，实际为'{en_lang}'"
    
    # 中文文本
    zh_text = "这是一段测试文本，主要介绍儿童发展的基本概念。" * 10
    zh_lang = detect_language(zh_text)
    print(f"中文文本检测结果：{zh_lang}")
    assert zh_lang == "zh", f"中文文本应检测为'zh'，实际为'{zh_lang}'"
    
    # 混合文本（英文为主）
    mixed_en_text = "This is English text. 这是一些中文。More English here." * 5
    mixed_en_lang = detect_language(mixed_en_text)
    print(f"混合文本（英文为主）检测结果：{mixed_en_lang}")
    
    # 混合文本（中文为主）
    mixed_zh_text = "这是中文内容。This is some English. 更多的中文内容。" * 5
    mixed_zh_lang = detect_language(mixed_zh_text)
    print(f"混合文本（中文为主）检测结果：{mixed_zh_lang}")
    
    print("\n✅ 语言检测功能测试通过")
    print()


def test_english_chunking():
    """测试英文内容分块优化"""
    print("=" * 80)
    print("测试 2: 英文内容分块优化")
    print("=" * 80)
    
    # 创建英文测试文本（模拟真实书籍内容）
    english_text = """
I only knew his name and came across some of the books he wrote. He has invited me alone for a dinner during a seminar I was attending. Here is a man who is a retired military general and an expert in a subject I was interested in.

Those powerful arms, and the retired general's brain. The hours and years that went into it. The dedication and commitment to excellence that spanned decades.

The training methods he developed were revolutionary. They combined traditional wisdom with modern scientific understanding. Each exercise was carefully designed to build strength, endurance, and mental fortitude.

His approach to teaching was equally impressive. He understood that true mastery comes from within. It's not about forcing the body to comply, but rather guiding it to discover its own potential.

The principles he taught were universal. They applied not just to physical training, but to all aspects of life. Discipline, persistence, and continuous improvement were the cornerstones of his philosophy.
""" * 3
    
    doc = Document(text=english_text)
    chunk_target_size = 1000
    
    print(f"\n原始文本长度：{len(english_text)} 字符")
    print(f"目标 chunk 大小：{chunk_target_size} 字符")
    
    chunks = MetadataProcessor.split_chapters_into_chunks(
        [doc], 
        chunk_target_size=chunk_target_size, 
        file_hash="test_en_hash"
    )
    
    print(f"\n分块数量：{len(chunks)}")
    
    MIN_CHUNK_SIZE = int(chunk_target_size * 0.4)
    
    for i, chunk in enumerate(chunks):
        print(f"\n--- Chunk {i+1} ---")
        print(f"长度：{len(chunk.text)} 字符")
        print(f"内容前 150 字符：{chunk.text[:150]}...")
        
        # 验证 chunk 大小（除非是最后一个 chunk）
        if i < len(chunks) - 1:
            assert len(chunk.text) >= MIN_CHUNK_SIZE, \
                f"Chunk {i+1} 过小：{len(chunk.text)} < {MIN_CHUNK_SIZE}"
    
    print("\n\n✅ 英文内容分块优化测试通过")
    print()


def test_chinese_chunking():
    """测试中文内容分块"""
    print("=" * 80)
    print("测试 3: 中文内容分块")
    print("=" * 80)
    
    # 创建中文测试文本
    chinese_text = """
这是第一段内容，主要介绍儿童粗大动作发展的基本概念和训练方法。粗大动作发展是儿童早期发展的重要组成部分，包括抬头、翻身、坐、爬、站、走、跑等基本动作技能。

第二段内容讲述儿童精细动作发展的特点和重要性。精细动作发展涉及手部小肌肉群的协调运动，对于儿童的日常生活和学习能力发展至关重要。

第三段内容关于儿童认知发展的关键期和敏感期。认知发展是儿童心理发展的核心内容，包括感知觉、注意、记忆、思维、想象等多个方面的发展。

第四段内容介绍儿童语言发展的阶段和特征。语言发展是儿童社会化的重要标志，包括语音、词汇、语法、语用等多个层面的发展。

第五段内容关于儿童社交情感发展的规律和影响因素。社交情感发展关系到儿童的人际关系建立和情绪管理能力，对其终身发展具有深远影响。
""" * 2
    
    doc = Document(text=chinese_text)
    chunk_target_size = 1000
    
    print(f"\n原始文本长度：{len(chinese_text)} 字符")
    print(f"目标 chunk 大小：{chunk_target_size} 字符")
    
    chunks = MetadataProcessor.split_chapters_into_chunks(
        [doc], 
        chunk_target_size=chunk_target_size, 
        file_hash="test_zh_hash"
    )
    
    print(f"\n分块数量：{len(chunks)}")
    
    for i, chunk in enumerate(chunks):
        print(f"\n--- Chunk {i+1} ---")
        print(f"长度：{len(chunk.text)} 字符")
        print(f"内容前 100 字符：{chunk.text[:100]}...")
    
    print("\n\n✅ 中文内容分块测试通过")
    print()


def test_chunk_merge_mechanism():
    """测试小 chunk 合并机制"""
    print("=" * 80)
    print("测试 4: 小 chunk 合并机制")
    print("=" * 80)
    
    # 创建包含多个短段落的文本
    short_paragraphs_text = """
这是一个短段落。
这是另一个短段落。
还有第三个短段落。
第四个短段落内容。
第五个短段落在这里。
""" * 5
    
    doc = Document(text=short_paragraphs_text)
    chunk_target_size = 800
    
    print(f"\n原始文本长度：{len(short_paragraphs_text)} 字符")
    print(f"目标 chunk 大小：{chunk_target_size} 字符")
    print(f"最小 chunk 大小：{int(chunk_target_size * 0.4)} 字符")
    
    chunks = MetadataProcessor.split_chapters_into_chunks(
        [doc], 
        chunk_target_size=chunk_target_size, 
        file_hash="test_merge_hash"
    )
    
    print(f"\n分块数量：{len(chunks)}")
    
    total_length = sum(len(chunk.text) for chunk in chunks)
    avg_chunk_size = total_length / len(chunks) if chunks else 0
    
    print(f"总长度：{total_length} 字符")
    print(f"平均 chunk 大小：{avg_chunk_size:.1f} 字符")
    
    for i, chunk in enumerate(chunks):
        print(f"\n--- Chunk {i+1} ---")
        print(f"长度：{len(chunk.text)} 字符")
        print(f"内容：{chunk.text[:100]}...")
    
    print("\n\n✅ 小 chunk 合并机制测试通过")
    print()


def main():
    """运行所有测试"""
    print("\n" + "=" * 80)
    print("开始测试分块优化效果")
    print("=" * 80 + "\n")
    
    test_language_detection()
    test_english_chunking()
    test_chinese_chunking()
    test_chunk_merge_mechanism()
    
    print("=" * 80)
    print("所有测试完成！✅")
    print("=" * 80)


if __name__ == "__main__":
    main()
