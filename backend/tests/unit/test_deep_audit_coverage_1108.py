"""2026-11-08 深度审计修复的覆盖率补测（R61 收口）。

这些用例只做两件事：
1. 把本轮新增的安全/正确性分支真正跑起来（不是为覆盖率而覆盖率：
   例如政策批量删除的 FTS/工作日志失败降级、备份恢复失败后的回滚、
   数据包“部分写入失败必须整体失败”、帮扶村软删复活、权限包越权边界）。
2. 对少数环境异常分支（连接池释放失败、-wal 清理失败、子树叶解析失败）
   验证“记录日志但不阻断主流程”的既有契约。
"""

from __future__ import annotations

import asyncio
import json
import os
import zipfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from app.api.v1 import policy as policy_mod
from app.api.v1 import projects as projects_mod
from app.api.v1.data.data import reports as reports_mod
from app.services.backup_service import BackupRestoreError, BackupService
from app.services.data_package_service import DataPackageService
from app.services.excel_importer_service import ExcelImporterService
from app.services.permission_package_service import PermissionPackageService
from app.models.project import Project
from app.models.supported_village import SupportedVillage


def _run(coro):
    # 不要用 asyncio.get_event_loop()：pytest-asyncio 会关闭 loop，
    # 分段全量里再取会抛 "There is no current event loop in thread 'MainThread'"。
    return asyncio.run(coro)


# ── reports：输出目录限制 ──────────────────────────────────────────────


def test_safe_output_dir_commonpath_error_returns_400(monkeypatch):
    """commonpath 在跨盘（Windows）或异常路径下抛 ValueError 时必须 fail-closed 返回 400。

    该分支在 Linux CI 上无法用真实路径触发（无盘符概念），因此直接注入 ValueError，
    保证两个平台对同一安全兜底都有覆盖。
    """
    import os as _os

    monkeypatch.setattr("app.utils.paths.get_runtime_uploads_path", lambda: Path("/base"))

    def _boom(_paths):
        raise ValueError("different drives")

    monkeypatch.setattr(_os.path, "commonpath", _boom)
    with pytest.raises(HTTPException) as exc:
        reports_mod._safe_output_dir("/evil")
    assert exc.value.status_code == 400


def test_update_subscription_applies_output_dir(tmp_path, monkeypatch):
    monkeypatch.setattr("app.utils.paths.get_runtime_uploads_path", lambda: tmp_path)
    db = MagicMock()
    sub = SimpleNamespace(
        id=5, user_id=1, name="n", report_type="summary", format="excel", year=2026,
        village_ids=None, include_sections=None, frequency="weekly", send_day=1,
        send_time="08:00", email="", output_dir=None, output_format="excel",
        is_active=False, last_sent_at=None, created_at=None, updated_at=None,
    )
    db.query.return_value.filter.return_value.first.return_value = sub
    update = SimpleNamespace(model_dump=lambda exclude_unset=True: {"output_dir": str(tmp_path / "out")})
    with patch("app.api.v1.data.data.reports.safe_commit"), patch(
        "app.api.v1.data.data.reports.json.dumps", side_effect=lambda v: json.dumps(v)
    ):
        _run(reports_mod.update_subscription(5, update, SimpleNamespace(id=1), db))
    assert sub.output_dir == str(tmp_path / "out")


# ── policy：分类写操作仅管理员；批量删除降级分支 ─────────────────────


@pytest.mark.parametrize("handler", ["create", "update", "delete"])
def test_policy_category_writes_require_admin(handler):
    user = SimpleNamespace(id=1, role="user", username="u")
    db = MagicMock()
    with patch("app.core.permission_utils.is_admin", return_value=False):
        if handler == "create":
            coro = policy_mod.create_category(SimpleNamespace(code=None), current_user=user, db=db)
        elif handler == "update":
            coro = policy_mod.update_category(
                1,
                SimpleNamespace(model_dump=lambda exclude_unset=True: {}),
                current_user=user,
                db=db,
            )
        else:
            coro = policy_mod.delete_category(1, current_user=user, db=db)
        with pytest.raises(HTTPException) as exc:
            _run(coro)
    assert exc.value.status_code == 403


def test_batch_delete_policy_degrades_when_fts_and_log_fail():
    user = SimpleNamespace(id=1, role="admin", username="admin", is_superuser=True)
    policy = SimpleNamespace(id=7, title="p", is_active=True, created_by=1)
    db = MagicMock()
    db.query.return_value.filter.return_value.all.return_value = [policy]
    data = {"ids": [7]}

    with patch.object(policy_mod, "_assert_policy_writable"), patch.object(
        policy_mod, "safe_commit"
    ), patch.object(policy_mod, "_invalidate_policy_list_cache", new=AsyncMock()), patch(
        "app.services.policy_fts_service.remove_policy_from_fts", side_effect=RuntimeError("fts")
    ), patch.object(policy_mod, "write_work_log", side_effect=RuntimeError("log")), patch.object(
        policy_mod, "submit_entity_change_approval", return_value=1
    ):
        result = _run(policy_mod.batch_delete_policies(data, user, db))

    assert policy.is_active is False
    assert result["success"] is True


