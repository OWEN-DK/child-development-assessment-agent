# 04 - Layer 3: LLM 诊断 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 04 - Layer 3: LLM 诊断

**Architecture:** 参考下方原文档的实现方案和数据模型

**Tech Stack:** Python, FastAPI, TypeScript, React

---

### Task 1: 实现核心逻辑与测试

**Files:**
- Create: `backend/src/core/validation/layers/layer3_llm.py`
- Modify: `backend/src/core/llm/factory.py`
- Test: `backend/tests/test_placeholder.py`

- [ ] **Step 1: Write the failing test**
  - 根据下方的验收标准和测试方案，编写对应的测试用例
- [ ] **Step 2: Run test to verify it fails**
  - 执行测试并确保看到预期失败信息 (Red)
- [ ] **Step 3: Write minimal implementation**
  - 根据下方"实现方案"中的步骤，编写或修改业务代码
- [ ] **Step 4: Run test to verify it passes**
  - 执行测试确保通过 (Green)
- [ ] **Step 5: Commit**
  - `git add` 相关文件并提交 commit

---

## 原始需求与设计细节 (供参考)

> **需求来源**: spec 文档 `05-validation-layers.md` 中 `5.3 Layer 3: LLM 诊断` 节
> **所属 Phase**: Phase 4

## 需求定义

对 Bad Case 进行语义分析，给出针对性深度建议。7 种失败类型 + 8 种根因，降级策略。

## 验收标准

- [ ] Bad Case ≥ 5 时触发，> 50 时分层抽样至 50 条
- [ ] 7 种失败类型分类正确
- [ ] 8 种根因分类正确
- [ ] 降级策略正确执行（超时重试/Rate Limit/json-repair）
- [ ] API 完全不可用时跳过，前端展示"LLM 服务不可用"

## 涉及文件

| 文件路径 | 操作 | 说明 |
|---------|------|------|
| `backend/src/core/validation/layers/layer3_llm.py` | 新增 | Layer 3 LLM 诊断实现 |
| `backend/src/core/llm/factory.py` | 修改 | 复用 LLM 工厂获取模型 |

## 实现方案

### 后端实现

