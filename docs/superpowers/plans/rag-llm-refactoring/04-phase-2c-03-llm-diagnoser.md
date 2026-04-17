# Phase 2C.3: LLM 诊断

> **前置文档:** [Overview](./04-phase-2c-00-overview.md)
> **状态:** ⏳ 完全待实现
> **预计工期:** 1 人天

## 目标

实现 LLM-as-Judge 深度诊断模块，对 Bad Case 进行语义分析，找出共性模式和根因，给出针对性深度建议。

---

### Task 2C.3.1: 诊断 Prompt 设计

**Files:**
- 通过 PromptManager 管理 (MySQL `prompt_versions` 表)

- [ ] **Step 1: 创建诊断 Prompt 初始版本**

> **⚠️ Prompt 存储约束**: 诊断 Prompt 必须通过 `PromptManager` 存入 MySQL，禁止硬编码在代码中。

**Prompt Key**: `rag_tuning_diagnosis`

**系统指令**:
```
你是一个 RAG 系统诊断专家。请分析以下失败的测试用例 (Bad Case)，找出共性根因，
并给出具体、可操作的优化建议。

分析维度：
1. 关键词覆盖：Bad Case 中的关键词是否出现在检索结果中
2. 领域集中度：Bad Case 集中在哪些发展领域
3. 查询复杂度：失败案例的查询类型分布
4. 年龄分布：失败案例的年龄段分布
5. 内容相关性：检索结果与查询的语义相关度

要求：
- 建议必须具体可操作（如"提高 bm25_top_k 从 10 到 15"，而非"优化检索"）
- 区分"参数调整"、"功能开关"、"内容补充"三类建议
- 每条建议标注预期效果和置信度
- 输出必须为合法 JSON，格式如下：
{
  "summary": "总体诊断总结",
  "findings": [
    {"category": "domain_concentration", "description": "...", "confidence": 0.85}
  ],
  "recommendations": [
    {
      "param": "rag_hybrid_bm25_top_k",
      "action": "increase",
      "suggested_value": 15,
      "expected_effect": "...",
      "priority": "high"
    }
  ]
}
```

- [ ] **Step 2: 通过 PromptManager 写入**

```python
# 首次部署时执行
await prompt_manager.create_prompt_version(
    prompt_key="rag_tuning_diagnosis",
    content="[上述系统指令内容]",
    description="RAG 调参 LLM 深度诊断 Prompt",
    variables=["bad_cases", "summary_stats"],
)
```

---

### Task 2C.3.2: Bad Case 聚合与 LLM 调用

**Files:**
- Create: `src/core/tuning/llm_diagnoser.py`
- Test: `tests/unit/tuning/test_llm_diagnoser.py`

- [ ] **Step 1: 扩展 Pydantic 模型**

```python
# src/model/tuning.py (追加)
from typing import Any, Dict, List, Optional, Tuple
from pydantic import BaseModel

class LLMFinding(BaseModel):
    """LLM 诊断发现"""
    category: str                      # 分类
    description: str                   # 发现描述
    confidence: float                  # 置信度 0-1

class LLMDiagnosis(BaseModel):
    """LLM 深度诊断结果"""
    summary: str                       # 诊断总结
    findings: List[LLMFinding]         # 发现列表
    recommendations: List["TuningSuggestion"]  # 建议列表
```

- [ ] **Step 2: 编写测试用例**

```python
async def test_diagnose_returns_none_when_bad_cases_less_than_3(mock_test_run_result_repo, mock_test_case_repo, mock_prompt_manager, mock_llm_factory):
    """Bad Case < 3 时不应触发 LLM 调用"""
    from src.core.tuning.llm_diagnoser import LLMDiagnoser
    
    # Mock 仅 2 个 Bad Case
    mock_test_run_result_repo.get_failed_results = AsyncMock(return_value=[
        MagicMock(test_case_id="tc_1"), MagicMock(test_case_id="tc_2")
    ])
    
    diagnoser = LLMDiagnoser(mock_test_run_result_repo, mock_test_case_repo, mock_prompt_manager, mock_llm_factory)
    result = await diagnoser.diagnose("test_run_id")
    
    assert result is None
    mock_llm_factory.create.assert_not_called()  # 确认未调用 LLM

async def test_diagnose_calls_llm_when_bad_cases_ge_3(mock_test_run_result_repo, mock_test_case_repo, mock_prompt_manager, mock_llm_factory):
    """Bad Case ≥ 3 时应触发 LLM 调用"""
    from src.core.tuning.llm_diagnoser import LLMDiagnoser
    
    # Mock 5 个 Bad Case
    mock_test_run_result_repo.get_failed_results = AsyncMock(return_value=[
        MagicMock(test_case_id=f"tc_{i}", query=f"query_{i}", recall=0.0, actual_count=2) for i in range(5)
    ])
    mock_test_case_repo.get_by_id = AsyncMock(MagicMock(
        domain=MagicMock(value="sensory_integration"), age=2.0,
        expected_keywords=["keyword1"],
    ))
    
    diagnoser = LLMDiagnoser(mock_test_run_result_repo, mock_test_case_repo, mock_prompt_manager, mock_llm_factory)
    result = await diagnoser.diagnose("test_run_id")
    
    assert result is not None
    mock_llm_factory.create.assert_called_once()  # 确认调用了 LLM
    assert isinstance(result, LLMDiagnosis)

async def test_aggregate_bad_cases_computes_domain_distribution():
    """Bad Case 聚合应正确计算领域分布"""
    from src.core.tuning.llm_diagnoser import LLMDiagnoser
    
    bad_cases = [
        {"domain": "sensory_integration", "age": 2.0},
        {"domain": "sensory_integration", "age": 3.0},
        {"domain": "gross_motor", "age": 5.0},
    ]
    
    diagnoser = LLMDiagnoser(None, None, None, None)
    stats = diagnoser._aggregate_bad_cases(bad_cases)
    
    assert stats["domain_distribution"]["sensory_integration"] == 2
    assert stats["domain_distribution"]["gross_motor"] == 1
```

