"""Prometheus 指标定义

从 backend/ 继承，定义 LLM 调用相关的 Prometheus 指标。
"""
from prometheus_client import Counter, Histogram

LLM_CALLS_TOTAL = Counter(
    "llm_calls_total",
    "LLM 调用总次数",
    ["provider", "model", "status"],
)

LLM_CALL_DURATION = Histogram(
    "llm_call_duration_seconds",
    "LLM 调用耗时",
    ["provider", "model"],
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0],
)

LLM_TOKENS_TOTAL = Counter(
    "llm_tokens_total",
    "LLM Token 消耗总量",
    ["provider", "model", "type"],
)

HTTP_REQUEST_DURATION = Histogram(
    "http_request_duration_seconds",
    "HTTP 请求耗时",
    ["method", "path", "status_code"],
    buckets=[0.01, 0.05, 0.1, 0.5, 1.0, 5.0, 10.0],
)
