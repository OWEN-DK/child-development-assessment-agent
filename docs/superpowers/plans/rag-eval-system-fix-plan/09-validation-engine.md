# 09 - 6 层校验引擎模块

**优先级**：🟡 P1
**工作量**：183h（23 人天）（原 160h + 23h 修复）
**依赖**：08-data-model-enhancement（数据模型）

---

## 一、需求背景

现有系统缺少对 RAG 检索质量的自动化诊断能力，无法定位问题根因和生成调优建议。需要实现需求文档要求的 6 层递进式校验引擎，在测试运行完成后自动触发，生成完整的诊断报告和调优建议。

### 1.1 设计原则

| 原则 | 说明 |
|------|------|
| **递进式诊断** | Layer 1-6 从简单到复杂，逐层深入，避免过度消耗资源 |
| **独立可测试** | 每层校验逻辑独立，可单独运行和单元测试 |
| **配置化阈值** | 所有阈值、规则可配置，支持热加载 |
| **优雅降级** | 某层失败不阻断整体流程，记录错误后继续下一层 |
| **用户决策** | 系统只提供建议，不自动应用配置（遵循 00-overview.md 核心原则） |

### 1.2 整体架构

```
测试运行完成
    ↓
ValidationEngine.execute(test_run_id)
    ↓
┌─────────────────────────────────────────┐
│ Layer 1: 规则引擎 (快速阈值校验)         │ ← 20h
│   输入：测试指标 (Precision/Recall/F1)    │
│   输出：配置优化建议                      │
└─────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────┐
│ Layer 2: 历史对比 (回归检测)             │ ← 20h
│   输入：同测试集历史最优记录              │
│   输出：版本差异分析、回归预警            │
└─────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────┐
│ Layer 3: LLM 诊断 (语义分析 Bad Case)    │ ← 40h
│   输入：Bad Case 列表                    │
│   输出：Query 重写、提示词优化建议        │
└─────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────┐
│ Layer 4: 数据质量检查                    │ ← 25h
│   输入：Golden 数据集、文档分块           │
│   输出：数据清洗、补全建议                │
└─────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────┐
│ Layer 5: 检索链路检查                    │ ← 30h
│   输入：Embedding 质量、意图标注          │
│   输出：Embedding 优化、意图识别建议      │
└─────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────┐
│ Layer 6: 验证保障                        │ ← 25h
│   输入：历史 Bad Case、交叉验证集         │
│   输出：回归检测、成本效果分析            │
└─────────────────────────────────────────┘
    ↓
结果合并去重 → 生成 TestReport → 保存数据库
```

---

## 二、Layer 1：规则引擎

**文件路径**：`backend/src/core/rag/validation/layer1_rules.py`
**工作量**：20h

### 2.1 职责

基于指标阈值快速校验，识别明显问题。这是最快的一层，通常在 100ms 内完成。

### 2.2 输入输出

| 维度 | 说明 |
|------|------|
| **输入** | `test_run_metrics`: Dict[str, float] - 测试运行计算的指标 |
| **输出** | `ValidationResult`: 包含状态、指标数据、调优建议列表 |

### 2.3 核心逻辑

```python
"""Layer 1 规则引擎 - 基于指标阈值的快速校验"""

from typing import Dict, List, Any
from dataclasses import dataclass


@dataclass
class ThresholdRule:
    """阈值规则"""
    metric_name: str          # 指标名称
    operator: str             # 操作符: lt/gt/le/ge/eq
    threshold: float          # 阈值
    severity: str             # 严重等级: critical/warning/info
    suggestion_template: str  # 建议模板（支持变量替换）


class Layer1RulesEngine:
    """Layer 1 规则引擎"""
    
    # 默认阈值规则（可配置化）
    DEFAULT_RULES = [
        ThresholdRule(
            metric_name="precision_at_5",
            operator="lt",
            threshold=0.6,
            severity="critical",
            suggestion_template="Precision@5 低于 {threshold}，建议提高 BM25 权重或优化提示词"
        ),
        ThresholdRule(
            metric_name="recall_at_5",
            operator="lt",
            threshold=0.5,
            severity="critical",
            suggestion_template="Recall@5 低于 {threshold}，建议扩大检索范围或优化分块策略"
        ),
        ThresholdRule(
            metric_name="f1_score",
            operator="lt",
            threshold=0.55,
            severity="warning",
            suggestion_template="F1 分数偏低，建议调整 BM25 和 Vector 权重比例"
        ),
        ThresholdRule(
            metric_name="mrr",
            operator="lt",
            threshold=0.7,
            severity="warning",
            suggestion_template="MRR 低于 {threshold}，建议优化重排序模型"
        ),
        ThresholdRule(
            metric_name="ndcg_at_5",
            operator="lt",
            threshold=0.65,
            severity="warning",
            suggestion_template="NDCG@5 偏低，建议检查排序逻辑"
        ),
    ]
    
    def execute(self, metrics: Dict[str, float]) -> Dict[str, Any]:
        """执行规则校验"""
        suggestions = []
        failed_rules = []
        
        for rule in self.DEFAULT_RULES:
            actual_value = metrics.get(rule.metric_name)
            if actual_value is None:
                continue
            
            # 检查是否触发规则
            if self._evaluate_rule(actual_value, rule):
                failed_rules.append({
                    "metric": rule.metric_name,
                    "actual": actual_value,
                    "threshold": rule.threshold,
                    "severity": rule.severity
                })
                
                # 生成调优建议
                suggestions.append({
                    "type": "config",
                    "reason": rule.suggestion_template.format(threshold=rule.threshold),
                    "current_value": {rule.metric_name: actual_value},
                    "suggested_value": self._generate_suggestion(rule.metric_name, actual_value),
                    "impact_analysis": {
                        "scope": f"影响 {rule.metric_name} 指标",
                        "expected_improvement": "预计提升 5-10%",
                        "risk": "可能影响其他指标"
                    },
                    "priority": "high" if rule.severity == "critical" else "medium"
                })
        
        # 确定整体状态
        if any(r["severity"] == "critical" for r in failed_rules):
            status = "fail"
        elif failed_rules:
            status = "warning"
        else:
            status = "pass"
        
        return {
            "status": status,
            "metrics": metrics,
            "failed_rules": failed_rules,
            "suggestions": suggestions
        }
    
    def _evaluate_rule(self, actual: float, rule: ThresholdRule) -> bool:
        """评估单个规则"""
        if rule.operator == "lt":
            return actual < rule.threshold
        elif rule.operator == "gt":
            return actual > rule.threshold
        elif rule.operator == "le":
            return actual <= rule.threshold
        elif rule.operator == "ge":
            return actual >= rule.threshold
        elif rule.operator == "eq":
            return abs(actual - rule.threshold) < 0.01
        return False
    
    def _generate_suggestion(self, metric_name: str, actual: float) -> Dict[str, Any]:
        """生成具体建议值"""
        suggestions = {
            "precision_at_5": {"bm25_weight": 0.6, "vector_weight": 0.4},
            "recall_at_5": {"top_k": 10, "chunk_size": 512},
            "f1_score": {"bm25_weight": 0.5, "vector_weight": 0.5},
            "mrr": {"reranker_enabled": True},
            "ndcg_at_5": {"reranker_enabled": True},
        }
        return suggestions.get(metric_name, {})
```

