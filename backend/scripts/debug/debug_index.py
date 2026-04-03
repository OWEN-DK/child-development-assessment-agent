#!/usr/bin/env python3
"""
调试脚本：检查索引初始化和向量存储
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

def check_index_initialization():
    print("=" * 80)
    print("检查索引初始化和向量存储")
    print("=" * 80)
    
    try:
        from src.config.settings import settings
        from src.service.index_manager_service import IndexManagerService, STORAGE_DIR
        
        print(f"\n配置信息:")
        print(f"  - 向量存储类型：{settings.vector_store_type}")
        print(f"  - 向量存储配置：{settings.vector_store_config}")
        print(f"  - RAG 存储目录：{STORAGE_DIR}")
        
        # 检查存储目录
        index_dir = os.path.join(STORAGE_DIR, "index")
        print(f"\n索引目录：{index_dir}")
        print(f"  - 是否存在：{os.path.exists(index_dir)}")
        
        if os.path.exists(index_dir):
            files = os.listdir(index_dir)
            print(f"  - 文件列表：{files}")
        
        # 检查 Chroma 数据目录
        chroma_path = settings.vector_store_config.get('persist_dir', './chroma_data')
        print(f"\nChroma 数据目录：{chroma_path}")
        print(f"  - 是否存在：{os.path.exists(chroma_path)}")
        
        if os.path.exists(chroma_path):
            files = os.listdir(chroma_path)
            print(f"  - 文件列表：{files}")
        
        # 初始化索引管理器
        print("\n正在初始化索引管理器...")
        index_manager = IndexManagerService()
        
        print(f"\n索引状态:")
        print(f"  - 索引对象：{index_manager.index}")
        print(f"  - 索引是否存在：{index_manager.index is not None}")
        
        if index_manager.index:
            print(f"  - 索引类型：{type(index_manager.index)}")
            print(f"  - 向量存储：{index_manager.index.vector_store}")
            print(f"  - 向量存储类型：{type(index_manager.index.vector_store)}")
            
            # 检查 docstore
            if hasattr(index_manager.index, 'docstore'):
                docstore = index_manager.index.docstore
                print(f"\nDocstore 状态:")
                print(f"  - Docstore 对象：{type(docstore)}")
                print(f"  - 文档数量：{len(docstore.docs) if hasattr(docstore, 'docs') else 'N/A'}")
                
                if hasattr(docstore, 'docs') and docstore.docs:
                    print(f"\n  前 5 个文档:")
                    for i, (doc_id, node) in enumerate(list(docstore.docs.items())[:5]):
                        print(f"\n    文档 {i+1}:")
                        print(f"      - ID: {doc_id}")
                        print(f"      - file_hash: {node.metadata.get('file_hash', 'N/A')}")
                        print(f"      - source_book: {node.metadata.get('source_book', 'N/A')}")
                        print(f"      - 内容长度：{len(node.text)} 字符")
                else:
                    print("\n  Docstore 为空！")
            
            # 检查向量存储
            if hasattr(index_manager.index, '_vector_store'):
                vector_store = index_manager.index._vector_store
                print(f"\n向量存储状态:")
                print(f"  - 向量存储对象：{type(vector_store)}")
                
                # 尝试获取 Chroma 集合
                if hasattr(vector_store, '_collection'):
                    collection = vector_store._collection
                    print(f"  - Chroma 集合：{collection}")
                    print(f"  - 集合名称：{collection.name}")
                    try:
                        count = collection.count()
                        print(f"  - 集合中文档数量：{count}")
                    except Exception as e:
                        print(f"  - 获取数量失败：{e}")
        
        print("\n" + "=" * 80)
        print("检查完成")
        print("=" * 80)
        
    except Exception as e:
        print(f"\n错误：{e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    check_index_initialization()
