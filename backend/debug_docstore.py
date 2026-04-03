#!/usr/bin/env python3
"""
调试 docstore 存储位置
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

def debug_docstore():
    print("=" * 80)
    print("调试 Docstore 存储位置")
    print("=" * 80)
    
    try:
        from src.service.index_manager_service import IndexManagerService
        from llama_index.core.schema import TextNode, NodeRelationship, RelatedNodeInfo
        
        # 初始化索引管理器
        print("\n正在初始化索引管理器...")
        index_manager = IndexManagerService()
        
        # 创建测试文档
        print("\n创建测试节点...")
        test_nodes = []
        for i in range(3):
            node = TextNode(text=f"这是测试文档的第 {i+1} 段内容。", metadata={"source": "test"})
            node.metadata["file_hash"] = "test_hash_123456"
            node.metadata["source_book"] = "测试文档"
            node.metadata["page_label"] = str(i + 1)
            node.relationships[NodeRelationship.SOURCE] = RelatedNodeInfo(node_id="test_hash_123456")
            test_nodes.append(node)
        
        print(f"  - 创建了 {len(test_nodes)} 个测试节点")
        
        # 插入节点
        print("\n正在插入测试节点到索引...")
        index_manager.insert_nodes(test_nodes)
        
        # 详细检查索引结构
        print("\n详细检查索引结构:")
        if index_manager.index:
            print(f"  - 索引类型：{type(index_manager.index)}")
            print(f"  - 索引属性：{dir(index_manager.index)}")
            
            # 检查 storage_context
            if hasattr(index_manager.index, 'storage_context'):
                sc = index_manager.index.storage_context
                print(f"\n  StorageContext:")
                print(f"    - 类型：{type(sc)}")
                print(f"    - 属性：{dir(sc)}")
                
                if hasattr(sc, 'docstore'):
                    print(f"\n  StorageContext.docstore:")
                    print(f"    - 类型：{type(sc.docstore)}")
                    print(f"    - 文档数量：{len(sc.docstore.docs) if hasattr(sc.docstore, 'docs') else 'N/A'}")
                    
                    if hasattr(sc.docstore, 'docs') and sc.docstore.docs:
                        print(f"\n    文档列表:")
                        for doc_id, node in sc.docstore.docs.items():
                            print(f"      - {doc_id}: {node.text[:30]}...")
            
            # 检查 index.docstore
            if hasattr(index_manager.index, 'docstore'):
                print(f"\n  Index.docstore:")
                print(f"    - 类型：{type(index_manager.index.docstore)}")
                print(f"    - 文档数量：{len(index_manager.index.docstore.docs) if hasattr(index_manager.index.docstore, 'docs') else 'N/A'}")
            
            # 检查 vector_store
            if hasattr(index_manager.index, '_vector_store'):
                print(f"\n  Vector Store:")
                print(f"    - 类型：{type(index_manager.index._vector_store)}")
                if hasattr(index_manager.index._vector_store, '_collection'):
                    collection = index_manager.index._vector_store._collection
                    print(f"    - Chroma 集合：{collection.name}")
                    print(f"    - 集合中文档数量：{collection.count()}")
        
        print("\n" + "=" * 80)
        
    except Exception as e:
        print(f"\n❌ 错误：{e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    debug_docstore()