### 2.4 性能指标

| 指标 | 目标值 |
|------|--------|
| 执行耗时 | < 100ms |
| 内存占用 | < 1MB |
| 规则数量 | 5-10 条（可配置） |

### 2.5 验收标准

- [ ] 所有默认阈值规则正确执行
- [ ] 阈值支持从配置系统热加载
- [ ] 建议生成符合输出规范
- [ ] 单元测试覆盖率 ≥ 90%

---

## 三、Layer 2：历史对比

**文件路径**：`backend/src/core/rag/validation/layer2_history.py`
**工作量**：20h

### 3.1 职责

对比历史最优版本，识别回归风险。通过对比当前测试指标与历史最优记录，检测是否有性能退化。

### 3.2 输入输出

| 维度 | 说明 |
|------|------|
| **输入** | `test_run_id`: str - 当前测试运行 ID<br>`test_set_id`: str - 测试集 ID |
| **输出** | `ValidationResult`: 包含回归检测结果、版本差异、调优建议 |

### 3.3 核心逻辑

```python
"""Layer 2 历史对比 - 回归检测"""

from typing import Dict, List, Any, Optional
from datetime import datetime


class Layer2HistoryComparator:
    """Layer 2 历史对比引擎"""
    
    # 回归检测阈值（指标下降超过此值视为回归）
    REGRESSION_THRESHOLD = 0.05  # 5%
    
    def execute(self, test_run_id: str, test_set_id: str) -> Dict[str, Any]:
        """执行历史对比"""
        # 1. 查询当前测试指标
        current_metrics = self._get_test_run_metrics(test_run_id)
        
        # 2. 查询同测试集历史最优记录
        best_history = self._get_best_history(test_set_id, exclude_run_id=test_run_id)
        if not best_history:
            return {
                "status": "pass",
                "message": "无历史记录，跳过对比",
                "suggestions": []
            }
        
        # 3. 对比指标差异
        diffs = self._calculate_diffs(current_metrics, best_history["metrics"])
        
        # 4. 检测回归
        regressions = [
            {
                "metric": metric,
                "current": diff["current"],
                "best": diff["best"],
                "diff": diff["diff"],
                "regression_pct": diff["diff_pct"]
            }
            for metric, diff in diffs.items()
            if diff["diff"] < -self.REGRESSION_THRESHOLD
        ]
        
        # 5. 生成调优建议
        suggestions = []
        if regressions:
            # 查询历史最优版本的配置
            best_config = self._get_run_config(best_history["id"])
            current_config = self._get_run_config(test_run_id)
            
            # 对比配置差异
            config_diffs = self._diff_configs(current_config, best_config)
            
            for regression in regressions:
                suggestions.append({
                    "type": "config",
                    "reason": f"{regression['metric']} 相比历史最优下降 {regression['regression_pct']:.1%}",
                    "current_value": {regression["metric"]: regression["current"]},
                    "suggested_value": {regression["metric"]: regression["best"]},
                    "impact_analysis": {
                        "scope": f"相比版本 {best_history.get('version_label', '未知')} 出现回归",
                        "expected_improvement": f"恢复到历史最优水平 (+{abs(regression['diff']):.2f})",
                        "risk": "需检查配置变更是否引入回归",
                        "config_diffs": config_diffs
                    },
                    "priority": "high"
                })
        
        # 6. 确定状态
        if regressions:
            status = "warning"
        else:
            status = "pass"
        
        return {
            "status": status,
            "current_metrics": current_metrics,
            "best_history": {
                "run_id": best_history["id"],
                "version_label": best_history.get("version_label"),
                "metrics": best_history["metrics"],
                "executed_at": best_history["executed_at"]
            },
            "diffs": diffs,
            "regressions": regressions,
            "suggestions": suggestions
        }
    
    def _get_best_history(self, test_set_id: str, exclude_run_id: str) -> Optional[Dict]:
        """获取同测试集历史最优记录"""
        # 查询数据库，按 f1_score 降序排序，取第一条
        # 排除当前运行
        pass
    
    def _calculate_diffs(self, current: Dict, best: Dict) -> Dict:
        """计算指标差异"""
        diffs = {}
        for metric in current:
            if metric in best:
                diff = current[metric] - best[metric]
                diff_pct = diff / best[metric] if best[metric] != 0 else 0
                diffs[metric] = {
                    "current": current[metric],
                    "best": best[metric],
                    "diff": diff,
                    "diff_pct": diff_pct
                }
        return diffs
    
    def _diff_configs(self, current: Dict, best: Dict) -> List[Dict]:
        """对比配置差异"""
        diffs = []
        all_keys = set(current.keys()) | set(best.keys())
        for key in all_keys:
            if current.get(key) != best.get(key):
                diffs.append({
                    "key": key,
                    "current": current.get(key),
                    "best": best.get(key)
                })
        return diffs
```

