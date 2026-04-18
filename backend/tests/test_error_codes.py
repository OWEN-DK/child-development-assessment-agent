"""测试错误码定义

测试 error_codes.py 中的错误码分段和常量定义
"""

import pytest
from src.utils import error_codes


class TestErrorCodeRanges:
    """测试错误码范围分配"""

    def test_success_code(self):
        """成功码为 0"""
        assert error_codes.ERROR_CODE_SUCCESS == 0
        assert error_codes.COMMON_SUCCESS == 0

    def test_common_range(self):
        """通用错误码范围 10000-10999"""
        assert error_codes.ERROR_CODE_RANGE_COMMON_START == 10000
        assert error_codes.ERROR_CODE_RANGE_COMMON_END == 10999

    def test_assessment_range(self):
        """评估模块错误码范围 11000-11999"""
        assert error_codes.ERROR_CODE_RANGE_ASSESSMENT_START == 11000
        assert error_codes.ERROR_CODE_RANGE_ASSESSMENT_END == 11999

    def test_rag_range(self):
        """RAG 模块错误码范围 12000-12999"""
        assert error_codes.ERROR_CODE_RANGE_RAG_START == 12000
        assert error_codes.ERROR_CODE_RANGE_RAG_END == 12999

    def test_rag_test_range(self):
        """RAG 测试模块错误码范围 13000-13999"""
        assert error_codes.ERROR_CODE_RANGE_RAG_TEST_START == 13000
        assert error_codes.ERROR_CODE_RANGE_RAG_TEST_END == 13999

    def test_config_range(self):
        """配置管理模块错误码范围 14000-14999"""
        assert error_codes.ERROR_CODE_RANGE_CONFIG_START == 14000
        assert error_codes.ERROR_CODE_RANGE_CONFIG_END == 14999

    def test_prompt_range(self):
        """提示词管理模块错误码范围 15000-15999"""
        assert error_codes.ERROR_CODE_RANGE_PROMPT_START == 15000
        assert error_codes.ERROR_CODE_RANGE_PROMPT_END == 15999

    def test_monitoring_range(self):
        """监控模块错误码范围 16000-16999"""
        assert error_codes.ERROR_CODE_RANGE_MONITORING_START == 16000
        assert error_codes.ERROR_CODE_RANGE_MONITORING_END == 16999


class TestCommonErrorCodes:
    """测试通用错误码"""

    def test_invalid_params(self):
        assert error_codes.COMMON_INVALID_PARAMS == 10001

    def test_missing_required_field(self):
        assert error_codes.COMMON_MISSING_REQUIRED_FIELD == 10002

    def test_unauthorized(self):
        assert error_codes.COMMON_UNAUTHORIZED == 10003

    def test_forbidden(self):
        assert error_codes.COMMON_FORBIDDEN == 10004

    def test_resource_not_found(self):
        assert error_codes.COMMON_RESOURCE_NOT_FOUND == 10005

    def test_duplicate_resource(self):
        assert error_codes.COMMON_DUPLICATE_RESOURCE == 10006

    def test_internal_error(self):
        assert error_codes.COMMON_INTERNAL_ERROR == 10007

    def test_service_unavailable(self):
        assert error_codes.COMMON_SERVICE_UNAVAILABLE == 10008

    def test_request_timeout(self):
        assert error_codes.COMMON_REQUEST_TIMEOUT == 10009

    def test_task_cancelled(self):
        assert error_codes.COMMON_TASK_CANCELLED == 10010


class TestAssessmentErrorCodes:
    """测试评估模块错误码"""

    def test_assessment_failed(self):
        assert error_codes.ASSESSMENT_FAILED == 11001

    def test_child_profile_invalid(self):
        assert error_codes.ASSESSMENT_CHILD_PROFILE_INVALID == 11002