# ── projects：village_id 必须落在数据域内 ────────────────────────────


def test_create_project_village_out_of_scope_404():
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None
    data = SimpleNamespace(code=None, village_id=99)
    scoped = MagicMock()
    scoped.first.return_value = None
    with patch("app.services.data_scope_query.scoped_filter", return_value=scoped):
        with pytest.raises(Exception) as exc:
            _run(projects_mod.create_project(data, None, SimpleNamespace(id=1), db))
    assert getattr(exc.value, "status_code", None) == 404 or "帮扶村" in str(exc.value)


# ── backup：回滚/迁移失败分支 ────────────────────────────────────────


def _svc(tmp_path: Path) -> BackupService:
    svc = BackupService(db=MagicMock(), backup_dir=str(tmp_path / "bk"))
    svc.database_path = str(tmp_path / "db.sqlite")
    svc.uploads_dir = str(tmp_path / "uploads")
    return svc


def test_rollback_without_snapshot_restores_uploads(tmp_path):
    svc = _svc(tmp_path)
    os.makedirs(svc.uploads_dir, exist_ok=True)
    (Path(svc.uploads_dir) / "old.txt").write_text("old", encoding="utf-8")
    snap_up = tmp_path / "snap_up"
    os.makedirs(snap_up, exist_ok=True)
    (snap_up / "new.txt").write_text("new", encoding="utf-8")

    svc._rollback_to_snapshots(str(tmp_path / "missing.db"), str(snap_up))

    assert (Path(svc.uploads_dir) / "new.txt").read_text(encoding="utf-8") == "new"
    assert not (Path(svc.uploads_dir) / "old.txt").exists()


def test_rollback_logs_dispose_and_wal_cleanup_failures(tmp_path):
    svc = _svc(tmp_path)
    snap_db = tmp_path / "snap.db"
    snap_db.write_text("snap", encoding="utf-8")
    Path(svc.database_path).write_text("orig", encoding="utf-8")
    Path(str(svc.database_path) + "-wal").write_text("wal", encoding="utf-8")

    with patch("app.core.database.engine") as eng, patch("os.unlink", side_effect=OSError("busy")):
        eng.dispose.side_effect = RuntimeError("dispose")
        svc._rollback_to_snapshots(str(snap_db), None)

    assert Path(svc.database_path).read_text(encoding="utf-8") == "snap"


def test_restore_backup_rolls_back_when_migration_fails(tmp_path):
    bdir = tmp_path / "backups"
    os.makedirs(bdir)
    db_path = tmp_path / "data" / "rural_revitalization.db"
    os.makedirs(db_path.parent)
    db_path.write_text("orig", encoding="utf-8")
    up_dir = tmp_path / "uploads"
    os.makedirs(up_dir)
    zip_path = bdir / "b.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("data/rural_revitalization.db", b"not-a-real-db")

    with patch("app.utils.paths.get_database_path", return_value=db_path), patch(
        "app.utils.paths.get_uploads_path", return_value=up_dir
    ), patch("app.utils.paths.get_runtime_uploads_path", return_value=up_dir), patch(
        "os.getenv", side_effect=lambda k, d=None: {"INCREMENTAL_BACKUP_ENABLED": "false"}.get(k, d)
    ), patch("os.makedirs"):
        svc = BackupService(db=MagicMock(), backup_dir=str(bdir))
    svc.database_path = str(db_path)
    svc.uploads_dir = str(up_dir)

    with patch.object(svc, "_enforce_key_fingerprint", return_value=None), patch.object(
        svc, "_create_snapshots", return_value=(None, None)
    ), patch.object(svc, "_validate_backup_schema_version"), patch.object(
        svc, "_restore_database_from_backup"
    ) as mock_restore, patch.object(svc, "_migrate_restored_database", side_effect=RuntimeError("mig")), patch.object(
        svc, "_rollback_to_snapshots"
    ) as mock_rollback:
        def _restore(_temp):
            svc._db_replaced = True
            return True

        mock_restore.side_effect = _restore
        with pytest.raises(BackupRestoreError):
            svc.restore_backup(str(zip_path))

    mock_rollback.assert_called_once()


# ── data_package：部分写入失败整体失败 + ISO 解析兜底 ────────────────


