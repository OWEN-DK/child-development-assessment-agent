"""调优顾问——双阶段建议生成：规则引擎 + LLM 诊断"""

from src.core.config.cache import ConfigCache
from src.schemas.rag_eval.tuning import TuningSuggestion
from src.utils.exceptions import AppException
from src.utils.id_generator import generate_id

_PRIORITY = {"critical": 3, "warning": 2, "info": 1}


class TuningAdvisor:
    """双阶段建议生成：规则引擎 + LLM 诊断"""

    def __init__(self, llm_factory=None, prompt_manager=None, config_cache=None):
        self._llm = llm_factory
        self._prompt = prompt_manager
        self._cache = config_cache or ConfigCache.get_instance()

    async def generate_suggestions(self, run_id, metrics, diagnosis, bad_cases) -> list:
        """两阶段策略：规则引擎 → LLM 诊断（仅 bad_cases ≥ min_bad_cases 时触发）"""
        suggestions = await self._rule_based(run_id, metrics, diagnosis)

        min_bad = int(self._cfg("rag.eval.tuning.min_bad_cases", 3))
        if len(bad_cases) >= min_bad:
            llm_sugs = await self._llm_diag(run_id, bad_cases, metrics)
            suggestions.extend(llm_sugs)

        max_sug = int(self._cfg("rag.eval.tuning.max_suggestions", 10))
        return suggestions[:max_sug]

    async def _rule_based(self, run_id, metrics, diagnosis) -> list:
        mkt = self._mk

        def _ms(ms): return ms.value < ms.threshold and not ms.passed

        sugs = []
        l1, l2, l3 = metrics.l1, metrics.l2, metrics.l3

        if _ms(l1.context_precision):
            sugs.append(mkt(run_id, "retrieval", "warning", "检索精确度偏低",
                f"context_precision={l1.context_precision.value:.2f}，建议调整 BM25/Vector 混合权重。",
                {"val": l1.context_precision.value}, {"action": "adjust_hybrid_weights", "direction": "increase_vector"}))
        if _ms(l1.context_recall):
            sugs.append(mkt(run_id, "retrieval", "warning", "检索召回率偏低",
                f"context_recall={l1.context_recall.value:.2f}，建议增加 Top-K。",
                {"val": l1.context_recall.value}, {"action": "increase_top_k", "top_k": 10}))
        if _ms(l1.noise_sensitivity):
            sugs.append(mkt(run_id, "retrieval", "warning", "噪声敏感度过高",
                f"noise_sensitivity={l1.noise_sensitivity.value:.2f}，建议增加过滤条件。",
                {"val": l1.noise_sensitivity.value}, {"action": "tighten_filter"}))
        if _ms(l2.faithfulness):
            sugs.append(mkt(run_id, "generation", "warning", "生成忠实度过低",
                f"faithfulness={l2.faithfulness.value:.2f}，建议优化上下文窗口。",
                {"val": l2.faithfulness.value}, {"action": "optimize_context"}))
        if _ms(l2.answer_relevancy):
            sugs.append(mkt(run_id, "generation", "info", "答案相关性偏低",
                f"answer_relevancy={l2.answer_relevancy.value:.2f}，建议优化 Prompt。",
                {"val": l2.answer_relevancy.value}, {"action": "refine_prompt"}))
        if _ms(l3.cost_efficiency):
            sugs.append(mkt(run_id, "cost", "info", "成本效率过低",
                f"cost_efficiency={l3.cost_efficiency.value:.2f}，建议减少 Top-K 或换更经济模型。",
                {"val": l3.cost_efficiency.value}, {"action": "reduce_cost"}))
        if diagnosis.layer3.status == "fail":
            sugs.append(mkt(run_id, "prompt", "critical", "提示词质量诊断未通过",
                "六层诊断第3层未通过，建议立即检查并修复提示词。", {}, {"action": "fix_prompt"}))
        if diagnosis.layer4.status == "fail":
            sugs.append(mkt(run_id, "configuration", "critical", "知识库质量诊断未通过",
                "六层诊断第4层未通过，建议检查文档完整性。", {}, {"action": "audit_kb"}))

        return sugs

    async def _llm_diag(self, run_id, bad_cases, metrics) -> list:
        if self._llm is None:
            raise AppException(500, 13001, "LLM 诊断不可用：llm_factory 未配置", "LLM_NOT_AVAILABLE")

        case_texts = []
        for c in bad_cases[:10]:
            q = getattr(c, "query", "") if hasattr(c, "query") else c.get("query", "")
            e = getattr(c, "error_message", "") if hasattr(c, "error_message") else c.get("error_message", "")
            case_texts.append(f"Q: {q}\nError: {e}")

        prompt = ("你是 RAG 系统诊断专家。分析以下坏案例，找出共性问题并给出具体调优建议。"
                  "输出 JSON 数组：[{\"category\":\"\", \"severity\":\"\", \"title\":\"\", \"description\":\"\"}]")

        try:
            llm = self._llm.create()
            resp = await llm.chat([
                {"role": "system", "content": prompt},
                {"role": "user", "content": f"坏案例 ({len(bad_cases)} 个):\n" + "\n---\n".join(case_texts)},
            ])
            import json as _json
            items = _json.loads(resp)
            if isinstance(items, dict):
                items = [items]
            return [self._mk(run_id, i.get("category", "generation"), i.get("severity", "info"),
                             i.get("title", ""), i.get("description", ""), source="llm") for i in items]
        except Exception:
            return []

    def _mk(self, run_id, category, severity, title, desc, current=None, suggested=None, source="rule_engine"):
        return TuningSuggestion(
            id=generate_id(), run_id=run_id, category=category, severity=severity,
            title=title, description=desc, current_value=current,
            suggested_value=suggested, priority=_PRIORITY.get(severity, 0),
            source=source, status="pending")

    def _cfg(self, key, default=None):
        config = self._cache.get_latest_config()
        if isinstance(config, dict):
            parts = key.split(".")
            val = config
            for p in parts:
                val = val.get(p, {}) if isinstance(val, dict) else {}
            return val if val != {} else default
        return default