### 3.4 性能指标

| 指标 | 目标值 |
|------|--------|
| 执行耗时 | < 500ms（含数据库查询） |
| 数据库查询次数 | ≤ 3 次 |
| 回归检测阈值 | 5%（可配置） |

### 3.5 验收标准

- [ ] 正确识别历史最优记录
- [ ] 回归检测准确率 ≥ 95%
- [ ] 配置差异对比完整
- [ ] 单元测试覆盖率 ≥ 85%

---

## 四、Layer 3：LLM 诊断

**文件路径**：`backend/src/core/rag/validation/layer3_llm.py`
**工作量**：40h

### 4.1 职责

使用 LLM 语义分析 Bad Case，识别深层问题。这是最复杂的一层，需要调用 LLM 进行语义理解。

### 4.2 输入输出

| 维度 | 说明 |
|------|------|
| **输入** | `bad_cases`: List[Dict] - Bad Case 列表（查询、预期结果、实际结果）<br>`max_batch_size`: int - 批量大小（默认 10） |
| **输出** | `ValidationResult`: 包含 LLM 诊断结果、Query 重写建议、提示词优化建议 |

### 4.3 核心设计

#### 4.3.1 模型选择

| 场景 | 推荐模型 | 原因 |
|------|----------|------|
| LLM 诊断 | `qwen-plus` | 成本低、中文理解好、支持 32k 上下文 |
| 降级模型 | `qwen-turbo` | 更便宜，速度更快 |

#### 4.3.2 并发控制

```python
# 并发策略
BATCH_SIZE = 10           # 每批分析 10 个 Bad Case
MAX_CONCURRENT = 3        # 最多 3 个并发请求
REQUEST_TIMEOUT = 30      # 单请求超时 30 秒
RETRY_COUNT = 2           # 失败重试 2 次
```

#### 4.3.3 核心逻辑

