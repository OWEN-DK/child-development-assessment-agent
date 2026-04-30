"""查询分解器 — 将复杂查询拆解为多个聚焦子查询"""

import json
import re
from dataclasses import dataclass
from typing import List, Optional

from src.config import settings
from src.core.llm.base import LLMRequest
from src.core.llm.factory import LLMFramework, LLMServiceFactoryCompat
from src.schemas.llm import LLMMessage
from src.utils.logger import logger


@dataclass
class SubQuery:
    """子查询"""

    text: str
    focus: str = ""


class QueryDecomposer:
    """将复杂查询分解为 2-4 个聚焦子查询"""

    def __init__(
        self,
        llm_enabled: bool = True,
        max_sub_queries: int = 4,
        model_name: Optional[str] = None,
    ):
        self.llm_enabled = llm_enabled
        self.max_sub_queries = max_sub_queries
        self.model_name = model_name or getattr(
            settings, "rag_query_decomposition_model", "qwen-turbo"
        )

    async def decompose(self, query: str) -> List[SubQuery]:
        """
        分解复杂查询

        Args:
            query: 原始复杂查询

        Returns:
            子查询列表。失败时返回只包含原始查询的列表（兜底不阻塞检索）。
        """
        if not self.llm_enabled:
            return self._rule_decompose(query)

        try:
            return await self._llm_decompose(query)
        except Exception as e:
            logger.warning(f"查询分解失败，回退到规则分解: {e}")
            return self._rule_decompose(query)

    async def _llm_decompose(self, query: str) -> List[SubQuery]:
        """LLM 拆解复杂查询"""
        prompt = f"""你是一个查询拆解专家。将用户复杂查询拆解为 2-4 个简单子查询，每个子查询聚焦于单一概念或知识点。

规则：
1. 去除"分析""评估""对比"等指令词，提炼核心检索概念
2. 去除人名、特定个体名称（如"小明"），保留通用术语
3. 每个子查询 ≤ 20 字，独立可检索
4. 子查询间不重复，覆盖原始查询的所有关键概念

示例：
复杂查询：分析小明在前庭觉、精细动作、社交三个维度的发展情况
→ 子查询：
  - "前庭觉训练方法"
  - "精细动作发展评估标准"
  - "儿童社交能力培养"

复杂查询：对比感觉统合训练和注意力训练的效果差异
→ 子查询：
  - "感觉统合训练效果"
  - "注意力训练效果"

查询："{query}"

只返回 JSON 数组，不要其他文本：
[{{"text": "子查询1", "focus": "聚焦概念1"}}, ...]"""

        llm = LLMServiceFactoryCompat.create(
            framework=LLMFramework.LLAMAINDEX,
            model_name=self.model_name,
            scenario="query_decomposition",
            temperature=0.2,
        )

        response = await llm.chat(
            LLMRequest(
                messages=[
                    LLMMessage(
                        role="system", content="你是儿童发展领域的查询拆解专家。"
                    ),
                    LLMMessage(role="user", content=prompt),
                ],
                model_name=self.model_name,
                temperature=0.2,
                max_tokens=256,
                scenario="query_decomposition",
            )
        )

        json_match = re.search(r"\[.*\]", response.content, re.DOTALL)
        if not json_match:
            raise ValueError(f"LLM 返回非 JSON 数组: {response.content[:100]}")

        data = json.loads(json_match.group())
        sub_queries = []
        for item in data[: self.max_sub_queries]:
            sub_queries.append(
                SubQuery(
                    text=item.get("text", "").strip(),
                    focus=item.get("focus", "").strip(),
                )
            )

        if not sub_queries:
            raise ValueError("拆解结果为空")

        logger.info(f"查询拆解: '{query[:50]}' → {[sq.text for sq in sub_queries]}")
        return sub_queries

    def _rule_decompose(self, query: str) -> List[SubQuery]:
        """规则兜底：按中文逗号/顿号/分号/和切分"""
        parts = re.split(r"[，、；和与及,;]", query)
        parts = [p.strip() for p in parts if len(p.strip()) >= 3]
        if len(parts) <= 1:
            return [SubQuery(text=query, focus="原始查询")]
        return [SubQuery(text=p, focus=p[:10]) for p in parts[: self.max_sub_queries]]
