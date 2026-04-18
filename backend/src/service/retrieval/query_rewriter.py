import re
from typing import Optional

from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import PromptTemplate

from src.config import settings
from src.core.llm.factory import LLMFramework, LLMServiceFactoryCompat
from src.core.prompt.manager import prompt_manager
from src.core.prompt_injection_guard import prompt_injection_guard
from src.schemas import LLMMessage, LLMRequest, SynonymExpansionResult
from src.utils.logger import logger


class QueryRewriter:
    """查询重写服务，负责查询重写和同义词扩展"""

    def __init__(
        self,
        dashscope_available: bool,
        query_analyzer=None,
        synonym_validator=None,
        local_expander=None,
    ):
        self.dashscope_available = dashscope_available
        self._query_analyzer = query_analyzer
        self._synonym_validator = synonym_validator
        self._local_expander = local_expander

    async def _rewrite_query(self, query: str, age: int) -> str:
        """重写查询以提高检索准确率"""
        if not settings.rag_config["query_rewrite"]["enabled"]:
            return query

        if not self.dashscope_available:
            return self._local_rewrite_query(query, age)

        try:
            # Prompt 注入检测
            injected, reason = prompt_injection_guard.detect_injection(query)
            if injected:
                logger.warning(f"Prompt injection detected in query rewrite: {reason}")
                query = prompt_injection_guard.sanitize_content(query)

            # 使用工厂创建 LLM 实例（使用兼容层保持向后兼容）
            llm = LLMServiceFactoryCompat.create(
                framework=LLMFramework.LANGCHAIN,
                model_name=settings.llm_models["query_rewrite"],
                scenario="query_rewrite",
                temperature=0.6,
            )

            # 通过 PromptManager 获取提示词并渲染
            system_prompt = await prompt_manager.get_prompt("rag_query_rewrite")
            user_prompt = await prompt_manager.get_prompt(
                "rag_query_rewrite", variables={"age": age, "query": query}
            )

            # 构建提示词
            messages = [
                LLMMessage(role="system", content=system_prompt),
                LLMMessage(role="user", content=user_prompt),
            ]

            # 调用 LLM
            response = await llm.chat(
                LLMRequest(
                    messages=messages,
                    model_name=settings.llm_models["query_rewrite"],
                    temperature=0.6,
                    max_tokens=256,
                    scenario="query_rewrite",
                    prompt_key="query_rewrite",
                )
            )
            rewritten_query = response.content.strip()
            logger.info(f"Query rewritten: '{query}' -> '{rewritten_query}'")
            return rewritten_query if rewritten_query else query
        except Exception as e:
            logger.warning(f"Query rewrite failed: {e}, using local fallback")
            return self._local_rewrite_query(query, age)

    def _local_rewrite_query(self, query: str, age: int) -> str:
        """本地查询重写兜底逻辑"""
        # 移除常见无意义词和标点
        query = re.sub(r"[?？!！.。，,]", " ", query)
        # 针对年龄添加关键词
        if age > 0:
            if age < 3:
                query += " 婴幼儿 早期教育"
            elif age < 6:
                query += " 幼儿园 学前教育"
            else:
                query += " 学龄儿童"
        return query.strip()

    def _validate_expansion(self, expansion_text: str, original_query: str) -> bool:
        """
        验证同义词扩展质量

        验证规则：
        1. 长度检查：不应超过 200 字符
        2. 格式检查：不应包含完整句子（句号、感叹号、问号、冒号）
        3. 必须包含原查询
        4. 不应包含敏感词或无关内容

        Args:
            expansion_text: 扩展后的文本
            original_query: 原始查询

        Returns:
            是否通过验证
        """
        # 长度检查
        if len(expansion_text) > 200:
            return False

        # 格式检查（不应包含完整句子）
        if any(punct in expansion_text for punct in ["。", "！", "？", "：", "\n"]):
            return False

        # 必须包含原查询
        if original_query not in expansion_text:
            return False

        # 检查是否包含明显的无关内容
        irrelevant_patterns = ["抱歉", "无法", "不知道", "请提供", "问题"]
        if any(pattern in expansion_text for pattern in irrelevant_patterns):
            return False

        return True

    async def _expand_synonyms(self, query: str) -> str:
        """同义词扩展以提高召回率，增加质量验证"""
        if not self.dashscope_available:
            return self._local_expand_synonyms(query)

        try:
            # Prompt 注入检测
            injected, reason = prompt_injection_guard.detect_injection(query)
            if injected:
                logger.warning(
                    f"Prompt injection detected in synonym expansion: {reason}"
                )
                query = prompt_injection_guard.sanitize_content(query)

            # Use LangChain structured output parser to enforce JSON format
            parser = PydanticOutputParser(pydantic_object=SynonymExpansionResult)

            # 通过 PromptManager 获取提示词并渲染
            base_prompt = await prompt_manager.get_prompt("synonym_expansion")

            # Create prompt template with format instructions
            prompt = PromptTemplate(
                template=base_prompt + "\n{format_instructions}\n",
                input_variables=["query"],
                partial_variables={
                    "format_instructions": parser.get_format_instructions()
                },
            )

            # Format prompt with query
            formatted_prompt = prompt.format(query=query)

            # 使用安全包装的提示词
            safe_prompt = formatted_prompt

            # 通过 PromptManager 获取系统提示词
            system_prompt = await prompt_manager.get_prompt("synonym_expansion")

            # 使用工厂创建 LLM 实例（使用兼容层保持向后兼容）
            llm = LLMServiceFactoryCompat.create(
                framework=LLMFramework.LANGCHAIN,
                model_name=settings.llm_models["query_rewrite"],
                scenario="synonym_expansion",
                temperature=0.8,
            )

            # 构建提示词
            messages = [
                LLMMessage(role="system", content=system_prompt),
                LLMMessage(role="user", content=safe_prompt),
            ]

            # 调用 LLM
            response = await llm.chat(
                LLMRequest(
                    messages=messages,
                    model_name=settings.llm_models["query_rewrite"],
                    temperature=0.8,
                    max_tokens=256,
                    scenario="synonym_expansion",
                    prompt_key="synonym_expansion",
                )
            )
            result_text = response.content.strip()

            # Clean response to remove markdown code block markers
            result_text = re.sub(
                r"^```(?:json)?\s*", "", result_text, flags=re.IGNORECASE
            )
            result_text = re.sub(r"\s*```$", "", result_text)
            result_text = result_text.strip()

            # Parse using structured parser
            try:
                result = parser.parse(result_text)
                synonym_list = [
                    str(s).strip() for s in result.synonyms if str(s).strip()
                ]
            except Exception as e:
                logger.warning(
                    f"同义词扩展JSON解析失败: {e}, 原始内容: {result_text[:100]}"
                )
                synonym_list = re.split(r"[\n、,，\s\"']+", result_text)
                synonym_list = [
                    s.strip() for s in synonym_list if s.strip() and len(s) < 20
                ]

            # 必须包含原词，否则回退
            if query not in synonym_list:
                synonym_list.insert(0, query)

            # 去重
            all_terms = list(dict.fromkeys(synonym_list))

            # 质量验证（Phase C-1 新增）
            if self._synonym_validator:
                report = self._synonym_validator.validate(all_terms, query)

                if not report.is_valid:
                    logger.warning(
                        f"同义词质量验证未通过：{len(report.rejected_terms)} 个词被拒绝，"
                        f"原因：{report.rejected_terms[:3]}"
                    )
                    all_terms = report.valid_terms

                    if len(all_terms) <= 1:
                        logger.warning("同义词质量验证后无有效扩展词，使用本地扩展")
                        return self._local_expand_synonyms(query)

                logger.info(
                    f"同义词验证通过：{len(report.valid_terms)} 个有效词，"
                    f"{len(report.rejected_terms)} 个被过滤"
                )

            expanded_query = " ".join(all_terms)

            # 保留原有验证作为二次检查
            if not self._validate_expansion(expanded_query, query):
                logger.warning(f"同义词扩展质量验证失败，使用本地扩展")
                return self._local_expand_synonyms(query)

            logger.info(f"同义词扩展成功：'{query}' -> '{expanded_query}'")
            return expanded_query

        except Exception as e:
            logger.warning(f"同义词扩展失败：{e}, 使用本地扩展")
            return self._local_expand_synonyms(query)

    def _local_expand_synonyms(self, query: str) -> str:
        """本地同义词扩展兜底逻辑（Phase C-2 升级）"""
        if not self._local_expander:
            return query

        synonyms = self._local_expander.expand(query)

        if self._synonym_validator:
            report = self._synonym_validator.validate(synonyms, query)
            synonyms = report.valid_terms

        return " ".join(synonyms)
