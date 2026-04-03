import asyncio
from src.service.rag_service import rag_service


async def debug_pdf_search():
    # 先查看所有PDF文档的内容
    if rag_service.index_manager.is_index_available():
        docstore = rag_service.index_manager.get_index().docstore
        pdf_docs = []
        for doc_id in docstore.docs:
            doc = docstore.docs[doc_id]
            file_name = doc.metadata.get("file_name", "")
            if file_name.lower().endswith(".pdf"):
                pdf_docs.append(doc)

        print(f"PDF文档总数量: {len(pdf_docs)}")
        if pdf_docs:
            print("\n前3个PDF文档内容示例:")
            for i, doc in enumerate(pdf_docs[:3]):
                print(
                    f"\nPDF {i+1} 来自: {doc.metadata.get('file_name')}, 页码: {doc.metadata.get('page_label')}"
                )
                print(f"内容: {doc.text[:300]}...")

    # 测试搜索时关闭过滤，查看PDF的得分情况
    print("\n\n调试搜索PDF内容:")
    query = "超越行为"  # 搜索PDF书名相关的内容

    # 直接获取检索结果，不经过过滤
    if getattr(rag_service.retrieval_service, 'bm25_retriever', None) and getattr(rag_service.retrieval_service, 'vector_retriever', None):
        expanded_query = await rag_service.retrieval_service._expand_synonyms(query)
        bm25_nodes = await rag_service.retrieval_service.bm25_retriever.aretrieve(expanded_query)
        vector_nodes = await rag_service.retrieval_service.vector_retriever.aretrieve(expanded_query)

        print(f"BM25检索到 {len(bm25_nodes)} 个结果")
        print(f"向量检索到 {len(vector_nodes)} 个结果")

        print("\nBM25结果详情:")
        for i, node in enumerate(bm25_nodes[:10]):
            source = node.node.metadata.get("file_name", "Unknown")
            print(
                f"{i+1}. 来源: {source}, 得分: {node.score:.4f}, 内容: {node.node.text[:100]}..."
            )

        print("\n向量检索结果详情:")
        for i, node in enumerate(vector_nodes[:10]):
            source = node.node.metadata.get("file_name", "Unknown")
            print(
                f"{i+1}. 来源: {source}, 得分: {node.score:.4f}, 内容: {node.node.text[:100]}..."
            )


if __name__ == "__main__":
    asyncio.run(debug_pdf_search())
