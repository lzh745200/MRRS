"""SEC-2 回归：全库 / 密钥 / 进程控制类操作必须仅超级管理员可执行。

背景（2026-10-31 审计）：这些端点的错误文案写的是"仅超级管理员"，实现却调用
``require_admin``，于是任意部门级 admin（role=admin, is_superuser=False）都能
下载/恢复全库备份、导出 PII 主密钥、关机。测试用「部门级 admin 必须 403」把
文案与实现钉死在一起。

本文件全部为直接函数调用（不启动 app / 不碰生产库），断言在权限检查处抛出
403 即返回，后续数据库/文件操作不会被执行。
"""

import asyncio
from types import SimpleNamespace

import pytest
from fastapi import BackgroundTasks, HTTPException

from app.core.permission_utils import (
    is_admin,
    is_superuser,
    require_admin,
    require_superuser,
)

SUPER_ADMIN = SimpleNamespace(id=1, username="root", role="super_admin", is_superuser=True)
# 部门级管理员：is_admin 为 True，但不是超级管理员（历史缺陷的放行主体）
DEPT_ADMIN = SimpleNamespace(id=2, username="dept", role="admin", is_superuser=False)
PLAIN_USER = SimpleNamespace(id=3, username="plain", role="user", is_superuser=False)


def _assert_403(fn, *args, **kwargs):
    with pytest.raises(HTTPException) as exc:
        fn(*args, **kwargs)
    assert exc.value.status_code == 403


def _assert_403_async(fn, *args, **kwargs):
    with pytest.raises(HTTPException) as exc:
        asyncio.run(fn(*args, **kwargs))
    assert exc.value.status_code == 403


# ---------------- require_superuser 语义 ----------------


def test_department_admin_is_admin_but_not_superuser():
    """前提：部门级 admin 仍应被 is_admin 放行（其它 40+ 调用点依赖该语义）。"""
    assert is_admin(DEPT_ADMIN) is True
    assert is_superuser(DEPT_ADMIN) is False


def test_require_superuser_rejects_department_admin():
    _assert_403(require_superuser, DEPT_ADMIN)


def test_require_superuser_accepts_super_admin():
    # 不抛异常即通过
    require_superuser(SUPER_ADMIN)


def test_require_superuser_accepts_role_flag_without_is_superuser():
    require_superuser(SimpleNamespace(role="super_admin", is_superuser=False))


def test_require_superuser_fails_closed_for_none_and_plain_user():
    _assert_403(require_superuser, None)
    _assert_403(require_superuser, PLAIN_USER)
    _assert_403(require_superuser, SimpleNamespace(role=None, is_superuser=False))


def test_require_superuser_decorator_mode_rejects_department_admin():
    @require_superuser
    async def endpoint(current_user=None):
        return "ok"

    with pytest.raises(HTTPException) as exc:
        asyncio.run(endpoint(current_user=DEPT_ADMIN))
    assert exc.value.status_code == 403

    assert asyncio.run(endpoint(current_user=SUPER_ADMIN)) == "ok"


def test_require_superuser_decorator_mode_401_when_no_user_present():
    """装饰器分支 must fail-closed：拿不到调用者身份 → 401 而非放行。"""

    @require_superuser
    async def endpoint():
        return "ok"

    with pytest.raises(HTTPException) as exc:
        asyncio.run(endpoint())
    assert exc.value.status_code == 401


def test_require_superuser_decorator_mode_scans_positional_args():
    """FastAPI 也允许把 current_user 作为位置参数传入 → args 扫描必须生效。"""

    @require_superuser
    async def endpoint(something, current_user):
        return "ok"

    assert asyncio.run(endpoint(None, SUPER_ADMIN)) == "ok"
    with pytest.raises(HTTPException) as exc:
        asyncio.run(endpoint(None, DEPT_ADMIN))
    assert exc.value.status_code == 403


def test_require_superuser_factory_mode():
    """require_superuser() 带参数形态（error_message）必须返回可用装饰器。"""
    decorator = require_superuser(error_message="只有超级管理员可以这样做")

    @decorator
    async def endpoint(current_user):
        return "ok"

    assert asyncio.run(endpoint(SUPER_ADMIN)) == "ok"
    with pytest.raises(HTTPException) as exc:
        asyncio.run(endpoint(DEPT_ADMIN))
    assert exc.value.status_code == 403


def test_require_admin_unchanged_for_department_admin():
    """回归保护：require_admin 不得被顺手收紧（40+ 端点依赖部门级 admin）。"""
    require_admin(DEPT_ADMIN)


# ---------------- 端点级：全库 / 密钥 / 进程控制 ----------------


def test_pii_key_export_rejects_department_admin():
    from app.api.v1.system.pii_key import export_pii_key

    _assert_403(export_pii_key, db=None, current_user=DEPT_ADMIN)


def test_pii_key_import_rejects_department_admin():
    from app.api.v1.system.pii_key import import_pii_key

    _assert_403(import_pii_key, body=SimpleNamespace(key="x" * 32), db=None, current_user=DEPT_ADMIN)


def test_backup_download_rejects_department_admin():
    from app.api.v1.system.backup import download_backup

    _assert_403_async(download_backup, filename="backup.zip", db=None, current_user=DEPT_ADMIN)


def test_backup_preview_rejects_department_admin():
    from app.api.v1.system.backup import preview_backup

    _assert_403_async(preview_backup, filename="backup.zip", db=None, current_user=DEPT_ADMIN)


def test_backup_restore_rejects_department_admin():
    from app.api.v1.system.backup import restore_backup

    _assert_403_async(
        restore_backup,
        body=SimpleNamespace(filename="backup.zip"),
        db=None,
        current_user=DEPT_ADMIN,
    )


def test_backup_verify_rejects_department_admin():
    from app.api.v1.system.backup import verify_backup

    _assert_403_async(verify_backup, filename="backup.zip", db=None, current_user=DEPT_ADMIN)


def test_shutdown_rejects_department_admin():
    from app.api.v1.system.system import shutdown_system

    _assert_403_async(shutdown_system, background_tasks=BackgroundTasks(), current_user=DEPT_ADMIN)


def test_restart_rejects_department_admin():
    from app.api.v1.system.system import restart_system

    _assert_403_async(restart_system, background_tasks=BackgroundTasks(), current_user=DEPT_ADMIN)


def test_super_admin_still_reaches_pii_key_export_business_logic():
    """超级管理员必须不被误拦（避免把门关死）：导出路径进入业务层，而非 403。"""
    from app.api.v1.system.pii_key import export_pii_key

    result = export_pii_key(db=None, current_user=SUPER_ADMIN)
    assert result is not None


# ---------------- SEC-4：审计日志销毁/改写同样仅超级管理员 ----------------


def test_audit_batch_delete_rejects_department_admin():
    from app.api.v1.system.audit import batch_delete_audit_logs

    _assert_403_async(
        batch_delete_audit_logs,
        body=SimpleNamespace(ids=[1], actions=None, action=None, before_date=None),
        current_user=DEPT_ADMIN,
        db=None,
    )


def test_audit_single_delete_rejects_department_admin():
    from app.api.v1.system.audit import delete_audit_log

    _assert_403_async(delete_audit_log, log_id=1, current_user=DEPT_ADMIN, db=None)


def test_audit_remark_update_rejects_department_admin():
    from app.api.v1.system.audit import update_audit_log_remark

    _assert_403_async(
        update_audit_log_remark,
        log_id=1,
        body=SimpleNamespace(remark="x"),
        current_user=DEPT_ADMIN,
        db=None,
    )
