# 09-2 Layer2 历史对比校验详细实现方案
**所属模块**：6层校验引擎
**功能**：对比当前测试运行与历史最优版本的指标差异，识别配置/提示词变更带来的回归风险，生成针对性调优建议
**文件路径**：`backend/src/core/rag/validation/layer2_history.py`
**依赖组件**：TestResultService、ConfigService、PromptService
---
## 一、核心校验逻辑
1. 获取当前测试运行的指标、使用的配置版本、提示词版本
2. 查询同测试集下的历史最优测试运行（按综合得分排序）
3. 对比指标差异：下降超过阈值的指标标记为回归问题
4. 对比配置/提示词变更：定位导致指标变化的具体修改点
5. 生成回归修复建议或优化建议
---
## 二、阈值配置
| 指标 | 下降阈值 | 风险等级 |
|------|----------|----------|
| Precision@1 | > 10% | 高风险 |
| Recall@3 | > 8% | 高风险 |
| F1 Score | > 10% | 高风险 |
| MRR | > 10% | 中风险 |
| NDCG@5 | > 8% | 中风险 |
| 平均检索耗时 | > 20% | 中风险 |
---
## 三、完整代码实现
```python
from uuid import UUID
from typing import List, Dict, Optional
from sqlalchemy import desc
from backend.schemas.rag_eval.tuning_suggestion import TuningSuggestionCreate
from backend.service.rag_test.test_result_service import TestResultService
from backend.service.rag_test.test_run_service import TestRunService
from backend.service.config.config_service import ConfigService
from backend.service.prompt.prompt_service import PromptService
from backend.core.rag.validation.base_validator import BaseValidator
import time
class Layer2HistoryValidator(BaseValidator):
    """Layer2 历史对比校验器"""
    def __init__(self, db):
        super().__init__(db)
        self.result_service = TestResultService(db)
        self.test_run_service = TestRunService(db)
        self.config_service = ConfigService(db)
        self.prompt_service = PromptService(db)
        # 阈值配置
        self.thresholds = {
            "precision@1": 0.1,  # 下降超过10%标记为问题
            "recall@3": 0.08,
            "f1_score": 0.1,
            "mrr": 0.1,
            "ndcg@5": 0.08,
            "avg_retrieval_time": 0.2
        }
    async def validate(self, test_run_id: UUID) -> Dict:
        start_time = time.time()
        # 1. 获取当前测试运行数据
        current_run = await self.test_run_service.get_test_run(test_run_id)
        current_metrics = await self.result_service.get_test_metrics(test_run_id)
        current_config_version = current_run.config_version
        current_prompt_version = current_run.prompt_version
        # 2. 获取同测试集下的历史最优运行
        best_run = await self._get_best_history_run(current_run.test_set_id)
        if not best_run:
            # 无历史数据，直接返回满分
            return {
                "layer": "layer2",
                "name": "历史对比校验",
                "score": 100,
                "issues": [],
                "suggestions": [],
                "details": {
                    "has_history": False,
                    "message": "无历史测试数据，跳过对比"
                },
                "cost_time": (time.time() - start_time) * 1000
            }
        # 3. 获取历史最优的指标、配置、提示词
        best_metrics = await self.result_service.get_test_metrics(best_run.id)
        best_config_version = best_run.config_version
        best_prompt_version = best_run.prompt_version
        # 4. 对比指标差异
        issues = []
        suggestions = []
        metric_diffs = {}
        for metric, threshold in self.thresholds.items():
            current_val = current_metrics.get(metric, 0)
            best_val = best_metrics.get(metric, 0)
            if best_val == 0:
                continue
            # 计算下降率
            decline_rate = (best_val - current_val) / best_val if current_val < best_val else 0
            metric_diffs[metric] = {
                "current": current_val,
                "best": best_val,
                "decline_rate": decline_rate,
                "has_issue": decline_rate > threshold
            }
            if decline_rate > threshold:
                # 标记为问题
                issues.append({
                    "type": f"{metric}_decline",
                    "metric": metric,
                    "current": current_val,
                    "best": best_val,
                    "decline_rate": decline_rate,
                    "threshold": threshold,
                    "description": f"{metric}指标下降超过{threshold*100:.0f}%，存在回归风险"
                })
                # 生成回滚建议
                suggestions.append(await self._generate_rollback_suggestion(
                    metric, current_val, best_val, decline_rate,
                    current_config_version, best_config_version,
                    current_prompt_version, best_prompt_version,
                    test_run_id
                ))
        # 5. 对比配置变更
        config_changes = await self._compare_configs(current_config_version, best_config_version)
        # 6. 对比提示词变更
        prompt_changes = await self._compare_prompts(current_prompt_version, best_prompt_version)
        # 7. 计算得分
        score = self._calculate_score(issues)
        # 8. 返回结果
        return {
            "layer": "layer2",
            "name": "历史对比校验",
            "score": score,
            "issues": issues,
            "suggestions": suggestions,
            "details": {
                "has_history": True,
                "best_run_id": str(best_run.id),
                "best_run_time": best_run.created_at.isoformat(),
                "best_score": best_run.overall_score,
                "current_score": current_run.overall_score,
                "metric_diffs": metric_diffs,
                "config_changes": config_changes,
                "prompt_changes": prompt_changes
            },
            "cost_time": (time.time() - start_time) * 1000
        }
    async def _get_best_history_run(self, test_set_id: UUID) -> Optional[object]:
        """获取同测试集下的历史最优运行（按综合得分最高）"""
        return self.db.query(
            self.test_run_service.model
        ).filter(
            self.test_run_service.model.test_set_id == test_set_id,
            self.test_run_service.model.status == "completed"
        ).order_by(
            desc(self.test_run_service.model.overall_score)
        ).first()
    async def _compare_configs(self, current_version: str, best_version: str) -> List[Dict]:
        """对比两个配置版本的差异"""
        if current_version == best_version:
            return []
        current_config = await self.config_service.get_config_by_version(current_version)
        best_config = await self.config_service.get_config_by_version(best_version)
        # 对比差异
        changes = []
        all_keys = set(current_config.keys()).union(set(best_config.keys()))
        for key in all_keys:
            current_val = current_config.get(key)
            best_val = best_config.get(key)
            if current_val != best_val:
                changes.append({
                    "key": key,
                    "current_value": current_val,
                    "best_value": best_val,
                    "change_type": "modified" if key in current_config and key in best_config else "added" if key in current_config else "removed"
                })
        return changes
    async def _compare_prompts(self, current_version: str, best_version: str) -> List[Dict]:
        """对比两个提示词版本的差异"""
        if current_version == best_version:
            return []
        current_prompts = await self.prompt_service.get_prompts_by_version(current_version)
        best_prompts = await self.prompt_service.get_prompts_by_version(best_version)
        changes = []
        all_keys = set(current_prompts.keys()).union(set(best_prompts.keys()))
        for key in all_keys:
            current_val = current_prompts.get(key, {}).get("content")
            best_val = best_prompts.get(key, {}).get("content")
            if current_val != best_val:
                changes.append({
                    "key": key,
                    "current_value": current_val,
                    "best_value": best_val,
                    "change_type": "modified" if key in current_prompts and key in best_prompts else "added" if key in current_prompts else "removed"
                })
        return changes
    async def _generate_rollback_suggestion(
        self, metric: str, current_val: float, best_val: float, decline_rate: float,
        current_config_version: str, best_config_version: str,
        current_prompt_version: str, best_prompt_version: str,
        test_run_id: UUID
    ) -> TuningSuggestionCreate:
        """生成回滚建议"""
        level = "high" if decline_rate > 0.1 else "medium"
        change_info = []
        suggested_value = {}
        # 判断是配置变更还是提示词变更导致的
        if current_config_version != best_config_version:
            change_info.append(f"配置版本从{best_config_version}变更为{current_config_version}")
            suggested_value["config_version"] = best_config_version
        if current_prompt_version != best_prompt_version:
            change_info.append(f"提示词版本从{best_prompt_version}变更为{current_prompt_version}")
            suggested_value["prompt_version"] = best_prompt_version
        if not change_info:
            change_info.append("未检测到配置或提示词变更，可能是数据变化导致")
        return TuningSuggestionCreate(
            suggestion_id=f"layer2-rollback-{metric}-{test_run_id}",
            type="config" if "config_version" in suggested_value else "prompt",
            level=level,
            current_value={
                metric: current_val,
                "current_config_version": current_config_version,
                "current_prompt_version": current_prompt_version
            },
            suggested_value=suggested_value,
            reason=f"{metric}指标从{best_val:.2f}下降到{current_val:.2f}，下降率{decline_rate*100:.1f}%，超过阈值。变更记录：{';'.join(change_info)}。",
            impact_analysis={
                "scope": "全链路" if len(suggested_value) > 1 else "配置" if "config_version" in suggested_value else "提示词",
                "expected_improvement": f"{metric}预计恢复到历史最优水平，提升{decline_rate*100:.1f}%",
                "risk": "低，回滚到已验证的历史版本"
            }
        )
    def _calculate_score(self, issues: List[Dict]) -> float:
        """计算Layer2得分"""
        base_score = 100
        for issue in issues:
            decline_rate = issue.get("decline_rate", 0)
            if decline_rate > 0.2:
                base_score -= 30
            elif decline_rate > 0.1:
                base_score -=20
            else:
                base_score -=10
        return max(0, min(100, base_score))
```
---
## 四、依赖接口扩展
需要在现有Service中新增两个方法（无侵入扩展，不修改现有逻辑）：
### 1. ConfigService 新增获取指定版本配置方法
**文件路径**：`backend/src/service/config/config_service.py`
```python
async def get_config_by_version(self, version: str) -> Dict:
    """获取指定版本的配置快照"""
    version_record = self.db.query(ConfigVersion).filter(ConfigVersion.version == version).first()
    if not version_record:
        return {}
    return version_record.config_snapshot
```
### 2. PromptService 新增获取指定版本提示词方法
**文件路径**：`backend/src/service/prompt/prompt_service.py`
```python
async def get_prompts_by_version(self, version: str) -> Dict:
    """获取指定版本的提示词快照"""
    version_record = self.db.query(PromptVersion).filter(PromptVersion.version == version).first()
    if not version_record:
        return {}
    return version_record.prompt_snapshot
```
---
## 五、集成点
在校验引擎调度器中添加Layer2校验器：
**文件路径**：`backend/src/core/rag/validation/engine.py`
```python
from .layer2_history import Layer2HistoryValidator
class ValidationEngine:
    def __init__(self):
        self.db = next(get_db())
        self.validators = [
            Layer1RulesValidator(self.db),
            Layer2HistoryValidator(self.db), # 新增Layer2
            # 其他层...
        ]
```
---
## 六、前端展示说明
Layer2校验结果在报告页面展示以下内容：
1. 历史最优版本对比卡片，显示指标升降趋势
2. 配置/提示词变更Diff对比，高亮差异点
3. 回滚建议卡片，支持一键回滚到历史最优版本
---
**验收标准**：
✅ 无历史数据时返回满分，不影响整体报告
✅ 能正确识别指标下降超过阈值的回归问题
✅ 能准确对比配置和提示词的版本差异
✅ 生成的回滚建议包含完整的变更原因和影响分析
✅ 得分计算逻辑合理，回归越严重得分越低
✅ 新增的Service方法无侵入，不影响现有功能
