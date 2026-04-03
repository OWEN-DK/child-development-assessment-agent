"""
元数据提取性能测试脚本
用于对比优化前后的性能差异
"""
import asyncio
import time
from src.core.metadata_extractor import MetadataExtractor, _llm_response_cache
from src.config.settings import settings


async def test_single_extraction():
    """测试单次提取性能"""
    sample_text = """
    儿童早期发展是人生中最重要的阶段之一。这个时期的孩子正处于快速发展的关键期，
    特别是在语言、认知、社交情感和运动技能方面。0-3 岁是大脑发育的黄金时期，
    神经元连接以惊人的速度形成。家长应该提供丰富的感官刺激和有意义的互动体验，
    帮助孩子建立安全依恋关系，培养好奇心和探索欲。
    
    推荐活动类型：亲子互动游戏
    适合年龄：1-3 岁
    涉及脑区：前额叶皮层、颞叶、边缘系统
    """
    
    print("\n=== 测试单次 LLM 元数据提取 ===")
    start = time.time()
    result = await MetadataExtractor.extract(sample_text, use_cache=True)
    elapsed = time.time() - start
    
    print(f"提取耗时：{elapsed:.2f}秒")
    print(f"主题：{result.topics}")
    print(f"脑区：{result.brain_regions}")
    print(f"年龄范围：{result.target_age_min}-{result.target_age_max}岁")
    print(f"活动类型：{result.activity_type}")
    
    return elapsed


async def test_batch_extraction():
    """测试批量提取性能（带缓存）"""
    sample_texts = [
        f"""
        儿童早期发展是人生中最重要的阶段之一。这个时期的孩子正处于快速发展的关键期，
        特别是在语言、认知、社交情感和运动技能方面。0-3 岁是大脑发育的黄金时期，
        神经元连接以惊人的速度形成。家长应该提供丰富的感官刺激和有意义的互动体验。
        这是第{i}段文本，内容略有不同。
        """
        for i in range(10)
    ]
    
    # 添加一些重复文本测试缓存效果
    sample_texts.extend(sample_texts[:5])
    
    print("\n=== 测试批量 LLM 元数据提取（15 条，含重复）===")
    start = time.time()
    
    tasks = [MetadataExtractor.extract(text, use_cache=True) for text in sample_texts]
    results = await asyncio.gather(*tasks)
    
    elapsed = time.time() - start
    
    print(f"批量提取耗时：{elapsed:.2f}秒")
    print(f"平均每条耗时：{elapsed/len(sample_texts):.2f}秒")
    print(f"缓存命中数：{len(_llm_response_cache)}条")
    print(f"缓存大小：{len(_llm_response_cache)}条")
    
    return elapsed


async def test_rule_based_extraction():
    """测试规则提取性能（作为对比）"""
    from src.core.metadata_extractor import _rule_extractor
    
    sample_text = """
    儿童早期发展是人生中最重要的阶段之一。这个时期的孩子正处于快速发展的关键期，
    特别是在语言、认知、社交情感和运动技能方面。适合 1 到 3 岁的孩子参与。
    通过亲子互动游戏，可以促进前额叶皮层和颞叶的发育。
    """
    
    print("\n=== 测试规则元数据提取（对比）===")
    start = time.time()
    result = _rule_extractor.extract(sample_text)
    elapsed = time.time() - start
    
    print(f"规则提取耗时：{elapsed:.4f}秒")
    print(f"主题：{result.topics}")
    print(f"年龄范围：{result.target_age_min}-{result.target_age_max}岁")
    
    return elapsed


async def main():
    """主测试函数"""
    print("=" * 60)
    print("元数据提取性能测试")
    print("=" * 60)
    print(f"当前并发配置：{settings.rag_metadata_extraction_concurrency}")
    print(f"LLM 模型：{settings.model_metadata_extraction}")
    
    # 测试规则提取（基线）
    rule_time = await test_rule_based_extraction()
    
    # 测试单次 LLM 提取
    single_time = await test_single_extraction()
    
    # 测试批量提取
    batch_time = await test_batch_extraction()
    
    # 测试缓存命中
    print("\n=== 测试缓存命中性能 ===")
    sample_text = """
    儿童早期发展是人生中最重要的阶段之一。这个时期的孩子正处于快速发展的关键期，
    特别是在语言、认知、社交情感和运动技能方面。0-3 岁是大脑发育的黄金时期。
    """
    
    # 第一次提取（未缓存）
    start1 = time.time()
    await MetadataExtractor.extract(sample_text, use_cache=True)
    time1 = time.time() - start1
    
    # 第二次提取（命中缓存）
    start2 = time.time()
    await MetadataExtractor.extract(sample_text, use_cache=True)
    time2 = time.time() - start2
    
    print(f"首次提取（未缓存）：{time1:.2f}秒")
    print(f"二次提取（命中缓存）：{time2:.4f}秒")
    print(f"缓存加速比：{time1/time2:.1f}x")
    
    # 总结
    print("\n" + "=" * 60)
    print("性能测试总结")
    print("=" * 60)
    print(f"规则提取耗时：{rule_time:.4f}秒（基线）")
    print(f"单次 LLM 提取：{single_time:.2f}秒（{single_time/rule_time:.1f}x 基线）")
    print(f"批量提取平均：{batch_time/15:.2f}秒/条")
    print(f"缓存命中提取：{time2:.4f}秒（{time1/time2:.1f}x 加速）")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
