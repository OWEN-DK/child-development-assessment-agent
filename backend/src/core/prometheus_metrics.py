"""Prometheus 监控指标定义"""

from prometheus_client import Counter, Histogram, Gauge

LLM_CALLS_TOTAL = Counter(
    "llm_calls_total",
    "Total LLM calls",
    ["model", "scenario", "status"],
)

LLM_CALL_DURATION = Histogram(
    "llm_call_duration_seconds",
    "LLM call duration",
    ["model", "scenario"],
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0],
)

LLM_TOKENS_TOTAL = Counter(
    "llm_tokens_total",
    "Total tokens consumed",
    ["model", "scenario", "type"],
)

ACTIVE_CONNECTIONS = Gauge(
    "llm_active_connections",
    "Active LLM connections",
    ["model"],
)

CACHE_HIT_RATE = Gauge(
    "cache_hit_rate",
    "Cache hit rate",
    ["cache_type"],
)
