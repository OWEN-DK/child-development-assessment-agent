"""灰度上线逻辑 — 根据百分比决定是否使用 Neo4j。

放置位置: backend/src/service/knowledge_qa_service.py (补充方法)
"""

from __future__ import annotations

import hashlib
import logging
import random

logger = logging.getLogger(__name__)


def should_use_neo4j(question_id: str, config_manager=None) -> bool:
    """根据灰度百分比决定是否使用 Neo4j。

    策略: 基于 question_id 的 hash 决定，确保同一问题始终走同一路径。

    Args:
        question_id: 问题唯一标识（如 UUID 或 hash）
        config_manager: 配置管理器

    Returns:
        是否使用 Neo4j
    """
    if config_manager is None:
        from config.core.manager import config_manager as _cm
        config_manager = _cm

    if not config_manager.get("neo4j.enabled", False):
        return False

    percentage = config_manager.get("neo4j.rollout_percentage", 0)

    if percentage >= 100:
        return True
    if percentage <= 0:
        return False

    # 基于 hash 的稳定分流（同一问题始终走同一路径）
    hash_val = int(hashlib.md5(question_id.encode()).hexdigest()[:8], 16)
    bucket = hash_val % 100

    use_neo4j = bucket < percentage

    if use_neo4j:
        logger.debug("灰度命中 Neo4j (bucket=%d < %d%%)", bucket, percentage)

    return use_neo4j
