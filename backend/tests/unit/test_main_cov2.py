# -*- coding: utf-8 -*-
"""app.main 定向覆盖率测试：模型导入失败兜底/alembic分支/种子管理员posix分支/WAL调度异常/审计钩子失败reload"""

import importlib
import os
import sys
from unittest.mock import MagicMock, patch

import app.main as main_mod


# ---------- _init_database_tables：模型导入失败兜底（377-378, 380） ----------

def test_init_database_tables_model_import_failure():
    import app.models

    with patch.object(app.models, "__all__", ["BrokenA", "BrokenB"]), patch.object(
        app.models, "__getattr__", side_effect=ImportError("boom"), create=True
    ), patch("app.core.database.engine", MagicMock()), patch(
        "app.models.base.Base.metadata", new=MagicMock()
    ), patch.object(
        main_mod, "_run_alembic_upgrade"
    ), patch.object(
        main_mod, "_migrate_missing_columns"
    ) as mig, patch(
        "app.core.database_indexes.create_indexes"
    ) as ci, patch.object(
        main_mod.settings, "ENABLE_AUTO_MIGRATION", True
    ):
        main_mod._init_database_tables()
    mig.assert_called_once()
    ci.assert_called_once()


# ---------- _run_alembic_upgrade（413-414, 434-435） ----------

def _fake_path_tree(exists: bool):
    leaf = MagicMock()
    leaf.exists.return_value = exists
    P = MagicMock()
    P.return_value.resolve.return_value.parent.parent.__truediv__.return_value = leaf
    return P


def test_run_alembic_upgrade_no_ini():
    with patch.object(main_mod, "Path", _fake_path_tree(False)):
        main_mod._run_alembic_upgrade()  # 仅记录 info 后返回


def test_run_alembic_upgrade_exception_swallowed():
    with patch.object(main_mod, "Path", _fake_path_tree(True)), patch(
        "alembic.config.Config", side_effect=RuntimeError("cfg fail")
    ):
        main_mod._run_alembic_upgrade()  # 异常被吞并 warning


# ---------- _seed_default_admin：出厂默认密码分支 + 组织查询异常（652-653） ----------

def test_seed_default_admin_factory_password_and_org_failure():
    """未设置 DEFAULT_ADMIN_PASSWORD 时使用出厂默认密码 Admin@2026，
    不再生成临时密码文件（旧行为已移除）；组织查询失败不影响创建。"""
    q_user = MagicMock()
    q_user.filter.return_value = q_user
    q_user.first.return_value = None  # 无管理员 → 走创建分支
    db = MagicMock()
    db.query = MagicMock(side_effect=[q_user, RuntimeError("org fail")])

    lockout = MagicMock()
    lockout.unlock_expired.return_value = 0

    with patch("app.core.database.SessionLocal", return_value=db), patch(
        "app.services.lockout_service.get_lockout_service", return_value=lockout
    ), patch.dict(os.environ, {"DEFAULT_ADMIN_PASSWORD": ""}), patch(
        "tempfile.mkstemp"
    ) as mkstemp:
        main_mod._seed_default_admin()

    # 不再生成临时密码文件
    mkstemp.assert_not_called()
    # 创建了管理员并提交
    db.add.assert_called_once()
    admin = db.add.call_args[0][0]
    from app.core.security import verify_password

    assert verify_password("Admin@2026", admin.hashed_password)
    assert admin.must_change_password is True  # 强制首次登录改密
    db.commit.assert_called_once()
    db.close.assert_called_once()


# ---------- WAL checkpoint 调度异常分支（861-862, 870-871） ----------

def test_wal_checkpoint_start_failure():
    with patch(
        "app.services.db_maintenance.start_wal_checkpoint_scheduler",
        side_effect=RuntimeError("x"),
    ):
        main_mod._start_wal_checkpoint_scheduler()


def test_wal_checkpoint_stop_failure():
    with patch(
        "app.services.db_maintenance.stop_wal_checkpoint_scheduler",
        side_effect=RuntimeError("x"),
    ):
        main_mod._stop_wal_checkpoint_scheduler()


# ---------- 模块导入期：审计事件钩子失败兜底（152-153） ----------

def test_reload_main_with_audit_hook_failure():
    # test_main_app.py 的用例会重新 import app.main，使 sys.modules["app.main"]
    # 指向新模块对象；Python 3.11 的 reload 要求与 sys.modules 中对象同一，先还原。
    sys.modules["app.main"] = main_mod
    with patch(
        "app.services.audit_event_handler.setup_audit_events",
        side_effect=RuntimeError("hook fail"),
    ):
        importlib.reload(main_mod)
    assert main_mod.app is not None
