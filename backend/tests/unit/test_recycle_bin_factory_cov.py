"""app.api.v1.recycle_bin 工厂注册端点 + 内部助手覆盖率攻坚测试

覆盖缺口（基线 miss）：
- 55：_get_or_404 记录不存在 → 404
- 60：_require_in_recycle_bin 记录未在回收站（is_active=True）→ 400
- 69：_verify_password 二次确认密码不正确 → 400
- 81-86：purge_preview 成功路径（级联统计预览）
- 129 / 142：batch-restore / batch-purge 空 ids → 400
- 150：_restore_record 中 db.get 未命中 → 404
- 158 / 180 / 228 / 256：on_changed 回调在各成功路径被 await
- 178：_purge_record 级联统计 success=False → 404
- 249：batch-purge 逐条记录不存在 → continue 跳过

说明：supported-villages 有自己的同语义端点（已由 e2e 覆盖）；本文件针对
register_recycle_bin_routes 工厂（school/projects/funds 挂载）注册到
独立 APIRouter 的路由做单元级验证，不影响全局 app。
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import APIRouter, FastAPI
from fastapi.testclient import TestClient

import app.api.v1.recycle_bin as rb
from app.core.database import get_db
from app.core.security import get_current_user

_MODEL = MagicMock(name="FakeModel")


def _admin():
    return SimpleNamespace(
        id=1, username="admin", role="admin", is_superuser=True, hashed_password="h"
    )


def _build(db, user, on_changed=None):
    """用工厂注册路由到独立 app，返回 TestClient（不污染全局 app）。"""
    router = APIRouter()
    rb.register_recycle_bin_routes(
        router, model=_MODEL, resource="记录",
        table_name="fake_records", on_changed=on_changed,
    )
    app = FastAPI()
    app.include_router(router, prefix="/rec")
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: db
    return TestClient(app, raise_server_exceptions=False)


def _soft_deleted_rec(**kw):
    return SimpleNamespace(is_active=False, deleted_at="2026-01-01", **kw)


class TestPurgePreview:
    def test_not_found_404(self):
        # 覆盖 recycle_bin.py:55 —— 记录不存在
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        resp = _build(db, _admin()).get("/rec/99/purge/preview")
        assert resp.status_code == 404

    def test_not_in_recycle_bin_400(self):
        # 覆盖 recycle_bin.py:60 —— 记录未软删（is_active=True）不在回收站
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = SimpleNamespace(is_active=True)
        resp = _build(db, _admin()).get("/rec/5/purge/preview")
        assert resp.status_code == 400
        assert "不在回收站" in resp.json()["detail"]

    def test_success_returns_cascade_stats(self):
        # 覆盖 recycle_bin.py:81-86 —— 级联统计预览成功
        db = MagicMock()
        rec = _soft_deleted_rec(village_name="甲村")
        db.query.return_value.filter.return_value.first.return_value = rec
        with patch("app.services.cascade_purge_service.CascadePurgeService") as m_cps:
            m_cps.return_value.preview.return_value = {"total_references": 3}
            resp = _build(db, _admin()).get("/rec/5/purge/preview")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["id"] == 5
        assert data["name"] == "甲村"
        assert data["total_references"] == 3
        m_cps.return_value.preview.assert_called_once_with("fake_records", 5)


class TestRestore:
    def test_record_missing_after_gate_404(self):
        # 覆盖 recycle_bin.py:150 —— 状态门通过但 db.get 未命中 → 404
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = _soft_deleted_rec()
        db.get.return_value = None
        resp = _build(db, _admin()).post("/rec/5/restore")
        assert resp.status_code == 404

    def test_success_with_on_changed(self):
        # 覆盖 recycle_bin.py:158 —— on_changed 回调被 await
        db = MagicMock()
        rec = _soft_deleted_rec(name="乙村")
        db.query.return_value.filter.return_value.first.return_value = rec
        db.get.return_value = rec
        on_changed = AsyncMock()
        with (
            patch("app.core.transaction.safe_commit"),
            patch("app.utils.audit_logger.AuditLogger"),
        ):
            resp = _build(db, _admin(), on_changed=on_changed).post("/rec/5/restore")
        assert resp.status_code == 200
        assert rec.is_active is True
        assert rec.deleted_at is None
        on_changed.assert_awaited_once()

    def test_restore_resets_cancelled_status_marker(self):
        # 项目软删以 status='cancelled' 作回收标记；恢复必须还原为 planned，
        # 否则默认列表（status != cancelled）过滤 → 「恢复成功却看不见」
        db = MagicMock()
        rec = _soft_deleted_rec(name="丙项目", status="cancelled")
        db.query.return_value.filter.return_value.first.return_value = rec
        db.get.return_value = rec
        with (
            patch("app.core.transaction.safe_commit"),
            patch("app.utils.audit_logger.AuditLogger"),
        ):
            resp = _build(db, _admin()).post("/rec/5/restore")
        assert resp.status_code == 200
        assert rec.status == "planned"
        assert rec.is_active is True

    def test_restore_keeps_non_cancelled_status(self):
        # 无回收标记的记录不受影响（其它模型 no-op 分支）
        db = MagicMock()
        rec = _soft_deleted_rec(name="丁", status="in_progress")
        db.query.return_value.filter.return_value.first.return_value = rec
        db.get.return_value = rec
        with (
            patch("app.core.transaction.safe_commit"),
            patch("app.utils.audit_logger.AuditLogger"),
        ):
            resp = _build(db, _admin()).post("/rec/6/restore")
        assert resp.status_code == 200
        assert rec.status == "in_progress"


class TestPurge:
    def test_wrong_password_400(self):
        # 覆盖 recycle_bin.py:69 —— 二次确认密码不正确 → 400
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = _soft_deleted_rec()
        with patch("app.core.security.verify_password", return_value=False):
            resp = _build(db, _admin()).post("/rec/5/purge", json={"confirm_password": "bad"})
        assert resp.status_code == 400
        assert "密码不正确" in resp.json()["detail"]

    def test_stats_failure_404(self):
        # 覆盖 recycle_bin.py:178 —— 级联清除 success=False → 404
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = _soft_deleted_rec()
        with (
            patch("app.core.security.verify_password", return_value=True),
            patch("app.services.cascade_purge_service.CascadePurgeService") as m_cps,
        ):
            m_cps.return_value.purge.return_value = {"success": False, "message": "记录不存在"}
            resp = _build(db, _admin()).post("/rec/5/purge", json={"confirm_password": "pw"})
        assert resp.status_code == 404
        assert "记录不存在" in resp.json()["detail"]

    def test_success_with_on_changed(self):
        # 覆盖 recycle_bin.py:180 —— on_changed 回调被 await
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = _soft_deleted_rec()
        on_changed = AsyncMock()
        with (
            patch("app.core.security.verify_password", return_value=True),
            patch("app.services.cascade_purge_service.CascadePurgeService") as m_cps,
            patch("app.utils.audit_logger.AuditLogger"),
            patch("app.services.immediate_backup.trigger_immediate_backup"),
        ):
            m_cps.return_value.purge.return_value = {
                "success": True, "deleted_records": 5, "details": {"x": 1},
            }
            resp = _build(db, _admin(), on_changed=on_changed).post(
                "/rec/5/purge", json={"confirm_password": "pw"}
            )
        assert resp.status_code == 200
        assert resp.json()["data"]["deleted_records"] == 5
        on_changed.assert_awaited_once()


class TestBatchEndpoints:
    def test_batch_restore_empty_ids_400(self):
        # 覆盖 recycle_bin.py:129 —— batch-restore 空 ids → 400
        resp = _build(MagicMock(), _admin()).post("/rec/batch-restore", json={"ids": []})
        assert resp.status_code == 400
        assert "ID 列表" in resp.json()["detail"]

    def test_batch_purge_empty_ids_400(self):
        # 覆盖 recycle_bin.py:142 —— batch-purge 空 ids → 400（需先过密码校验）
        with patch("app.core.security.verify_password", return_value=True):
            resp = _build(MagicMock(), _admin()).post(
                "/rec/batch-purge", json={"confirm_password": "pw", "ids": []}
            )
        assert resp.status_code == 400
        assert "ID 列表" in resp.json()["detail"]

    def test_batch_restore_success_with_on_changed(self):
        # 覆盖 recycle_bin.py:228 —— on_changed 回调被 await
        db = MagicMock()
        rec_cancelled = _soft_deleted_rec(name="批量丙", status="cancelled")
        db.query.return_value.filter.return_value.update.return_value = 2
        db.query.return_value.filter.return_value.all.return_value = [rec_cancelled]
        on_changed = AsyncMock()
        with patch("app.core.transaction.safe_commit"):
            resp = _build(db, _admin(), on_changed=on_changed).post(
                "/rec/batch-restore", json={"ids": [1, 2]}
            )
        assert resp.status_code == 200
        assert resp.json()["data"]["restored"] == 2
        on_changed.assert_awaited_once()
        # 批量恢复同样清除 cancelled 回收标记
        assert rec_cancelled.status == "planned"

    def test_batch_purge_missing_skipped_and_on_changed(self):
        # 覆盖 recycle_bin.py:249（不存在记录 continue）与 256（on_changed await）
        db = MagicMock()
        db.query.return_value.filter.return_value.first.side_effect = [
            None,                     # id=1 不存在 → continue
            _soft_deleted_rec(),      # id=2 存在 → purge 成功
        ]
        on_changed = AsyncMock()
        with (
            patch("app.core.security.verify_password", return_value=True),
            patch("app.services.cascade_purge_service.CascadePurgeService") as m_cps,
            patch("app.utils.audit_logger.AuditLogger"),
            patch("app.services.immediate_backup.trigger_immediate_backup"),
        ):
            m_cps.return_value.purge.return_value = {"success": True, "deleted_records": 1}
            resp = _build(db, _admin(), on_changed=on_changed).post(
                "/rec/batch-purge", json={"confirm_password": "pw", "ids": [1, 2]}
            )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["purged"] == 1
        assert data["ids"] == [2]
        on_changed.assert_awaited_once()
