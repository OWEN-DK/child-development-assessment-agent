"""书籍匹配节点 — 直接搜索 + 27B 单次 LLM 调用匹配

7B qwen-turbo 已统一切换为 qwen3.5-27b。搜索由 Python 代码直接执行，LLM 做单次 structured_output 调用。
"""

import asyncio
import logging
from typing import Any, Dict, List

from pydantic import BaseModel, Field

from src.core.knowledge_qa.tools import (
    clear_search_accumulator,
    clear_tool_call_state,
    get_search_accumulator,
    init_search_accumulator,
    init_tool_call_state,
)
from src.schemas.knowledge_qa import (
    KnowledgeQAState,
    MatchedBook,
    NoMatchingBooksError,
    push_progress,
)

logger = logging.getLogger(__name__)


class MatchedBookItem(BaseModel):
    """单本书匹配结果（LLM 结构化输出）"""
    book_id: str = Field(description="搜索结果中的 source_book 字段值（文件名）")
    title: str = Field(description="推断的书名")
    match_reason: str = Field(description="匹配理由，一句话")


class MatchBooksResponse(BaseModel):
    """书籍匹配 LLM 输出"""
    matched_books: List[MatchedBookItem] = Field(description="匹配的书籍列表，按匹配度排序")

class QueryAnalysisResult(BaseModel):
    """查询分析结构化输出（单次 LLM 调用完成意图分类+实体提取+问题分解+查询改写）"""
    intent: str = Field(
        description="问题意图分类: solution_seeking(寻求方案) | knowledge_query(知识查询) | problem_diagnosis(问题诊断) | general(通用)"
    )
    child_age: str = Field(default="", description="孩子年龄，如 '8岁'")
    child_gender: str = Field(default="", description="孩子性别: 男/女/未知")
    behavior_traits: List[str] = Field(
        default_factory=list,
        description="行为特征列表，如 ['注意力不集中', '坐不住', '好动']"
    )
    cognitive_traits: List[str] = Field(
        default_factory=list,
        description="认知/学习特征，如 ['写作业困难', '上课不听讲']"
    )
    emotional_traits: List[str] = Field(
        default_factory=list,
        description="情绪/社交特征，如 ['被老师投诉', '社交困难']"
    )
    sub_questions: List[str] = Field(
        default_factory=list,
        description="问题分解后的子问题，每个聚焦一个维度，2-3个"
    )
    rewritten_queries: List[str] = Field(
        default_factory=list,
        description="从不同角度改写的搜索查询，2-3个，去除解决方案导向词汇"
    )




async def _batch_resolve_book_ids(raw_ids: list[str]) -> dict[str, str]:
    """通过 HTTP 调用 RAG 服务批量将 book_id 映射为 DocumentRecord UUID。

    先前直接查询知识库数据库，现已改为 HTTP 调用 /rag/books/batch-resolve，
    为后续知识库独立部署做准备。
    """
    if not raw_ids:
        return {}

    trimmed_ids = [rid.strip() for rid in raw_ids]
    try:
        from src.core.knowledge_qa.tools import _get_http_client

        client = _get_http_client()
        books = await client.batch_resolve_books(trimmed_ids)

        mapping: dict[str, str] = {}
        for b in books:
            uuid_str = b["id"]
            mapping[uuid_str] = uuid_str
            if b.get("file_name"):
                mapping[b["file_name"]] = uuid_str
                mapping[b["file_name"].strip()] = uuid_str
            if b.get("file_hash"):
                mapping[b["file_hash"]] = uuid_str
        return mapping
    except Exception as e:
        logger.warning(f"批量 book_id 解析失败 (HTTP): {e}")
        return {}



def _apply_source_quota(
    results: List[Dict],
    max_per_source_ratio: float = 0.4,
    min_sources: int = 2,
) -> List[Dict]:
    """对搜索结果施加来源配额，防止单一书籍垄断 top-K。

    策略：每本书最多占结果总数的 max_per_source_ratio（默认 40%）。
    超出配额的结果降级排列在配额内结果之后，保证候选池的来源多样性。
    """
    if not results:
        return results

    total = len(results)
    max_per_source = max(int(total * max_per_source_ratio), min_sources)

    in_quota: List[Dict] = []
    over_quota: List[Dict] = []
    seen_per_source: Dict[str, int] = {}

    for r in results:
        sb = r.get("source_book", "")
        count = seen_per_source.get(sb, 0)
        if count < max_per_source:
            in_quota.append(r)
            seen_per_source[sb] = count + 1
        else:
            over_quota.append(r)

    return in_quota + over_quota


