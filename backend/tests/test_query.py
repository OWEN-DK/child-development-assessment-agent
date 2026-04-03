from src.config.settings import settings
import chromadb
from src.core.embedding import SafeDashScopeEmbedding

client = chromadb.PersistentClient(path=settings.vector_store_config.get('persist_dir', './chroma_data'))
collection = client.get_or_create_collection('child_development')

embedder = SafeDashScopeEmbedding(
    model_name=settings.embedding_model_name, 
    api_key=settings.dashscope_api_key,
    embed_batch_size=settings.embedding_batch_size
)
query_emb = embedder.get_query_embedding('孩子')

results = collection.query(
    query_embeddings=[query_emb],
    n_results=10,
    include=['distances', 'documents', 'metadatas']
)
print('Query: 孩子')
for i in range(len(results['ids'][0])):
    doc = results['documents'][0][i]
    dist = results['distances'][0][i]
    print(f"ID: {results['ids'][0][i]}, Score: {1-dist:.4f}, Has Keyword: {'孩子' in doc}")
    print(f"Text: {doc[:50]}...")
