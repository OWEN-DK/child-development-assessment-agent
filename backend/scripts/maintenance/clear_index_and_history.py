#!/usr/bin/env python3
"""清空索引和历史记录，方便后续导入"""

import os
import sys
import shutil
import json
import chromadb
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

from src.config.settings import settings
from src.service.document_manager import document_manager
from src.service.document_ingestion_service import import_task_manager


def clear_chroma_collection():
    """清空 Chroma 数据库中的所有集合"""
    print("=" * 60)
    print("清空 Chroma 数据库...")
    print("=" * 60)
    
    try:
        # 获取 Chroma 配置
        persist_dir = settings.vector_store_config.get("persist_dir", "./chroma_data")
        collection_name = settings.vector_store_config.get("collection_name", "documents")
        
        print(f"Chroma 数据目录：{persist_dir}")
        print(f"集合名称：{collection_name}")
        
        # 连接到 Chroma 数据库
        client = chromadb.PersistentClient(path=persist_dir)
        
        # 列出所有集合
        collections = client.list_collections()
        print(f"找到 {len(collections)} 个集合")
        
        # 删除所有集合
        for coll in collections:
            print(f"  - 删除集合：{coll.name}")
            client.delete_collection(coll.name)
        
        print("✓ Chroma 数据库已清空")
        return True
        
    except Exception as e:
        print(f"✗ 清空 Chroma 数据库失败：{e}")
        return False


def clear_llama_index_storage():
    """清空 Llama Index 的存储目录"""
    print("\n" + "=" * 60)
    print("清空 Llama Index 存储...")
    print("=" * 60)
    
    try:
        storage_dir = settings.rag_storage_dir
        print(f"存储目录：{storage_dir}")
        
        if not os.path.exists(storage_dir):
            print("  - 存储目录不存在，跳过")
            return True
        
        # 删除存储目录
        print(f"  - 删除目录：{storage_dir}")
        shutil.rmtree(storage_dir)
        
        # 重新创建空目录
        os.makedirs(storage_dir, exist_ok=True)
        
        print("✓ Llama Index 存储已清空")
        return True
        
    except Exception as e:
        print(f"✗ 清空 Llama Index 存储失败：{e}")
        return False


def clear_document_manager():
    """清空文档管理器中的记录"""
    print("\n" + "=" * 60)
    print("清空文档管理器...")
    print("=" * 60)
    
    try:
        # 获取所有文档
        docs = document_manager.list_documents()
        print(f"找到 {len(docs)} 个文档记录")
        
        # 删除所有文档
        for doc in docs:
            print(f"  - 删除文档：{doc.file_name} (hash: {doc.file_hash})")
            document_manager.delete_document(doc.file_hash)
        
        if len(docs) == 0:
            print("  - 没有文档需要删除")
        
        print("✓ 文档管理器已清空")
        return True
        
    except Exception as e:
        print(f"✗ 清空文档管理器失败：{e}")
        return False


def clear_import_tasks():
    """清空导入任务历史记录"""
    print("\n" + "=" * 60)
    print("清空导入任务历史...")
    print("=" * 60)
    
    try:
        task_dir = import_task_manager.task_dir
        print(f"任务目录：{task_dir}")
        
        if not os.path.exists(task_dir):
            print("  - 任务目录不存在，跳过")
            return True
        
        # 删除所有任务文件
        task_files = [f for f in os.listdir(task_dir) if f.endswith(".json")]
        print(f"找到 {len(task_files)} 个任务文件")
        
        for task_file in task_files:
            task_path = os.path.join(task_dir, task_file)
            try:
                # 读取任务信息
                with open(task_path, "r", encoding="utf-8") as f:
                    task_data = json.load(f)
                
                file_name = task_data.get("file_name", "unknown")
                print(f"  - 删除任务：{file_name} ({task_file})")
                os.remove(task_path)
            except Exception as e:
                print(f"  - 删除任务失败 {task_file}: {e}")
                # 直接删除文件
                try:
                    os.remove(task_path)
                except:
                    pass
        
        print("✓ 导入任务历史已清空")
        return True
        
    except Exception as e:
        print(f"✗ 清空导入任务历史失败：{e}")
        return False


def clear_temp_uploads():
    """清空临时上传目录"""
    print("\n" + "=" * 60)
    print("清空临时上传文件...")
    print("=" * 60)
    
    try:
        temp_dir = settings.rag_temp_upload_dir
        print(f"临时目录：{temp_dir}")
        
        if not os.path.exists(temp_dir):
            print("  - 临时目录不存在，跳过")
            return True
        
        # 删除所有临时文件
        temp_files = os.listdir(temp_dir)
        print(f"找到 {len(temp_files)} 个临时文件")
        
        for temp_file in temp_files:
            temp_path = os.path.join(temp_dir, temp_file)
            try:
                if os.path.isfile(temp_path):
                    os.remove(temp_path)
                elif os.path.isdir(temp_path):
                    shutil.rmtree(temp_path)
            except Exception as e:
                print(f"  - 删除失败 {temp_file}: {e}")
        
        print("✓ 临时上传文件已清空")
        return True
        
    except Exception as e:
        print(f"✗ 清空临时上传文件失败：{e}")
        return False


def main():
    """主函数"""
    print("\n" + "=" * 60)
    print("清空索引和历史记录")
    print("=" * 60)
    print(f"数据目录：{settings.data_dir}")
    print(f"RAG 存储目录：{settings.rag_storage_dir}")
    print(f"临时上传目录：{settings.rag_temp_upload_dir}")
    print()
    
    # 执行清空操作
    results = []
    
    results.append(("Chroma 数据库", clear_chroma_collection()))
    results.append(("Llama Index 存储", clear_llama_index_storage()))
    results.append(("文档管理器", clear_document_manager()))
    results.append(("导入任务历史", clear_import_tasks()))
    results.append(("临时上传文件", clear_temp_uploads()))
    
    # 汇总结果
    print("\n" + "=" * 60)
    print("清空结果汇总")
    print("=" * 60)
    
    success_count = sum(1 for _, success in results if success)
    total_count = len(results)
    
    for name, success in results:
        status = "✓ 成功" if success else "✗ 失败"
        print(f"{status} - {name}")
    
    print()
    print(f"总计：{success_count}/{total_count} 项成功")
    
    if success_count == total_count:
        print("\n✓ 所有索引和历史记录已清空，可以开始导入新数据！")
        return 0
    else:
        print("\n✗ 部分操作失败，请检查错误信息")
        return 1


if __name__ == "__main__":
    sys.exit(main())