async def _extract_candidate_books(search_results: List[Dict]) -> List[Dict]:
    """从搜索结果中提取候选书籍信息（去重，书名规范化去扩展名）。"""
    import re as _re

    seen = {}
    for r in search_results:
        sb = r.get("source_book", "")
        if not sb:
            continue
        # 规范化: trim + 去文件扩展名
        sb_clean = sb.strip()
        for ext in (".epub", ".pdf", ".txt", ".md", ".docx", ".html", ".mobi"):
            if sb_clean.lower().endswith(ext):
                sb_clean = sb_clean[:-len(ext)].strip()
                break
        if sb_clean and sb_clean not in seen:
            seen[sb_clean] = {
                "source_book": sb_clean,  # 使用规范化后的书名
                "_raw_source_book": sb,    # 保留原始值用于精确 DB 匹配
                "file_hash": r.get("file_hash", ""),
                "chapters": [],
            }
        if sb_clean in seen:
            ch = r.get("chapter_title", "")
            if ch and ch not in seen[sb_clean]["chapters"]:
                seen[sb_clean]["chapters"].append(ch)
    return list(seen.values())




def _extract_child_profile(question: str) -> dict:
    """从用户问题中提取孩子的行为/认知/情绪特征。

    不依赖 LLM，纯规则提取。用于生成多维度搜索 query，
    避免直接用原始问题搜索导致的单书垄断。

    Returns:
        {"age": "8岁", "behavior": [...], "cognitive": [...], "emotional": [...]}
    """
    import re

    profile = {"age": "", "behavior": [], "cognitive": [], "emotional": []}

    # 年龄提取
    age_match = re.search(r"(\d{1,2})\s*[岁歲]", question)
    if age_match:
        profile["age"] = f"{age_match.group(1)}岁"

    # 行为特征（身体/动作层面）
    behavior_patterns = [
        ("注意力不集中", ["注意力不集中", "注意力差", "不集中", "走神", "分心"]),
        ("坐不住", ["坐不住", "静不下来", "好动", "多动", "扭来扭去"]),
        ("冲动", ["冲动", "控制不住", "忍不住"]),
        ("动作慢", ["动作慢", "磨蹭", "拖延"]),
    ]
    for label, keywords in behavior_patterns:
        if any(kw in question for kw in keywords):
            profile["behavior"].append(label)

    # 认知特征（学习/思维层面）
    cognitive_patterns = [
        ("写作业困难", ["写作业", "作业", "做作业"]),
        ("上课不听讲", ["上课", "课堂", "听课"]),
        ("学习困难", ["学习不好", "成绩", "跟不上", "学不会"]),
        ("记忆力差", ["记不住", "记忆力", "容易忘"]),
    ]
    for label, keywords in cognitive_patterns:
        if any(kw in question for kw in keywords):
            profile["cognitive"].append(label)

    # 情绪/社交特征
    emotional_patterns = [
        ("被投诉", ["投诉", "被老师", "老师说"]),
        ("情绪问题", ["发脾气", "哭闹", "焦虑", "紧张", "害怕"]),
        ("社交困难", ["不合群", "社交", "交朋友", "被欺负"]),
    ]
    for label, keywords in emotional_patterns:
        if any(kw in question for kw in keywords):
            profile["emotional"].append(label)

    return profile


