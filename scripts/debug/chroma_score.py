from llama_index.core import VectorStoreIndex, StorageContext, Settings
from llama_index.core.schema import TextNode
from llama_index.vector_stores.chroma import ChromaVectorStore
from llama_index.core.embeddings import MockEmbedding
import chromadb
import shutil
import os

Settings.embed_model = MockEmbedding(embed_dim=1536)

if os.path.exists('test_chroma'): shutil.rmtree('test_chroma')
db = chromadb.PersistentClient(path='test_chroma')
collection = db.get_or_create_collection('test')
vector_store = ChromaVectorStore(chroma_collection=collection)
storage_context = StorageContext.from_defaults(vector_store=vector_store)

nodes = [TextNode(text='hello world', id_='1')]
index = VectorStoreIndex(nodes, storage_context=storage_context)
retriever = index.as_retriever()
nodes_retrieved = retriever.retrieve('hello world')
print('Score for identical match (L2 space):', nodes_retrieved[0].score)

collection2 = db.get_or_create_collection('test2', metadata={'hnsw:space': 'cosine'})
vector_store2 = ChromaVectorStore(chroma_collection=collection2)
storage_context2 = StorageContext.from_defaults(vector_store=vector_store2)

index2 = VectorStoreIndex(nodes, storage_context=storage_context2)
retriever2 = index2.as_retriever()
nodes_retrieved2 = retriever2.retrieve('hello world')
print('Score for identical match (Cosine space):', nodes_retrieved2[0].score)
