#!/usr/bin/env python3
"""
测试索引创建和数据存储
"""
import sys
import os

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 设置环境变量
os.environ['DASHSCOPE_API_KEY'] = 'sk-a571867722db45bc9da8d259aea8ad4a'
os.environ['VECTOR_STORE_TYPE'] = 'chroma'
os.environ['VECTOR_STORE_CONFIG'] = '{"persist_dir": "./chroma_data", "collection_name": "child_development"}'
os.environ['RAG_STORAGE_DIR'] = './storage'

def test_index_creation():
    print("=" * 80)
    print("测试索引创建和数据存储")
    print("=" * 80)
    
    try:
        from src.config.settings import settings
        from src.service.index_manager_service import IndexManagerService
        from llama_index.core import Document
        from llama_index.core.schema import NodeWithScore
        import time
        
        print(f"\n配置信息:")
        print(f"  - 向量存储类型：{settings.vector_store_type}")
        print(f"  - 向量存储配置：{settings.vector_store_config}")
        print(f"  - RAG 存储目录：{settings.rag_storage_dir}")
        
        # 初始化索引管理器
        print("\n正在初始化索引管理器...")
        index_manager = IndexManagerService()
        
        print(f"\n索引初始化状态:")
        print(f"  - 索引是否存在：{index_manager.index is not None}")
        
        # 创建测试文档
        print("\n创建测试文档...")
        test_docs = [
            Document(text="这是一个测试文档的第一段内容。", metadata={"source": "test"}),
            Document(text="这是测试文档的第二段内容，用于验证索引功能。", metadata={"source": "test"}),
            Document(text="这是第三段内容，确保数据能够正确存储到 Chroma 数据库中。", metadata={"source": "test"})
        ]
        
        # 转换为 Node
        from llama_index.core.schema import TextNode
        from llama_index.core.schema import NodeRelationship, RelatedNodeInfo
        import hashlib
        
        test_nodes = []
        for i, doc in enumerate(test_docs):
            node = TextNode(text=doc.text, metadata=doc.metadata)
            node.metadata["file_hash"] = "test_hash_123456"
            node.metadata["source_book"] = "测试文档"
            node.metadata["page_label"] = str(i + 1)
            node.relationships[NodeRelationship.SOURCE] = RelatedNodeInfo(node_id="test_hash_123456")
            test_nodes.append(node)
        
        print(f"  - 创建了 {len(test_nodes)} 个测试节点")
        
        # 插入节点
        print("\n正在插入测试节点到索引...")
        index_manager.insert_nodes(test_nodes)
        
        # 等待持久化完成
        print("等待数据持久化...")
        time.sleep(2)
        
        # 验证数据
        print("\n验证数据存储...")
        
        # 1. 检查 docstore
        if index_manager.index and hasattr(index_manager.index, 'docstore'):
            docstore = index_manager.index.docstore
            print(f"\nDocstore 状态:")
            print(f"  - 文档数量：{len(docstore.docs)}")
            
            if docstore.docs:
                print(f"\n  存储的文档:")
                for doc_id, node in docstore.docs.items():
                    print(f"    - ID: {doc_id}")
                    print(f"      file_hash: {node.metadata.get('file_hash', 'N/A')}")
                    print(f"      内容长度：{len(node.text)} 字符")
        
        # 2. 检查 Chroma 数据库
        chroma_path = settings.vector_store_config.get('persist_dir', './chroma_data')
        print(f"\nChroma 数据库路径：{chroma_path}")
        
        if os.path.exists(chroma_path):
            files = os.listdir(chroma_path)
            print(f"  - 文件列表：{files}")
            
            # 使用 sqlite3 检查
            import subprocess
            result = subprocess.run(
                ['sqlite3', f'{chroma_path}/chroma.sqlite3', 'SELECT COUNT(*) FROM embeddings;'],
                capture_output=True,
                text=True,
                cwd=os.path.dirname(os.path.abspath(__file__))
            )
            print(f"  - Embeddings 数量：{result.stdout.strip()}")
        
        # 3. 测试获取分块
        print("\n测试获取分块...")
        chunks = index_manager.get_document_chunks("test_hash_123456")
        print(f"  - 找到的分块数量：{len(chunks)}")
        
        if chunks:
            print(f"\n  分块详情:")
            # Convert chunks to list if it's not already to support slicing
            chunks_list = list(chunks) if not isinstance(chunks, list) else chunks
            for i, chunk in enumerate(chunks_list[:3]):
                print(f"\n    分块 {i+1}:")
                print(f"      - ID: {chunk['id']}")
                print(f"      - 内容：{chunk['content'][:50]}...")
                print(f"      - 元数据：{chunk['metadata']}")
        
        print("\n" + "=" * 80)
        print("✅ 测试完成！如果看到分块数据，说明索引创建成功")
        print("=" * 80)
        
        return len(chunks) > 0
        
    except Exception as e:
        print(f"\n❌ 错误：{e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_index_creation()
    sys.exit(0 if success else 1)