async def _analyze_query(question: str) -> QueryAnalysisResult:
    """综合查询分析：意图分类 + 实体提取 + 问题分解 + 查询改写。

    一次 LLM 调用完成所有分析，与规则提取并行执行。
    LLM 失败时返回空结果（不影响后续规则提取的降级路径）。
    """
    from src.core.knowledge_qa.nodes.base import _invoke_llm_structured

    system_prompt = """你是一个儿童教育领域的查询分析专家。分析用户问题，输出结构化结果。

## 任务
1. **意图分类**：判断问题属于哪类
   - solution_seeking: 寻求具体方案/方法/建议（如"有什么运动可以改善"）
   - problem_diagnosis: 诊断孩子问题原因（如"为什么注意力不集中"）
   - knowledge_query: 查询知识/概念（如"什么是前庭觉"）
   - general: 其他

2. **实体提取**：从问题中提取孩子的年龄、性别、行为特征、认知特征、情绪特征
   - 行为特征：身体/动作层面（注意力不集中、坐不住、好动、冲动等）
   - 认知特征：学习/思维层面（写作业困难、上课不听讲、记忆力差等）
   - 情绪特征：情绪/社交层面（被投诉、发脾气、不合群等）

3. **问题分解**：将原问题拆分为 2-3 个子问题，每个聚焦一个维度
   - 子问题应覆盖：行为表现、认知发展、情绪社交
   - 子问题用于独立搜索，确保不同书籍都能被命中

4. **查询改写**：生成 2-3 个搜索友好的查询语句
   - 去除解决方案导向词汇（"有什么运动"、"怎么改善"、"推荐"等）
   - 保留孩子的核心特征描述
   - 每个查询从不同角度切入"""

    user_message = f"用户问题：{question}"

    try:
        result = await _invoke_llm_structured(
            system_prompt=system_prompt,
            user_message=user_message,
            response_format=QueryAnalysisResult,
            step_label="query_analysis",
            timeout_seconds=15,
            no_cache=True,
        )
        logger.info(
            f"query_analysis: intent={result.intent}, "
            f"behavior={result.behavior_traits}, "
            f"sub_q={len(result.sub_questions)}, "
            f"rewrite={len(result.rewritten_queries)}"
        )
        return result
    except Exception as e:
        logger.warning(f"query_analysis LLM 失败，降级到规则提取: {e}")
        # 降级：用规则提取结果构造 QueryAnalysisResult
        profile = _extract_child_profile(question)
        return QueryAnalysisResult(
            intent="general",
            child_age=profile["age"],
            behavior_traits=profile["behavior"],
            cognitive_traits=profile["cognitive"],
            emotional_traits=profile["emotional"],
            sub_questions=[],
            rewritten_queries=[],
        )


async def _analyze_and_search_books(question: str) -> List[Dict]:
    """搜索知识库：综合查询分析管线。

    三阶段分析：
    1. 意图分类 + 实体提取（LLM + 规则并行）
    2. 问题分解 + 查询改写（LLM）
    3. 多维度搜索 + 来源配额
    """
    import httpx
    import re
    from src.config import settings

    host = getattr(settings, "app_host", "127.0.0.1")
    port = getattr(settings, "app_port", 8000)
    if host == "0.0.0.0":
        host = "127.0.0.1"

    # ═══════════════════════════════════════════════════════════
    # Phase 1: 并行分析 — LLM 分析 + 规则提取同时进行
    # ═══════════════════════════════════════════════════════════
    analysis_task = _analyze_query(question)
    profile = _extract_child_profile(question)  # 同步，零延迟

    try:
        analysis = await asyncio.wait_for(analysis_task, timeout=20)
    except Exception:
        # LLM 超时或失败，用规则提取结果构造空分析
        analysis = QueryAnalysisResult(
            intent="general",
            child_age=profile["age"],
            behavior_traits=profile["behavior"],
            cognitive_traits=profile["cognitive"],
            emotional_traits=profile["emotional"],
        )

    # 合并：LLM 结果为主，规则提取为补充
    age_str = analysis.child_age or profile["age"]
    behavior = analysis.behavior_traits or profile["behavior"]
    cognitive = analysis.cognitive_traits or profile["cognitive"]
    emotional = analysis.emotional_traits or profile["emotional"]
    intent = analysis.intent

    logger.info(
        f"query_analysis 合并结果: intent={intent}, age={age_str}, "
        f"behavior={behavior}, cognitive={cognitive}, emotional={emotional}"
    )

    # ═══════════════════════════════════════════════════════════
    # Phase 2: 构建多维度搜索 query
    # ═══════════════════════════════════════════════════════════
    queries = []
    seen = set()

    def _add(q):
        """去重添加查询"""
        q = q.strip()
        if q and q not in seen and len(q) >= 2:
            seen.add(q)
            queries.append(q)

    # 来源 A: LLM 问题分解 — 子问题（approach 3）
    for sq in analysis.sub_questions[:3]:
        _add(sq)

    # 来源 B: LLM 查询改写 — 去除方案导向词汇的中性查询（approach 1）
    for rq in analysis.rewritten_queries[:3]:
        _add(rq)

    # 来源 C: 规则提取 — 实体维度查询（approach 2）
    if behavior:
        _add(f"{age_str}儿童 {' '.join(behavior[:3])}".strip())
    if cognitive:
        _add(f"儿童 {' '.join(cognitive[:2])} 学习能力".strip())
    if emotional:
        _add(f"儿童 {' '.join(emotional[:2])} 情绪调节".strip())

    # 来源 D: 意图路由 — 根据意图添加领域关键词（approach 2）
    if intent == "solution_seeking":
        # 方案寻求类：添加多维度领域词，避免被单一方案词主导
        if any(kw in question for kw in ['注意', '专注', '集中', '坐不住', '走神']):
            _add("儿童注意力发展")
        if any(kw in question for kw in ['学习', '作业', '成绩', '上课']):
            _add("儿童学习方法")
        if any(kw in question for kw in ['情绪', '多动', '冲动', '投诉', '行为']):
            _add("儿童情绪调节")
    elif intent == "problem_diagnosis":
        _add("儿童发展心理学")
        _add("儿童认知发展")
    elif intent == "knowledge_query":
        # 知识查询类：直接用问题搜索更准确
        _add(question)

    # 来源 E: 书名提及
    for bm in re.findall(r'《([^》]+)》', question):
        _add(bm)

    # 来源 F: 通用领域词
    _add("儿童发展")

    # Fallback
    if not queries:
        _add(question)

    logger.info(f"match_books 搜索策略: {len(queries)} 组 query, 意图={intent}, 前3: {queries[:3]}")

    all_results = []
    seen_ids = set()

    async with httpx.AsyncClient(
        base_url=f"http://{host}:{port}",
        timeout=httpx.Timeout(10.0),
    ) as client:
        for query in queries[:6]:
            try:
                resp = await client.get(
                    "/rag/search",
                    params={"query": query, "limit": 15},
                )
                resp.raise_for_status()
                data = resp.json()
                results = data.get("data", {}).get("results", [])
                logger.info(f"match_books 搜索 '{query[:40]}' 返回 {len(results)} 条")
            except Exception as e:
                logger.warning(f"match_books 搜索失败 (query={query[:50]}): {e}")
                continue

            for r in results:
                rid = r.get("id", "")
                if rid and rid not in seen_ids:
                    seen_ids.add(rid)
                    all_results.append(r)

            if len(all_results) >= 25:
                break

    return all_results


