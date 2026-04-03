"""
测试 DashScope Embedding API 连接和响应
用于排查索引创建卡住的问题
"""
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.config.settings import settings
from src.core.embedding import SafeDashScopeEmbedding
from src.utils.logger import logger

def test_embedding_api():
    """测试嵌入 API 是否正常工作"""
    print("=" * 80)
    print("测试 DashScope Embedding API")
    print("=" * 80)
    
    print(f"\n配置信息:")
    print(f"  - 模型名称：{settings.embedding_model_name}")
    print(f"  - API Key: {'*' * 8}{settings.dashscope_api_key[-4:] if settings.dashscope_api_key else '未配置'}")
    print(f"  - 最大文本长度：{settings.embedding_max_text_length}")
    
    # 创建嵌入模型实例
    try:
        embed_model = SafeDashScopeEmbedding(
            model_name=settings.embedding_model_name,
            api_key=settings.dashscope_api_key
        )
        print(f"\n✓ 嵌入模型初始化成功")
    except Exception as e:
        print(f"\n✗ 嵌入模型初始化失败：{e}")
        return False
    
    # 测试简单嵌入
    test_texts = [
        "这是一个测试文本。",
        "Testing embedding API.",
        "Short text",
    ]
    
    print(f"\n正在测试嵌入 API 调用...")
    print(f"  - 测试文本数量：{len(test_texts)}")
    
    try:
        import time
        start_time = time.time()
        embeddings = embed_model.get_text_embedding_batch(test_texts)
        elapsed = time.time() - start_time
        
        print(f"\n✓ API 调用成功 (耗时：{elapsed:.2f}秒)")
        print(f"  - 返回嵌入数量：{len(embeddings)}")
        print(f"  - 嵌入维度：{len(embeddings[0]) if embeddings else 0}")
        
        # 验证嵌入质量
        for i, (text, emb) in enumerate(zip(test_texts, embeddings)):
            print(f"  - 文本 {i+1}: '{text[:30]}...' -> 维度 {len(emb)}")
        
        return True
        
    except Exception as e:
        print(f"\n✗ API 调用失败：{e}")
        import traceback
        traceback.print_exc()
        return False

def test_long_text():
    """测试长文本处理"""
    print("\n" + "=" * 80)
    print("测试长文本处理")
    print("=" * 80)
    
    embed_model = SafeDashScopeEmbedding(
        model_name=settings.embedding_model_name,
        api_key=settings.dashscope_api_key
    )
    
    # 创建一个超过限制的文本
    long_text = "这是一个测试文本。" * 200  # 约 3400 字符
    print(f"\n测试文本长度：{len(long_text)} 字符")
    print(f"最大允许长度：{embed_model.max_text_length} 字符")
    
    try:
        import time
        start_time = time.time()
        embedding = embed_model.get_text_embedding(long_text)
        elapsed = time.time() - start_time
        
        print(f"\n✓ 长文本处理成功 (耗时：{elapsed:.2f}秒)")
        print(f"  - 嵌入维度：{len(embedding)}")
        return True
        
    except Exception as e:
        print(f"\n✗ 长文本处理失败：{e}")
        return False

def test_network_timeout():
    """测试网络超时情况"""
    print("\n" + "=" * 80)
    print("测试网络超时处理")
    print("=" * 80)
    
    embed_model = SafeDashScopeEmbedding(
        model_name=settings.embedding_model_name,
        api_key=settings.dashscope_api_key
    )
    
    # 测试大量文本以模拟真实场景
    test_texts = [f"测试文本 {i}" for i in range(50)]
    print(f"\n发送 {len(test_texts)} 个文本进行嵌入...")
    
    try:
        import time
        start_time = time.time()
        embeddings = embed_model.get_text_embedding_batch(test_texts, show_progress=True)
        elapsed = time.time() - start_time
        
        print(f"\n✓ 批量嵌入成功 (耗时：{elapsed:.2f}秒)")
        print(f"  - 平均每个文本耗时：{elapsed / len(test_texts) * 1000:.0f}ms")
        return True
        
    except Exception as e:
        print(f"\n✗ 批量嵌入失败：{e}")
        return False

if __name__ == "__main__":
    print("\nDashScope Embedding API 诊断工具")
    print("用于排查索引创建卡住的问题\n")
    
    # 测试 1: 基本 API 连接
    test1_passed = test_embedding_api()
    
    # 测试 2: 长文本处理
    if test1_passed:
        test2_passed = test_long_text()
    else:
        test2_passed = False
        print("\n跳过测试 2（因为测试 1 失败）")
    
    # 测试 3: 网络超时
    if test1_passed:
        test3_passed = test_network_timeout()
    else:
        test3_passed = False
        print("\n跳过测试 3（因为测试 1 失败）")
    
    # 总结
    print("\n" + "=" * 80)
    print("诊断结果总结")
    print("=" * 80)
    print(f"测试 1 (基本 API): {'✓ 通过' if test1_passed else '✗ 失败'}")
    print(f"测试 2 (长文本): {'✓ 通过' if test2_passed else '✗ 失败'}")
    print(f"测试 3 (批量处理): {'✓ 通过' if test3_passed else '✗ 失败'}")
    
    if all([test1_passed, test2_passed, test3_passed]):
        print("\n✓ 所有测试通过！API 连接正常。")
        print("\n如果索引创建仍然卡住，可能的原因:")
        print("  1. 节点数量太多（1490 个），建议检查日志中的批次处理信息")
        print("  2. 某个特定节点的内容导致问题，检查日志中的错误信息")
        print("  3. 向量存储写入慢，检查 ChromaDB 的性能")
    else:
        print("\n✗ 部分测试失败，请检查:")
        print("  1. DASHSCOPE_API_KEY 环境变量是否正确配置")
        print("  2. 网络连接是否正常")
        print("  3. API 账户是否有足够余额")
        print("  4. 查看上方详细错误信息")
    
    print("\n" + "=" * 80)
