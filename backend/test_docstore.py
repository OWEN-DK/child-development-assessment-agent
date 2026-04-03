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
print('Nodes in docstore:', len(index.docstore.docs))

index2 = VectorStoreIndex(nodes, storage_context=storage_context, store_nodes_override=True)
print('Nodes in docstore with override:', len(index2.docstore.docs))
