from src.config.settings import settings
from llama_index.core import VectorStoreIndex, StorageContext, Settings
from llama_index.core.schema import TextNode
from llama_index.vector_stores.chroma import ChromaVectorStore
from src.core.embedding import SafeDashScopeEmbedding
import chromadb
import shutil
import os

import asyncio
async def main():
    Settings.embed_model = SafeDashScopeEmbedding(
        model_name=settings.embedding_model_name, api_key=settings.dashscope_api_key
    )

    if os.path.exists('test_chroma'): shutil.rmtree('test_chroma')
    db = chromadb.PersistentClient(path='test_chroma')
    
    collection_l2 = db.get_or_create_collection('test_l2', metadata={'hnsw:space': 'l2'})
    vector_store_l2 = ChromaVectorStore(chroma_collection=collection_l2)
    storage_context_l2 = StorageContext.from_defaults(vector_store=vector_store_l2)

    collection_cos = db.get_or_create_collection('test_cos', metadata={'hnsw:space': 'cosine'})
    vector_store_cos = ChromaVectorStore(chroma_collection=collection_cos)
    storage_context_cos = StorageContext.from_defaults(vector_store=vector_store_cos)

    nodes = [
        TextNode(text='临床医生是指直接参与诊断、治疗和护理病人的医生。', id_='1'),
        TextNode(text='这里是一些关于育儿的知识。', id_='2')
    ]
    
    index_l2 = VectorStoreIndex(nodes, storage_context=storage_context_l2)
    retriever_l2 = index_l2.as_retriever(similarity_top_k=2)
    
    index_cos = VectorStoreIndex(nodes, storage_context=storage_context_cos)
    retriever_cos = index_cos.as_retriever(similarity_top_k=2)

    query = "临床医生"
    expanded_query = "临床医生 医师 大夫 medical doctor clinician physician"

    print("--- L2 Space ---")
    print(f"Query: {query}")
    for n in retriever_l2.retrieve(query):
        print(f"  Score: {n.score:.4f}, Text: {n.text}")
    print(f"Query: {expanded_query}")
    for n in retriever_l2.retrieve(expanded_query):
        print(f"  Score: {n.score:.4f}, Text: {n.text}")

    print("\n--- Cosine Space ---")
    print(f"Query: {query}")
    for n in retriever_cos.retrieve(query):
        print(f"  Score: {n.score:.4f}, Text: {n.text}")
    print(f"Query: {expanded_query}")
    for n in retriever_cos.retrieve(expanded_query):
        print(f"  Score: {n.score:.4f}, Text: {n.text}")

if __name__ == '__main__':
    asyncio.run(main())
