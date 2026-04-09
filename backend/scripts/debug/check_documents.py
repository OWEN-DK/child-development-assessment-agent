import sys
import os
import json
# Add backend to path so 'src' can be imported
backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.insert(0, backend_dir)

from src.service.document_manager import document_manager
from src.config.settings import settings


def check_documents():
    print("=" * 80)
    print("文档管理器检查")
    print("=" * 80)
    
    # 1. 列出所有文档
    docs = document_manager.list_documents()
    print(f"\n1. 文档管理器中的文档: {len(docs)}")
    for doc in docs:
        print(f"\n   文档: {doc.file_name}")
        print(f"   - 哈希: {doc.file_hash}")
        print(f"   - 状态: {doc.status}")
        print(f"   - 进度: {doc.progress}%")
        print(f"   - ref_doc_ids: {doc.ref_doc_ids}")
        if hasattr(doc, 'metadata') and doc.metadata:
            print(f"   - 元数据:")
            print(f"     - 标题: {doc.metadata.title}")
            print(f"     - 总页数: {doc.metadata.total_pages}")
            print(f"     - 章节数: {doc.metadata.chapter_count}")
    
    # 2. 检查 document_store.json 文件
    store_path = os.path.join(settings.data_dir, "document_store.json")
    print(f"\n2. 文档存储文件: {store_path}")
    if os.path.exists(store_path):
        with open(store_path, 'r', encoding='utf-8') as f:
            store_data = json.load(f)
        print(f"   文件存在 ✓")
        print(f"   内容: {json.dumps(store_data, ensure_ascii=False, indent=2)[:500]}...")
    else:
        print(f"   文件不存在 ✗")
    
    # 3. 检查导入任务状态
    task_dir = os.path.join(settings.data_dir, "import_tasks")
    print(f"\n3. 导入任务目录: {task_dir}")
    if os.path.exists(task_dir):
        task_files = [f for f in os.listdir(task_dir) if f.endswith('.json')]
        print(f"   任务文件数: {len(task_files)}")
        for task_file in task_files[:5]:  # 只显示前5个
            task_path = os.path.join(task_dir, task_file)
            with open(task_path, 'r', encoding='utf-8') as f:
                task_data = json.load(f)
            print(f"\n   任务: {task_file}")
            print(f"   - 文件名: {task_data.get('file_name')}")
            print(f"   - 状态: {task_data.get('status')}")
            print(f"   - 进度: {task_data.get('progress')}%")
            print(f"   - 阶段: {task_data.get('current_stage')}")
    else:
        print(f"   目录不存在 ✗")
    
    print("\n" + "=" * 80)


if __name__ == "__main__":
    check_documents()