```python
"""Layer 3 LLM 诊断 - 语义分析 Bad Case"""

import asyncio
import json
from typing import Dict, List, Any
from json_repair import repair_json


class Layer3LLMDiagnoser:
    """Layer 3 LLM 诊断引擎"""
    
    # Prompt Key（通过 PromptManager 动态加载，禁止硬编码）
    DIAGNOSIS_PROMPT_KEY = "layer3_llm_diagnosis"
    
    # Token 预算控制
    MAX_TOKENS_PER_BATCH = 5000    # 每批最多 5k tokens
    MAX_TOTAL_TOKENS = 50000       # 总预算 50k tokens
    
    async def _build_prompt(self, bad_cases: List[Dict]) -> str:
        """通过 PromptManager 动态加载 Prompt（禁止硬编码）"""
        from src.core.prompt_impl.facade import prompt_manager
        
        bad_cases_json = json.dumps(bad_cases, ensure_ascii=False, indent=2)
        return await prompt_manager.get_prompt(
            self.DIAGNOSIS_PROMPT_KEY,
            variables={"bad_cases_json": bad_cases_json}
        )
    
    def _rule_based_fallback(self, bad_cases: List[Dict]) -> Dict:
        """LLM 不可用时的降级策略：基于规则的简单诊断"""
        error_patterns = []
        suggestions = []
        
        # 统计错误类型
        error_type_counts = {}
        for case in bad_cases:
            error_type = case.get("error_type", "unknown")
            error_type_counts[error_type] = error_type_counts.get(error_type, 0) + 1
        
        # 生成规则建议
        for error_type, count in error_type_counts.items():
            if error_type == "recall_insufficient":
                suggestions.append({
                    "type": "config",
                    "reason": f"召回不足问题出现 {count} 次，建议扩大检索范围",
                    "current_value": {"top_k": 5},
                    "suggested_value": {"top_k": 10},
                    "impact_analysis": {
                        "scope": "影响所有查询",
                        "expected_improvement": "Recall@5 预计提升 10-15%",
                        "risk": "可能降低 Precision@5"
                    },
                    "priority": "high"
                })
            elif error_type == "ranking_error":
                suggestions.append({
                    "type": "config",
                    "reason": f"排序错误出现 {count} 次，建议启用重排序",
                    "current_value": {"reranker_enabled": False},
                    "suggested_value": {"reranker_enabled": True},
                    "impact_analysis": {
                        "scope": "影响所有查询",
                        "expected_improvement": "MRR 预计提升 15-20%",
                        "risk": "增加约 50ms 延迟"
                    },
                    "priority": "high"
                })
        
        return {
            "status": "warning",
            "message": "LLM 服务不可用，使用规则降级诊断",
            "error_patterns": [{"pattern": k, "count": v, "description": f"出现 {v} 次"} for k, v in error_type_counts.items()],
            "suggestions": suggestions
        }
    
    async def execute(self, bad_cases: List[Dict], max_batch_size: int = 10) -> Dict[str, Any]:
        """执行 LLM 诊断"""
        if not bad_cases:
            return {
                "status": "pass",
                "message": "无 Bad Case，跳过诊断",
                "suggestions": []
            }
        
        # 1. 分批处理
        batches = [bad_cases[i:i+max_batch_size] for i in range(0, len(bad_cases), max_batch_size)]
        
        # 2. 并发诊断（限制并发数）
        semaphore = asyncio.Semaphore(3)  # 最多 3 个并发
        tasks = [
            self._diagnose_batch(batch, semaphore)
            for batch in batches
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 3. 合并结果
        all_suggestions = []
        error_patterns = []
        failed_batches = 0
        
        for result in results:
            if isinstance(result, Exception):
                failed_batches += 1
                continue
            
            all_suggestions.extend(result.get("suggestions", []))
            error_patterns.extend(result.get("error_patterns", []))
        
        # 4. 去重建议
        deduplicated_suggestions = self._deduplicate_suggestions(all_suggestions)
        
        # 5. 确定状态
        if failed_batches > len(batches) * 0.5:
            status = "fail"
        elif deduplicated_suggestions:
            status = "warning"
        else:
            status = "pass"
        
        return {
            "status": status,
            "error_patterns": self._merge_error_patterns(error_patterns),
            "suggestions": deduplicated_suggestions,
            "total_cases": len(bad_cases),
            "analyzed_cases": len(bad_cases) - (failed_batches * max_batch_size),
            "failed_batches": failed_batches
        }
    
    async def _diagnose_batch(self, batch: List[Dict], semaphore: asyncio.Semaphore) -> Dict:
        """诊断单个批次"""
        async with semaphore:
            # 1. 通过 PromptManager 动态加载 Prompt
            prompt = await self._build_prompt(batch)
            
            # 2. 调用 LLM（带重试和超时）
            for attempt in range(3):  # 最多重试 2 次
                try:
                    response = await asyncio.wait_for(
                        self._call_llm(prompt),
                        timeout=30  # 30 秒超时
                    )
                    
                    # 3. 解析 JSON（使用 json_repair 容错）
                    repaired_json = repair_json(response)
                    result = json.loads(repaired_json)
                    return result
                    
                except asyncio.TimeoutError:
                    if attempt == 2:
                        raise Exception(f"LLM 请求超时（30s）")
                except Exception as e:
                    if attempt == 2:
                        raise e
                    await asyncio.sleep(1)  # 重试前等待 1 秒
    
    async def _call_llm(self, prompt: str) -> str:
        """调用 LLM（复用现有 LLMServiceFactory）"""
        from src.core.llm.factory import LLMServiceFactory
        
        service = LLMServiceFactory.create_service(scene="diagnosis")
        response = await service.generate(prompt)
        return response
    
    async def execute(self, bad_cases: List[Dict], max_batch_size: int = 10) -> Dict[str, Any]:
        """执行 LLM 诊断（带降级策略）"""
        if not bad_cases:
            return {
                "status": "pass",
                "message": "无 Bad Case，跳过诊断",
                "suggestions": []
            }
        
        # 1. 分批处理
        batches = [bad_cases[i:i+max_batch_size] for i in range(0, len(bad_cases), max_batch_size)]
        
        # 2. 检查 LLM 服务可用性
        try:
            from src.core.llm.factory import LLMServiceFactory
            service = LLMServiceFactory.create_service(scene="diagnosis")
            # 快速健康检查
            await asyncio.wait_for(service.health_check(), timeout=5.0)
        except Exception:
            logger.warning("LLM 服务不可用，降级到规则诊断")
            return self._rule_based_fallback(bad_cases)
        
        # 3. 并发诊断（限制并发数）
        semaphore = asyncio.Semaphore(3)  # 最多 3 个并发
        tasks = [
            self._diagnose_batch(batch, semaphore)
            for batch in batches
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 4. 合并结果
        all_suggestions = []
        error_patterns = []
        failed_batches = 0
        
        for result in results:
            if isinstance(result, Exception):
                failed_batches += 1
                continue
            
            all_suggestions.extend(result.get("suggestions", []))
            error_patterns.extend(result.get("error_patterns", []))
        
        # 5. 去重建议
        deduplicated_suggestions = self._deduplicate_suggestions(all_suggestions)
        
        # 6. 确定状态
        if failed_batches > len(batches) * 0.5:
            # 超过 50% 批次失败，降级到规则诊断
            logger.warning(f"LLM 诊断失败率过高 ({failed_batches}/{len(batches)})，降级到规则诊断")
            return self._rule_based_fallback(bad_cases)
        elif deduplicated_suggestions:
            status = "warning"
        else:
            status = "pass"
        
        return {
            "status": status,
            "error_patterns": self._merge_error_patterns(error_patterns),
            "suggestions": deduplicated_suggestions,
            "total_cases": len(bad_cases),
            "analyzed_cases": len(bad_cases) - (failed_batches * max_batch_size),
            "failed_batches": failed_batches
        }
    
    def _deduplicate_suggestions(self, suggestions: List[Dict]) -> List[Dict]:
        """去重建议（基于 type + reason 相似度）"""
        from difflib import SequenceMatcher
        
        deduplicated = []
        for sugg in suggestions:
            is_duplicate = False
            for existing in deduplicated:
                if (sugg["type"] == existing["type"] and 
                    SequenceMatcher(None, sugg["reason"], existing["reason"]).ratio() > 0.85):
                    # 合并适用案例
                    existing["applicable_cases"] = list(set(
                        existing.get("applicable_cases", []) + 
                        sugg.get("applicable_cases", [])
                    ))
                    is_duplicate = True
                    break
            
            if not is_duplicate:
                deduplicated.append(sugg)
        
        return deduplicated
    
    def _merge_error_patterns(self, patterns: List[Dict]) -> List[Dict]:
        """合并错误模式（按 pattern 名称聚合）"""
        merged = {}
        for pattern in patterns:
            name = pattern["pattern"]
            if name not in merged:
                merged[name] = pattern
            else:
                merged[name]["count"] += pattern["count"]
        return list(merged.values())
```

### 4.4 降级策略

| 场景 | 降级策略 |
|------|----------|
| LLM 请求超时 | 重试 2 次，仍失败则标记该批次为"未分析" |
| LLM 返回非 JSON | 使用 `json_repair` 修复，修复失败则跳过 |
| 超过 50% 批次失败 | 整体状态标记为 `fail`，但返回已成功分析的结果 |
| LLM 服务不可用 | 跳过 Layer 3，不阻断整体流程 |

### 4.5 性能指标

| 指标 | 目标值 |
|------|--------|
| 单批次耗时 | < 30s（含 LLM 调用） |
| 总耗时（100 用例） | < 3 分钟（10 批 × 3 并发） |
| Token 消耗 | < 50k tokens/100 用例 |
| JSON 解析成功率 | ≥ 95%（使用 json_repair） |

