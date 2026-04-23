# 09-1 Layer1 规则引擎详细实现方案
**所属模块**：6层校验引擎
**功能**：基于指标阈值的快速规则校验，识别明显的配置问题，生成调优建议
**文件路径**：`backend/src/core/rag/validation/layer1_rules.py`
---
## 一、核心规则定义
### 校验指标与阈值配置（可配置化，存储在config表中）
| 指标 | 阈值 | 规则说明 | 建议级别 |
|------|------|----------|----------|
| Precision@1 | < 0.6 | 首条准确率过低，召回/排序逻辑有问题 | high |
| Recall@3 | < 0.8 | 前三页召回率过低，召回逻辑有问题 | high |
| F1 Score | < 0.7 | 综合准确率过低 | high |
| MRR | < 0.7 | 平均倒数排名过低，排序逻辑有问题 | medium |
| NDCG@5 | < 0.75 | 归一化折损累计增益过低，排序逻辑有问题 | medium |
| 空查询占比 | > 0.1 | 空结果查询占比过高，召回覆盖不足 | high |
| 平均检索耗时 | > 1000ms | 检索耗时过长，性能问题 | medium |
| 分块平均长度 | < 200 / > 1000 | 分块长度不合理，过长过短都会影响效果 | medium |
| 融合检索权重 | 向量权重 < 0.3 / > 0.7 | 融合权重不合理，偏向单一检索方式 | medium |
| 阈值过滤分数 | > 0.6 | 过滤阈值过高，导致召回不足 | high |
---
## 二、完整代码实现
```python
from uuid import UUID
from typing import List, Dict
from backend.schemas.rag_eval.tuning_suggestion import TuningSuggestionCreate
from backend.service.rag_test.test_result_service import TestResultService
from backend.service.config.config_service import ConfigService
from backend.core.rag.validation.base_validator import BaseValidator
class Layer1RulesValidator(BaseValidator):
    """Layer1 规则引擎校验器"""
    def __init__(self, db):
        super().__init__(db)
        self.result_service = TestResultService(db)
        self.config_service = ConfigService(db)
        # 阈值配置，后续可迁移到数据库配置
        self.thresholds = {
            "precision@1": 0.6,
            "recall@3": 0.8,
            "f1_score": 0.7,
            "mrr": 0.7,
            "ndcg@5": 0.75,
            "empty_query_rate": 0.1,
            "avg_retrieval_time": 1000,  # ms
            "chunk_length_min": 200,
            "chunk_length_max": 1000,
            "vector_weight_min": 0.3,
            "vector_weight_max": 0.7,
            "filter_threshold_max": 0.6
        }
    async def validate(self, test_run_id: UUID) -> Dict:
        """
        执行Layer1校验
        :param test_run_id: 测试运行ID
        :return: 校验结果 + 调优建议
        """
        # 1. 获取测试结果指标
        test_metrics = await self.result_service.get_test_metrics(test_run_id)
        # 2. 获取当前配置
        current_config = await self.config_service.get_all_config()
        # 3. 执行规则校验
        issues = []
        suggestions = []
        # 3.1 校验Precision@1
        if test_metrics.get("precision@1", 0) < self.thresholds["precision@1"]:
            issues.append({
                "type": "precision_low",
                "metric": "precision@1",
                "current": test_metrics.get("precision@1", 0),
                "threshold": self.thresholds["precision@1"],
                "description": "首条准确率过低，排序/召回逻辑需要优化"
            })
            # 生成建议
            suggestions.append(TuningSuggestionCreate(
                suggestion_id=f"layer1-precision-{test_run_id}",
                type="config",
                level="high",
                current_value={"precision@1": test_metrics.get("precision@1", 0)},
                suggested_value={
                    "rag.retrieval.vector_weight": 0.6,
                    "rag.retrieval.keyword_weight": 0.4,
                    "rag.rerank.enable": True
                },
                reason=f"当前Precision@1={test_metrics.get('precision@1', 0):.2f} < 阈值{self.thresholds['precision@1']}，首条准确率过低，可能是排序权重不合理或未开启重排序。",
                impact_analysis={
                    "scope": "检索全链路",
                    "expected_improvement": "Precision@1预计提升20%-30%",
                    "risk": "低，不会影响召回率"
                }
            ))
        # 3.2 校验Recall@3
        if test_metrics.get("recall@3", 0) < self.thresholds["recall@3"]:
            issues.append({
                "type": "recall_low",
                "metric": "recall@3",
                "current": test_metrics.get("recall@3", 0),
                "threshold": self.thresholds["recall@3"],
                "description": "前三页召回率过低，召回逻辑需要优化"
            })
            suggestions.append(TuningSuggestionCreate(
                suggestion_id=f"layer1-recall-{test_run_id}",
                type="config",
                level="high",
                current_value={
                    "recall@3": test_metrics.get("recall@3", 0),
                    "rag.retrieval.filter_threshold": current_config.get("rag.retrieval.filter_threshold", 0.5),
                    "rag.retrieval.top_k": current_config.get("rag.retrieval.top_k", 5)
                },
                suggested_value={
                    "rag.retrieval.filter_threshold": 0.3,
                    "rag.retrieval.top_k": 10
                },
                reason=f"当前Recall@3={test_metrics.get('recall@3', 0):.2f} < 阈值{self.thresholds['recall@3']}，召回率过低，可能是过滤阈值过高或召回数量不足。",
                impact_analysis={
                    "scope": "检索全链路",
                    "expected_improvement": "Recall@3预计提升15%-25%",
                    "risk": "中，可能会增加少量检索耗时"
                }
            ))
        # 3.3 校验平均检索耗时
        if test_metrics.get("avg_retrieval_time", 0) > self.thresholds["avg_retrieval_time"]:
            issues.append({
                "type": "retrieval_time_high",
                "metric": "avg_retrieval_time",
                "current": test_metrics.get("avg_retrieval_time", 0),
                "threshold": self.thresholds["avg_retrieval_time"],
                "description": "平均检索耗时过长，性能需要优化"
            })
            suggestions.append(TuningSuggestionCreate(
                suggestion_id=f"layer1-time-{test_run_id}",
                type="config",
                level="medium",
                current_value={
                    "avg_retrieval_time": test_metrics.get("avg_retrieval_time", 0),
                    "rag.retrieval.top_k": current_config.get("rag.retrieval.top_k", 10),
                    "rag.rerank.enable": current_config.get("rag.rerank.enable", True)
                },
                suggested_value={
                    "rag.retrieval.top_k": 5,
                    "rag.rerank.top_n": 3
                },
                reason=f"当前平均检索耗时={test_metrics.get('avg_retrieval_time', 0):.0f}ms > 阈值{self.thresholds['avg_retrieval_time']}ms，耗时过长，可能是召回数量过多或重排序参数不合理。",
                impact_analysis={
                    "scope": "检索性能",
                    "expected_improvement": "检索耗时预计减少30%-40%",
                    "risk": "低，对准确率影响较小"
                }
            ))
        # 3.4 校验过滤阈值
        filter_threshold = current_config.get("rag.retrieval.filter_threshold", 0.5)
        if filter_threshold > self.thresholds["filter_threshold_max"]:
            issues.append({
                "type": "filter_threshold_high",
                "metric": "rag.retrieval.filter_threshold",
                "current": filter_threshold,
                "threshold": self.thresholds["filter_threshold_max"],
                "description": "过滤阈值过高，导致召回不足"
            })
            suggestions.append(TuningSuggestionCreate(
                suggestion_id=f"layer1-filter-{test_run_id}",
                type="config",
                level="high",
                current_value={"rag.retrieval.filter_threshold": filter_threshold},
                suggested_value={"rag.retrieval.filter_threshold": 0.3},
                reason=f"当前过滤阈值={filter_threshold} > 阈值{self.thresholds['filter_threshold_max']}，过高的阈值会过滤掉很多相关结果，导致召回率低。",
                impact_analysis={
                    "scope": "检索召回",
                    "expected_improvement": "Recall@3预计提升20%左右",
                    "risk": "低，只会增加少量无关结果"
                }
            ))
        # 3.5 校验向量权重
        vector_weight = current_config.get("rag.retrieval.vector_weight", 0.5)
        if vector_weight < self.thresholds["vector_weight_min"] or vector_weight > self.thresholds["vector_weight_max"]:
            issues.append({
                "type": "vector_weight_unreasonable",
                "metric": "rag.retrieval.vector_weight",
                "current": vector_weight,
                "threshold": f"{self.thresholds['vector_weight_min']}-{self.thresholds['vector_weight_max']}",
                "description": "融合检索权重不合理，偏向单一检索方式"
            })
            suggested_weight = 0.5 if vector_weight < 0.3 else 0.6
            suggestions.append(TuningSuggestionCreate(
                suggestion_id=f"layer1-weight-{test_run_id}",
                type="config",
                level="medium",
                current_value={"rag.retrieval.vector_weight": vector_weight},
                suggested_value={"rag.retrieval.vector_weight": suggested_weight, "rag.retrieval.keyword_weight": 1 - suggested_weight},
                reason=f"当前向量权重={vector_weight}，不在合理范围{self.thresholds['vector_weight_min']}-{self.thresholds['vector_weight_max']}内，会导致检索效果偏向单一方式，融合效果差。",
                impact_analysis={
                    "scope": "检索融合",
                    "expected_improvement": "F1得分预计提升5%-10%",
                    "risk": "低"
                }
            ))
        # 4. 计算Layer1得分（0-100）
        score = self._calculate_score(test_metrics, issues)
        # 5. 返回结果
        return {
            "layer": "layer1",
            "name": "规则引擎校验",
            "score": score,
            "issues": issues,
            "suggestions": suggestions,
            "metrics": test_metrics,
            "thresholds": self.thresholds
        }
    def _calculate_score(self, metrics: Dict, issues: List[Dict]) -> float:
        """计算Layer1得分"""
        base_score = 100
        # 每个高优先级问题扣20分，中优先级扣10分，低优先级扣5分
        for issue in issues:
            level = self._get_issue_level(issue["type"])
            if level == "high":
                base_score -= 20
            elif level == "medium":
                base_score -= 10
            else:
                base_score -=5
        return max(0, min(100, base_score))
    def _get_issue_level(self, issue_type: str) -> str:
        """获取问题优先级"""
        high_issues = ["precision_low", "recall_low", "filter_threshold_high"]
        if issue_type in high_issues:
            return "high"
        return "medium"
```
---
## 三、基类定义（统一所有校验器接口）
**文件路径**：`backend/src/core/rag/validation/base_validator.py`
```python
from abc import ABC, abstractmethod
from uuid import UUID
from typing import Dict
class BaseValidator(ABC):
    """校验器基类"""
    def __init__(self, db):
        self.db = db
    @abstractmethod
    async def validate(self, test_run_id: UUID) -> Dict:
        """
        执行校验
        :param test_run_id: 测试运行ID
        :return: 校验结果，包含得分、问题列表、建议列表
        """
        pass
```
---
## 四、集成点
在校验引擎调度入口中调用Layer1校验：
**文件路径**：`backend/src/core/rag/validation/engine.py`
```python
from uuid import UUID
from backend.core.db.session import get_db
from .layer1_rules import Layer1RulesValidator
from .layer2_history import Layer2HistoryValidator
# ...其他层导入
class ValidationEngine:
    """6层校验引擎调度器"""
    def __init__(self):
        self.db = next(get_db())
        self.validators = [
            Layer1RulesValidator(self.db),
            # Layer2HistoryValidator(self.db),
            # Layer3LlmValidator(self.db),
            # Layer4DataValidator(self.db),
            # Layer5RetrievalValidator(self.db),
            # Layer6VerificationValidator(self.db)
        ]
    async def generate_report(self, test_run_id: UUID):
        """生成完整校验报告"""
        all_results = []
        all_suggestions = []
        total_score = 0
        # 执行所有层校验
        for validator in self.validators:
            result = await validator.validate(test_run_id)
            all_results.append(result)
            all_suggestions.extend(result.get("suggestions", []))
            total_score += result.get("score", 0)
        # 计算综合得分
        overall_score = total_score / len(self.validators) if self.validators else 0
        # 保存报告
        # ...调用ReportService保存逻辑
```
---
## 五、配置化改造（后续迭代）
将阈值配置迁移到数据库配置表，支持页面动态调整：
1. 在`config`表中新增以`rag.validation.layer1`为前缀的配置项
2. 在`ConfigService`中新增获取Layer1阈值的方法
3. 校验器初始化时从数据库加载阈值，而非硬编码
---
**验收标准**：
✅ 所有规则覆盖需求定义的指标阈值校验
✅ 每个问题生成对应的调优建议，包含原因、当前值、建议值、影响分析
✅ 得分计算逻辑合理，能准确反映规则校验的结果
✅ 基类接口统一，方便后续层的接入
✅ 与校验引擎调度器集成正常