class TestRagErrorCodes:
    """测试 RAG 模块错误码"""

    def test_document_not_found(self):
        assert error_codes.RAG_DOCUMENT_NOT_FOUND == 12001

    def test_unsupported_file_type(self):
        assert error_codes.RAG_UNSUPPORTED_FILE_TYPE == 12002

    def test_document_parse_failed(self):
        assert error_codes.RAG_DOCUMENT_PARSE_FAILED == 12003

    def test_index_not_available(self):
        assert error_codes.RAG_INDEX_NOT_AVAILABLE == 12004

    def test_chunk_not_found(self):
        assert error_codes.RAG_CHUNK_NOT_FOUND == 12005


class TestRagTestErrorCodes:
    """测试 RAG 测试模块错误码"""

    def test_test_case_not_found(self):
        assert error_codes.RAG_TEST_CASE_NOT_FOUND == 13001

    def test_test_set_not_found(self):
        assert error_codes.RAG_TEST_SET_NOT_FOUND == 13002

    def test_test_run_not_found(self):
        assert error_codes.RAG_TEST_RUN_NOT_FOUND == 13003

    def test_draft_not_found(self):
        assert error_codes.RAG_DRAFT_NOT_FOUND == 13004

    def test_report_not_found(self):
        assert error_codes.RAG_REPORT_NOT_FOUND == 13005

    def test_import_failed(self):
        assert error_codes.RAG_IMPORT_FAILED == 13006


class TestConfigErrorCodes:
    """测试配置管理模块错误码"""

    def test_config_validation_failed(self):
        assert error_codes.CONFIG_VALIDATION_FAILED == 14001

    def test_config_conflict(self):
        assert error_codes.CONFIG_CONFLICT == 14002

    def test_rollback_failed(self):
        assert error_codes.CONFIG_ROLLBACK_FAILED == 14003


class TestPromptErrorCodes:
    """测试提示词管理模块错误码"""

    def test_prompt_not_found(self):
        assert error_codes.PROMPT_NOT_FOUND == 15001

    def test_prompt_version_not_found(self):
        assert error_codes.PROMPT_VERSION_NOT_FOUND == 15002

    def test_prompt_test_failed(self):
        assert error_codes.PROMPT_TEST_FAILED == 15003

    def test_prompt_variable_invalid(self):
        assert error_codes.PROMPT_VARIABLE_INVALID == 15004


class TestMonitoringErrorCodes:
    """测试监控模块错误码"""

    def test_trace_not_found(self):
        assert error_codes.MONITORING_TRACE_NOT_FOUND == 16001

    def test_metric_not_available(self):
        assert error_codes.MONITORING_METRIC_NOT_AVAILABLE == 16002


class TestErrorCodeConsistency:
    """测试错误码与异常类的一致性"""

    def test_exception_codes_match_constants(self):
        """验证异常类的 code 与错误码常量一致"""
        from src.utils.exceptions import (
            InvalidParamsException,
            MissingRequiredFieldException,
            UnauthorizedException,
            ForbiddenException,
            ResourceNotFoundException,
            DuplicateResourceException,
            InternalServerErrorException,
            ServiceUnavailableException,
            RequestTimeoutException,
            TaskCancelledException,
        )

        assert InvalidParamsException().code == error_codes.COMMON_INVALID_PARAMS
        assert MissingRequiredFieldException().code == error_codes.COMMON_MISSING_REQUIRED_FIELD
        assert UnauthorizedException().code == error_codes.COMMON_UNAUTHORIZED
        assert ForbiddenException().code == error_codes.COMMON_FORBIDDEN
        assert ResourceNotFoundException().code == error_codes.COMMON_RESOURCE_NOT_FOUND
        assert DuplicateResourceException().code == error_codes.COMMON_DUPLICATE_RESOURCE
        assert InternalServerErrorException().code == error_codes.COMMON_INTERNAL_ERROR
        assert ServiceUnavailableException().code == error_codes.COMMON_SERVICE_UNAVAILABLE
        assert RequestTimeoutException().code == error_codes.COMMON_REQUEST_TIMEOUT
        assert TaskCancelledException().code == error_codes.COMMON_TASK_CANCELLED