async def _llm_match_books(question: str, candidates: List[Dict]) -> List[MatchedBookItem]:
    """使用 27B LLM 从候选书籍中选择匹配的书籍。"""
    if not candidates:
        return []

    from src.core.llm.factory import LLMServiceFactoryCompat

    # 构建候选摘要
    candidate_text = ""
    for i, c in enumerate(candidates):
        chapters_str = "、".join(c["chapters"][:3]) if c["chapters"] else "未知"
        candidate_text += (
            f"[{i}] book_id=\"{c['source_book']}\", "
            f"涉及章节: {chapters_str}\n"
        )

    prompt = f"""你是一个文献检索专家。根据用户问题，从候选书籍中评估每本书的相关性。

用户问题：{question}

候选书籍（从知识库搜索结果中提取）：
{candidate_text}

请评估每本候选书籍与用户问题的相关性，返回所有有一定关联的书籍，按匹配度排序。
- 只要书籍主题与问题的任一方面相关（如儿童发展、教育、运动、心理、营养等），就应纳入匹配结果
- book_id 必须使用候选书籍中显示的 book_id 值
- title 根据 book_id 推断一个有意义的书名（去掉文件扩展名）
- 为每本书写一句话匹配理由
- 如果候选书籍确实都不相关，才返回空数组"""

    model = LLMServiceFactoryCompat.create_raw(
        model_name="qwen3.5-27b",
        temperature=0.3,
    )

    try:
        structured_model = model.with_structured_output(MatchBooksResponse)
        result = await asyncio.wait_for(
            structured_model.ainvoke(prompt),
            timeout=15,
        )
        return result.matched_books
    except Exception as e:
        logger.warning(f"LLM 书籍匹配失败: {e}")
        return []


