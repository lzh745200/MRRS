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
    AuthenticationError,
    AuthorizationError,
    NotFoundError,
    ConflictError,
    UserNotFoundError,
    UserLockedError,
    PasswordValidationError,
    FileUploadError,
    BackupError,
    RestoreError,
    BackupNotFoundError,
    ForbiddenException,
    exc_paginated_response,
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
    def test_authentication_error(self):
        err = AuthenticationError()
        assert err.status_code in (200, 401, 403)
        assert err.message == "认证失败"

    def test_authorization_error(self):
        err = AuthorizationError()
        assert err.status_code in (200, 401, 403, 404)
        assert err.message == "权限不足"

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
    def test_user_not_found(self):
        err = UserNotFoundError("admin")
        assert "用户" in err.message
        assert err.status_code == 404

    def test_user_not_found_no_username(self):
        err = UserNotFoundError()
        assert "用户" in err.message

    def test_user_already_exists(self):
        err = UserAlreadyExistsError("admin")
        assert err.status_code == 409

    def test_user_locked_with_time(self):
        err = UserLockedError("5分钟")
        assert "5分钟" in err.message
        assert err.status_code in (200, 401, 403, 404)

    def test_user_locked_without_time(self):
        err = UserLockedError()
        assert "锁定" in err.message

class TestPasswordValidationError:
    def test_basic(self):
        err = PasswordValidationError("密码太弱")
        assert err.message == "密码太弱"
        assert err.status_code == 400

class TestFileUploadError:
    def test_basic(self):
        err = FileUploadError("文件过大", details={"max_size": "10MB"})
        assert err.status_code == 400
        assert err.details["max_size"] == "10MB"

class TestBackupErrors:
    def test_backup_error(self):
        err = BackupError()
        assert err.status_code == 500

    def test_restore_error(self):
        err = RestoreError()
        assert err.status_code == 500

    def test_backup_not_found(self):
        err = BackupNotFoundError()
        assert err.status_code == 404

class TestCompatAliases:
    def test_not_found_exception(self):
        err = NotFoundException()
        assert isinstance(err, BusinessError)

    def test_authentication_exception(self):
        err = AuthenticationException()
        assert isinstance(err, BusinessError)

    def test_forbidden_exception(self):
        err = ForbiddenException()
        assert isinstance(err, BusinessError)

class TestGetErrorMessage:
    def test_known_code(self):
        # USER_NOT_FOUND is now an alias for RESOURCE_NOT_FOUND (=3001)
        msg = get_error_message(ErrorCode.USER_NOT_FOUND)
        assert msg == "资源不存在"  # canonical message for RESOURCE_NOT_FOUND

    def test_all_codes_have_messages(self):
        for code in ErrorCode:
            assert code in ERROR_MESSAGES, f"Missing message for {code}"

class TestExcPaginatedResponse:
    def test_basic(self):
        result = exc_paginated_response([1, 2, 3], total=10, page=1, page_size=3)
        assert result["items"] == [1, 2, 3]
        assert result["total"] == 10
        assert result["page"] == 1

# ==================== 响应模块测试 ====================

from app.core.response import (
    PaginationMeta,
    success_response,
    paginated_response,
    error_response,
    validation_error_response,
    not_found_response,
    unauthorized_response,
    forbidden_response,
    server_error_response,
    ApiResponse,
    ErrorDetail,
)

class TestPaginationMeta:
    def test_from_pagination(self):
        meta = PaginationMeta.from_pagination(page=1, page_size=10, total=25)
        assert meta.page == 1
        assert meta.page_size == 10
        assert meta.total == 25
        assert meta.total_pages == 3
        assert meta.has_next is True
        assert meta.has_prev is False

    def test_last_page(self):
        meta = PaginationMeta.from_pagination(page=3, page_size=10, total=25)
        assert meta.has_next is False
        assert meta.has_prev is True

    def test_single_page(self):
        meta = PaginationMeta.from_pagination(page=1, page_size=10, total=5)
        assert meta.total_pages == 1
        assert meta.has_next is False
        assert meta.has_prev is False

    def test_empty_result(self):
        meta = PaginationMeta.from_pagination(page=1, page_size=10, total=0)
        assert meta.total_pages == 0

    def test_zero_page_size(self):
        meta = PaginationMeta.from_pagination(page=1, page_size=0, total=10)
        assert meta.total_pages == 0

class TestSuccessResponse:
    def test_default(self):
        resp = success_response()
        assert resp["code"] == 200
        assert resp["message"] == "success"
        assert resp["success"] is True
        assert "data" not in resp

    def test_with_data(self):
        resp = success_response(data={"key": "value"}, message="ok")
        assert resp["data"]["key"] == "value"
        assert resp["message"] == "ok"

    def test_with_pagination(self):
        pagination = PaginationMeta.from_pagination(1, 10, 50)
        resp = paginated_response(data=[1, 2], pagination=pagination)
        assert "pagination" in resp["meta"]

    def test_with_request_id(self):
        resp = success_response(request_id="req-123")
        assert resp["request_id"] == "req-123"

class TestPaginatedResponse:
    def test_basic(self):
        pagination = PaginationMeta.from_pagination(1, 10, 3)
        resp = paginated_response(data=[1, 2, 3], pagination=pagination)
        assert resp["data"] == [1, 2, 3]
        assert "pagination" in resp["meta"]

class TestErrorResponse:
    def test_basic(self):
        resp = error_response(message="出错了", code=400)
        assert resp["code"] == 400
        assert resp["message"] == "出错了"

    def test_with_errors(self):
        resp = error_response(message="验证失败", errors=[{"field": "name"}])
        assert len(resp["errors"]) == 1

    def test_validation_error_response(self):
        resp = validation_error_response([{"field": "email", "message": "无效"}])
        assert resp["code"] == 422

    def test_not_found_response(self):
        resp = not_found_response("项目")
        assert resp["code"] == 404
        assert "项目" in resp["message"]

    def test_unauthorized_response(self):
        resp = unauthorized_response()
        assert resp["code"] in (200, 401, 403)

    def test_forbidden_response(self):
        resp = forbidden_response()
        assert resp["code"] in (200, 401, 403, 404)

    def test_server_error_response(self):
        resp = server_error_response()
        assert resp["code"] == 500

class TestApiResponseModel:
    def test_success_method(self):
        resp = ApiResponse.success()
        assert resp["code"] == 200
        assert resp["message"] == "success"

    def test_error_detail_dataclass(self):
        detail = ErrorDetail(field="name", message="必填", type="REQUIRED")
        assert detail.field == "name"
        assert detail.type == "REQUIRED"

    def test_error_response_function(self):
        resp = error_response(code=400, message="bad request")
        assert resp["code"] == 400

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
