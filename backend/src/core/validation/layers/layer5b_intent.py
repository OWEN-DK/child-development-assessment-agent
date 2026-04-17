"""Layer 5b: 意图识别准确率"""

import logging
from typing import Any
from collections import defaultdict
from sqlalchemy import select

from src.models.rag_eval.query_intent_log import RagEvalQueryIntentLog
from src.models.rag_eval.intent_annotation import RagEvalIntentAnnotation

logger = logging.getLogger(__name__)

INTENT_TYPES = {
    "factual_query": "事实查询",
    "how_to": "方法指导",
    "comparison": "对比分析",
    "definition": "定义解释",
    "troubleshooting": "问题诊断",
}


class Layer5bIntentAccuracy:
    """Layer 5b: 意图识别准确率"""

    def __init__(self, session_factory, test_run):
        self.session_factory = session_factory
        self.test_run = test_run

    async def execute(self) -> dict:
        """执行意图准确率校验"""
        # 从数据库查询 RagEvalQueryIntentLog，关联 RagEvalIntentAnnotation 获取手动标注
        async with self.session_factory() as session:
            stmt = (
                select(RagEvalQueryIntentLog, RagEvalIntentAnnotation)
                .outerjoin(
                    RagEvalIntentAnnotation,
                    RagEvalQueryIntentLog.case_id == RagEvalIntentAnnotation.case_id,
                )
                .where(RagEvalQueryIntentLog.run_id == self.test_run.id)
            )
            result = await session.execute(stmt)
            rows = result.all()

        query_analyses = [
            {
                "query": log.query,
                "predicted_intent": log.predicted_intent,
                "confidence": log.confidence,
                "label_source": "manual" if annotation else "auto",
                "manual_intent": annotation.intent_type if annotation else None,
            }
            for log, annotation in rows
        ]

        if not query_analyses:
            return {"status": "skipped", "data": {"reason": "缺少查询分析结果"}}

        auto_labeled = [qa for qa in query_analyses if qa.get("label_source") == "auto"]
        manual_labeled = [
            qa for qa in query_analyses if qa.get("label_source") == "manual"
        ]

        low_confidence_queries = [
            qa for qa in query_analyses if qa.get("confidence", 1.0) < 0.8
        ]

        accuracy = None
        if manual_labeled:
            correct = sum(
                1
                for qa in manual_labeled
                if qa.get("predicted_intent") == qa.get("manual_intent")
            )
            accuracy = correct / len(manual_labeled)

        accuracy_by_type = defaultdict(lambda: {"correct": 0, "total": 0})
        for qa in manual_labeled:
            intent = qa.get("manual_intent") or qa.get("predicted_intent")
            accuracy_by_type[intent]["total"] += 1
            if qa.get("predicted_intent") == qa.get("manual_intent"):
                accuracy_by_type[intent]["correct"] += 1

        warnings = []
        if accuracy is not None and accuracy < 0.80:
            warnings.append(
                {
                    "level": "warning",
                    "message": f"意图识别准确率低 ({accuracy:.1%} < 80%)",
                }
            )

        low_confidence_ratio = (
            len(low_confidence_queries) / len(query_analyses) if query_analyses else 0
        )
        if low_confidence_ratio > 0.30:
            warnings.append(
                {
                    "level": "warning",
                    "message": f"低置信度查询过多 ({low_confidence_ratio:.1%} > 30%)",
                }
            )

        return {
            "status": "completed",
            "data": {
                "overall_accuracy": accuracy,
                "accuracy_by_type": {
                    k: v["correct"] / v["total"] if v["total"] > 0 else None
                    for k, v in accuracy_by_type.items()
                },
                "low_confidence_queries": [
                    {"query": qa.get("query"), "confidence": qa.get("confidence")}
                    for qa in low_confidence_queries[:10]
                ],
                "low_confidence_ratio": low_confidence_ratio,
                "warnings": warnings,
            },
        }