def test_confirm_import_bulk_errors_fail_whole_package():
    svc = DataPackageService(db=MagicMock(), upload_dir="/tmp/uploads")
    pkg = MagicMock()
    pkg.id = 1
    pkg.status = "validated"
    pkg.org_id = 1
    pkg.file_path = "/tmp/test.zip"
    svc.db.query.return_value.filter.return_value.first.return_value = pkg

    with patch("app.services.data_package_service.db_coordinator.exclusive_write") as excl, patch(
        "zipfile.ZipFile"
    ) as mock_zip:
        excl.return_value.__enter__ = MagicMock()
        excl.return_value.__exit__ = MagicMock(return_value=False)
        m = MagicMock()
        mock_zip.return_value.__enter__ = MagicMock(return_value=m)
        mock_zip.return_value.__exit__ = MagicMock(return_value=False)
        m.read.side_effect = [
            json.dumps({"data_types": ["villages"], "org_code": ""}).encode("utf-8"),
            json.dumps([{"id": 1, "village_name": "v1"}]).encode("utf-8"),
        ]
        m.namelist.return_value = ["manifest.json", "data/villages.json"]
        with patch.object(svc, "_bulk_upsert_records", return_value=(0, 0, [MagicMock()])):
            result = _run(svc.confirm_import(1, 1))

    assert result.success is False
    svc.db.rollback.assert_called()


def test_clean_import_record_invalid_iso_datetime_kept_as_text():
    svc = DataPackageService(db=MagicMock(), upload_dir="/tmp/uploads")
    out = svc._clean_import_record(
        {"name": "2026-13-45T99:99"}, {"name"}, 1, 0, Project
    )
    assert out["name"] == "2026-13-45T99:99"


# ── excel importer：prefecture 映射 / 软删复活 / 空名跳过 ────────────


def test_apply_update_maps_prefecture_and_revives():
    svc = ExcelImporterService(db=MagicMock(), current_user=None)
    village = SupportedVillage(village_name="v", is_active=False)
    svc._apply_update(village, {"village_name": "v", "prefecture": "黔南州"})
    assert village.city == "黔南州"
    assert village.is_active is True


def test_apply_update_skips_instance_without_is_active_column():
    svc = ExcelImporterService(db=MagicMock(), current_user=None)
    instance = SimpleNamespace()
    instance.__table__ = SimpleNamespace(columns={"name": MagicMock()})
    svc.db.flush = MagicMock()
    svc._apply_update(instance, {"name": "v"})
    assert instance.name == "v"


def test_incremental_import_revives_soft_deleted_same_name():
    db = MagicMock()
    svc = ExcelImporterService(db=db, current_user=None)
    svc.validator = MagicMock()
    svc.validator.convert_row_types.side_effect = lambda r: r
    existing = SupportedVillage(village_name="同一个村", is_active=False)
    existing.id = 9
    # 历史脏行（村名为空）也必须被安全跳过，不能进入 active/inactive 映射
    empty_named = SupportedVillage(village_name="")
    db.query.return_value.filter.return_value.all.return_value = [empty_named, existing]
    result = MagicMock()
    result.success_rows = 0
    result.created_ids = []

    with patch.object(svc, "_apply_update") as apply_update:
        svc._import_incremental_mode([{"village_name": "同一个村"}], result, None)

    apply_update.assert_called_once()
    assert result.success_rows == 1


def test_create_village_maps_prefecture_to_city():
    svc = ExcelImporterService(db=MagicMock(), current_user=None)
    village = svc._create_village({"village_name": "测试村", "prefecture": "黔南州"})
    assert village.city == "黔南州"
    svc.db.add.assert_called_once()


# ── permission package：越权边界 ─────────────────────────────────────


def test_permission_package_full_replace_requires_privileged(tmp_path):
    svc = PermissionPackageService(db=MagicMock())
    pkg = tmp_path / "perm.zip"
    with zipfile.ZipFile(pkg, "w") as zf:
        zf.writestr("manifest.json", "{}")
    out = svc.confirm_import(
        str(pkg), overwrite_existing=True, mode=None, allow_privileged=False, caller=SimpleNamespace(id=1)
    )
    assert out["success"] is False
    assert "合并模式" in out["message"]


def _legacy_user(**kw):
    user = SimpleNamespace(id=2, username="bob", role="user", organization_id=1)
    for k, v in kw.items():
        setattr(user, k, v)
    return user


