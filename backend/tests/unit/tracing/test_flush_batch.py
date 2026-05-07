"""TraceWriter._build_llm_call 和批量路径单元测试"""

import pytest

from src.core.tracing.writer import TraceWriter


class TestBuildLlmCall:
    """测试 _build_llm_call 静态方法"""

    def test_basic_build(self):
        """基本构建：包含必需字段"""
        item = {
            "span_id": "span-001",
            "trace_id": "trace-001",
            "parent_span_id": "parent-001",
            "prompt_messages": [{"role": "user", "content": "hello"}],
            "model_name": "qwen-plus",
            "call_parameters": {"model": "qwen-plus", "scenario": "test"},
        }
        log = TraceWriter._build_llm_call(item)

        assert log is not None
        assert log.span_id == "span-001"
        assert log.trace_id == "trace-001"
        assert log.parent_span_id == "parent-001"
        assert log.prompt_messages == [{"role": "user", "content": "hello"}]
        assert log.model_name == "qwen-plus"

    def test_returns_none_without_span_id(self):
        """无 span_id 时返回 None"""
        item = {"trace_id": "trace-001", "model_name": "qwen-plus"}
        log = TraceWriter._build_llm_call(item)
        assert log is None

    def test_model_from_call_parameters(self):
        """model_name 从 call_parameters.model 回退"""
        item = {
            "span_id": "span-001",
            "call_parameters": {"model": "qwen-turbo"},
        }
        log = TraceWriter._build_llm_call(item)
        assert log.model_name == "qwen-turbo"

    def test_model_defaults_to_unknown(self):
        """无 model 信息时默认 unknown"""
        item = {"span_id": "span-001"}
        log = TraceWriter._build_llm_call(item)
        assert log.model_name == "unknown"

    def test_request_id_generated_when_missing(self):
        """无 request_id 时自动生成 UUID"""
        item = {"span_id": "span-001", "model_name": "qwen-plus"}
        log = TraceWriter._build_llm_call(item)
        assert log.request_id is not None
        assert len(log.request_id) > 0


class TestApplyLlmItemFields:
    """测试 _apply_llm_item_fields 静态方法"""

    def test_completion_message(self):
        """设置 completion_message"""
        item = {"span_id": "s1", "model_name": "m1"}
        log = TraceWriter._build_llm_call(item)

        TraceWriter._apply_llm_item_fields(log, {"completion_message": "response text"})
        assert log.completion_message == "response text"

    def test_tokens_as_dict(self):
        """tokens 为 dict 时计算总 token 和 cost"""
        item = {"span_id": "s1", "model_name": "qwen-plus"}
        log = TraceWriter._build_llm_call(item)

        TraceWriter._apply_llm_item_fields(log, {
            "tokens": {"input_tokens": 100, "output_tokens": 50, "total_tokens": 150},
            "call_parameters": {"model": "qwen-plus"},
        })
        assert log.tokens == 150
        assert log.cost is not None

    def test_tokens_total_calculated_from_io(self):
        """tokens dict 无 total_tokens 时从 input+output 计算"""
        item = {"span_id": "s1", "model_name": "qwen-plus"}
        log = TraceWriter._build_llm_call(item)

        TraceWriter._apply_llm_item_fields(log, {
            "tokens": {"input_tokens": 100, "output_tokens": 50},
            "call_parameters": {"model": "qwen-plus"},
        })
        assert log.tokens == 150

    def test_ttft_sets_completion_start_time(self):
        """ttft 设置 completion_start_time_ms"""
        item = {"span_id": "s1", "model_name": "m1"}
        log = TraceWriter._build_llm_call(item)

        TraceWriter._apply_llm_item_fields(log, {"ttft": 200})
        assert log.completion_start_time_ms == 200

    def test_ttft_none_sets_null(self):
        """ttft=None 时 completion_start_time_ms 为 None"""
        item = {"span_id": "s1", "model_name": "m1"}
        log = TraceWriter._build_llm_call(item)

        TraceWriter._apply_llm_item_fields(log, {"ttft": None})
        assert log.completion_start_time_ms is None

    def test_error_sets_level_and_parameter(self):
        """error 字段设置 ERROR 级别和 call_parameters"""
        item = {"span_id": "s1", "model_name": "m1", "call_parameters": {"model": "m1"}}
        log = TraceWriter._build_llm_call(item)

        TraceWriter._apply_llm_item_fields(log, {"error": "timeout"})
        assert log.level.value == "ERROR"
        assert log.call_parameters["error"] == "timeout"


class TestUpdateLlmCall:
    """测试 _update_llm_call 静态方法"""

    def test_updates_parent_span_id_if_missing(self):
        """已有记录无 parent_span_id 时从 item 补充"""
        item = {"span_id": "s1", "model_name": "m1"}
        log = TraceWriter._build_llm_call(item)
        assert log.parent_span_id is None

        TraceWriter._update_llm_call(log, {"parent_span_id": "parent-001"})
        assert log.parent_span_id == "parent-001"

    def test_does_not_overwrite_existing_parent_span_id(self):
        """已有记录有 parent_span_id 时不覆盖"""
        item = {"span_id": "s1", "model_name": "m1", "parent_span_id": "original"}
        log = TraceWriter._build_llm_call(item)

        TraceWriter._update_llm_call(log, {"parent_span_id": "new-parent"})
        assert log.parent_span_id == "original"

    def test_merges_completion_message(self):
        """更新时合并 completion_message"""
        item = {"span_id": "s1", "model_name": "m1"}
        log = TraceWriter._build_llm_call(item)

        TraceWriter._update_llm_call(log, {"completion_message": "final response"})
        assert log.completion_message == "final response"
