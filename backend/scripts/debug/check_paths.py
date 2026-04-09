import sys
import os
# Add backend to path so 'src' can be imported
backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.insert(0, backend_dir)

from src.config.settings import settings


def check_paths():
    print("=" * 80)
    print("路径检查")
    print("=" * 80)
    
    print(f"\n当前工作目录: {os.getcwd()}")
    
    # 检查向量存储路径
    persist_dir = settings.vector_store_config.get("persist_dir")
    print(f"\n配置的persist_dir: {persist_dir}")
    abs_persist_dir = os.path.abspath(persist_dir)
    print(f"绝对路径: {abs_persist_dir}")
    print(f"路径是否存在: {os.path.exists(abs_persist_dir)}")
    
    if os.path.exists(abs_persist_dir):
        files = os.listdir(abs_persist_dir)
        print(f"目录内容: {files}")
    
    # 检查索引路径
    index_dir = os.path.join(settings.rag_storage_dir, "index")
    abs_index_dir = os.path.abspath(index_dir)
    print(f"\n索引目录: {abs_index_dir}")
    print(f"路径是否存在: {os.path.exists(abs_index_dir)}")
    
    if os.path.exists(abs_index_dir):
        files = os.listdir(abs_index_dir)
        print(f"目录内容: {files}")
    
    # 检查文档存储路径
    print(f"\n文档存储文件: {os.path.abspath('./storage/document_store.json')}")
    print(f"是否存在: {os.path.exists(os.path.abspath('./storage/document_store.json'))}")
    
    # 查看是否有其他chroma目录
    print(f"\n查找所有chroma.sqlite3文件:")
    for root, dirs, files in os.walk(backend_dir):
        if 'chroma.sqlite3' in files:
            full_path = os.path.join(root, 'chroma.sqlite3')
            size = os.path.getsize(full_path) / 1024 / 1024
            print(f"   - {full_path} (大小: {size:.2f} MB)")
    
    print("\n" + "=" * 80)


if __name__ == "__main__":
    check_paths()
