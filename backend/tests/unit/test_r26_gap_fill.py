"""R26-T03 补测：审计留痕（W04/W07）+ 数据权限守卫（D01/D10）。

锁死本批新增的可执行行/分支，保障后端 100% 覆盖率门禁：
- W04 effectiveness.evaluate_village：评估成功补 write_work_log；审计异常不阻断主流程。
- W07 permission_package.confirm_import：导入成功补 write_work_log；审计异常不阻断主流程。
- D01 control_package._assert_org_reachable：超管放行 / 子树内放行 / 越权 403 / 无组织 403。
- D10 data.data.reports.generate_report：comprehensive 与 statistics 两分支均经数据权限包裹。
"""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient


# ══════════════════════════════════════════════════════════════════
#  W04 — effectiveness.evaluate_village 补记工作日志
# ══════════════════════════════════════════════════════════════════

@pytest.fixture
def eff_client():
    from app.api.v1.deps import get_current_active_user, get_db
    from app.main import app

    original = app.dependency_overrides.copy()
    db = MagicMock()
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_active_user] = lambda: SimpleNamespace(
        id=1, username="admin", is_superuser=True
    )
    with patch("app.api.v1.effectiveness.apply_scope_filter", side_effect=lambda q, *a, **kw: q):
        yield TestClient(app, raise_server_exceptions=False), db
    app.dependency_overrides = original


class TestW04EffectivenessWorkLog:
    def test_evaluate_success_writes_work_log(self, eff_client):
        c, _ = eff_client
        with (
            patch("app.api.v1.effectiveness.EffectivenessService.evaluate_village", return_value={"score": 88}),
            patch("app.api.v1.effectiveness.write_work_log") as wwl,
        ):
            resp = c.post("/api/v1/effectiveness/evaluate", json={"village_id": 3, "year": 2026})
        assert resp.status_code == 200
        assert wwl.called
        # entity_id = village_id，log_type/action 契约
        args, kwargs = wwl.call_args
        assert args[1] == "effectiveness"
        assert args[2] == "evaluate"
        assert kwargs["user_id"] == 1

    def test_evaluate_audit_failure_not_blocking(self, eff_client):
        c, _ = eff_client
        with (
            patch("app.api.v1.effectiveness.EffectivenessService.evaluate_village", return_value={"score": 77}),
            patch("app.api.v1.effectiveness.write_work_log", side_effect=Exception("audit down")),
        ):
            resp = c.post("/api/v1/effectiveness/evaluate", json={"village_id": 3, "year": 2026})
        assert resp.status_code == 200
        assert resp.json()["score"] == 77


# ══════════════════════════════════════════════════════════════════
#  W07 — permission_package.confirm_import 补记工作日志
# ══════════════════════════════════════════════════════════════════

class TestW07PermissionPackageWorkLog:
    @staticmethod
    def _admin():
        return SimpleNamespace(id=1, username="admin", role="admin", is_superuser=True)

    @pytest.fixture
    def svc(self):
        import app.api.v1.permission_package as pp

        with patch.object(pp, "PermissionPackageService") as m:
            yield m.return_value, pp

    def test_confirm_success_writes_work_log(self, svc, tmp_path):
        service, pp = svc
        (tmp_path / "pkg.zip").write_bytes(b"PK")
        service.confirm_import.return_value = {"success": True}
        with (
            patch("app.utils.paths.get_runtime_uploads_path", return_value=tmp_path),
            patch("app.api.v1.permission_package.write_work_log") as wwl,
        ):
            resp = pp.confirm_import_permission_package(
                "pkg.zip",
                SimpleNamespace(overwrite_existing=True, mode=None),
                self._admin(),
                MagicMock(),
            )
        assert resp.status_code == 200
        assert wwl.called
        args = wwl.call_args[0]
        assert args[1] == "permission_package"
        assert args[2] == "import"

    def test_confirm_audit_failure_not_blocking(self, svc, tmp_path):
        service, pp = svc
        (tmp_path / "pkg.zip").write_bytes(b"PK")
        service.confirm_import.return_value = {"success": True}
        with (
            patch("app.utils.paths.get_runtime_uploads_path", return_value=tmp_path),
            patch("app.api.v1.permission_package.write_work_log", side_effect=Exception("audit down")),
        ):
            resp = pp.confirm_import_permission_package(
                "pkg.zip",
                SimpleNamespace(overwrite_existing=True, mode=None),
                self._admin(),
                MagicMock(),
            )
        assert resp.status_code == 200


