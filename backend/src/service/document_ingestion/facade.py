from typing import Callable
import logging

from src.service.document_ingestion.book_ingestor import BookIngestor

logger = logging.getLogger(__name__)


class DocumentIngestionService:
    def __init__(self, index_manager):
        self.book_ingestor = BookIngestor(index_manager)

    async def ingest_book_resumable(
        self,
        file_path: str,
        original_filename: str = None,
        progress_callback: Callable[[str, float, str], None] = None,
        task_id: str = None,
        force_restart: bool = False,
        max_concurrency: int = 4,
    ) -> str:
        result = await self.book_ingestor.ingest_book_resumable(
            file_path, original_filename, progress_callback, task_id, force_restart, max_concurrency
        )

        # Neo4j 直写：文档摄入完成后自动导入知识图谱
        await self._maybe_import_to_neo4j(file_path, original_filename)

        return result

    async def ingest_book(
        self,
        file_path: str,
        original_filename: str = None,
        progress_callback: Callable[[str, float, str], None] = None,
        task_id: str = None,
    ):
        result = await self.book_ingestor.ingest_book(file_path, original_filename, progress_callback, task_id)

        # Neo4j 直写：文档摄入完成后自动导入知识图谱
        await self._maybe_import_to_neo4j(file_path, original_filename)

        return result

    async def _maybe_import_to_neo4j(self, file_path: str, original_filename: str = None):
        """Neo4j 直写逻辑 — 文档摄入后自动写入知识图谱。

        仅在 NEO4J_ENABLED=True 且文件为 EPUB 时触发。
        失败不影响主流程（降级策略）。
        """
        try:
            from src.config.modules.neo4j import neo4j_settings
            if not neo4j_settings.neo4j_enabled:
                return

            if not file_path.lower().endswith('.epub'):
                return

            # 生成 book_id（使用文件名）
            book_id = original_filename or file_path.split('/')[-1].replace('.epub', '')

            logger.info("Neo4j 直写: 开始导入 %s", book_id)

            from src.core.knowledge_qa.neo4j.chapter_parser import parse_epub
            from src.core.knowledge_qa.neo4j.aggregator import aggregate_chapters
            from src.core.knowledge_qa.neo4j.driver import get_neo4j_driver

            # 解析 EPUB
            parse_result = parse_epub(file_path, book_id)

            # 聚合章节
            chapter_results = []
            for ch in parse_result.chapters:
                chapter_results.append({
                    "success": True,
                    "chapter_id": ch.id,
                    "concepts": [],  # 需要 AI 提取后填充
                    "claims": [],
                    "prescriptions": [],
                })

            aggregated = aggregate_chapters(chapter_results, book_id, parse_result.book_title)

            # 写入 Neo4j（仅 Book 节点和 AutoEntity）
            driver = get_neo4j_driver()
            if driver:
                with driver.session() as session:
                    session.run("""
                        MERGE (b:Book {book_id: $book_id})
                        SET b.title = $title
                    """, book_id=book_id, title=parse_result.book_title)
                logger.info("Neo4j 直写: Book 节点 %s 已创建", book_id)

        except Exception as e:
            logger.warning("Neo4j 直写失败（不影响主流程）: %s", e)