- [ ] **Step 3: 运行测试验证失败**
Run: `pytest tests/unit/tuning/test_llm_diagnoser.py -v`
Expected: FAIL - 模块不存在

- [ ] **Step 4: 实现 LLM 诊断器**

```python
# src/core/tuning/llm_diagnoser.py
"""LLM 诊断器：Bad Case 语义深度分析"""
from typing import Any, Dict, List, Optional
from json_repair import repair_json
import json
from src.model.tuning import LLMDiagnosis, TuningSuggestion, LLMFinding
from src.core.prompt.manager import prompt_manager
from src.core.llm.factory import LLMServiceFactory
from src.utils.logger import logger


# Bad Case 触发阈值
MIN_BAD_CASES_FOR_DIAGNOSIS = 3


class LLMDiagnoser:
    """LLM 诊断器：对失败测试用例进行语义分析"""
    
    def __init__(
        self,
        test_run_result_repo=None,
        test_case_repo=None,
        prompt_mgr=None,
        llm_factory=None,
    ):
        """初始化 LLM 诊断器"""
        self.test_run_result_repo = test_run_result_repo
        self.test_case_repo = test_case_repo
        self.prompt_mgr = prompt_mgr or prompt_manager
        self.llm_factory = llm_factory or LLMServiceFactory
    
    async def diagnose(self, run_id: str) -> Optional[LLMDiagnosis]:
        """对指定测试运行的 Bad Case 进行诊断"""
        # 获取失败的测试结果
        failed_results = await self.test_run_result_repo.get_failed_results(run_id)
        
        if len(failed_results) < MIN_BAD_CASES_FOR_DIAGNOSIS:
            logger.info(f"Bad Case 数量 {len(failed_results)} < {MIN_BAD_CASES_FOR_DIAGNOSIS}，跳过 LLM 诊断")
            return None
        
        # 聚合 Bad Case 统计信息
        bad_cases_data = await self._collect_bad_cases_data(failed_results)
        summary_stats = self._aggregate_bad_cases(bad_cases_data)
        
        # 获取诊断 Prompt
        prompt_content = await self.prompt_mgr.get_prompt("rag_tuning_diagnosis")
        
        # 构建 LLM 输入
        llm_input = {
            "bad_cases": bad_cases_data,
            "summary_stats": summary_stats,
        }
        
        # 调用 LLM
        llm = self.llm_factory.create(scene="report_generation")
        response = await llm.ainvoke(
            messages=[
                {"role": "system", "content": prompt_content},
                {"role": "user", "content": json.dumps(llm_input, ensure_ascii=False)},
            ]
        )
        
        # 解析输出
        raw_output = response.content if hasattr(response, "content") else str(response)
        diagnosis = self._parse_llm_output(raw_output)
        
        if diagnosis:
            logger.info(f"LLM 诊断完成: {len(diagnosis.findings)} 个发现, {len(diagnosis.recommendations)} 条建议")
        
        return diagnosis
    
    async def _collect_bad_cases_data(self, failed_results: List[Any]) -> List[Dict[str, Any]]:
        """收集 Bad Case 详细数据"""
        bad_cases = []
        for result in failed_results:
            # 关联 TestCase 获取领域/年龄/关键词信息
            test_case = await self.test_case_repo.get_by_id(result.test_case_id)
            if not test_case:
                continue
            
            # 从检索结果中提取实际关键词和相关度
            actual_keywords = self._extract_keywords_from_results(result)
            avg_relevance = self._compute_avg_relevance(result)
            
            bad_cases.append({
                "query": result.query,
                "domain": test_case.domain.value if hasattr(test_case.domain, "value") else str(test_case.domain),
                "age": float(test_case.age),
                "expected_keywords": test_case.expected_keywords or [],
                "actual_keywords": actual_keywords,
                "recall": result.recall or 0.0,
                "retrieved_docs_count": result.actual_count or 0,
                "avg_relevance": avg_relevance,
            })
        
        return bad_cases
    
    def _extract_keywords_from_results(self, result: Any) -> List[str]:
        """从检索结果中提取实际出现的关键词"""
        if not hasattr(result, "retrieved_docs") or not result.retrieved_docs:
            return []
        
        # 合并所有检索结果的文本
        all_text = "".join(doc.content for doc in result.retrieved_docs if hasattr(doc, "content"))
        
        # 使用 jieba 分词（支持中英文混合）
        try:
            import jieba
            words = jieba.lcut(all_text)
        except ImportError:
            # 降级方案：按空格分割（仅支持英文）
            words = all_text.split()
        
        # 过滤停用词和短词
        from collections import Counter
        stopwords = {"的", "了", "是", "在", "和", "与", "或", "a", "the", "is", "in", " ", "\n"}
        keywords = [w.strip() for w in words if len(w.strip()) > 1 and w.strip() not in stopwords]
        return [word for word, _ in Counter(keywords).most_common(20)]
    
    def _compute_avg_relevance(self, result: Any) -> float:
        """计算检索结果的平均相关度分数"""
        if not hasattr(result, "retrieved_docs") or not result.retrieved_docs:
            return 0.0
        
        scores = [doc.score for doc in result.retrieved_docs if hasattr(doc, "score") and doc.score is not None]
        return sum(scores) / len(scores) if scores else 0.0
    
    def _aggregate_bad_cases(self, bad_cases: List[Dict[str, Any]]) -> Dict[str, Any]:
        """聚合 Bad Case 统计信息"""
        if not bad_cases:
            return {"total_bad_cases": 0}
        
        # 领域分布
        domain_distribution = {}
        for case in bad_cases:
            domain = case.get("domain", "unknown")
            domain_distribution[domain] = domain_distribution.get(domain, 0) + 1
        
        # 年龄分布
        age_distribution = {}
        for case in bad_cases:
            age = case.get("age", 0)
            if age < 2:
                bucket = "0-2"
            elif age < 4:
                bucket = "2-4"
            elif age < 6:
                bucket = "4-6"
            else:
                bucket = "6+"
            age_distribution[bucket] = age_distribution.get(bucket, 0) + 1
        
        # 平均检索相关度
        avg_relevance = sum(c.get("avg_relevance", 0) for c in bad_cases) / len(bad_cases)
        
        return {
            "total_bad_cases": len(bad_cases),
            "domain_distribution": domain_distribution,
            "age_distribution": age_distribution,
            "avg_relevance": round(avg_relevance, 4),
        }
    
    def _parse_llm_output(self, raw_output: str) -> Optional[LLMDiagnosis]:
        """解析 LLM 输出，使用 json-repair 修复格式问题"""
        try:
            repaired = repair_json(raw_output)
            parsed = json.loads(repaired)
            
            # 将 recommendations 转换为 TuningSuggestion 列表
            recommendations = []
            for idx, rec in enumerate(parsed.get("recommendations", [])):
                recommendations.append(TuningSuggestion(
                    id=f"llm_diag_{idx}_{rec.get('param', '')}",
                    param_name=rec.get("param", ""),
                    current_value=None,
                    suggested_value=rec.get("suggested_value"),
                    action=rec.get("action", ""),
                    reason="",
                    expected_effect=rec.get("expected_effect", ""),
                    priority=rec.get("priority", "medium"),
                    source="llm",
                ))
            
            # 将 findings 转换为 LLMFinding 列表
            findings = []
            for f in parsed.get("findings", []):
                findings.append(LLMFinding(
                    category=f.get("category", ""),
                    description=f.get("description", ""),
                    confidence=f.get("confidence", 0.0),
                ))
            
            return LLMDiagnosis(
                summary=parsed.get("summary", ""),
                findings=findings,
                recommendations=recommendations,
            )
        except Exception as e:
            logger.error(f"LLM 输出解析失败: {e}")
            return None
```

- [ ] **Step 5: 运行测试验证通过**
Run: `pytest tests/unit/tuning/test_llm_diagnoser.py -v`
Expected: PASS

---

**上一阶段:** [历史对比分析](./04-phase-2c-02-history-analyzer.md)  
**下一阶段:** [统一引擎 + API](./04-phase-2c-04-engine-api.md)