# ══════════════════════════════════════════════════════════════════
#  D01 — control_package 目标组织可及性守卫
# ══════════════════════════════════════════════════════════════════

class _ChainQuery:
    """可链式调用的最小查询桩：filter() 返回自身，first() 返回预设值。"""

    def __init__(self, first_result):
        self._first = first_result

    def filter(self, *args, **kwargs):
        return self

    def first(self):
        return self._first


class _Db:
    def __init__(self, query_obj):
        self._q = query_obj

    def query(self, *args, **kwargs):
        return self._q


class TestD01OrgReachabilityGuard:
    def test_superuser_allowed(self):
        from app.api.v1.control_package import _assert_org_reachable

        admin = SimpleNamespace(is_superuser=True, role="super_admin", organization_id=5)
        # 超管放行：不访问 db
        _assert_org_reachable(MagicMock(), admin, 999)

    def test_non_super_org_in_subtree_allowed(self):
        from app.api.v1.control_package import _assert_org_reachable

        user = SimpleNamespace(is_superuser=False, role="admin", organization_id=5)
        db = _Db(_ChainQuery(SimpleNamespace(id=5)))
        with patch("app.api.v1.control_package._get_org_subtree", return_value=([5, 6], ["a", "b"])):
            _assert_org_reachable(db, user, 6)  # 子树内放行，不抛异常

    def test_non_super_org_outside_subtree_forbidden(self):
        from app.api.v1.control_package import _assert_org_reachable

        user = SimpleNamespace(is_superuser=False, role="admin", organization_id=5)
        db = _Db(_ChainQuery(None))
        with patch("app.api.v1.control_package._get_org_subtree", return_value=([5, 6], ["a", "b"])):
            with pytest.raises(HTTPException) as exc_info:
                _assert_org_reachable(db, user, 999)
        assert exc_info.value.status_code == 403

    def test_non_super_without_org_forbidden(self):
        from app.api.v1.control_package import _assert_org_reachable

        user = SimpleNamespace(is_superuser=False, role="admin", organization_id=None)
        db = _Db(_ChainQuery(None))
        with pytest.raises(HTTPException) as exc_info:
            _assert_org_reachable(db, user, 1)
        assert exc_info.value.status_code == 403


# ══════════════════════════════════════════════════════════════════
#  D10 — data.data.reports.generate_report 数据权限包裹
# ══════════════════════════════════════════════════════════════════

@pytest.fixture
def reports_client():
    from app.api.v1.data.data.reports import get_report_service
    from app.core.database import get_db
    from app.core.security import get_current_user
    from app.main import app

    original = app.dependency_overrides.copy()
    db = MagicMock()
    svc = MagicMock()
    svc.db = db
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_report_service] = lambda: svc
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
        id=1, username="root", full_name="管理员"
    )
    yield TestClient(app, raise_server_exceptions=False), db, svc
    app.dependency_overrides = original


class TestD10ReportsDataScope:
    def test_comprehensive_wrapped_by_data_scope(self, reports_client):
        c, db, _ = reports_client
        village = SimpleNamespace(
            id=1, village_name="幸福村", department="军区", support_unit="某部", region_scope="省内"
        )
        q = MagicMock()
        q.filter.return_value = q
        q.limit.return_value = q
        q.all.return_value = [village]
        db.query.return_value = q

        with patch(
            "app.api.v1.data.data.reports.filter_by_data_scope",
            side_effect=lambda query, *a, **kw: query,
        ) as fbds:
            resp = c.post("/api/v1/reports/generate", json={"report_type": "comprehensive", "year": 2026})

        assert resp.status_code == 200
        assert resp.json()["data"]["total_villages"] == 1
        assert fbds.call_count == 1

    def test_statistics_wrapped_by_data_scope(self, reports_client):
        c, db, _ = reports_client
        q = MagicMock()
        q.filter.return_value = q
        q.count.return_value = 42
        db.query.return_value = q

        with patch(
            "app.api.v1.data.data.reports.filter_by_data_scope",
            side_effect=lambda query, *a, **kw: query,
        ) as fbds:
            resp = c.post("/api/v1/reports/generate", json={"report_type": "statistics", "year": 2026})

        assert resp.status_code == 200
        assert resp.json()["data"]["statistics"]["total_villages"] == 42
        assert fbds.call_count == 1
