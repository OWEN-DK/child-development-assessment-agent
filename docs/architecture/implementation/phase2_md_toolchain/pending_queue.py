"""待提炼队列 — 管理 Layer 1 尚未覆盖的知识条目。

放置位置: backend/src/core/knowledge_qa/neo4j/pending_queue.py
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class PendingItem:
    """一条待提炼项。"""
    id: str
    topic: str
    reason: str
    source_books: list[str] = field(default_factory=list)
    status: str = "pending"  # pending / processing / resolved / discarded
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    resolved_at: Optional[str] = None
    resolved_by: Optional[str] = None


class PendingQueue:
    """待提炼队列管理器。"""

    def __init__(self, neo4j_session=None):
        self._session = neo4j_session

    def add(self, topic: str, reason: str, source_books: list[str] = None) -> PendingItem:
        """添加待提炼项。"""
        item = PendingItem(
            id=str(uuid.uuid4()),
            topic=topic,
            reason=reason,
            source_books=source_books or [],
        )

        if self._session:
            self._session.run("""
                CREATE (pq:PendingQueue {
                    id: $id, topic: $topic, reason: $reason,
                    source_books: $source_books, status: 'pending',
                    created_at: $created_at
                })
            """, id=item.id, topic=item.topic, reason=item.reason,
                source_books=item.source_books, created_at=item.created_at,
            )

        logger.info("待提炼队列新增: %s — %s", item.topic[:50], item.reason[:50])
        return item

    def list_pending(self, limit: int = 50) -> list[dict]:
        """列出待处理项。"""
        if self._session:
            result = self._session.run("""
                MATCH (pq:PendingQueue {status: 'pending'})
                RETURN pq ORDER BY pq.created_at DESC LIMIT $limit
            """, limit=limit)
            return result.data()
        return []

    def resolve(self, item_id: str, resolved_by: str):
        """标记为已处理。"""
        if self._session:
            self._session.run("""
                MATCH (pq:PendingQueue {id: $id})
                SET pq.status = 'resolved', pq.resolved_by = $by,
                    pq.resolved_at = $at
            """, id=item_id, by=resolved_by,
                at=datetime.now(timezone.utc).isoformat(),
            )
        logger.info("待提炼项已解决: %s by %s", item_id, resolved_by)