### 4.6 验收标准

- [ ] LLM 诊断准确率 ≥ 80%（人工抽检）
- [ ] JSON 解析成功率 ≥ 95%
- [ ] 超时控制有效（单请求 < 30s）
- [ ] 降级策略正确触发
- [ ] 单元测试覆盖率 ≥ 80%

---

## 五、Layer 4：数据质量检查

**文件路径**：`backend/src/core/rag/validation/layer4_data.py`
**工作量**：25h

### 5.1 职责

检查数据集质量问题，包括 Golden 数据集覆盖度、文档分块质量、测试用例多样性。

### 5.2 输入输出

| 维度 | 说明 |
|------|------|
| **输入** | `test_set_id`: str - 测试集 ID<br>`source_doc_ids`: List[str] - 源文档 ID 列表 |
| **输出** | `ValidationResult`: 包含数据质量检查结果、清洗建议 |

### 5.3 核心逻辑

```python
"""Layer 4 数据质量检查"""

from typing import Dict, List, Any


class Layer4DataQualityChecker:
    """Layer 4 数据质量检查引擎"""
    
    async def execute(self, test_set_id: str, source_doc_ids: List[str]) -> Dict[str, Any]:
        """执行数据质量检查"""
        suggestions = []
        
        # 1. 检查 Golden 数据集覆盖度
        coverage_check = await self._check_golden_coverage(test_set_id)
        if coverage_check["coverage"] < 0.7:
            suggestions.append({
                "type": "data",
                "reason": f"Golden 数据集覆盖度仅 {coverage_check['coverage']:.1%}，低于 70% 阈值",
                "current_value": {"coverage": coverage_check["coverage"]},
                "suggested_value": {"coverage": 0.8},
                "impact_analysis": {
                    "scope": "影响测试评估的可靠性",
                    "expected_improvement": "提高覆盖度至 80%+，增强评估可信度",
                    "risk": "需要人工标注成本"
                },
                "priority": "high"
            })
        
        # 2. 检查文档分块质量
        chunking_check = await self._check_chunking_quality(source_doc_ids)
        if chunking_check["avg_chunk_size"] > 1000:
            suggestions.append({
                "type": "config",
                "reason": f"平均分块大小 {chunking_check['avg_chunk_size']} 过大，建议减小",
                "current_value": {"chunk_size": chunking_check["avg_chunk_size"]},
                "suggested_value": {"chunk_size": 512},
                "impact_analysis": {
                    "scope": "影响检索精度",
                    "expected_improvement": "减小分块可提高 Precision@k",
                    "risk": "可能丢失上下文信息"
                },
                "priority": "medium"
            })
        
        # 3. 检查文档重复率
        duplication_check = await self._check_duplication(source_doc_ids)
        if duplication_check["duplication_rate"] > 0.1:
            suggestions.append({
                "type": "data",
                "reason": f"文档重复率 {duplication_check['duplication_rate']:.1%}，建议去重",
                "current_value": {"duplication_rate": duplication_check["duplication_rate"]},
                "suggested_value": {"duplication_rate": 0.05},
                "impact_analysis": {
                    "scope": "浪费存储空间，影响检索效率",
                    "expected_improvement": "去重后可减少存储和检索开销",
                    "risk": "需确认重复文档是否有意保留"
                },
                "priority": "medium"
            })
        
        # 4. 检查测试用例多样性
        diversity_check = await self._check_test_case_diversity(test_set_id)
        if diversity_check["cognitive_dimension_coverage"] < 0.6:
            suggestions.append({
                "type": "data",
                "reason": f"认知维度覆盖率 {diversity_check['cognitive_dimension_coverage']:.1%}，测试用例类型单一",
                "current_value": {"coverage": diversity_check["cognitive_dimension_coverage"]},
                "suggested_value": {"coverage": 0.8},
                "impact_analysis": {
                    "scope": "测试评估不全面",
                    "expected_improvement": "增加认知维度覆盖，提高评估全面性",
                    "risk": "需要生成更多测试用例"
                },
                "priority": "medium"
            })
        
        # 确定状态
        if any(s["priority"] == "high" for s in suggestions):
            status = "warning"
        elif suggestions:
            status = "info"
        else:
            status = "pass"
        
        return {
            "status": status,
            "coverage_check": coverage_check,
            "chunking_check": chunking_check,
            "duplication_check": duplication_check,
            "diversity_check": diversity_check,
            "suggestions": suggestions
        }
    
    async def _check_golden_coverage(self, test_set_id: str) -> Dict:
        """检查 Golden 数据集覆盖度"""
        # 查询测试用例总数
        # 查询有 Golden 标注的用例数
        # 计算覆盖率 = 有标注用例 / 总用例
        pass
    
    async def _check_chunking_quality(self, source_doc_ids: List[str]) -> Dict:
        """检查文档分块质量"""
        # 查询分块统计（平均大小、最大大小、最小大小）
        pass
    
    async def _check_duplication(self, source_doc_ids: List[str]) -> Dict:
        """检查文档重复率"""
        # 使用 MinHash 或 SimHash 检测重复文档
        pass
    
    async def _check_test_case_diversity(self, test_set_id: str) -> Dict:
        """检查测试用例多样性"""
        # 统计各认知维度用例数量
        # 计算覆盖度 = 有用例的维度数 / 总维度数（12）
        pass
```

### 5.4 性能指标

| 指标 | 目标值 |
|------|--------|
| 执行耗时 | < 2s |
| 数据库查询次数 | ≤ 5 次 |
| 重复检测准确率 | ≥ 90% |

### 5.5 验收标准

- [ ] Golden 覆盖度计算准确
- [ ] 分块质量检查完整
- [ ] 重复检测有效
- [ ] 单元测试覆盖率 ≥ 85%

---

## 六、Layer 5：检索链路检查

