from src.config.settings import settings
import chromadb
from src.core.embedding import SafeDashScopeEmbedding

print(settings.vector_store_config)
client = chromadb.PersistentClient(path=settings.vector_store_config.get('persist_dir', './chroma_data'))
print('Collections:', client.list_collections())
if client.list_collections():
    collection = client.get_collection(client.list_collections()[0].name)
    print('Collection count:', collection.count())
    
    embedder = SafeDashScopeEmbedding(model_name=settings.embedding_model_name, api_key=settings.dashscope_api_key)
    query_emb = embedder.get_query_embedding('孩子')
    
    results = collection.query(
        query_embeddings=[query_emb],
        n_results=5,
        include=['distances', 'documents', 'metadatas']
    )
    for i in range(len(results['ids'][0])):
        dist = results['distances'][0][i]
        print(f"Distance: {dist:.4f}, Score (1-dist): {1 - dist:.4f}")
        print(f"Text preview: {results['documents'][0][i][:50]}")
