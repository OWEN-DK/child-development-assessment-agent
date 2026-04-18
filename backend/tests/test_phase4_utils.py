"""Phase 4 测试：冗余代码消除 - 工具模块

测试所有新创建的工具函数。
"""

import os
import tempfile
from datetime import datetime, timezone, timedelta
from enum import Enum
from pathlib import Path

import pytest

from src.utils.response import handle_api_error, not_found, server_error, require
from src.utils.serializers import safe_isoformat, safe_enum_value, model_to_dict
from src.utils.file_ops import ensure_dir, safe_remove, read_json, write_json, read_text, write_text, file_exists, dir_exists
from src.utils.time_utils import utc_now, time_range, safe_timestamp, add_time, is_expired, format_duration
from src.utils.crypto import hash_content, hash_file, generate_token
from src.utils.id_generator import generate_id, generate_short_id, generate_prefixed_id, is_valid_uuid
from src.utils.auth_helpers import get_user_id, get_username, is_authenticated, require_auth
from src.utils.exceptions import (
    InternalServerErrorException,
    ResourceNotFoundException,
    UnauthorizedException,
    ForbiddenException,
)


class TestResponseUtils:
    """测试响应与错误处理工具"""

    def test_handle_api_error_with_detail(self):
        with pytest.raises(InternalServerErrorException) as exc_info:
            handle_api_error(ValueError("test error"), "获取数据")
        assert exc_info.value.status_code == 500
        assert "获取数据失败" in exc_info.value.message
        assert "test error" in exc_info.value.message

    def test_handle_api_error_without_detail(self):
        with pytest.raises(InternalServerErrorException) as exc_info:
            handle_api_error(ValueError("test error"), "获取数据", include_detail=False)
        assert exc_info.value.message == "获取数据失败"

    def test_not_found(self):
        with pytest.raises(ResourceNotFoundException) as exc_info:
            not_found("测试用例", {"id": "123"})
        assert exc_info.value.status_code == 404
        assert exc_info.value.error_code == "测试用例_NOT_FOUND"
        assert exc_info.value.details == {"id": "123"}

    def test_server_error(self):
        with pytest.raises(InternalServerErrorException) as exc_info:
            server_error("自定义错误")
        assert exc_info.value.message == "自定义错误"

    def test_require_success(self):
        require(True, ForbiddenException())

    def test_require_failure(self):
        with pytest.raises(ForbiddenException):
            require(False, ForbiddenException())