**文件路径**：`backend/src/core/rag/validation/layer5_retrieval.py`
**工作量**：30h

### 6.1 职责

检查检索全链路问题，包括 Embedding 质量、意图识别准确率、错误模式分组。

### 6.2 输入输出

| 维度 | 说明 |
|------|------|
| **输入** | `test_run_id`: str - 测试运行 ID<br>`intent_annotations`: List[IntentAnnotation] - 意图标注数据 |
| **输出** | `ValidationResult`: 包含检索链路检查结果、Embedding 优化建议 |

### 6.3 核心逻辑

```python
"""Layer 5 检索链路检查"""

from typing import Dict, List, Any


class Layer5RetrievalChecker:
    """Layer 5 检索链路检查引擎"""
    
    async def execute(self, test_run_id: str, intent_annotations: List[Dict]) -> Dict[str, Any]:
        """执行检索链路检查"""
        suggestions = []
        
        # 1. 检查 Embedding 质量
        embedding_check = await self._check_embedding_quality(test_run_id)
        if embedding_check["avg_cosine_similarity"] < 0.6:
            suggestions.append({
                "type": "config",
                "reason": f"Embedding 平均余弦相似度 {embedding_check['avg_cosine_similarity']:.2f} 偏低",
                "current_value": {"model": embedding_check["model"]},
                "suggested_value": {"model": "text-embedding-v3"},
                "impact_analysis": {
                    "scope": "影响所有向量检索",
                    "expected_improvement": "切换至 v3 模型，相似度预计提升 10-15%",
                    "risk": "v3 模型成本略高（+20%）"
                },
                "priority": "high"
            })
        
        # 2. 检查意图识别准确率
        intent_check = await self._check_intent_accuracy(intent_annotations)
        if intent_check["accuracy"] < 0.75:
            suggestions.append({
                "type": "prompt",
                "reason": f"意图识别准确率 {intent_check['accuracy']:.1%}，低于 75% 阈值",
                "current_value": {"accuracy": intent_check["accuracy"]},
                "suggested_value": {"accuracy": 0.85},
                "impact_analysis": {
                    "scope": "影响查询路由和权重分配",
                    "expected_improvement": "优化意图识别 Prompt，准确率预计提升至 85%+",
                    "risk": "需重新标注部分数据验证"
                },
                "priority": "high"
            })
        
        # 3. 错误模式分组
        error_patterns = await self._group_error_patterns(test_run_id)
        
        # 4. 检查检索链路完整性
        pipeline_check = await self._check_pipeline_integrity(test_run_id)
        
        # 确定状态
        if any(s["priority"] == "high" for s in suggestions):
            status = "warning"
        elif suggestions:
            status = "info"
        else:
            status = "pass"
        
        return {
            "status": status,
            "embedding_check": embedding_check,
            "intent_check": intent_check,
            "error_patterns": error_patterns,
            "pipeline_check": pipeline_check,
            "suggestions": suggestions
        }
    
    async def _check_embedding_quality(self, test_run_id: str) -> Dict:
        """检查 Embedding 质量"""
        # 查询检索结果的余弦相似度分布
        # 计算平均相似度、异常值比例
        pass
    
    async def _check_intent_accuracy(self, intent_annotations: List[Dict]) -> Dict:
        """检查意图识别准确率"""
        # 对比系统识别的意图与人工标注的意图
        # 计算准确率 = 匹配数 / 总标注数
        pass
    
    async def _group_error_patterns(self, test_run_id: str) -> List[Dict]:
        """错误模式分组"""
        # 按错误类型分组：召回不足、排序错误、相关性差
        pass
    
    async def _check_pipeline_integrity(self, test_run_id: str) -> Dict:
        """检查检索链路完整性"""
        # 检查各步骤是否正常执行：查询重写 → 检索 → 重排序 → 过滤
        pass
```

### 6.4 性能指标

| 指标 | 目标值 |
|------|--------|
| 执行耗时 | < 3s |
| Embedding 检测准确率 | ≥ 90% |
| 意图识别准确率计算 | 100%（确定性计算） |

### 6.5 验收标准

- [ ] Embedding 质量检测有效
- [ ] 意图识别准确率计算准确
- [ ] 错误模式分组合理
- [ ] 单元测试覆盖率 ≥ 85%

---

## 七、Layer 6：验证保障

**文件路径**：`backend/src/core/rag/validation/layer6_verification.py`
**工作量**：25h

### 7.1 职责

验证优化效果，降低风险。包括回归检测、交叉验证、成本效果分析。

### 7.2 输入输出

| 维度 | 说明 |
|------|------|
| **输入** | `test_run_id`: str - 测试运行 ID<br>`suggestions`: List[Dict] - 前 5 层生成的调优建议 |
| **输出** | `ValidationResult`: 包含验证结果、成本效果分析 |

### 7.3 核心逻辑

