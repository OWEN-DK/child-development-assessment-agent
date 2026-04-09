import asyncio
from src.service.rag_service import rag_service


async def test_search():
    # 测试搜索PDF内容
    query = "行为"  # 搜索PDF书中的常见内容
    results = await rag_service.search_content(query, limit=10)

    print(f"搜索关键词: '{query}'")
    print(f"找到结果数量: {len(results)}")

    if results:
        for i, result in enumerate(results):
            print(f"\n{i+1}. 来源: {result['source_book']}")
            print(f"   得分: {result['score']:.2f}")
            print(f"   内容: {result['content'][:200]}...")
    else:
        print("未找到任何结果")

        # 调试：获取所有文档，看有没有PDF内容
        print("\n调试：查看索引中的所有文档来源:")
        if rag_service.index_manager.is_index_available():
            docstore = rag_service.index_manager.get_index().docstore
            sources = set()
            for doc_id in docstore.docs:
                doc = docstore.docs[doc_id]
                source = doc.metadata.get("file_name", "Unknown")
                sources.add(source)
            print(f"所有来源: {sources}")

            # 统计PDF和EPUB的数量
            pdf_count = sum(
                1
                for doc_id in docstore.docs
                if docstore.docs[doc_id]
                .metadata.get("file_name", "")
                .lower()
                .endswith(".pdf")
            )
            epub_count = sum(
                1
                for doc_id in docstore.docs
                if docstore.docs[doc_id]
                .metadata.get("file_name", "")
                .lower()
                .endswith(".epub")
            )
            print(f"PDF文档数量: {pdf_count}")
            print(f"EPUB文档数量: {epub_count}")


if __name__ == "__main__":
    asyncio.run(test_search())
