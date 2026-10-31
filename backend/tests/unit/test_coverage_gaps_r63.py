"""覆盖率收口（R63，2026-11-01）：main 最终段 99.98% 的四处未覆盖分支。

backend-test 的 `12/12` 段（`--cov-fail-under=100`）报出 4 处缺口，本文件逐条补定向用例：

1. `app/api/v1/deps.py` —— `authenticated_user_id` / `authenticated_username` 的
   fail-closed 分支（非法认证对象必须 401，而不是把 `None` 写进数据库）；
2. `app/services/machine_code_service.py` —— `get_organization_pass_codes` 的
   `organization_ids` 过滤分支（SEC-3 数据范围：部门级 admin 不得跨组织读通行码）；
3. `app/services/data_package_service.py` —— `decrypt_file_auto` 缺失时的
   `AttributeError` 兜底（旧版加密组件才提供该能力）；
4. `app/services/approval_workflow_service.py` —— `get_tasks_with_count` 的
   `date_to` 非零点分支（只有零点才把上界推到当日 23:59:59）。
"""

from __future__ import annotations

import zipfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from app.api.v1.deps import authenticated_user_id, authenticated_username


class TestAuthHelpersFailClosed:
    """认证对象取值出口：非法就 401，绝不把 None/非字符串写进服务层。"""

    def test_user_id_rejects_missing_id(self):
        with pytest.raises(HTTPException) as exc:
            authenticated_user_id(SimpleNamespace(id=None))
        assert exc.value.status_code == 401

    def test_user_id_rejects_non_int_id(self):
        with pytest.raises(HTTPException) as exc:
            authenticated_user_id(SimpleNamespace(id="7"))
        assert exc.value.status_code == 401

    def test_user_id_returns_int(self):
        assert authenticated_user_id(SimpleNamespace(id=7)) == 7

    def test_username_rejects_non_str(self):
        with pytest.raises(HTTPException) as exc:
            authenticated_username(SimpleNamespace(username=7))
        assert exc.value.status_code == 401

    def test_username_rejects_empty_str(self):
        with pytest.raises(HTTPException) as exc:
            authenticated_username(SimpleNamespace(username=""))
        assert exc.value.status_code == 401

    def test_username_returns_str(self):
        assert authenticated_username(SimpleNamespace(username="admin")) == "admin"


class TestOrganizationPassCodeScope:
    """organization_ids 过滤：传列表必须落到 SQL 的 IN 条件上。"""

    @staticmethod
    def _service():
        from app.services.machine_code_service import MachineCodeService

        db = MagicMock()
        query = MagicMock()
        db.query.return_value = query
        query.filter.return_value = query
        query.count.return_value = 0
        query.options.return_value = query
        query.order_by.return_value = query
        query.offset.return_value = query
        query.limit.return_value = query
        query.all.return_value = []
        return MachineCodeService(db=db), query

    def test_organization_ids_is_applied_as_in_filter(self):
        service, query = self._service()

        records, total = service.get_organization_pass_codes(organization_ids=[3, 4])

        assert (records, total) == ([], 0)
        rendered = [str(call.args[0]) for call in query.filter.call_args_list]
        assert any(" IN " in text for text in rendered), rendered

    def test_empty_organization_ids_still_filters(self):
        service, query = self._service()

        records, total = service.get_organization_pass_codes(organization_ids=[])

        assert (records, total) == ([], 0)
        assert len(query.filter.call_args_list) == 2


class TestEncryptedPackageWithoutAutoDecrypt:
    """加密组件没有 decrypt_file_auto 时，必须转成可读的业务错误。"""

    async def test_missing_decrypt_auto_raises_business_error(self):
        from app.core.exceptions import BusinessError
        from app.services.data_package_service import DataPackageService
        from app.services.password_encryption_service import PasswordEncryptionService

        with patch("app.services.data_package_service.os.makedirs"), patch(
            "app.utils.paths.get_app_data_dir", return_value=Path("/tmp/pkg")
        ):
            service = DataPackageService(db=MagicMock(), upload_dir="/tmp/uploads")
            service.logger = MagicMock()
            with patch("zipfile.ZipFile", side_effect=zipfile.BadZipFile("bad")), patch.object(
                PasswordEncryptionService, "decrypt_file_auto", None, create=True
            ):
                with pytest.raises(BusinessError, match="加密文件解析失败"):
                    await service.import_encrypted_package(
                        "/tmp/missing.zip", "missing.zip", 1, 1, password="secret"
                    )


class TestTaskQueryDateToBranch:
    """date_to 只在零点时把上界推到当日末，非零点必须按原值比较。"""

    @staticmethod
    def _service():
        from app.services.approval_workflow_service import ApprovalWorkflowService

        db = MagicMock()
        query = MagicMock()
        db.query.return_value = query
        for method in ("options", "filter", "order_by", "offset", "limit"):
            getattr(query, method).return_value = query
        query.count.return_value = 0
        query.all.return_value = []
        return ApprovalWorkflowService(db=db), query

    def test_date_to_with_explicit_time_keeps_value(self):
        service, _query = self._service()

        result = service.get_tasks_with_count(date_to="2026-08-01T10:30:00")

        assert result == {"items": [], "total": 0}

    def test_date_to_at_midnight_still_works(self):
        service, _query = self._service()

        result = service.get_tasks_with_count(date_to="2026-08-01")

        assert result == {"items": [], "total": 0}
