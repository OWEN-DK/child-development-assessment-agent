"""调优引擎门面——统一入口协调建议生成、冲突检测和配置变更"""

from src.repository.rag_eval.tuning_suggestion_repository import TuningSuggestionRepository
from src.schemas.rag_eval.tuning import ConfigVersionRead, TuningSuggestion
from src.service.rag_eval.tuning.advisor import TuningAdvisor
from src.service.rag_eval.tuning.config_changer import ConfigChanger
from src.service.rag_eval.tuning.conflict_detector import ConflictDetector
from src.utils.exceptions import AppException


class TuningEngineFacade:
    """调优引擎门面——协调建议生成、冲突检测和配置变更，全部 DB 持久化"""

    def __init__(
        self,
        advisor: TuningAdvisor,
        conflict_detector: ConflictDetector,
        config_changer: ConfigChanger,
        suggestion_repo: TuningSuggestionRepository,
        config_cache=None,
    ):
        self._advisor = advisor
        self._detector = conflict_detector
        self._changer = config_changer
        self._repo = suggestion_repo

    async def analyze(self, run_id, metrics, diagnosis, bad_cases=None) -> list[TuningSuggestion]:
        """分析双轨结果并生成调优建议"""
        bad_cases = bad_cases or []
        raw = await self._advisor.generate_suggestions(run_id, metrics, diagnosis, bad_cases)

        # 冲突检测与标记
        if len(raw) >= 2:
            conflicts = self._detector.detect_conflicts(raw)
            cmap = {}
            for cp in conflicts:
                cmap[cp.suggestion_id_1] = cp.suggestion_id_2
                cmap[cp.suggestion_id_2] = cp.suggestion_id_1
            for s in raw:
                if s.id in cmap:
                    s.conflict_with = cmap[s.id]

        # 持久化
        persisted = []
        for s in raw:
            orm = await self._repo.create(self._to_db(s))
            persisted.append(self._to_schema(orm))
        return persisted

    async def get_suggestions(self, run_id) -> list[TuningSuggestion]:
        orms = await self._repo.get_by_run_id(run_id)
        return [self._to_schema(o) for o in orms]

    async def adopt(self, suggestion_id) -> ConfigVersionRead:
        sug = await self._repo.get_by_id(suggestion_id)
        if sug is None:
            raise AppException(404, 13001, f"建议不存在: {suggestion_id}", "SUGGESTION_NOT_FOUND")
        if sug.status != "pending":
            raise AppException(400, 13001, f"建议非 pending 状态: {sug.status}", "SUGGESTION_NOT_PENDING")

        schema = self._to_schema(sug)
        cv = await self._changer.apply_suggestion(schema)
        await self._repo.update(suggestion_id, {"status": "adopted", "applied_config_version_id": cv.id})
        return cv

    async def reject(self, suggestion_id, reason=None):
        sug = await self._repo.get_by_id(suggestion_id)
        if sug is None:
            raise AppException(404, 13001, f"建议不存在: {suggestion_id}", "SUGGESTION_NOT_FOUND")
        data = {"status": "rejected"}
        if reason:
            data["description"] = f"{sug.description}\n[拒绝原因] {reason}"
        await self._repo.update(suggestion_id, data)

    async def ignore(self, suggestion_id):
        sug = await self._repo.get_by_id(suggestion_id)
        if sug is None:
            raise AppException(404, 13001, f"建议不存在: {suggestion_id}", "SUGGESTION_NOT_FOUND")
        await self._repo.update(suggestion_id, {"status": "ignored"})

    def _to_schema(self, o) -> TuningSuggestion:
        return TuningSuggestion(
            id=o.id, run_id=o.run_id, report_id=getattr(o, "report_id", None),
            category=o.category, severity=o.severity, title=o.title,
            description=o.description, current_value=getattr(o, "current_value", None),
            suggested_value=getattr(o, "suggested_value", None),
            expected_impact=getattr(o, "expected_impact", None),
            source=getattr(o, "source", None), priority=getattr(o, "priority", None),
            safe_range=getattr(o, "safe_range", None), status=o.status,
            conflict_with=getattr(o, "conflict_with", None),
            applied_config_version_id=getattr(o, "applied_config_version_id", None),
        )

    def _to_db(self, s: TuningSuggestion) -> dict:
        return {
            "id": s.id, "run_id": s.run_id, "report_id": s.report_id,
            "category": s.category, "severity": s.severity, "title": s.title,
            "description": s.description, "current_value": s.current_value,
            "suggested_value": s.suggested_value, "expected_impact": s.expected_impact,
            "source": s.source or "rule_engine", "priority": s.priority or 0,
            "safe_range": s.safe_range, "status": s.status,
            "conflict_with": s.conflict_with,
            "applied_config_version_id": s.applied_config_version_id,
        }
