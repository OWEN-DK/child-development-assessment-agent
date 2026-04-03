import os
import time
import shutil
from src.service.document_manager import document_manager
from src.service.index_manager_service import IndexManagerService
from src.config.settings import settings

print("=" * 60)
print("RAG 系统修复工具")
print("=" * 60)

# 1. 清理卡住的文档
print("\n1. 清理卡住的文档...")
docs = document_manager.list_documents()
for doc in docs:
    print(f"   - 发现文档: {doc.file_name}, 状态: {doc.status}")
    if doc.status == "processing":
        print(f"   - 删除卡住的文档: {doc.file_name}")
        document_manager.delete_document(doc.file_hash)

# 2. 清理损坏的 storage 目录
print("\n2. 清理 storage 目录...")
storage_dir = settings.rag_storage_dir
if os.path.exists(storage_dir):
    # 备份当前目录
    backup_dir = f"{storage_dir}.bak.{int(time.time())}"
    print(f"   - 备份当前 storage 到: {backup_dir}")
    shutil.copytree(storage_dir, backup_dir)

    # 清空 storage 目录但保留 document_store.json
    for item in os.listdir(storage_dir):
        item_path = os.path.join(storage_dir, item)
        if item != "document_store.json" and not item.startswith("."):
            if os.path.isdir(item_path):
                shutil.rmtree(item_path)
            else:
                os.remove(item_path)
    print("   - 已清理 storage 目录")

# 3. 验证修复结果
print("\n3. 验证修复结果...")
docs = document_manager.list_documents()
print(f"   - 当前文档数量: {len(docs)}")

index_manager = IndexManagerService()
print(
    f"   - 索引状态: {'可用' if index_manager.is_index_available() else '未构建 (正常，需要先导入文档)'}"
)

print("\n" + "=" * 60)
print("✅ RAG 系统修复完成！")
print("=" * 60)
print("\n下一步：")
print("1. 重新导入你的 EPUB/PDF 文档")
print("2. 文档导入完成后，RAG 检索功能将恢复正常")