async def match_books_node(state: KnowledgeQAState) -> Dict[str, Any]:
    """书籍匹配节点：直接搜索知识库 + 27B LLM 单次匹配。"""
    await push_progress("started", "正在分析问题意图并匹配书籍…")

    init_search_accumulator()
    init_tool_call_state(max_calls=10)

    try:
        # Step 1: 直接调用 search_knowledge_base 工具搜索知识库
        search_results = await _analyze_and_search_books(state.question)
        logger.info(f"match_books 直接搜索: {len(search_results)} 条结果")

        if not search_results:
            raise NoMatchingBooksError()

        # Step 2: 从搜索结果中提取候选书籍
        # 来源配额：防止单一书籍垄断搜索结果
        search_results = _apply_source_quota(search_results)
        candidates = await _extract_candidate_books(search_results)
        logger.info(f"match_books 候选书籍: {[c['source_book'] for c in candidates]}")

        if not candidates:
            raise NoMatchingBooksError()

        # Step 3: 使用 27B LLM 做匹配评估（单次调用，无工具）
        matched_items = await _llm_match_books(state.question, candidates)

        # Step 4: 确保足够多的书籍被匹配（至少 2 本，以增加引用多样性）
        if len(matched_items) < 2 and len(candidates) >= 2:
            logger.info(f"LLM 仅匹配 {len(matched_items)} 本，补充候选书籍以确保多样性")
            existing_ids = {m.book_id for m in matched_items}
            for c in candidates:
                clean_name = c["source_book"]
                if clean_name not in existing_ids:
                    matched_items.append(MatchedBookItem(
                        book_id=clean_name,
                        title=clean_name,
                        match_reason="综合匹配：该书籍内容与问题领域相关",
                    ))
                    existing_ids.add(clean_name)
        if not matched_items:
            logger.info("LLM 匹配返回空，降级为直接提取")
            for c in candidates:
                clean_name = c["source_book"]
                matched_items.append(MatchedBookItem(
                    book_id=clean_name,
                    title=clean_name,
                    match_reason="从搜索结果中自动匹配",
                ))

        # Step 5: 构建 search_book_ids — 包含所有候选书籍的 file_hash
        # 后续 RAG 检索不再做 LLM 级别的书籍过滤，而是让向量相似度自然排序
        # 这样所有已索引的书籍内容都能被搜索到，只是更匹配的内容排在前列
        search_book_ids: list[str] = []
        source_to_hash: Dict[str, str] = {}
        for c in candidates:
            fh = c.get("file_hash", "")
            if fh:
                raw_name = c.get("_raw_source_book", c["source_book"])
                clean_name = c["source_book"]
                source_to_hash[clean_name] = fh
                if raw_name != clean_name:
                    source_to_hash[raw_name] = fh
                if fh not in search_book_ids:
                    search_book_ids.append(fh)
        logger.info(
            f"search_book_ids 覆盖所有候选书籍 ({len(search_book_ids)} 本): "
            f"{[c['source_book'] for c in candidates]}"
        )

        # Step 6: 解析 LLM 匹配结果 → books_detail（仅用于报告展示，不影响检索范围）
        raw_ids = [m.book_id for m in matched_items]
        id_mapping = await _batch_resolve_book_ids(raw_ids)

        books_detail = []
        for i, item in enumerate(matched_items):
            # 多路径解析: 先精确匹配，再 trim，再用 file_hash 降级
            resolved_id = (
                id_mapping.get(item.book_id)
                or id_mapping.get(item.book_id.strip())
            )
            if not resolved_id:
                # 用规范化前的原始书名重试
                for c in candidates:
                    if c["source_book"] == item.book_id and c.get("_raw_source_book"):
                        resolved_id = id_mapping.get(c["_raw_source_book"])
                        if resolved_id:
                            break

            fh = source_to_hash.get(item.book_id, "") or source_to_hash.get(item.book_id.strip(), "")

            if not resolved_id and not fh:
                logger.warning(f"book_id 无法解析且无 file_hash: {item.book_id}")
                continue

            if not resolved_id:
                # 最终降级: 用 file_hash 作为 book_id
                resolved_id = fh

            books_detail.append(MatchedBook(
                book_id=resolved_id,
                title=item.title,
                source_type="book",
                match_reason=item.match_reason,
                is_primary=(i == 0),
            ))

        if not books_detail:
            raise NoMatchingBooksError()

        await push_progress("books_matched", f"已匹配书籍: {books_detail[0].title}")

        # search_book_ids: 所有候选书籍的 file_hash（供 RAG 检索，不做书籍级过滤）
        # books_detail: LLM 匹配结果（供报告展示）
        return {
            "matched_book_ids": search_book_ids,
            "matched_books_detail": books_detail,
            "current_step": ["books_matched"],
        }

    except NoMatchingBooksError:
        raise

    except Exception as e:
        logger.exception(f"match_books 节点异常: {e}")
        return {
            "matched_book_ids": [],
            "matched_books_detail": [],
            "errors": state.errors + [f"match_books_failed: {e}"],
            "current_step": ["books_matched_failed"],
        }

    finally:
        clear_search_accumulator()
        clear_tool_call_state()
