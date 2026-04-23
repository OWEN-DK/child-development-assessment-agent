from typing import Callable

from src.service.document_ingestion.book_ingestor import BookIngestor


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
        return await self.book_ingestor.ingest_book_resumable(
            file_path, original_filename, progress_callback, task_id, force_restart, max_concurrency
        )

    async def ingest_book(
        self,
        file_path: str,
        original_filename: str = None,
        progress_callback: Callable[[str, float, str], None] = None,
        task_id: str = None,
    ):
        return await self.book_ingestor.ingest_book(file_path, original_filename, progress_callback, task_id)
