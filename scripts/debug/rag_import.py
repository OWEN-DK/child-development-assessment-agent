import asyncio
import os
from src.service.rag_service import rag_service


async def test_rag_import():
    print("=" * 60)
    print("测试 RAG 文档导入")
    print("=" * 60)

    # 测试文件路径
    book_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "book")
    test_file = os.path.join(book_dir, "运动改变大脑 .epub")

    if not os.path.exists(test_file):
        print(f"❌ 测试文件不存在: {test_file}")
        return

    print(f"\n使用测试文件: {test_file}")

    # 进度回调
    def progress_callback(stage, progress, message):
        print(f"   [{stage}] {progress:.1f}% - {message}")

    try:
        print("\n开始导入...")
        await rag_service.ingest_book(
            test_file,
            original_filename="运动改变大脑.epub",
            progress_callback=progress_callback,
        )

        print("\n" + "=" * 60)
        print("✅ 文档导入成功！")
        print("=" * 60)

        # 验证索引
        print(f"\n索引状态: {'可用' if rag_service.index_manager.is_index_available() else '不可用'}")
        if rag_service.index_manager.is_index_available():
            print(f"文档数量: {len(rag_service.index_manager.get_index().docstore.docs)}")

        # 测试检索
        print("\n测试检索功能...")
        results = await rag_service.retrieve_knowledge(
            "前庭觉训练 3岁儿童", age=3, limit=3
        )
        print(f"检索到 {len(results)} 条结果")
        for i, item in enumerate(results, 1):
            print(f"\n{i}. {item.source_book} (得分: {item.relevance_score:.2f})")
            print(f"   {item.content[:100]}...")

    except Exception as e:
        print(f"\n❌ 导入失败: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_rag_import())
