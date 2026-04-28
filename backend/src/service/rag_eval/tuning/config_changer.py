"""配置变更执行器——建议采纳、配置快照创建与回滚"""

from datetime import datetime

from sqlalchemy import desc, select as _select

from src.core.config.cache import ConfigCache
from src.repository.rag_eval.config_version_repository import ConfigVersionRepository
from src.repository.rag_eval.config_change_set_repository import ConfigChangeSetRepository
from src.schemas.rag_eval.tuning import ConfigVersionRead, TuningSuggestion
from src.utils.exceptions import AppException, RollbackFailedException
from src.utils.id_generator import generate_id
from src.utils.orm_mapper import OrmMapper


class ConfigChanger:
    """配置变更执行与回滚"""

    def __init__(
        self,
        config_version_repo: ConfigVersionRepository,
        change_set_repo: ConfigChangeSetRepository,
        config_cache=None,
        config_manager=None,
        orm_mapper=None,
    ):
        self._ver = config_version_repo
        self._cs = change_set_repo
        self._cache = config_cache or ConfigCache.get_instance()
        self._mgr = config_manager
        self._mapper = orm_mapper or OrmMapper()

    async def apply_suggestion(self, suggestion: TuningSuggestion) -> ConfigVersionRead:
        """应用建议：创建快照→ConfigVersion→ChangeSet→刷新ConfigCache"""
        current = self._cache.get_latest_config() or {}
        new_snap = self._build_snapshot(current, suggestion)

        latest = await self._ver.get_latest_version()
        version_num = (latest.version_number + 1) if latest else 1
        vid = generate_id()

        await self._ver.create({
            "id": vid, "version_number": version_num,
            "version_label": f"Auto-tuning: {suggestion.title[:50]}",
            "config_snapshot": new_snap,
            "change_summary": f"应用建议 {suggestion.id}: {suggestion.title}",
            "created_by": "tuning_engine",
        })

        csid = generate_id()
        await self._cs.create({
            "id": csid, "change_set_label": suggestion.title[:100],
            "config_version_id": vid, "status": "committed",
        })

        await self._cache.reload()
        version = await self._ver.get_by_id(vid)
        return self._mapper.to_read(version, ConfigVersionRead)

    async def rollback(self, change_set_id: str, reason: str):
        """回滚变更集：恢复前版本快照→标记rolled_back→刷新缓存"""
        cs = await self._cs.get_by_id(change_set_id)
        if cs is None:
            raise AppException(404, 14003, f"变更集不存在: {change_set_id}", "CHANGE_SET_NOT_FOUND")
        if cs.status == "rolled_back":
            raise AppException(400, 14003, "变更集已回滚，不可重复操作", "ALREADY_ROLLED_BACK")

        cur_ver = await self._ver.get_by_id(cs.config_version_id)
        if cur_ver is None:
            raise RollbackFailedException(f"配置版本不存在: {cs.config_version_id}")

        async with self._ver.db_session_factory() as session:
            result = await session.execute(
                _select(cur_ver.__class__)
                .where(cur_ver.__class__.version_number < cur_ver.version_number)
                .order_by(desc(cur_ver.__class__.created_at)).limit(1))
            prev = result.scalar_one_or_none()

        if prev is None:
            raise RollbackFailedException("没有可回滚的前一配置版本")

        latest = await self._ver.get_latest_version()
        rollback_num = (latest.version_number + 1) if latest else 1

        await self._ver.create({
            "id": generate_id(), "version_number": rollback_num,
            "version_label": f"Rollback: {reason[:50]}",
            "config_snapshot": prev.config_snapshot,
            "change_summary": f"回滚变更集 {change_set_id}: {reason}",
            "created_by": "tuning_engine",
        })

        await self._cs.update(change_set_id, {
            "status": "rolled_back", "rollback_reason": reason, "rolled_back_at": datetime.now(),
        })
        await self._cache.reload()

    def _build_snapshot(self, current: dict, suggestion: TuningSuggestion) -> dict:
        import copy
        snap = copy.deepcopy(current)
        sug = suggestion.suggested_value if isinstance(suggestion.suggested_value, dict) else {}
        action = sug.get("action", "")
        rag = snap.get("rag", {}) if isinstance(snap.get("rag"), dict) else {}

        if action == "adjust_hybrid_weights":
            d = sug.get("direction", "increase_vector")
            w = float(rag.get("vector_weight", 0.5))
            w = max(0.1, min(1.0, w + (0.1 if d == "increase_vector" else -0.1)))
            if not isinstance(snap.get("rag"), dict):
                snap["rag"] = {}
            snap["rag"]["vector_weight"] = w
        elif action == "increase_top_k":
            if not isinstance(snap.get("rag"), dict):
                snap["rag"] = {}
            snap["rag"]["top_k"] = int(sug.get("top_k", 10))
        elif action == "tighten_filter":
            t = float(rag.get("search_threshold", 0.25))
            if not isinstance(snap.get("rag"), dict):
                snap["rag"] = {}
            snap["rag"]["search_threshold"] = min(0.8, t + 0.05)

        snap["_auto_tuned_from"] = suggestion.id
        snap["_auto_tuned_action"] = action
        return snap
