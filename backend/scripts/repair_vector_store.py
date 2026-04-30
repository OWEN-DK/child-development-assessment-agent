"""重建向量存储：将 docstore 中的节点重新嵌入并写入 Chroma。

用法: cd backend && uv run python scripts/repair_vector_store.py
"""
import asyncio
import sys
import os

# 确保项目根目录在 path 中
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from src.config import settings
from src.utils.logger import logger


async def main():
    from src.service.index_manager.facade import IndexManagerService
    from src.service.document_manager import document_manager
    from src.service.cache_service import CacheService

    cache_service = CacheService()
    index_manager = IndexManagerService(document_manager, cache_service)

    if not index_manager.is_index_available():
        logger.error("索引未加载，请先上传至少一个文档")
        return 1

    # 修复前统计
    docstore_count = 0
    if hasattr(index_manager.storage_manager.index, "docstore"):
        docstore_count = len(index_manager.storage_manager.index.docstore.docs)

    chroma_count = 0
    if hasattr(index_manager.storage_manager.index, "_vector_store"):
        vs = index_manager.storage_manager.index._vector_store
        if hasattr(vs, '_collection') and vs._collection:
            chroma_count = vs._collection.count()

    logger.info(f"修复前：docstore={docstore_count} 节点, Chroma={chroma_count} 文档")

    if chroma_count >= docstore_count:
        logger.info("向量存储状态正常，无需修复")
        return 0

    result = index_manager.index_operations.repair_vector_store()
    logger.info(f"修复结果: {result}")
    return 0 if result["errors"] == 0 else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
