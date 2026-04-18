import json
import os
import threading
from datetime import datetime
from typing import Dict, List, Optional

from src.config import settings
from src.schemas import DocumentRecord, DocumentStore
from src.utils.logger import logger

DOCUMENT_STORE_PATH = f"{settings.rag_storage_dir}/document_store.json"


class DocumentManager:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(DocumentManager, cls).__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self.store_path = DOCUMENT_STORE_PATH
        self.store = DocumentStore()
        self._load_store()
        self._initialized = True

    def _load_store(self):
        """Load document store from JSON file."""
        if os.path.exists(self.store_path):
            try:
                with open(self.store_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.store = DocumentStore(**data)
                logger.info(f"Loaded document store from {self.store_path}")
            except Exception as e:
                logger.error(f"Failed to load document store: {e}")
                # Keep empty store if load fails
        else:
            logger.info("No existing document store found. Starting fresh.")

    def _save_store(self):
        """Save document store to JSON file."""
        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(self.store_path), exist_ok=True)

            with open(self.store_path, "w", encoding="utf-8") as f:
                f.write(self.store.model_dump_json(indent=2))
            logger.info(f"Saved document store to {self.store_path}")
        except Exception as e:
            logger.error(f"Failed to save document store: {e}")

    def add_document(self, doc: DocumentRecord):
        """Add or update a document record."""
        with self._lock:
            self.store.docs[doc.file_hash] = doc
            self._save_store()

    def get_document(self, file_hash: str) -> Optional[DocumentRecord]:
        """Get a document record by hash."""
        return self.store.docs.get(file_hash)

    def get_document_by_name(self, file_name: str) -> Optional[DocumentRecord]:
        """Get a document record by file name."""
        for doc in self.store.docs.values():
            if doc.file_name == file_name:
                return doc
        return None

    def delete_document(self, file_hash: str) -> bool:
        """Delete a document record by hash."""
        with self._lock:
            if file_hash in self.store.docs:
                del self.store.docs[file_hash]
                self._save_store()
                return True
            return False

    def exists(self, file_hash: str) -> bool:
        """Check if a document exists by hash."""
        return file_hash in self.store.docs

    def list_documents(self) -> List[DocumentRecord]:
        """List all documents."""
        return list(self.store.docs.values())


document_manager = DocumentManager()