```python
# backend/src/core/validation/layers/layer3_llm.py
import json
import logging
import asyncio
from typing import Any

from json_repair import repair_json
from src.core.llm.factory import get_llm

logger = logging.getLogger(__name__)

FAILURE_TYPES = [
    "未召回", "排序倒置", "误杀", "语义不匹配",
    "部分召回", "年龄过滤排除", "重排序误判",
]

ROOT_CAUSES = [
    "Embedding 质量问题", "分块不合理", "关键词缺失", "同义词未覆盖",
    "年龄过滤过严", "重排序模型不匹配", "查询路由错误", "分块粒度不当",
]

LLM_DIAGNOSIS_PROMPT = """
你是一位 RAG 检索系统诊断专家。请分析以下 Bad Case，给出失败类型、根因和建议措施。

当前配置摘要：
{config_summary}

Bad Case 列表（共 {count} 条）：
{bad_cases}

请以 JSON 数组格式返回，每条包含：
- query: 查询文本
- failure_type: 失败类型（{failure_types}）
- root_cause: 根因（{root_causes}）
- confidence: 置信度 (0-1)
- suggestion: 建议措施
- priority: 优先级 (HIGH/MEDIUM/LOW)

只输出 JSON，不要其他内容。
"""

class Layer3LLMDiagnosis:
    """Layer 3: LLM 诊断"""
    
    def __init__(self, db, test_run):
        self.db = db
        self.test_run = test_run
    
    async def execute(self) -> dict:
        """执行 LLM 诊断"""
        bad_cases = await self._get_bad_cases()
        
        if len(bad_cases) < 5:
            return {"status": "skipped", "data": {"reason": "Bad Case 数量不足 5 条"}}
        
        # 抽样策略
        if len(bad_cases) > 50:
            bad_cases = self._stratified_sample(bad_cases, 50)
        
        config_summary = json.dumps(self.test_run.config_snapshot or {}, ensure_ascii=False)[:500]
        bad_cases_text = json.dumps(bad_cases, ensure_ascii=False)
        
        prompt = LLM_DIAGNOSIS_PROMPT.format(
            config_summary=config_summary,
            count=len(bad_cases),
            bad_cases=bad_cases_text,
            failure_types="/".join(FAILURE_TYPES),
            root_causes="/".join(ROOT_CAUSES),
        )
        
        try:
            response = await self._call_llm_with_retry(prompt, max_retries=2)
            diagnosis = self._parse_llm_response(response)
            return self._summarize(diagnosis)
        except Exception as e:
            logger.error(f"Layer 3 LLM 诊断失败: {e}")
            return {"status": "degraded", "data": {"reason": "LLM 服务不可用，已跳过深度诊断"}}
    
    async def _get_bad_cases(self) -> list:
        """获取 Bad Case 列表 (hit_at_5 = 0)
        
        通过 session_factory 创建独立 session 查询 TestRunResult 表，
        关联 TestCase 获取 expected_document_ids。
        """
        from src.models.rag_eval.test_run_result import RagEvalTestRunResult
        from src.models.rag_eval.test_case import RagEvalTestCase
        
        async with self.session_factory() as session:
            # 查询该 run 下所有 hit_at_5 = 0 的结果
            results = await session.execute(
                select(RagEvalTestRunResult)
                .where(RagEvalTestRunResult.run_id == self.test_run.id)
                .where(RagEvalTestRunResult.hit_at_5 == 0)
            )
            run_results = results.scalars().all()
            
            bad_cases = []
            for rr in run_results:
                # 关联查询 TestCase 获取期望文档 ID
                tc_result = await session.execute(
                    select(RagEvalTestCase).where(RagEvalTestCase.id == rr.case_id)
                )
                tc = tc_result.scalar_one_or_none()
                
                bad_cases.append({
                    "query": rr.query or "",
                    "expected_docs": tc.expected_document_ids if tc else [],
                    "actual_docs": rr.matched_doc_ids or [],
                    "matched_scores": rr.matched_doc_scores or [],
                    "hit_at_1": rr.hit_at_1,
                    "hit_at_3": rr.hit_at_3,
                    "hit_at_5": rr.hit_at_5,
                    "domain": tc.domain.value if tc and tc.domain else "unknown",
                    "age_months": tc.age_months if tc else 0,
                })
            
            return bad_cases
    
    def _stratified_sample(self, bad_cases: list, target: int) -> list:
        """按 domain × age_group 分层抽样（Bad Case 尚无 failure_type）"""
        from collections import defaultdict
        by_stratum = defaultdict(list)
        for bc in bad_cases:
            domain = bc.get("domain", "unknown")
            age_group = bc.get("age_group", "unknown")
            by_stratum[(domain, age_group)].append(bc)

        sampled = []
        per_stratum = max(3, target // len(by_stratum))
        for cases in by_stratum.values():
            sampled.extend(cases[:per_stratum])

        return sampled[:target]
    
    async def _call_llm_with_retry(self, prompt: str, max_retries: int = 2) -> str:
        """带重试的 LLM 调用"""
        llm = get_llm()
        last_error = None
        
        for attempt in range(max_retries):
            try:
                response = await asyncio.wait_for(llm.ainvoke(prompt), timeout=120)
                return response.content if hasattr(response, "content") else str(response)
            except asyncio.TimeoutError:
                last_error = "超时"
                if attempt < max_retries - 1:
                    await asyncio.sleep(2)
            except Exception as e:
                if "429" in str(e):
                    last_error = "Rate Limit"
                    await asyncio.sleep(5)
                else:
                    raise
        
        raise Exception(f"LLM 调用失败 ({last_error})")
    
    def _parse_llm_response(self, response: str) -> list:
        """解析 LLM 响应，使用 json-repair 修复"""
        try:
            repaired = repair_json(response)
            return json.loads(repaired) if isinstance(repaired, str) else repaired
        except Exception:
            return []
    
    def _summarize(self, diagnosis: list) -> dict:
        """汇总统计"""
        failure_type_counts = {}
        root_cause_counts = {}
        
        for d in diagnosis:
            ft = d.get("failure_type", "unknown")
            rc = d.get("root_cause", "unknown")
            failure_type_counts[ft] = failure_type_counts.get(ft, 0) + 1
            root_cause_counts[rc] = root_cause_counts.get(rc, 0) + 1
        
        return {
            "status": "completed",
            "data": {
                "diagnosis": diagnosis,
                "summary": {
                    "most_common_failure_type": max(failure_type_counts, key=failure_type_counts.get) if failure_type_counts else None,
                    "most_common_root_cause": max(root_cause_counts, key=root_cause_counts.get) if root_cause_counts else None,
                    "total_analyzed": len(diagnosis),
                },
            },
        }
```

## 测试方案

```python
@pytest.mark.asyncio
async def test_bad_case_below_threshold():
    """Bad Case < 5 时跳过"""
    ...

@pytest.mark.asyncio
async def test_stratified_sampling():
    """分层抽样正确"""
    ...

@pytest.mark.asyncio
async def test_llm_degradation():
    """LLM 不可用时降级"""
    ...
```

## 注意事项

- 使用 `json-repair` 库作为后备（CLAUDE.md 要求）
- 超时上限 120s（含重试）
- Bad Case 定义：`hit_at_5 = 0` 的用例（未在前 5 个结果中命中任何期望文档）
- Bad Case 阈值配置：通过 `rag_bad_case_llm_threshold` 配置项控制（默认 5），从配置中心读取
- 抽样策略：按 `domain × age_group` 分层抽样，保证各领域/年龄段代表
