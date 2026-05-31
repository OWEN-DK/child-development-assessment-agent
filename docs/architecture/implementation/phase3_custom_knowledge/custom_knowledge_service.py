"""自定义知识服务 — 三通道匹配引擎 + 上传解析 + 入库

放置位置: backend/src/service/custom_knowledge_service.py
"""

from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import yaml

logger = logging.getLogger(__name__)

SEMANTIC_THRESHOLD = 0.80


@dataclass
class MatchResult:
    """三通道匹配结果"""
    hit: bool = False
    matched_items: List[dict] = field(default_factory=list)  # Neo4j CustomRule 完整数据
    match_channel: str = ""  # "keyword" | "pattern" | "semantic"
    latency_ms: int = 0


class CustomKnowledgeService:
    """自定义知识服务

    职责:
    - match(): 三通道匹配引擎（keyword → pattern → semantic）
    - upload_and_parse(): 解析上传的 .md 文件
    - generate_keywords_and_patterns(): LLM 自动生成匹配条件
    - confirm_and_save(): 双写入库
    """

    def __init__(self, repo, embedding_helper=None):
        """
        Args:
            repo: CustomKnowledgeRepository 实例
            embedding_helper: EmbeddingHelper 实例（可选，语义匹配用）
        """
        self._repo = repo
        self._emb = embedding_helper

    # ════════════════════════════════════════════════════════════
    # 三通道匹配引擎
    # ════════════════════════════════════════════════════════════

    async def match(self, question: str) -> MatchResult:
        """三通道短路匹配: keyword → pattern → semantic

        命中后从 Neo4j 取完整 CustomRule + 关联实体。
        """
        start = time.monotonic()

        # ── 通道 1: 关键词精确匹配 ──
        try:
            hits = await self._repo.keyword_match(question)
            if hits:
                items = await self._enrich_batch([i.rule_id for i in hits])
                if items:
                    await self._record_hits([i.rule_id for i in hits])
                    return MatchResult(
                        hit=True, matched_items=items, match_channel="keyword",
                        latency_ms=self._ms(start),
                    )
        except Exception as e:
            logger.warning(f"keyword match error: {e}")

        # ── 通道 2: 正则模式匹配 ──
        try:
            hits = await self._repo.pattern_match(question)
            if hits:
                items = await self._enrich_batch([i.rule_id for i in hits])
                if items:
                    await self._record_hits([i.rule_id for i in hits])
                    return MatchResult(
                        hit=True, matched_items=items, match_channel="pattern",
                        latency_ms=self._ms(start),
                    )
        except Exception as e:
            logger.warning(f"pattern match error: {e}")

        # ── 通道 3: 语义向量匹配 ──
        try:
            items = await self._semantic_match(question)
            if items:
                await self._record_hits([i["rule_id"] for i in items])
                return MatchResult(
                    hit=True, matched_items=items, match_channel="semantic",
                    latency_ms=self._ms(start),
                )
        except Exception as e:
            logger.warning(f"semantic match error (degraded): {e}")

        return MatchResult(hit=False, latency_ms=self._ms(start))

    async def _semantic_match(self, question: str) -> List[dict]:
        """通道 3: cosine similarity ≥ 0.80"""
        if not self._emb:
            return []
        q_emb = await self._emb.embed_text(question)
        if not q_emb:
            return []
        items = await self._repo.get_all_enabled()
        scored = []
        for item in items:
            if not item.embedding:
                continue
            try:
                score = self._emb.cosine_similarity(q_emb, item.embedding)
                if score >= SEMANTIC_THRESHOLD:
                    enriched = await self._enrich(item.rule_id)
                    if enriched:
                        scored.append((score, enriched))
            except Exception:
                pass
        scored.sort(key=lambda x: x[0], reverse=True)
        return [i for _, i in scored]

    async def _enrich(self, rule_id: str) -> Optional[dict]:
        """从 Neo4j 取 CustomRule 完整数据 + 关联实体"""
        rule = await self._repo.get_custom_rule(rule_id)
        if not rule:
            return None
        rule["relations"] = await self._repo.get_custom_rule_relations(rule_id)
        return rule

    async def _enrich_batch(self, rule_ids: List[str]) -> List[dict]:
        results = []
        for rid in rule_ids:
            r = await self._enrich(rid)
            if r:
                results.append(r)
        return results

    async def _record_hits(self, rule_ids: List[str]) -> None:
        for rid in rule_ids:
            try:
                await self._repo.increment_hit(rid)
            except Exception:
                pass

    @staticmethod
    def _ms(start: float) -> int:
        return int((time.monotonic() - start) * 1000)

    # ════════════════════════════════════════════════════════════
    # 上传解析
    # ════════════════════════════════════════════════════════════

    async def upload_and_parse(self, files: List[Dict[str, str]]) -> List[dict]:
        """解析上传的 .md 文件，提取规则列表。

        Args:
            files: [{"filename": "xxx.md", "content": "..."}]

        Returns:
            [{"title": ..., "content": ..., "category": ..., "priority": ..., "source": ...}]
        """
        all_rules = []
        for f in files:
            content = f["content"]
            try:
                fm_match = re.match(r'^---\n(.*?)\n---\n', content, re.DOTALL)
                if not fm_match:
                    logger.warning(f"文件 {f['filename']} 缺少 YAML front matter，跳过")
                    continue
                fm = yaml.safe_load(fm_match.group(1))
                body = content[fm_match.end():]
                source = fm.get("source", "")

                # 按 ## 规则 分割
                sections = re.split(r'^## 规则\n', body, flags=re.MULTILINE)
                for sec in sections:
                    # 按 ### 分割每条规则
                    rules = re.split(r'^### ', sec, flags=re.MULTILINE)
                    for rule in rules:
                        if not rule.strip():
                            continue
                        lines = rule.strip().split('\n')
                        title = lines[0].strip()
                        props, content_lines = {}, []
                        for line in lines[1:]:
                            m = re.match(r'^\s*-\s*\*\*(.+?)\*\*:\s*(.+)$', line)
                            if m:
                                props[m.group(1).strip()] = m.group(2).strip()
                            elif line.strip() == '---':
                                continue
                            else:
                                content_lines.append(line)
                        rule_content = "\n".join(content_lines).strip()
                        if not rule_content:
                            logger.warning(f"规则 '{title}' 缺少正文，跳过")
                            continue
                        all_rules.append({
                            "title": title,
                            "content": rule_content,
                            "category": props.get("category", "general"),
                            "priority": int(props.get("priority", 100)),
                            "source": source,
                        })
            except Exception as e:
                logger.warning(f"解析文件 {f['filename']} 失败: {e}")
        return all_rules

    # ════════════════════════════════════════════════════════════
    # LLM 关键词 + 正则生成
    # ════════════════════════════════════════════════════════════

    async def generate_keywords_and_patterns(self, rules: List[dict]) -> List[dict]:
        """LLM 为每条规则自动生成 keywords + trigger_patterns"""
        from src.core.llm.factory import LLMServiceFactoryCompat
        from langchain_core.messages import HumanMessage, SystemMessage

        model = LLMServiceFactoryCompat.create_raw(model_name="qwen3.5-27b", temperature=0.2)
        system = (
            "根据以下知识内容，提取 3-8 个精确匹配关键词和 2-4 个正则触发模式。\n"
            "关键词应覆盖: 专有名词、术语缩写、常见同义表达。\n"
            "正则应覆盖: 用户的口语化变体（如 '注意力不集中' / '注意力缺陷'）。\n"
            "输出严格 JSON: {\"keywords\": [...], \"trigger_patterns\": [...]}"
        )

        results = []
        for rule in rules:
            try:
                resp = await model.ainvoke([
                    SystemMessage(content=system),
                    HumanMessage(content=f"标题: {rule['title']}\n正文: {rule['content'][:2000]}"),
                ])
                raw = resp.content.strip()
                if raw.startswith("```"):
                    raw = raw.split("\n", 1)[1].rsplit("```", 1)[0]
                data = json.loads(raw)
                rule["keywords"] = data.get("keywords", [])
                rule["trigger_patterns"] = data.get("trigger_patterns", [])
            except Exception as e:
                logger.warning(f"LLM keyword extraction failed for '{rule['title']}': {e}")
                rule["keywords"] = []
                rule["trigger_patterns"] = []
            results.append(rule)
        return results

    # ════════════════════════════════════════════════════════════
    # 确认入库
    # ════════════════════════════════════════════════════════════

    async def confirm_and_save(self, rules: List[dict]) -> Dict[str, int]:
        """确认入库: 双写 Neo4j CustomRule + MySQL 索引"""
        saved, skipped = 0, 0
        for rule in rules:
            try:
                rule_id = f"cr_{int(time.time() * 1000)}_{saved}"
                rule["rule_id"] = rule_id

                # 1. Neo4j 写入
                await self._repo.create_custom_rule(rule)

                # 2. MySQL 索引写入
                await self._repo.upsert_index(rule_id, {
                    "keywords": rule.get("keywords", []),
                    "trigger_patterns": rule.get("trigger_patterns", []),
                    "priority": rule.get("priority", 100),
                    "enabled": True,
                })

                # 3. 异步计算 embedding（失败不阻塞）
                if self._emb:
                    try:
                        kw = " ".join(rule.get("keywords", []))
                        emb = await self._emb.embed_text(f"{rule['title']} {kw}")
                        if emb:
                            await self._repo.update_embedding(rule_id, emb)
                    except Exception as e:
                        logger.debug(f"embedding computation failed: {e}")

                saved += 1
            except Exception as e:
                logger.warning(f"save rule '{rule.get('title')}' failed: {e}")
                skipped += 1

        return {"saved": saved, "skipped": skipped}
