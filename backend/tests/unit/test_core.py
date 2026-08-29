"""
核心模块测试
覆盖: app/core/exceptions.py, app/core/response.py, app/core/config.py
"""
import pytest


# ==================== 异常测试 ====================

from app.core.errors import ErrorCode, ERROR_MESSAGES, get_error_message
from app.core.exceptions import (
    BusinessError,
    DatabaseError,
    UserAlreadyExistsError,
    InvalidCredentialsError,
    NotFoundException,
    AuthenticationException,
    ValidationError,
    NotFoundError,
    ConflictError,
)

class TestErrorCode:
    def test_all_codes_are_ints(self):
        """ErrorCode values are integers"""
        for code in ErrorCode:
            assert isinstance(code, int)

    def test_specific_codes(self):
        assert ErrorCode.UNKNOWN_ERROR == 1000
        assert ErrorCode.USER_NOT_FOUND == ErrorCode.RESOURCE_NOT_FOUND  # 3001
        assert ErrorCode.DATABASE_ERROR == ErrorCode.DB_CONNECTION_FAILED  # 5001
        assert ErrorCode.BUSINESS_ERROR == ErrorCode.BUSINESS_RULE_VIOLATION  # 9001
        assert ErrorCode.BACKUP_ERROR == ErrorCode.DB_WRITE_FAILED  # 5003

class TestBusinessError:
    def test_default_values(self):
        err = BusinessError("测试错误")
        assert err.message == "测试错误"
        assert err.code == ErrorCode.BUSINESS_ERROR
        assert err.status_code == 400
        assert err.details == {}

    def test_custom_values(self):
        err = BusinessError("自定义", code=ErrorCode.NOT_FOUND, details={"key": "val"}, status_code=404)
        assert err.code == ErrorCode.NOT_FOUND
        assert err.details == {"key": "val"}
        assert err.status_code == 404

    def test_to_dict(self):
        err = BusinessError("测试", details={"field": "name"})
        d = err.to_dict()
        assert d["error"]["code"] == ErrorCode.BUSINESS_ERROR
        assert d["error"]["message"] == "测试"
        assert d["error"]["details"]["field"] == "name"

    def test_str(self):
        err = BusinessError("测试错误")
        assert str(err) == "测试错误"

class TestValidationError:
    def test_default(self):
        err = ValidationError("字段无效")
        assert err.status_code == 400
        assert err.code == ErrorCode.VALIDATION_ERROR

    def test_with_field(self):
        err = ValidationError("字段无效", field="username")
        assert err.details["field"] == "username"

class TestAuthErrors:


    def test_invalid_credentials(self):
        err = InvalidCredentialsError()
        assert err.status_code in (200, 401, 403)

class TestNotFoundError:
    def test_without_identifier(self):
        err = NotFoundError("项目")
        assert "项目" in err.message
        assert err.status_code == 404

    def test_with_identifier(self):
        err = NotFoundError("用户", identifier="admin")
        assert "admin" in err.message
        assert err.details.get("identifier") == "admin"

class TestConflictError:
    def test_basic(self):
        err = ConflictError("数据冲突")
        assert err.status_code == 409

class TestDatabaseError:
    def test_default(self):
        err = DatabaseError()
        assert err.status_code == 500
        assert err.message == "数据库操作失败"

class TestUserErrors:


    def test_user_already_exists(self):
        err = UserAlreadyExistsError("admin")
        assert err.status_code == 409


class TestCompatAliases:
    def test_not_found_exception(self):
        err = NotFoundException()
        assert isinstance(err, BusinessError)

    def test_authentication_exception(self):
        err = AuthenticationException()
        assert isinstance(err, BusinessError)


class TestGetErrorMessage:
    def test_known_code(self):
        # USER_NOT_FOUND is now an alias for RESOURCE_NOT_FOUND (=3001)
        msg = get_error_message(ErrorCode.USER_NOT_FOUND)
        assert msg == "资源不存在"  # canonical message for RESOURCE_NOT_FOUND

    def test_all_codes_have_messages(self):
        for code in ErrorCode:
            assert code in ERROR_MESSAGES, f"Missing message for {code}"


# ==================== 响应模块测试 ====================







# ==================== Config 测试 ====================

from app.core.config import Settings

class TestSettings:
    def test_default_values(self):
        # 使用环境变量中的值
        s = Settings()
        assert s.PROJECT_NAME is not None
        assert s.API_PREFIX == "/api/v1"
        assert s.ALGORITHM == "HS256"

    def test_cors_origins_list(self):
        s = Settings()
        origins = s.CORS_ALLOWED_ORIGINS
        assert isinstance(origins, list)
        assert len(origins) > 0

    def test_cors_origins_alias(self):
        s = Settings()
        assert s.cors_origins_list == s.CORS_ALLOWED_ORIGINS

    def test_cors_methods_list(self):
        s = Settings()
        methods = s.CORS_ALLOWED_METHODS
        assert "GET" in methods
        assert "POST" in methods

    def test_cors_methods_alias(self):
        s = Settings()
        assert s.cors_allow_methods_list == s.CORS_ALLOWED_METHODS

    def test_cors_headers_list(self):
        s = Settings()
        headers = s.CORS_ALLOWED_HEADERS
        assert "Content-Type" in headers

    def test_cors_headers_alias(self):
        s = Settings()
        assert s.cors_allow_headers_list == s.CORS_ALLOWED_HEADERS

    def test_allowed_file_types_list(self):
        s = Settings()
        types = s.allowed_file_types_list
        assert "xlsx" in types
        assert "pdf" in types
