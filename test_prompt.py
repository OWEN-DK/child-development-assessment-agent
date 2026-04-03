from langchain_core.prompts import PromptTemplate

SYNONYM_EXPANSION_PROMPT = """
输入：皮层
输出：{"synonyms": ["皮层", "大脑皮层"]}

输入：{query}
输出：
"""

prompt = PromptTemplate(
    template=SYNONYM_EXPANSION_PROMPT,
    input_variables=["query"]
)

try:
    formatted = prompt.format(query="老师")
    print(formatted)
except Exception as e:
    print(f"Exception type: {type(e)}")
    print(f"Exception str: {e}")