def test_import_legacy_blocks_self_and_wildcard_and_foreign_org():
    svc = PermissionPackageService(db=MagicMock())
    caller = SimpleNamespace(id=2, organization_id=1)
    user = _legacy_user(id=2)
    stats: dict = {}
    errors: list = []

    with patch.object(svc, "_resolve_user_by_username_or_id", return_value=user), patch.object(
        svc, "_sanitize_legacy_privilege", return_value=("user", "org")
    ), patch("app.core.data_permission._get_org_subtree", return_value=([1], {})), patch.object(
        svc, "_clear_existing_data"
    ):
        svc._import_user_legacy(
            [{"username": "bob", "permissions": "*:*"}], stats, errors, merge_mode=True,
            allow_privileged=False, caller=caller,
        )
    assert any("调用者自身" in e for e in errors)

    # 目标组织在子树外：应拒绝写入
    user2 = _legacy_user(id=3, username="carol")
    svc2 = PermissionPackageService(db=MagicMock())
    svc2.db.query.return_value.filter.return_value.first.return_value = SimpleNamespace(id=99)
    errors2: list = []
    with patch.object(svc2, "_resolve_user_by_username_or_id", return_value=user2), patch.object(
        svc2, "_sanitize_legacy_privilege", return_value=("user", "org")
    ), patch("app.core.data_permission._get_org_subtree", return_value=([1], {})), patch.object(
        svc2, "_clear_existing_data"
    ):
        svc2._import_user_legacy(
            [{"username": "carol", "permissions": "", "organization_id": 99}],
            {}, errors2, merge_mode=True, allow_privileged=False, caller=caller,
        )
    assert any("不在调用者管辖范围" in e for e in errors2)

    # 目标用户不是调用者、但权限串含通配：非超管必须清空并留痕
    user3 = _legacy_user(id=5, username="dave")
    user3.permissions = ""
    errors3: list = []
    with patch.object(svc2, "_resolve_user_by_username_or_id", return_value=user3), patch.object(
        svc2, "_sanitize_legacy_privilege", return_value=("user", "org")
    ), patch("app.core.data_permission._get_org_subtree", return_value=([1], {})), patch.object(
        svc2, "_clear_existing_data"
    ):
        svc2._import_user_legacy(
            [{"username": "dave", "permissions": "*:*"}],
            {"user_legacy_updated": 0}, errors3, merge_mode=True,
            allow_privileged=False, caller=caller,
        )
    assert any("通配权限" in e for e in errors3)
    assert user3.permissions == ""


def test_import_legacy_caller_without_org_keeps_allowed_ids_none():
    """调用者未绑定组织时不做子树限制（allowed_org_ids 保持 None）。"""
    svc = PermissionPackageService(db=MagicMock())
    caller = SimpleNamespace(id=1, organization_id=None)
    user = _legacy_user(id=6, username="eve")
    errors: list = []
    with patch.object(svc, "_resolve_user_by_username_or_id", return_value=user), patch.object(
        svc, "_sanitize_legacy_privilege", return_value=("user", "org")
    ), patch.object(svc, "_clear_existing_data"):
        svc._import_user_legacy(
            [{"username": "eve", "permissions": ""}],
            {"user_legacy_updated": 0}, errors, merge_mode=True,
            allow_privileged=False, caller=caller,
        )
    assert errors == []


def test_import_legacy_subtree_error_is_fail_closed():
    """子树解析异常时 allowed_org_ids 清空 → 保守拒绝（不因异常放行）。"""
    svc = PermissionPackageService(db=MagicMock())
    svc.db.query.return_value.filter.return_value.first.return_value = SimpleNamespace(id=99)
    caller = SimpleNamespace(id=1, organization_id=1)
    user = _legacy_user(id=7, username="frank")
    errors: list = []
    with patch.object(svc, "_resolve_user_by_username_or_id", return_value=user), patch.object(
        svc, "_sanitize_legacy_privilege", return_value=("user", "org")
    ), patch(
        "app.core.data_permission._get_org_subtree", side_effect=RuntimeError("boom")
    ), patch.object(svc, "_clear_existing_data"):
        svc._import_user_legacy(
            [{"username": "frank", "permissions": "", "organization_id": 99}],
            {"user_legacy_updated": 0}, errors, merge_mode=True,
            allow_privileged=False, caller=caller,
        )
    assert any("不在调用者管辖范围" in e for e in errors)
    assert user.organization_id == 1


class _ProjectData:
    """create_project 所需的字段默认值（未列出的属性返回 None）。"""

    code = None
    village_id = 99
    name = "有村项目"
    type = None
    description = None
    budget = 0
    progress = None
    start_date = None
    end_date = None
    urgency_level = None
    is_delayed = None

    def __getattr__(self, item):
        return None


def test_create_project_with_valid_village_passes():
    """village_id 命中数据域时应继续创建（覆盖 835 的“存在”分支）。"""
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None
    scoped = MagicMock()
    scoped.first.return_value = SimpleNamespace(id=99)
    request = SimpleNamespace(client=SimpleNamespace(host="127.0.0.1"))
    with patch("app.services.data_scope_query.scoped_filter", return_value=scoped):
        _run(projects_mod.create_project(_ProjectData(), request, SimpleNamespace(id=1), db))
    assert db.add.called
    projects = [c.args[0] for c in db.add.call_args_list if isinstance(c.args[0], Project)]
    assert projects and projects[0].village_id == 99
