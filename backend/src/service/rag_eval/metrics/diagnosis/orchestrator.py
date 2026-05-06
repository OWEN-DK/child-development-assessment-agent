"""六层诊断编排器

按顺序 1→6 执行各层诊断，单层失败不阻塞后续层。
计算综合健康度并构建 DiagnosisResult。
"""

import time
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Optional

from src.core.config.cache import ConfigCache
from src.schemas.rag_eval.diagnosis import DiagnosisResult, LayerIssue, LayerResult
from src.schemas.rag_eval.test_run import TestRunRead, TestRunResultItem
from src.utils.logger import logger

_DEFAULT_DIAGNOSIS_CONFIG: dict[str, Any] = {
    "rag.eval.diagnosis.timeout_ms": 60000,
    "rag.eval.diagnosis.concurrency": 3,
    "rag.eval.diagnosis.layer3.enabled": True,
    "rag.eval.diagnosis.layer3.model": "",
    "rag.eval.diagnosis.layer4.golden_case_ids": [],
}


class DiagnosisLayer(ABC):
    """诊断层抽象基类，每层独立执行诊断，层与层之间不共享可变状态"""

    @property
    @abstractmethod
    def layer_number(self) -> int: ...
    @property
    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    async def diagnose(
        self, run_id: str, results: list[TestRunResultItem], run_data: TestRunRead
    ) -> LayerResult: ...

    def _get_config(self, config_cache: ConfigCache, key: str, default: Any = None) -> Any:
        config = config_cache.get_latest_config()
        if config and key in config:
            return config[key]
        return _DEFAULT_DIAGNOSIS_CONFIG.get(key, default)


class DiagnosisOrchestrator:
    """六层诊断编排器，按 1→6 顺序执行各层，异常不阻塞后续层"""

    def __init__(self, layers: dict[int, DiagnosisLayer], config_cache: Optional[ConfigCache] = None):
        self._layers = layers
        self._config_cache = config_cache or ConfigCache.get_instance()

    async def run_all(
        self, run_id: str, results: list[TestRunResultItem], run_data: TestRunRead
    ) -> DiagnosisResult:
        """执行全部 6 层诊断"""
        layer_results: list[LayerResult] = []
        for layer_num in sorted(self._layers.keys()):
            try:
                result = await self.run_layer(layer_num, run_id, results, run_data)
            except Exception as e:
                logger.error(f"诊断层 {layer_num} 执行异常: {e}")
                result = LayerResult(
                    layer=layer_num, name=f"Layer{layer_num}", status="error", score=0.0,
                    total_cases=len(results), affected_cases=0,
                    issues=[LayerIssue(
                        severity="critical", category="execution_error",
                        description=f"层 {layer_num} 执行异常: {str(e)}", affected_items=[run_id],
                    )],
                    execution_time_ms=0,
                )
            layer_results.append(result)

        overall_health = _calc_overall(layer_results)
        total_issues = sum(len(r.issues) for r in layer_results)
        critical_issues = sum(sum(1 for i in r.issues if i.severity == "critical") for r in layer_results)

        return DiagnosisResult(
            layer1=_get_layer(layer_results, 1), layer2=_get_layer(layer_results, 2),
            layer3=_get_layer(layer_results, 3), layer4=_get_layer(layer_results, 4),
            layer5=_get_layer(layer_results, 5), layer6=_get_layer(layer_results, 6),
            overall_health=overall_health, total_issues=total_issues,
            critical_issues=critical_issues, diagnosed_at=datetime.now(),
        )

    async def run_layer(
        self, layer: int, run_id: str, results: list[TestRunResultItem], run_data: TestRunRead
    ) -> LayerResult:
        """只执行指定层的诊断"""
        if layer not in self._layers:
            raise ValueError(f"未知诊断层编号: {layer}")
        return await self._layers[layer].diagnose(run_id, results, run_data)


def _calc_overall(layer_results: list[LayerResult]) -> float:
    if not layer_results:
        return 1.0
    return round(sum(r.score for r in layer_results) / len(layer_results), 4)


def _get_layer(layer_results: list[LayerResult], layer_num: int) -> LayerResult:
    for r in layer_results:
        if r.layer == layer_num:
            return r
    return LayerResult(layer=layer_num, name=f"Layer{layer_num}", status="skip", score=1.0,
                       total_cases=0, affected_cases=0,
                       issues=[], details={}, execution_time_ms=0)
