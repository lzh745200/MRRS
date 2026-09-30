"""v1.12.9 覆盖率补口：app/api/v1/system/init.py 初始化失败必须中止（W15 深审）。

覆盖行（当前代码行号）：
- 152-175 创建超级管理员失败 → db.rollback() + 500，绝不继续 set_initialized：
  修复前只 warning 后继续，系统会被标记"已初始化"却没有任何超管，
  而 /initialize 不可重入 → 部署被永久锁死；
- 177-192 成功路径收尾（set_initialized + finalize 步骤 + 返回体）；
- 193-197 总体异常兜底 500，内部原因只进日志（W1-T8 错误细节不出站）；
- 246-266 初始化前检查清单端点。
"""

from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from app.api.v1.system import init as init_api


def _request():
    return init_api.InitRequest(
        organization_name="测试帮扶单位",
        admin_username="admin",
        admin_password="Str0ng!Passw0rd",
        admin_email="admin@test.com",
    )


class TestInitializeSystemAdminFailure:
    async def test_admin_creation_failure_aborts_and_never_marks_initialized(self):
        db = MagicMock()
        db.query.side_effect = RuntimeError("database is locked")
        svc = MagicMock()
        svc.is_initialized.return_value = False

        with patch.object(init_api, "SystemConfigService", return_value=svc), patch.object(
            init_api, "PasswordPolicy"
        ) as m_policy:
            m_policy.validate.return_value = (True, "")
            with pytest.raises(HTTPException) as ei:
                await init_api.initialize_system(_request(), db)

        assert ei.value.status_code == 500
        assert "超级管理员账号创建失败" in ei.value.detail
        svc.set_initialized.assert_not_called()
        db.rollback.assert_called_once()

    async def test_generic_failure_returns_sanitized_500(self):
        svc = MagicMock()
        svc.is_initialized.side_effect = RuntimeError("config table missing")
        with patch.object(init_api, "SystemConfigService", return_value=svc):
            with pytest.raises(HTTPException) as ei:
                await init_api.initialize_system(_request(), MagicMock())
        assert ei.value.status_code == 500
        assert ei.value.detail == "系统初始化失败，请稍后重试或联系管理员"
        assert "config table missing" not in ei.value.detail

    async def test_already_initialized_rejected(self):
        svc = MagicMock()
        svc.is_initialized.return_value = True
        with patch.object(init_api, "SystemConfigService", return_value=svc):
            with pytest.raises(HTTPException) as ei:
                await init_api.initialize_system(_request(), MagicMock())
        assert ei.value.status_code == 400
        svc.set_initialized.assert_not_called()


class TestInitializeSystemSuccess:
    async def test_full_success_path_finalizes(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        svc = MagicMock()
        svc.is_initialized.return_value = False

        with patch.object(init_api, "SystemConfigService", return_value=svc), patch.object(
            init_api, "PasswordPolicy"
        ) as m_policy, patch.object(init_api, "safe_commit") as m_commit, patch(
            "app.core.security.get_password_hash", return_value="hashed-pw"
        ):
            m_policy.validate.return_value = (True, "")
            result = await init_api.initialize_system(_request(), db)

        assert result["success"] is True
        assert result["data"]["admin_username"] == "admin"
        steps = {s["step"]: s["status"] for s in result["data"]["steps"]}
        assert steps["admin_user"] == "success"
        assert steps["finalize"] == "success"
        svc.set_initialized.assert_called_once_with(org_id=1)
        db.add.assert_called_once()
        m_commit.assert_called_once_with(db)

    async def test_existing_admin_skipped_step(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = MagicMock()
        svc = MagicMock()
        svc.is_initialized.return_value = False

        with patch.object(init_api, "SystemConfigService", return_value=svc), patch.object(
            init_api, "PasswordPolicy"
        ) as m_policy, patch.object(init_api, "safe_commit"), patch(
            "app.core.security.get_password_hash", return_value="hashed-pw"
        ):
            m_policy.validate.return_value = (True, "")
            result = await init_api.initialize_system(_request(), db)

        steps = {s["step"]: s["status"] for s in result["data"]["steps"]}
        assert steps["admin_user"] == "skipped"
        db.add.assert_not_called()


class TestInitChecklist:
    async def test_checklist_returns_all_items(self):
        result = await init_api.get_init_checklist()
        assert result["success"] is True
        checklist = result["data"]["checklist"]
        assert len(checklist) == 8
        assert all({"item", "required"} <= set(row) for row in checklist)