```python
"""Layer 6 验证保障"""

from typing import Dict, List, Any


class Layer6Verification:
    """Layer 6 验证保障引擎"""
    
    async def execute(self, test_run_id: str, suggestions: List[Dict]) -> Dict[str, Any]:
        """执行验证保障"""
        verification_results = []
        
        # 1. 回归检测：对比历史 Bad Case 修复情况
        regression_check = await self._check_regression_fix(test_run_id)
        verification_results.append(regression_check)
        
        # 2. 交叉验证：不同测试集结果一致性
        cross_validation = await self._cross_validate(test_run_id)
        verification_results.append(cross_validation)
        
        # 3. 成本效果分析：Token 消耗与指标提升对比
        cost_analysis = await self._analyze_cost_effectiveness(test_run_id, suggestions)
        
        # 生成验证建议
        suggestions = []
        if cross_validation["consistency"] < 0.7:
            suggestions.append({
                "type": "data",
                "reason": f"跨测试集一致性 {cross_validation['consistency']:.1%} 偏低，建议增加测试集多样性",
                "current_value": {"consistency": cross_validation["consistency"]},
                "suggested_value": {"consistency": 0.8},
                "impact_analysis": {
                    "scope": "影响评估结果的可信度",
                    "expected_improvement": "提高一致性至 80%+",
                    "risk": "需要扩充测试集"
                },
                "priority": "medium"
            })
        
        if cost_analysis["cost_per_improvement"] > 100:
            suggestions.append({
                "type": "config",
                "reason": f"单次指标提升成本 {cost_analysis['cost_per_improvement']:.0f} tokens 过高",
                "current_value": {"cost_per_improvement": cost_analysis["cost_per_improvement"]},
                "suggested_value": {"cost_per_improvement": 50},
                "impact_analysis": {
                    "scope": "影响系统运行成本",
                    "expected_improvement": "优化配置降低 Token 消耗",
                    "risk": "可能影响指标提升幅度"
                },
                "priority": "low"
            })
        
        # 确定状态
        if any(v["status"] == "fail" for v in verification_results):
            status = "warning"
        elif suggestions:
            status = "info"
        else:
            status = "pass"
        
        return {
            "status": status,
            "verification_results": verification_results,
            "cost_analysis": cost_analysis,
            "suggestions": suggestions
        }
    
    async def _check_regression_fix(self, test_run_id: str) -> Dict:
        """回归检测：对比历史 Bad Case 修复情况"""
        # 查询历史 Bad Case
        # 检查当前测试是否修复了这些 Bad Case
        pass
    
    async def _cross_validate(self, test_run_id: str) -> Dict:
        """交叉验证：不同测试集结果一致性"""
        # 查询其他测试集的结果
        # 计算指标一致性（标准差）
        pass
    
    async def _analyze_cost_effectiveness(self, test_run_id: str, suggestions: List[Dict]) -> Dict:
        """成本效果分析"""
        # 查询 Token 消耗
        # 计算每次指标提升的 Token 成本
        pass
```

### 7.4 性能指标

| 指标 | 目标值 |
|------|--------|
| 执行耗时 | < 2s |
| 交叉验证测试集数量 | ≥ 3 个 |
| 成本计算准确率 | 100% |

### 7.5 验收标准

- [ ] 回归检测准确
- [ ] 交叉验证有效
- [ ] 成本分析完整
- [ ] 单元测试覆盖率 ≥ 85%

---

## 八、统一调度引擎

**文件路径**：`backend/src/core/rag/validation/engine.py`
**工作量**：20h

### 8.1 职责

6 层校验统一调度入口，结果合并去重，生成完整 TestReport 对象。

### 8.2 核心逻辑

