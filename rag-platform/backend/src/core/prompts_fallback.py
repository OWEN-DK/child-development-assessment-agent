"""
提示词降级备用文件

仅作为 PromptManager 不可用时的降级备用。
提示词的唯一真实来源是 MySQL 数据库 (prompt_versions 表)。
业务代码应使用 prompt_manager.get_prompt()，不应直接导入本文件。
"""

# ── 检索相关 ──

RAG_QUERY_TEMPLATE = "针对 {issues} 的 {goals} 建议"

QUERY_REWRITE_PROMPT = """
你是专业的检索优化专家。请将用户的原始查询重写为更适合知识库检索的形式：
1. 扩展相关同义词和专业术语
2. 保持查询简洁，不超过 200 字
3. 只返回重写后的查询文本，不需要其他解释

原始查询: {query}
重写后的查询:
"""

SYNONYM_EXPANSION_PROMPT = """
请为以下查询生成相关同义词和近义词扩展：
查询: {query}
"""

# ── 元数据提取 ──

METADATA_EXTRACTION_PROMPT = """
请从以下文档中提取关键元数据：
文档内容: {content}
"""

# ── 验证 ──

VALIDATION_SYSTEM_PROMPT = "你是专业的质量审核专家。"

# ── 报告 ──

REPORTING_SYSTEM_PROMPT = "你是专业的报告生成专家。"

# ── 评分 ──

SCORING_SYSTEM_PROMPT = "你是专业的评估评分专家。"

# ── 评估 (继承) ──

ASSESSMENT_SYSTEM_PROMPT = "你是专业的评估分析专家。"

CATEGORY_INFERENCE_PROMPT = "请根据以下内容推断类别: {content}"

INTENSITY_INFERENCE_PROMPT = "请根据以下内容评估强度: {content}"

# ── 测试用例生成 ──

TEST_CASE_DRAFT_GENERATION_PROMPT = """
请从以下文档片段生成测试用例：
文档: {document_text}
"""

TEST_CASE_GENERATION_CHUNK_GROUNDED_PROMPT = """
请从以下文档分块生成测试用例：
分块: {chunk_text}
"""

# ── 草稿生成 ──

DRAFT_GENERATION_RAG_PROMPT = """
请基于检索结果生成测试用例草稿：
查询: {query}
检索结果: {retrieved_contexts}
"""

# ── RAG 评估指标 ──

RAG_EVAL_METRIC_ANSWER_RELEVANCY_GENERATE_PROMPT = """
请根据以下问题生成参考答案：
问题: {query}
"""

RAG_EVAL_METRIC_FAITHFULNESS_EXTRACT_CLAIMS_PROMPT = """
请从以下答案中提取陈述主张：
答案: {answer}
"""

RAG_EVAL_METRIC_FAITHFULNESS_VERIFY_CLAIM_PROMPT = """
请验证以下主张是否可被上下文支持：
主张: {claim}
上下文: {context}
"""

RAG_EVAL_METRIC_FAITHFULNESS_BATCH_VERIFY_PROMPT = """
请批量验证以下主张：
主张列表: {claims}
上下文: {context}
"""

RAG_EVAL_METRIC_GROUNDEDNESS_PROMPT = """
请评估以下答案的基于程度：
答案: {answer}
上下文: {context}
"""

RAG_EVAL_METRIC_GROUNDEDNESS_BATCH_PROMPT = """
请批量评估基于程度：
答案列表: {answers}
"""

# ── L3 诊断 ──

LAYER3_DEVIATION_ANALYSIS_PROMPT = """
请分析以下答案与预期的偏差：
预期: {expected}
实际: {actual}
"""

LAYER3_HALLUCINATION_DETECTION_PROMPT = """
请检测以下答案中的幻觉：
答案: {answer}
上下文: {context}
"""
