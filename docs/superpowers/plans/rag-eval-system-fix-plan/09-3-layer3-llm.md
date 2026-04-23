# 09-3 Layer3 LLM诊断校验详细实现方案
**所属模块**：6层校验引擎
**功能**：调用大模型对Bad Case进行语义分析，识别深层问题根因，生成针对性调优建议
**文件路径**：`backend/src/core/rag/validation/layer3_llm.py`
**依赖组件**：LLMFactory、PromptManager、TestResultService、json_repair
---
## 一、核心诊断场景
| 问题类型 | 识别维度 | 建议方向 |
|----------|----------|----------|
| Query理解错误 | 意图识别错误、实体抽取错误、歧义理解 | 优化Query理解提示词、新增实体识别规则 |
| 检索内容不相关 | 检索结果和Query语义不匹配、片段内容过时 | 优化检索提示词、补充相关文档、优化向量模型 |
| 回答生成错误 | 回答幻觉、内容不完整、格式不符合要求 | 优化回答生成提示词、增加幻觉校验规则 |
| 知识缺失 | 知识库没有相关内容 | 补充相关文档到知识库 |
---
## 二、提示词模板（存储在prompt_fallback.py中，后续迁移到PromptManager）
```python
RAG_DIAGNOSTIC_PROMPT = """
你是RAG系统诊断专家，请分析以下Bad Case，找出问题根因并给出优化建议。
【测试用例信息】
Query：{query}
预期答案：{expected_answer}
实际检索到的片段：
{retrieved_chunks}
实际生成的回答：{actual_answer}
评估指标：Precision={precision}, Recall={recall}, F1={f1_score}
【诊断要求】
1. 分析问题根因，从以下分类中选择：query_understanding_error, retrieval_irrelevant, answer_generation_error, knowledge_missing, other
2. 给出详细的问题描述，说明具体哪里出错
3. 给出可落地的优化建议，精确到提示词修改、配置调整、数据补充的具体内容
4. 输出严格按照JSON格式，不要有其他多余内容，格式如下：
{
    "root_cause": "问题分类",
    "description": "详细问题描述",
    "suggestion_type": "prompt/config/data",
    "suggestion_content": {
        // 根据类型填写具体建议：prompt类型填提示词修改内容，config类型填配置调整项，data类型填需要补充的内容
    },
    "improvement_estimate": "预期提升效果",
    "risk_level": "low/medium/high"
}
"""
```
---
## 三、完整代码实现
```python
from uuid import UUID
from typing import List, Dict
import json
from json_repair import repair_json
from backend.schemas.rag_eval.tuning_suggestion import TuningSuggestionCreate
from backend.service.rag_test.test_result_service import TestResultService
from backend.core.llm.factory import LLMFactory
from backend.core.prompt.manager import PromptManager
from backend.core.rag.validation.base_validator import BaseValidator
import time
class Layer3LlmValidator(BaseValidator):
    """Layer3 LLM诊断校验器"""
    def __init__(self, db):
        super().__init__(db)
        self.result_service = TestResultService(db)
        self.llm_client = LLMFactory.get_instance()
        self.prompt_manager = PromptManager(db)
        # 诊断阈值：只诊断F1得分低于0.6的Bad Case
        self.bad_case_threshold = 0.6
        # 最大诊断数量，避免Token消耗过多
        self.max_diagnose_count = 20
    async def validate(self, test_run_id: UUID) -> Dict:
        start_time = time.time()
        # 1. 获取测试用例结果，筛选出Bad Case
        all_results = await self.result_service.get_test_results(test_run_id)
        bad_cases = [r for r in all_results if r.f1_score < self.bad_case_threshold][:self.max_diagnose_count]
        if not bad_cases:
            return {
                "layer": "layer3",
                "name": "LLM诊断校验",
                "score": 100,
                "issues": [],
                "suggestions": [],
                "details": {
                    "bad_case_count": 0,
                    "message": "无Bad Case，跳过诊断"
                },
                "cost_time": (time.time() - start_time) * 1000
            }
        # 2. 批量诊断Bad Case
        issues = []
        suggestions = []
        diagnose_results = []
        root_cause_stats = {}  # 根因统计
        for case in bad_cases:
            diagnose_result = await self._diagnose_single_case(case)
            if not diagnose_result:
                continue
            diagnose_results.append(diagnose_result)
            # 统计根因
            root_cause = diagnose_result.get("root_cause", "other")
            root_cause_stats[root_cause] = root_cause_stats.get(root_cause, 0) + 1
            # 生成问题
            issues.append({
                "type": root_cause,
                "query": case.query,
                "f1_score": case.f1_score,
                "description": diagnose_result.get("description", ""),
                "case_id": str(case.id)
            })
            # 生成调优建议
            suggestion = self._generate_suggestion(diagnose_result, case)
            if suggestion:
                suggestions.append(suggestion)
        # 3. 去重建议（相同类型的建议合并）
        suggestions = self._deduplicate_suggestions(suggestions)
        # 4. 计算得分：根据Bad Case占比和严重程度
        score = self._calculate_score(len(bad_cases), len(all_results), root_cause_stats)
        # 5. 返回结果
        return {
            "layer": "layer3",
            "name": "LLM诊断校验",
            "score": score,
            "issues": issues,
            "suggestions": suggestions,
            "details": {
                "total_case_count": len(all_results),
                "bad_case_count": len(bad_cases),
                "bad_case_rate": len(bad_cases) / len(all_results) if all_results else 0,
                "root_cause_stats": root_cause_stats,
                "diagnose_results": diagnose_results
            },
            "cost_time": (time.time() - start_time) * 1000
        }
    async def _diagnose_single_case(self, case) -> Optional[Dict]:
        """诊断单个Bad Case"""
        try:
            # 构建提示词
            retrieved_chunks_str = "\n".join([f"[{i+1}] {chunk.get('content', '')[:300]}..." for i, chunk in enumerate(case.retrieved_chunks)])
            prompt = await self.prompt_manager.get_prompt(
                "rag.diagnostic",
                variables={
                    "query": case.query,
                    "expected_answer": case.expected_answer,
                    "retrieved_chunks": retrieved_chunks_str,
                    "actual_answer": case.actual_answer,
                    "precision": case.precision,
                    "recall": case.recall,
                    "f1_score": case.f1_score
                }
            )
            # 调用大模型
            response = await self.llm_client.chat_completion([{"role": "user", "content": prompt}])
            response_content = response.choices[0].message.content
            # 修复JSON格式，处理截断或格式错误
            repaired_json = repair_json(response_content)
            return json.loads(repaired_json)
        except Exception as e:
            # 诊断失败，记录日志，不影响整体流程
            import logging
            logging.error(f"Bad case diagnose failed: {str(e)}")
            return None
    def _generate_suggestion(self, diagnose_result: Dict, case) -> Optional[TuningSuggestionCreate]:
        """根据诊断结果生成调优建议"""
        try:
            suggestion_type = diagnose_result.get("suggestion_type", "other")
            if suggestion_type not in ["prompt", "config", "data"]:
                return None
            root_cause = diagnose_result.get("root_cause", "other")
            level = "medium"
            if root_cause in ["answer_generation_error", "knowledge_missing"]:
                level = "high"
            return TuningSuggestionCreate(
                suggestion_id=f"layer3-{suggestion_type}-{root_cause}-{case.id}",
                type=suggestion_type,
                level=level,
                current_value={
                    "query": case.query,
                    "f1_score": case.f1_score,
                    "root_cause": diagnose_result.get("description", "")
                },
                suggested_value=diagnose_result.get("suggestion_content", {}),
                reason=f"Bad Case诊断：{diagnose_result.get('description', '')}，根因分类：{root_cause}。",
                impact_analysis={
                    "scope": "对应场景的回答效果",
                    "expected_improvement": diagnose_result.get("improvement_estimate", "预计提升对应场景准确率10%-30%"),
                    "risk": diagnose_result.get("risk_level", "low")
                }
            )
        except Exception as e:
            import logging
            logging.error(f"Generate suggestion failed: {str(e)}")
            return None
    def _deduplicate_suggestions(self, suggestions: List[TuningSuggestionCreate]) -> List[TuningSuggestionCreate]:
        """去重相同类型的建议，合并相似建议"""
        seen = set()
        unique_suggestions = []
        for s in suggestions:
            # 按类型+建议内容哈希去重
            key = f"{s.type}_{json.dumps(s.suggested_value, sort_keys=True)}"
            if key not in seen:
                seen.add(key)
                unique_suggestions.append(s)
        return unique_suggestions
    def _calculate_score(self, bad_case_count: int, total_count: int, root_cause_stats: Dict[str, int]) -> float:
        """计算Layer3得分"""
        if total_count == 0:
            return 100
        bad_case_rate = bad_case_count / total_count
        base_score = 100 - (bad_case_rate * 100)
        # 高优先级根因扣分
        high_risk_count = root_cause_stats.get("answer_generation_error", 0) + root_cause_stats.get("knowledge_missing", 0)
        base_score -= high_risk_count * 5
        return max(0, min(100, base_score))
```
---
## 四、依赖配置
1. 在`prompt_fallback.py`中新增`rag.diagnostic`提示词（后续迁移到PromptManager数据库）
2. LLMFactory已支持异步调用，无需修改
3. 安装`json_repair`依赖（已在`pyproject.toml`中包含）
---
## 五、集成点
在校验引擎调度器中添加Layer3校验器：
**文件路径**：`backend/src/core/rag/validation/engine.py`
```python
from .layer3_llm import Layer3LlmValidator
class ValidationEngine:
    def __init__(self):
        self.db = next(get_db())
        self.validators = [
            Layer1RulesValidator(self.db),
            Layer2HistoryValidator(self.db),
            Layer3LlmValidator(self.db), # 新增Layer3
            # 其他层...
        ]
```
---
## 六、性能优化配置
| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| max_diagnose_count | 20 | 单次测试最多诊断的Bad Case数量，避免Token消耗过多 |
| bad_case_threshold | 0.6 | F1得分低于该值才会被诊断 |
| llm_timeout | 30s | LLM调用超时时间，避免阻塞 |
---
**验收标准**：
✅ 能正确识别Bad Case的根因，分类准确
✅ 生成的建议可落地，包含具体的修改内容
✅ 自动修复JSON格式错误，兼容模型输出截断或格式问题
✅ 自动去重相似建议，避免重复推荐
✅ 得分计算逻辑合理，Bad Case越多得分越低
✅ 诊断失败不影响整体报告生成，有异常捕获机制
✅ 复用现有LLM和PromptManager组件，无重复开发
