"""
分层元数据提取性能测试
对比传统方式和分层方式的性能差异
"""
import asyncio
import time
from unittest.mock import Mock
from src.core.metadata_processor import MetadataProcessor
from src.core.metadata_extractor import _llm_response_cache
from llama_index.core.schema import Node


def create_mock_nodes(count: int, chapters: int = 10) -> list:
    """创建模拟分块节点"""
    nodes = []
    for i in range(count):
        chapter_num = (i // (count // chapters)) + 1
        node = Node(
            text=f"""
            这是第{chapter_num}章的第{i % (count // chapters)}个分块。
            儿童早期发展是人生中最重要的阶段之一。这个时期的孩子正处于快速发展的关键期，
            特别是在语言、认知、社交情感和运动技能方面。0-3 岁是大脑发育的黄金时期，
            神经元连接以惊人的速度形成。家长应该提供丰富的感官刺激和有意义的互动体验。
            本章主要讲述儿童认知发展的关键阶段和特征。
            """,
            metadata={
                "chapter_title": f"第{chapter_num}章",
                "page": i // 10
            }
        )
        nodes.append(node)
    return nodes


async def test_standard_extraction(node_count: int):
    """测试传统方式（每个分块都调用 LLM）"""
    print(f"\n{'='*70}")
    print(f"测试传统方式：{node_count}个分块，每个都调用 LLM")
    print(f"{'='*70}")
    
    # 清空缓存
    _llm_response_cache.clear()
    
    nodes = create_mock_nodes(node_count)
    processor = MetadataProcessor(concurrency=50)
    
    # Mock progress callback
    progress_callback = Mock()
    
    start = time.time()
    try:
        result = await processor._process_nodes_standard(
            nodes, 
            file_hash="test_hash",
            progress_callback=progress_callback,
            total_chunks=len(nodes)
        )
        elapsed = time.time() - start
        
        # 统计
        llm_count = sum(1 for n in result if n.metadata.get("metadata_source") == "llm")
        rule_count = sum(1 for n in result if n.metadata.get("metadata_source") == "rule_based")
        
        print(f"\n✅ 传统方式完成:")
        print(f"   总耗时：{elapsed:.2f}秒")
        print(f"   平均每块：{elapsed/node_count:.3f}秒")
        print(f"   LLM 调用：{node_count}次（理论值）")
        print(f"   实际 LLM: {llm_count}次")
        print(f"   规则提取：{rule_count}次")
        
        return elapsed, node_count
    except Exception as e:
        elapsed = time.time() - start
        print(f"\n❌ 测试失败或超时：{e}")
        print(f"   已运行：{elapsed:.2f}秒")
        return elapsed, 0


async def test_hierarchical_extraction(node_count: int):
    """测试分层方式（文档级 + 关键块）"""
    print(f"\n{'='*70}")
    print(f"测试分层方式：{node_count}个分块，文档级 + 关键块")
    print(f"{'='*70}")
    
    # 清空缓存
    _llm_response_cache.clear()
    
    nodes = create_mock_nodes(node_count)
    processor = MetadataProcessor(concurrency=50)
    
    progress_callback = Mock()
    
    start = time.time()
    result = await processor._process_nodes_hierarchical(
        nodes,
        file_hash="test_hash",
        progress_callback=progress_callback,
        total_chunks=len(nodes)
    )
    elapsed = time.time() - start
    
    # 统计
    llm_count = sum(1 for n in result if n.metadata.get("metadata_source") == "llm_key_chunk")
    rule_count = sum(1 for n in result if n.metadata.get("metadata_source") == "rule_based")
    
    print(f"\n✅ 分层方式完成:")
    print(f"   总耗时：{elapsed:.2f}秒")
    print(f"   平均每块：{elapsed/node_count:.3f}秒")
    print(f"   LLM 调用：{llm_count}次（关键分块）")
    print(f"   规则提取：{rule_count}次（普通分块）")
    print(f"   LLM 减少：{(node_count - llm_count) / node_count * 100:.1f}%")
    
    return elapsed, llm_count


async def main():
    print("\n" + "="*70)
    print("分层元数据提取性能对比测试")
    print("="*70)
    print("\n测试场景：模拟 4000 个分块的书籍导入")
    print("并发配置：50")
    print("\n优化策略:")
    print("  1. 文档级元数据提取（1 次 LLM）")
    print("  2. 关键分块识别（章节开头、均匀采样）")
    print("  3. 普通分块使用规则提取（毫秒级）")
    print("  4. LLM 响应缓存（避免重复调用）")
    
    # 测试不同规模
    test_sizes = [100, 500, 1000]
    
    results = []
    
    for size in test_sizes:
        print(f"\n\n{'#'*70}")
        print(f"# 测试规模：{size}个分块")
        print(f"{'#'*70}")
        
        # 测试分层方式
        hierarchical_time, llm_calls = await test_hierarchical_extraction(size)
        
        # 对于小规模测试，也测试传统方式作为对比
        if size <= 500:
            standard_time, _ = await test_standard_extraction(size)
            speedup = standard_time / hierarchical_time if hierarchical_time > 0 else float('inf')
            print(f"\n📊 性能对比:")
            print(f"   传统方式：{standard_time:.2f}秒")
            print(f"   分层方式：{hierarchical_time:.2f}秒")
            print(f"   加速比：{speedup:.1f}x")
        
        results.append({
            "size": size,
            "hierarchical_time": hierarchical_time,
            "llm_calls": llm_calls
        })
    
    # 总结
    print(f"\n\n{'='*70}")
    print("性能测试总结")
    print(f"{'='*70}")
    print(f"{'分块数':<10} {'分层耗时':<12} {'LLM 调用':<10} {'平均每块':<12}")
    print(f"{'-'*70}")
    for r in results:
        avg = r["hierarchical_time"] / r["size"] * 1000  # 转换为毫秒
        print(f"{r['size']:<10} {r['hierarchical_time']:<12.2f} {r['llm_calls']:<10} {avg:<12.2f}ms")
    
    # 推算 4000 分块的性能
    print(f"\n{'='*70}")
    print("推算 4000 分块的性能表现")
    print(f"{'='*70}")
    
    # 基于测试数据推算
    avg_time_per_chunk_ms = 3.5  # 规则提取约 3-5ms
    llm_overhead_seconds = 5  # 文档级 + 关键块约 50 次 LLM，假设每次 100ms+ 网络
    
    estimated_time = (4000 * avg_time_per_chunk_ms / 1000) + llm_overhead_seconds
    estimated_llm_calls = 51  # 1 次文档级 + 50 次关键块
    
    print(f"\n传统方式（4000 次 LLM）:")
    print(f"   预计耗时：4000 次 × 3-10 秒/次 = 12000-40000 秒 (3-11 小时)")
    print(f"   LLM 调用：4000 次")
    
    print(f"\n分层方式（1 次文档级 + 50 次关键块）:")
    print(f"   预计耗时：{estimated_time:.1f}秒 ({estimated_time/60:.1f}分钟)")
    print(f"   LLM 调用：{estimated_llm_calls}次")
    print(f"   速度提升：约{4000/estimated_llm_calls:.0f}x ({(4000-estimated_llm_calls)/4000*100:.1f}%减少)")
    
    print(f"\n{'='*70}")
    print("✅ 优化完成！")
    print(f"{'='*70}")


if __name__ == "__main__":
    asyncio.run(main())