```python
"""6 层校验引擎 - 统一调度"""

import asyncio
import logging
from typing import Dict, List, Any
from datetime import datetime, timezone

from src.core.exceptions import AppException

logger = logging.getLogger(__name__)


class ValidationEngine:
    """6 层校验引擎"""
    
    def __init__(self):
        from .layer1_rules import Layer1RulesEngine
        from .layer2_history import Layer2HistoryComparator
        from .layer3_llm import Layer3LLMDiagnoser
        from .layer4_data import Layer4DataQualityChecker
        from .layer5_retrieval import Layer5RetrievalChecker
        from .layer6_verification import Layer6Verification
        
        self.layer1 = Layer1RulesEngine()
        self.layer2 = Layer2HistoryComparator()
        self.layer3 = Layer3LLMDiagnoser()
        self.layer4 = Layer4DataQualityChecker()
        self.layer5 = Layer5RetrievalChecker()
        self.layer6 = Layer6Verification()
    
    @classmethod
    async def execute(cls, test_run_id: str) -> Dict[str, Any]:
        """执行 6 层校验（类方法，便捷调用）"""
        engine = cls()
        return await engine.run(test_run_id)
    
    async def run(self, test_run_id: str) -> Dict[str, Any]:
        """执行完整校验流程（带全局超时和并行优化）"""
        # 设置全局超时（5 分钟）
        try:
            return await asyncio.wait_for(
                self._run_internal(test_run_id),
                timeout=300  # 5 分钟超时
            )
        except asyncio.TimeoutError:
            logger.error(f"校验执行超时: test_run={test_run_id}")
            raise AppException(
                status_code=500,
                code=50001,
                error_code="VALIDATION_TIMEOUT",
                message="校验执行超时（5 分钟），请减少测试用例数量或联系管理员"
            )
    
    async def _run_internal(self, test_run_id: str) -> Dict[str, Any]:
        """内部执行逻辑（无超时包装）"""
        start_time = datetime.now(timezone.utc)
        
        # 1. 获取测试运行数据
        test_run = await self._get_test_run(test_run_id)
        if not test_run:
            raise ValueError(f"测试运行不存在: {test_run_id}")
        
        metrics = test_run["metrics"]
        bad_cases = test_run["bad_cases"]
        test_set_id = test_run["test_set_id"]
        source_doc_ids = test_run["source_doc_ids"]
        
        # 2. 递进式执行 6 层校验
        results = {}
        all_suggestions = []
        
        # Layer 1: 规则引擎（快速）
        try:
            results["layer1_rules"] = await self.layer1.execute(metrics)
            all_suggestions.extend(results["layer1_rules"].get("suggestions", []))
        except Exception as e:
            logger.error(f"Layer 1 执行失败: {e}")
            results["layer1_rules"] = {"status": "fail", "error": str(e)}
        
        # Layer 2: 历史对比
        try:
            results["layer2_history"] = await self.layer2.execute(test_run_id, test_set_id)
            all_suggestions.extend(results["layer2_history"].get("suggestions", []))
        except Exception as e:
            logger.error(f"Layer 2 执行失败: {e}")
            results["layer2_history"] = {"status": "fail", "error": str(e)}
        
        # Layer 3: LLM 诊断（仅在有 Bad Case 时执行）
        if bad_cases:
            try:
                results["layer3_llm"] = await self.layer3.execute(bad_cases)
                all_suggestions.extend(results["layer3_llm"].get("suggestions", []))
            except Exception as e:
                logger.error(f"Layer 3 执行失败: {e}")
                results["layer3_llm"] = {"status": "fail", "error": str(e)}
        else:
            results["layer3_llm"] = {"status": "pass", "message": "无 Bad Case"}
        
        # Layer 4-6 并行执行（无依赖关系）
        layer4_task = self._safe_execute_layer(
            self.layer4.execute(test_set_id, source_doc_ids),
            "layer4_data"
        )
        layer5_task = self._safe_execute_layer(
            self.layer5.execute(test_run_id, await self._get_intent_annotations()),
            "layer5_retrieval"
        )
        layer6_task = self._safe_execute_layer(
            self.layer6.execute(test_run_id, all_suggestions),
            "layer6_verification"
        )
        
        # 并行执行 Layer 4-6
        layer4_result, layer5_result, layer6_result = await asyncio.gather(
            layer4_task, layer5_task, layer6_task,
            return_exceptions=True
        )
        
        # 收集并行结果
        for result_key, result in [
            ("layer4_data", layer4_result),
            ("layer5_retrieval", layer5_result),
            ("layer6_verification", layer6_result)
        ]:
            if isinstance(result, Exception):
                logger.error(f"{result_key} 执行失败: {result}")
                results[result_key] = {"status": "fail", "error": str(result)}
            else:
                results[result_key] = result
                all_suggestions.extend(result.get("suggestions", []))
        
        # 3. 合并去重建议
        deduplicated_suggestions = self._deduplicate_suggestions(all_suggestions)
        
        # 4. 计算综合评分
        overall_score = self._calculate_overall_score(results)
        
        # 5. 生成 TestReport
        report = {
            "test_run_id": test_run_id,
            "validation_results": results,
            "tuning_suggestions": deduplicated_suggestions,
            "overall_score": overall_score,
            "generated_at": datetime.now(timezone.utc),
            "execution_time_ms": (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
        }
        
        # 6. 保存到数据库
        await self._save_report(report)
        
        logger.info(f"校验完成: test_run={test_run_id}, score={overall_score}, suggestions={len(deduplicated_suggestions)}")
        
        return report
    
    async def _safe_execute_layer(self, coro, layer_name: str) -> Dict:
        """安全执行单层校验，异常不传播"""
        try:
            return await coro
        except Exception as e:
            logger.error(f"{layer_name} 执行失败: {e}")
            return {"status": "fail", "error": str(e)}
    
    def _deduplicate_suggestions(self, suggestions: List[Dict]) -> List[Dict]:
        """去重建议（基于 type + reason 相似度）"""
        from difflib import SequenceMatcher
        
        deduplicated = []
        for sugg in suggestions:
            is_duplicate = False
            for existing in deduplicated:
                if (sugg["type"] == existing["type"] and 
                    SequenceMatcher(None, sugg["reason"], existing["reason"]).ratio() > 0.85):
                    # 保留优先级更高的
                    if self._priority_value(sugg["priority"]) > self._priority_value(existing["priority"]):
                        deduplicated.remove(existing)
                        deduplicated.append(sugg)
                    is_duplicate = True
                    break
            
            if not is_duplicate:
                deduplicated.append(sugg)
        
        # 按优先级排序
        deduplicated.sort(key=lambda s: self._priority_value(s["priority"]), reverse=True)
        
        return deduplicated
    
    def _priority_value(self, priority: str) -> int:
        """优先级数值化"""
        return {"high": 3, "medium": 2, "low": 1}.get(priority, 0)
    
    def _calculate_overall_score(self, results: Dict) -> float:
        """计算综合评分 0-100"""
        # 基础分 100，每层失败扣分
        score = 100.0
        
        for layer_name, result in results.items():
            if result.get("status") == "fail":
                score -= 15
            elif result.get("status") == "warning":
                score -= 5
        
        return max(0.0, min(100.0, score))
    
    async def _get_test_run(self, test_run_id: str) -> Dict:
        """获取测试运行数据"""
        pass
    
    async def _get_intent_annotations(self) -> List[Dict]:
        """获取意图标注数据"""
        pass
    
    async def _save_report(self, report: Dict):
        """保存报告到数据库"""
        pass
```

### 8.3 集成方式

在现有测试运行完成后自动触发校验：

```python
# backend/src/service/rag_test/facade.py

async def complete_test_run(self, test_run_id: str):
    """完成测试运行"""
    # 1. 聚合测试结果
    # 2. 计算指标
    # 3. 自动触发 6 层校验
    report = await ValidationEngine.execute(test_run_id)
    
    # 4. 推送 SSE 通知
    await self.sse_publisher.publish("test_complete", {
        "test_run_id": test_run_id,
        "overall_score": report["overall_score"],
        "suggestions_count": len(report["tuning_suggestions"])
    })
```

### 8.4 性能指标

| 指标 | 目标值 |
|------|--------|
| 总耗时（100 用例） | < 5 分钟 |
| 内存占用 | < 50MB |
| 建议去重率 | ≥ 80% |
| 综合评分准确率 | ≥ 85%（人工抽检） |

### 8.5 验收标准

- [ ] 6 层校验完整执行
- [ ] 某层失败不阻断整体流程
- [ ] 建议去重有效
- [ ] 综合评分合理
- [ ] 报告保存到数据库
- [ ] 单元测试覆盖率 ≥ 85%

---

## 九、整体验收标准

- [ ] 每层校验逻辑独立可测试，单元测试覆盖率 ≥ 80%
- [ ] 完整校验 100 用例的测试集耗时 < 5 分钟
- [ ] 每个建议符合输出规范，包含原因、对比、影响分析、预期提升
- [ ] 与现有 RAG 流水线无缝集成，无需修改现有检索逻辑
- [ ] LLM 输出解析稳定，无 JSON 格式错误
- [ ] 降级策略正确触发，不阻断整体流程
- [ ] 综合评分 0-100，反映系统整体健康度

---
**注意**：监控指标先记录到日志，后续再接入 Prometheus
