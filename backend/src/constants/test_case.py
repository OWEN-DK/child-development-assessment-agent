from typing import List

# 测试用例领域枚举
TEST_CASE_DOMAINS: List[str] = [
    "粗大动作",
    "精细动作",
    "语言发展",
    "认知能力",
    "社交情感",
    "感觉统合"
]

# 重复检测组合字段
TEST_CASE_UNIQUE_FIELDS: List[str] = ["query", "age", "domain"]

# JSON导入必填字段
TEST_CASE_REQUIRED_FIELDS: List[str] = ["query", "age"]
