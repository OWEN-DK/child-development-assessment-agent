#!/usr/bin/env python3
"""
修复 docstore 持久化问题

问题根因：LlamaIndex 在使用 Chroma 向量存储时，docstore 的持久化可能没有正确触发。
解决方案：在 insert_nodes 后手动触发 docstore 的持久化。
"""
import sys
import os
import json

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 设置环境变量
os.environ['DASHSCOPE_API_KEY'] = 'sk-a571867722db45bc9da8d259aea8ad4a'
os.environ['VECTOR_STORE_TYPE'] = 'chroma'
os.environ['VECTOR_STORE_CONFIG'] = '{"persist_dir": "./chroma_data", "collection_name": "child_development"}'
os.environ['RAG_STORAGE_DIR'] = './storage'

def fix_docstore_persist():
    print("=" * 80)
    print("修复 Docstore 持久化问题")
    print("=" * 80)
    
    try:
        from src.config.settings import settings
        from src.service.index_manager_service import IndexManagerService, STORAGE_DIR
        from llama_index.core import Document
        from llama_index.core.schema import TextNode, NodeRelationship, RelatedNodeInfo
        import time
        
        # 初始化索引管理器
        print("\n正在初始化索引管理器...")
        index_manager = IndexManagerService()
        
        # 创建测试文档
        print("\n创建测试文档...")
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
        
        # 关键修复：手动持久化 docstore
        print("\n手动持久化 docstore...")
        if index_manager.index and hasattr(index_manager.index, 'docstore'):
            docstore = index_manager.index.docstore
            index_dir = os.path.join(STORAGE_DIR, "index")
            
            # 直接写入 docstore.json
            docstore_path = os.path.join(index_dir, "docstore.json")
            
            # 获取所有文档
            docs = {}
            for doc_id, node in docstore.docs.items():
                docs[doc_id] = {
                    "id": doc_id,
                    "text": node.text,
                    "metadata": node.metadata,
                    "start_char_idx": node.start_char_idx,
                    "end_char_idx": node.end_char_idx,
                    "relationships": {
                        k.value: {"node_id": v.node_id} if hasattr(v, 'node_id') else str(v)
                        for k, v in node.relationships.items()
                    } if node.relationships else {}
                }
            
            docstore_data = {"docs": docs}
            
            with open(docstore_path, 'w', encoding='utf-8') as f:
                json.dump(docstore_data, f, ensure_ascii=False, indent=2)
            
            print(f"  - 已写入 {len(docs)} 个文档到 {docstore_path}")
            
            # 验证写入
            with open(docstore_path, 'r', encoding='utf-8') as f:
                verify_data = json.load(f)
                print(f"  - 验证：文件中现在有 {len(verify_data.get('docs', {}))} 个文档")
        
        # 等待持久化完成
        print("等待数据持久化...")
        time.sleep(1)
        
        # 重新初始化索引管理器以验证
        print("\n重新初始化索引管理器以验证...")
        index_manager2 = IndexManagerService()
        
        # 测试获取分块
        print("\n测试获取分块...")
        chunks = index_manager2.get_document_chunks("test_hash_123456")
        print(f"  - 找到的分块数量：{len(chunks)}")
        
        if chunks:
            print(f"\n  ✅ 成功！分块详情:")
            for i, chunk in enumerate(chunks):
                print(f"\n    分块 {i+1}:")
                print(f"      - ID: {chunk['id']}")
                print(f"      - 内容：{chunk['content'][:50]}...")
                print(f"      - 元数据：{chunk['metadata']}")
        else:
            print(f"\n  ❌ 仍然没有找到分块")
        
        print("\n" + "=" * 80)
        print("修复完成")
        print("=" * 80)
        
        return len(chunks) > 0
        
    except Exception as e:
        print(f"\n❌ 错误：{e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = fix_docstore_persist()
    sys.exit(0 if success else 1)