class StatusEnum(Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"


class TestSerializers:
    """测试序列化工具"""

    def test_safe_isoformat_none(self):
        assert safe_isoformat(None) is None

    def test_safe_isoformat_datetime(self):
        dt = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        result = safe_isoformat(dt)
        assert result == "2024-01-01T12:00:00+00:00"

    def test_safe_isoformat_date(self):
        from datetime import date
        d = date(2024, 1, 1)
        result = safe_isoformat(d)
        assert result == "2024-01-01"

    def test_safe_enum_value_none(self):
        assert safe_enum_value(None) is None

    def test_safe_enum_value(self):
        result = safe_enum_value(StatusEnum.ACTIVE)
        assert result == "active"

    def test_model_to_dict_with_fields(self):
        class MockModel:
            def __init__(self):
                self.id = 1
                self.name = "test"
                self.created_at = datetime(2024, 1, 1, tzinfo=timezone.utc)
                self.status = StatusEnum.ACTIVE

        model = MockModel()
        result = model_to_dict(model, fields={
            "id": None,
            "name": None,
            "created_at": safe_isoformat,
            "status": safe_enum_value,
        })
        assert result["id"] == 1
        assert result["name"] == "test"
        assert result["created_at"] == "2024-01-01T00:00:00+00:00"
        assert result["status"] == "active"

    def test_model_to_dict_auto(self):
        class MockModel:
            def __init__(self):
                self.id = 1
                self.name = "test"
                self._sa_instance_state = "internal"

        model = MockModel()
        result = model_to_dict(model)
        assert result["id"] == 1
        assert result["name"] == "test"
        assert "_sa_instance_state" not in result


class TestFileOps:
    """测试文件操作工具"""

    def test_ensure_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            new_dir = Path(tmpdir) / "a" / "b" / "c"
            result = ensure_dir(new_dir)
            assert result.exists()
            assert result.is_dir()

    def test_safe_remove_exists(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "test.txt"
            file_path.write_text("test")
            assert safe_remove(file_path) is True
            assert not file_path.exists()

    def test_safe_remove_not_exists(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "nonexistent.txt"
            assert safe_remove(file_path) is False

    def test_read_json_not_exists(self):
        result = read_json("/nonexistent/path.json", default={"key": "value"})
        assert result == {"key": "value"}

    def test_read_write_json(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "test.json"
            data = {"name": "测试", "value": 123}
            write_json(file_path, data)
            result = read_json(file_path)
            assert result == data

    def test_read_text_not_exists(self):
        result = read_text("/nonexistent/path.txt", default="default")
        assert result == "default"

    def test_read_write_text(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "test.txt"
            content = "测试内容"
            write_text(file_path, content)
            result = read_text(file_path)
            assert result == content

    def test_file_exists(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "test.txt"
            file_path.write_text("test")
            assert file_exists(file_path) is True
            assert file_exists(Path(tmpdir) / "nonexistent.txt") is False

    def test_dir_exists(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            assert dir_exists(tmpdir) is True
            assert dir_exists(Path(tmpdir) / "nonexistent") is False


class TestTimeUtils:
    """测试时间处理工具"""

    def test_utc_now(self):
        now = utc_now()
        assert now.tzinfo == timezone.utc

    def test_time_range(self):
        start, end = time_range(days=7)
        assert end > start
        assert (end - start).days == 7

    def test_safe_timestamp_none(self):
        assert safe_timestamp(None) is None

    def test_safe_timestamp(self):
        dt = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        result = safe_timestamp(dt)
        assert result == "2024-01-01T12:00:00+00:00"

    def test_add_time(self):
        dt = datetime(2024, 1, 1, tzinfo=timezone.utc)
        result = add_time(dt, days=1, hours=2)
        assert result == datetime(2024, 1, 2, 2, 0, 0, tzinfo=timezone.utc)

    def test_is_expired_false(self):
        dt = utc_now()
        assert is_expired(dt, ttl_seconds=3600) is False

    def test_is_expired_true(self):
        dt = utc_now() - timedelta(hours=2)
        assert is_expired(dt, ttl_seconds=3600) is True

    def test_format_duration_ms(self):
        assert format_duration(0.5) == "500ms"

    def test_format_duration_seconds(self):
        assert format_duration(30.5) == "30.5s"

    def test_format_duration_minutes(self):
        assert format_duration(125) == "2m 5s"

    def test_format_duration_hours(self):
        assert format_duration(3661) == "1h 1m"


class TestCrypto:
    """测试加密哈希工具"""

    def test_hash_content_string(self):
        result1 = hash_content("test")
        result2 = hash_content("test")
        assert result1 == result2
        assert len(result1) == 64

    def test_hash_content_bytes(self):
        result = hash_content(b"test")
        assert len(result) == 64

    def test_hash_content_different(self):
        result1 = hash_content("test1")
        result2 = hash_content("test2")
        assert result1 != result2

    def test_hash_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "test.txt"
            file_path.write_text("test content")
            result = hash_file(str(file_path))
            assert len(result) == 64

    def test_generate_token(self):
        token = generate_token(32)
        assert len(token) == 64
        token2 = generate_token(32)
        assert token != token2


class TestIdGenerator:
    """测试 ID 生成工具"""

    def test_generate_id(self):
        id1 = generate_id()
        id2 = generate_id()
        assert len(id1) == 36
        assert id1 != id2

    def test_generate_short_id(self):
        short_id = generate_short_id()
        assert len(short_id) == 8

    def test_generate_prefixed_id(self):
        prefixed = generate_prefixed_id("task")
        assert prefixed.startswith("task_")
        assert len(prefixed) > 5

    def test_is_valid_uuid_true(self):
        assert is_valid_uuid("550e8400-e29b-41d4-a716-446655440000") is True

    def test_is_valid_uuid_false(self):
        assert is_valid_uuid("not-a-uuid") is False


class TestAuthHelpers:
    """测试认证辅助工具"""

    def test_get_user_id_none(self):
        assert get_user_id(None) == "system"

    def test_get_user_id_with_id(self):
        class MockUser:
            id = "user123"
            username = "testuser"
        assert get_user_id(MockUser()) == "user123"

    def test_get_user_id_without_id(self):
        class MockUser:
            username = "testuser"
        assert get_user_id(MockUser()) == "testuser"

    def test_get_username_none(self):
        assert get_username(None) == "system"

    def test_get_username(self):
        class MockUser:
            username = "testuser"
        assert get_username(MockUser()) == "testuser"

    def test_is_authenticated_none(self):
        assert is_authenticated(None) is False

    def test_is_authenticated(self):
        assert is_authenticated(object()) is True

    def test_require_auth_none(self):
        with pytest.raises(UnauthorizedException):
            require_auth(None)

    def test_require_auth(self):
        require_auth(object())
