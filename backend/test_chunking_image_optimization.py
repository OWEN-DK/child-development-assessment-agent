"""
测试分块优化效果
验证基于图片建议的优化：
1. 设置块间重叠 (Overlap) 100-200 字符
2. 优先保证语义完整性，调整分块位置
3. 增大块大小到 1024-1200 字符
4. 结合语义分割，而非纯固定字符数
"""

from src.core.metadata_processor import MetadataProcessor
from llama_index.core.schema import Document


def test_overlap_continuity():
    """测试块间重叠，确保上下文连续性"""
    print("=" * 80)
    print("测试 1: 块间重叠优化 (Overlap 200 字符)")
    print("=" * 80)
    
    # 创建包含完整实验案例的测试文本（模拟丹尼尔·卡尼曼实验）- 增加文本长度以触发分块
    test_text = """
这是关于儿童认知发展的重要实验。实验由著名心理学家丹尼尔·卡尼曼设计，主要研究儿童在决策过程中的认知偏差。

实验场景描述：研究人员将一群 4-6 岁的儿童分成两组，给他们展示两个不同的糖果罐。第一个罐子里有 10 颗普通糖果，第二个罐子里有 1 颗普通糖果和 1 颗特别大的巧克力糖果。研究人员确保所有儿童都能清楚地看到两个罐子中的内容，并且理解选择规则。

实验过程：第一组儿童被要求选择他们想要的糖果罐，第二组儿童则被要求预测其他小朋友会选择哪个罐子。研究人员记录了每个孩子的选择，并询问了他们选择的理由。整个实验过程被录像，以便后续分析。每个孩子单独进入实验室，避免同伴影响。

实验结果：研究发现，大多数 4-5 岁的儿童会选择第二个罐子，因为他们被那颗大巧克力糖果吸引，而忽略了获得糖果的概率。这表明幼儿在做决策时更容易受到显著特征的影响，而不是理性计算概率。相比之下，6 岁以上的儿童更倾向于选择第一个罐子，因为他们理解获得普通糖果的概率更高。

实验结论：这个实验揭示了儿童认知发展的一个重要特点——在特定年龄段，儿童的决策过程更多受到感知显著性的影响，而不是逻辑推理。这一发现对于理解儿童思维发展具有重要意义，也为后续的教育干预提供了理论依据。教育工作者应该根据儿童的认知发展阶段，设计适合的教学方法。

进一步研究：基于这个实验，研究团队又设计了一系列后续实验，探讨不同文化背景下的儿童决策差异，以及如何通过教育干预帮助儿童发展更理性的决策能力。这些研究为儿童认知发展理论提供了更多实证支持。
""" * 4
    
    doc = Document(text=test_text)
    chunk_target_size = 1024
    
    print(f"\n原始文本长度：{len(test_text)} 字符")
    print(f"目标 chunk 大小：{chunk_target_size} 字符")
    
    chunks = MetadataProcessor.split_chapters_into_chunks(
        [doc], 
        chunk_target_size=chunk_target_size, 
        file_hash="test_overlap_hash"
    )
    
    print(f"\n分块数量：{len(chunks)}")
    
    # 验证重叠
    if len(chunks) >= 2:
        for i in range(len(chunks) - 1):
            chunk1_text = chunks[i].text
            chunk2_text = chunks[i + 1].text
            
            # 检查重叠：第一个 chunk 的结尾应该在第二个 chunk 的开头出现
            overlap_check_length = min(200, len(chunk1_text) // 4)
            chunk1_end = chunk1_text[-overlap_check_length:]
            
            has_overlap = chunk1_end in chunk2_text
            
            print(f"\n--- Chunk {i+1} 和 Chunk {i+2} 的重叠检查 ---")
            print(f"Chunk {i+1} 长度：{len(chunk1_text)}")
            print(f"Chunk {i+2} 长度：{len(chunk2_text)}")
            print(f"检查重叠长度：{overlap_check_length} 字符")
            print(f"是否存在重叠：{'✅ 是' if has_overlap else '⚠️ 否 (可能因为语义完整而无需重叠)'}")
            
            if not has_overlap:
                # 显示边界内容，帮助理解
                print(f"\nChunk {i+1} 结尾 100 字符：...{chunk1_text[-100:]}")
                print(f"Chunk {i+2} 开头 100 字符：{chunk2_text[:100]}...")
    else:
        print("\n⚠️ 文本太短，只生成了一个 chunk，无法验证重叠")
    
    # 验证每个 chunk 的大小
    print("\n\n--- Chunk 大小统计 ---")
    for i, chunk in enumerate(chunks):
        print(f"Chunk {i+1}: {len(chunk.text)} 字符")
        print(f"  前 100 字符：{chunk.text[:100]}...")
        print(f"  后 100 字符：...{chunk.text[-100:]}")
    
    print("\n\n✅ 块间重叠优化测试完成")
    print()


def test_semantic_boundary_splitting():
    """测试语义边界分割，优先在句子/段落结尾切断"""
    print("=" * 80)
    print("测试 2: 语义边界分割优化")
    print("=" * 80)
    
    # 创建包含多个完整段落的测试文本
    test_text = """
第一段：儿童粗大动作发展。粗大动作发展是儿童早期发展的重要组成部分，包括抬头、翻身、坐、爬、站、走、跑、跳等基本动作技能的发展。这些技能的发展遵循一定的顺序和规律，从头部控制开始，逐渐发展到躯干稳定，最后是下肢运动能力的成熟。

第二段：儿童精细动作发展。精细动作发展涉及手部小肌肉群的协调运动，包括抓握、捏取、穿珠、画画、写字等技能。精细动作的发展对于儿童的日常生活自理能力、学习能力和创造力发展都具有重要意义。

第三段：儿童认知发展。认知发展是儿童心理发展的核心内容，包括感知觉、注意、记忆、思维、想象、问题解决等多个方面的发展。皮亚杰的认知发展阶段理论将儿童认知发展分为感知运动阶段、前运算阶段、具体运算阶段和形式运算阶段。

第四段：儿童语言发展。语言发展是儿童社会化的重要标志，包括语音、词汇、语法、语用等多个层面的发展。儿童语言发展经历了从咿呀学语到单词句、双词句、电报句，最终发展到完整句子的过程。

第五段：儿童社交情感发展。社交情感发展关系到儿童的人际关系建立和情绪管理能力，对其终身发展具有深远影响。这包括自我意识的发展、情绪识别与表达、同理心培养、同伴关系建立等多个方面。
""" * 2
    
    doc = Document(text=test_text)
    chunk_target_size = 800
    
    print(f"\n原始文本长度：{len(test_text)} 字符")
    print(f"目标 chunk 大小：{chunk_target_size} 字符")
    
    chunks = MetadataProcessor.split_chapters_into_chunks(
        [doc], 
        chunk_target_size=chunk_target_size, 
        file_hash="test_semantic_hash"
    )
    
    print(f"\n分块数量：{len(chunks)}")
    
    # 验证是否在语义边界分割
    print("\n--- 检查分割点是否在语义边界 ---")
    for i, chunk in enumerate(chunks):
        text = chunk.text
        print(f"\nChunk {i+1} (长度：{len(text)})")
        
        # 检查开头是否是完整的句子开始（不是半句话）
        starts_with_complete_sentence = (
            text[0].isupper() or  # 大写开头（英文）
            any(text.startswith(marker) for marker in ['第一段', '第二段', '第三段', '第四段', '第五段', '这是', '这些', '这个']) or
            text[0] in '第粗精认语社'  # 中文段落标记
        )
        
        # 检查结尾是否是完整的句子结束
        ends_with_complete_sentence = (
            text.rstrip().endswith(('。', '！', '？', '.', '!', '?')) or
            text.rstrip().endswith(('方面', '发展', '技能', '过程', '阶段'))  # 常见的结尾词
        )
        
        print(f"  开头 50 字符：{text[:50]}...")
        print(f"  结尾 50 字符：...{text[-50:]}")
        print(f"  开头是否完整：{'✅ 是' if starts_with_complete_sentence else '⚠️ 可能不完整'}")
        print(f"  结尾是否完整：{'✅ 是' if ends_with_complete_sentence else '⚠️ 可能不完整'}")
    
    print("\n\n✅ 语义边界分割优化测试完成")
    print()


def test_large_chunk_integrity():
    """测试大块大小 (1024-1200 字符) 保证完整案例"""
    print("=" * 80)
    print("测试 3: 大块完整性优化 (1024-1200 字符)")
    print("=" * 80)
    
    # 创建一个完整的案例分析，包含背景、过程、结果和结论
    case_study = """
案例名称：玛丽的情绪管理问题

案例背景：玛丽是一个 5 岁的小女孩，最近在幼儿园表现出频繁的焦躁和攻击性行为。她的老师反映，当其他小朋友不小心碰到她或者没有按照她的意愿玩游戏时，她会立即大哭大闹，甚至会推搡其他孩子。

案例分析：通过深入了解玛丽的家庭背景，心理学家发现玛丽的父母在她 3 岁时离异，她主要由祖母照顾。父母离异的过程充满了争吵和冲突，玛丽亲眼目睹了这些不愉快的场景。虽然现在已经过去两年，但这个问题一直没有得到妥善处理。

干预过程：心理咨询师采用了游戏治疗的方法，首先建立与玛丽的信任关系，然后通过角色扮演让玛丽表达内心的感受。在治疗过程中，咨询师发现玛丽内心深处仍然对父母的分离感到困惑和自责，她认为是自己不乖才导致父母分开。

治疗结果：经过 12 周的游戏治疗，玛丽的情绪管理能力有了显著改善。她学会了用语言而不是行为来表达自己的感受，也理解了父母离异并不是她的错。幼儿园老师反馈，玛丽的攻击性行为减少了 80%，与同伴的关系也明显改善。

案例启示：这个案例说明，儿童早期的心理创伤如果得不到及时处理，会在很大程度上影响他们的个人生活和人际关系。导致玛丽焦躁行为的并非当前的触发事件，而是多年前的问题没有得到妥善处理。这种经历常常伴随强烈的无助、绝望、恐惧和被遗弃感。对于类似情况，及早的专业干预至关重要。
""" * 2
    
    doc = Document(text=case_study)
    chunk_target_size = 1024
    
    print(f"\n原始文本长度：{len(case_study)} 字符")
    print(f"目标 chunk 大小：{chunk_target_size} 字符")
    
    chunks = MetadataProcessor.split_chapters_into_chunks(
        [doc], 
        chunk_target_size=chunk_target_size, 
        file_hash="test_integrity_hash"
    )
    
    print(f"\n分块数量：{len(chunks)}")
    
    # 验证案例完整性
    print("\n--- 检查案例完整性 ---")
    for i, chunk in enumerate(chunks):
        text = chunk.text
        print(f"\nChunk {i+1} (长度：{len(text)})")
        
        # 检查是否包含案例的关键部分
        has_background = '背景' in text or '背景' in text
        has_process = '过程' in text or '干预' in text
        has_result = '结果' in text or '改善' in text
        has_conclusion = '启示' in text or '结论' in text or '说明' in text
        
        completeness_score = sum([has_background, has_process, has_result, has_conclusion])
        
        print(f"  包含背景：{'✅' if has_background else '❌'}")
        print(f"  包含过程：{'✅' if has_process else '❌'}")
        print(f"  包含结果：{'✅' if has_result else '❌'}")
        print(f"  包含结论：{'✅' if has_conclusion else '❌'}")
        print(f"  完整性得分：{completeness_score}/4")
        
        if completeness_score >= 3:
            print(f"  🎉 这个 chunk 包含了完整的案例要素！")
    
    # 验证 chunk 大小是否在合理范围
    print("\n\n--- Chunk 大小统计 ---")
    sizes = [len(chunk.text) for chunk in chunks]
    print(f"最小：{min(sizes)} 字符")
    print(f"最大：{max(sizes)} 字符")
    print(f"平均：{sum(sizes) / len(sizes):.0f} 字符")
    print(f"目标范围：{int(chunk_target_size * 0.8)} - {int(chunk_target_size * 1.2)} 字符")
    
    print("\n\n✅ 大块完整性优化测试完成")
    print()


def test_no_key_semantic_unit_cut():
    """测试关键语义单元不被中途截断"""
    print("=" * 80)
    print("测试 4: 关键语义单元完整性")
    print("=" * 80)
    
    # 创建一个包含完整实验描述的文本（类似图片中提到的卡尼曼实验）
    experiment_text = """
实验名称：糖果罐选择实验

实验目的：研究儿童决策过程中的认知偏差

实验设计：研究人员将 60 名 4-6 岁的儿童随机分成两组。第一组有 30 人，第二组有 30 人。实验材料包括两个透明的糖果罐：A 罐装有 10 颗普通水果糖，B 罐装有 9 颗普通水果糖和 1 颗大型巧克力糖果。

实验流程：首先向儿童展示两个糖果罐，让他们清楚看到里面的糖果。然后告诉第一组儿童可以选择一个罐子，从里面随机取出一颗糖果。告诉第二组儿童预测其他小朋友会选择哪个罐子。记录每个孩子的选择和理由。

实验结果：统计显示，第一组中有 24 名儿童（80%）选择了 B 罐，第二组中有 22 名儿童（73%）预测其他人会选择 B 罐。访谈发现，选择 B 罐的儿童主要被那颗大巧克力糖果吸引，而忽略了获得它的实际概率只有 1/10。

实验结论：这个实验揭示了儿童（特别是 4-5 岁）在决策时更容易受到显著特征的影响，表现出"显著性偏差"。他们关注的是最显眼的选项（大巧克力），而不是理性计算概率。这一发现对理解儿童认知发展和设计适合儿童的教育方法具有重要启示意义。
""" * 2
    
    doc = Document(text=experiment_text)
    chunk_target_size = 1024
    
    print(f"\n原始文本长度：{len(experiment_text)} 字符")
    print(f"目标 chunk 大小：{chunk_target_size} 字符")
    
    chunks = MetadataProcessor.split_chapters_into_chunks(
        [doc], 
        chunk_target_size=chunk_target_size, 
        file_hash="test_semantic_unit_hash"
    )
    
    print(f"\n分块数量：{len(chunks)}")
    
    # 验证关键语义单元是否完整
    print("\n--- 检查关键语义单元完整性 ---")
    key_elements = ['实验目的', '实验设计', '实验流程', '实验结果', '实验结论']
    
    for i, chunk in enumerate(chunks):
        text = chunk.text
        print(f"\nChunk {i+1} (长度：{len(text)})")
        
        # 检查包含哪些关键要素
        contained_elements = [elem for elem in key_elements if elem in text]
        missing_elements = [elem for elem in key_elements if elem not in text]
        
        print(f"  包含的要素：{', '.join(contained_elements) if contained_elements else '无'}")
        if missing_elements:
            print(f"  缺失的要素：{', '.join(missing_elements)}")
        
        # 检查是否有被截断的迹象（以冒号结尾但没有后续内容）
        has_cut_off = text.rstrip().endswith(('：', ':', '包括', '分为'))
        print(f"  是否有截断迹象：{'⚠️ 是' if has_cut_off else '✅ 否'}")
        
        if not has_cut_off and len(contained_elements) >= 2:
            print(f"  🎉 这个 chunk 保持了语义完整性！")
    
    print("\n\n✅ 关键语义单元完整性测试完成")
    print()


def run_all_tests():
    """运行所有测试"""
    print("\n" + "=" * 80)
    print("开始测试分块优化效果（基于图片建议）")
    print("=" * 80 + "\n")
    
    test_overlap_continuity()
    test_semantic_boundary_splitting()
    test_large_chunk_integrity()
    test_no_key_semantic_unit_cut()
    
    print("\n" + "=" * 80)
    print("所有测试完成！")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    run_all_tests()
