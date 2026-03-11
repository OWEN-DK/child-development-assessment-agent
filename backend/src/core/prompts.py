from typing import List, Dict

# --------------------------
# Retrieval Prompts
# --------------------------
RAG_QUERY_TEMPLATE = "针对 {issues} 的 {goals} 训练建议"

# --------------------------
# Mock Data Prompts (for fallback)
# --------------------------
MOCK_KNOWLEDGE_ITEMS = [
    {
        "content": "前庭刺激活动（如荡秋千、旋转）对于调节过度活跃或迟钝的前庭系统至关重要。",
        "source_book": "感觉统合与儿童发展",
        "brain_regions": ["前庭系统", "脑干"],
        "benefits": ["改善平衡", "调节唤醒水平"],
        "risk_level": "Medium",
        "target_age_min": 3,
        "target_age_max": 12,
        "relevance_score": 0.95
    },
    {
        "content": "对于 {age} 岁的儿童，大肌肉运动（如跳跃、攀爬）能促进本体感的发展。",
        "source_book": "儿童动作发展指南",
        "brain_regions": ["小脑", "运动皮层"],
        "benefits": ["增强身体意识", "提升动作协调性"],
        "risk_level": "Low",
        "target_age_min": -1, # Will be adjusted dynamically
        "target_age_max": 2,  # Will be adjusted dynamically
        "relevance_score": 0.88
    }
]

# --------------------------
# Metadata Extraction Prompts
# --------------------------
METADATA_EXTRACTION_PROMPT = """
You are an expert in child development and sensory integration.
Your task is to extract structured metadata from the following text chunk.

Text Chunk:
{text}

Please extract the following information in JSON format:
1. summary: A brief summary of the content (max 50 words).
2. topics: A list of key topics (e.g., "Vestibular System", "Proprioception", "Attention").
3. brain_regions: A list of brain regions mentioned or implied (e.g., "Cerebellum", "Frontal Lobe").
4. target_age_min: The minimum applicable age (integer). If not specified, infer from context or return 0.
5. target_age_max: The maximum applicable age (integer). If not specified, infer from context or return 18.
6. activity_type: The type of content (e.g., "Theory", "Assessment", "Game/Activity", "Advice").

Return ONLY the JSON object.
"""

# --------------------------
# System Prompts (Placeholders)
# --------------------------

# Node1: Validation
VALIDATION_SYSTEM_PROMPT = """
你是一个专业的儿童发展数据校验助手。
你的任务是校验用户输入的儿童画像和拟定计划是否完整、合理。
如果发现数据缺失，请尝试根据上下文进行合理推断。
"""

# Node2: Assessment
ASSESSMENT_SYSTEM_PROMPT = """
你是一个资深的儿童发展评估专家。
请根据儿童的画像（年龄、性别、问题）和历史记录，分析其当前的发展状态。
重点关注前庭觉、本体感、触觉等感统维度的发展情况。
"""

# Node4: Scoring
SCORING_SYSTEM_PROMPT = """
你是一个严格的儿童训练计划评估员。
请根据儿童的发展状态和检索到的科学依据，对拟定的训练计划进行多维度打分。
评分维度包括：科学性、年龄适配度、安全性。
"""

# Node5: Reporting
REPORTING_SYSTEM_PROMPT = """
你是一个充满同理心的儿童发展专家。
请根据所有的评估结果，为家长生成一份易于理解的评估报告。
报告应包含：总分、科学依据、预期改善、调整建议。
使用 Markdown 格式，语气要亲切、专业。
"""
