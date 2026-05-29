"""矛盾审计节点：检测跨书籍的观点冲突。

在 generate_s4_citations → conclusion 之间运行。
从 S2/S3 structured_data 提取带 source_books 的声明，
使用 LLM 语义对比检测矛盾，结果注入 S5 结论。
"""

import json
import logging
from typing import Any, Dict, List, Literal

from pydantic import BaseModel, Field

from src.core.knowledge_qa.nodes.base import _invoke_llm_structured
from src.schemas.knowledge_qa import KnowledgeQAState, push_progress

logger = logging.getLogger(__name__)

# ── LLM 输出 Schema ──


class ContradictionItem(BaseModel):
    """单条矛盾发现"""

    topic: str = Field(..., description="矛盾主题")
    view_a: str = Field(..., description="观点 A 及其来源书籍")
    view_b: str = Field(..., description="观点 B 及其来源书籍")
    resolution: str = Field(
        default="",
        description="调和建议或选择理由",
    )
    severity: Literal["minor", "moderate", "critical"] = "moderate"


class ContradictionAuditResponse(BaseModel):
    contradictions: List[ContradictionItem] = Field(default_factory=list)


# ── System Prompt ──

CONTRADICTION_AUDIT_SYSTEM = """你是一个跨书籍观点一致性审计专家。你的任务是：

1. 接收不同书籍对同一主题的观点声明
2. 判断是否存在实质性矛盾（不仅仅是措辞差异）
3. 如果存在矛盾，说明双方观点并提供调和建议

判断标准：
- **关键矛盾 (critical)**：两本书对同一问题给出相反的建议（如 A 说"必须运动"，B 说"禁止运动"）
- **中度矛盾 (moderate)**：侧重点明显不同，可能导致用户困惑（如 A 强调强度，B 强调频率）
- **轻微差异 (minor)**：同一观点不同表述，本质一致

输出要求：
- 只报告实质性矛盾，不报告措辞差异
- 每条矛盾必须准确标注来源书籍
- resolution 应给出调和建议，帮助用户做出选择"""


# ── 核心函数 ──


def _extract_sourced_claims(state: KnowledgeQAState) -> List[Dict]:
    """从 S2/S3 structured_data 提取带 source_books 的声明。

    只提取至少有 1 个 source_book 的条目——否则无法判断矛盾。
    """
    claims: List[Dict] = []

    # S2: problems
    s2 = state.sections.get(2)
    if s2 and s2.structured_data:
        for p in s2.structured_data.get("problems") or []:
            source_books = p.get("source_books", [])
            if source_books:
                claims.append({
                    "section": 2,
                    "type": "问题识别",
                    "topic": p.get("name") or p.get("description", ""),
                    "detail": p.get("description", ""),
                    "severity": p.get("severity", ""),
                    "source_books": source_books,
                })

    # S3: exercise_types
    s3 = state.sections.get(3)
    if s3 and s3.structured_data:
        for et in s3.structured_data.get("exercise_types") or []:
            source_books = et.get("source_books", [])
            if source_books:
                claims.append({
                    "section": 3,
                    "type": "运动推荐",
                    "topic": et.get("name", ""),
                    "detail": et.get("recommendation_rationale", ""),
                    "tier": et.get("tier", ""),
                    "source_books": source_books,
                })

    return claims


def _build_contradiction_prompt(
    question: str,
    claims: List[Dict],
    matched_books: List[Any],
) -> str:
    """构建矛盾审计 LLM prompt。"""
    books_summary = "\n".join(
        f"- {b.title}" + (f"（{b.author}）" if hasattr(b, "author") and b.author else "")
        for b in matched_books
    ) if matched_books else "（无书籍信息）"

    claims_text = "\n\n".join(
        f"### 声明 {i + 1}\n"
        f"- 类型: {c['type']}\n"
        f"- 主题: {c['topic']}\n"
        f"- 详情: {c.get('detail', '')}\n"
        f"- 来源书籍: {', '.join(c['source_books'])}"
        for i, c in enumerate(claims)
    )

    return (
        f"## 用户问题\n{question}\n\n"
        f"## 参考书籍\n{books_summary}\n\n"
        f"## 待审计的声明\n{claims_text}\n\n"
        f"请审计以上声明中是否存在跨书籍的观点矛盾。"
    )


async def contradiction_audit_node(state: KnowledgeQAState) -> Dict[str, Any]:
    """矛盾审计节点：检测跨书籍观点冲突。

    降级路径:
      1. claims < 2 → 返回空（无足够多来源数据审计）
      2. LLM 调用失败 → 返回空（不阻塞主流程）
    """
    await push_progress("contradiction_audit", "正在审计跨书籍观点一致性…")

    # Step 1: 提取带来源标注的声明
    claims = _extract_sourced_claims(state)

    if len(claims) < 2:
        logger.info(
            f"contradiction_audit: claims={len(claims)} < 2，跳过审计"
        )
        await push_progress(
            "contradiction_audit_done",
            "未发现足够的多来源声明，跳过矛盾审计",
        )
        return {
            "contradictions": [],
            "current_step": ["contradiction_audit_clean"],
        }

    # Step 2: LLM 审计
    prompt = _build_contradiction_prompt(
        state.question, claims, state.matched_books_detail
    )

    try:
        result = await _invoke_llm_structured(
            system_prompt=CONTRADICTION_AUDIT_SYSTEM,
            user_message=prompt,
            response_format=ContradictionAuditResponse,
            step_label="contradiction_audit",
            timeout_seconds=30,
        )
    except Exception as e:
        logger.warning(f"contradiction_audit LLM 调用失败: {e}")
        return {
            "contradictions": [],
            "current_step": ["contradiction_audit_failed"],
        }

    contradictions_list = [
        c.model_dump() for c in result.contradictions
    ]

    await push_progress(
        "contradiction_audit_done",
        f"矛盾审计完成：发现 {len(contradictions_list)} 处潜在矛盾",
    )

    return {
        "contradictions": contradictions_list,
        "current_step": ["contradiction_audit_done"],
    }
