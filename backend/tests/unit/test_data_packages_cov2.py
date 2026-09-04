"""app.api.v1.data.data.data_packages 二轮覆盖补全

覆盖缺口（基线 miss）：
- 106-107：_safe_write_work_log 日志失败不阻断
- 276-277：_received_package_to_dict data_types 非法 JSON → 原样单元素列表
- 650：_compute_package_diff_stats 未知 dtype / 缺数据文件 → continue
- 696 / 770：detect-changes / incremental-export 未绑定组织 → 400
- 710 / 714-715 / 717-718：detect-changes 无 model continue / org_id 过滤 / 无 updated_at 全 0
- 772 / 859：无权访问组织 → 403
- 808-809 / 927-928：导入导出历史记录失败 → warning 不阻断
- 827-831 / 946-950：BusinessError 400 与通用异常 500
- 853：包不存在 → 404；863-865：差异统计失败 → 500
- 1520-1524：_ensure_package_org_access 非管理员无权 → 404
- 1629 / 1696 / 1723：版本对比/详情/删除的版本不存在 → 404
"""

import json
import zipfile
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

import app.api.v1.data.data.data_packages as dp
from app.core.database import get_db
from app.core.exceptions import BusinessError
from app.core.security import get_current_user


def _admin():
    return SimpleNamespace(
        id=1, username="admin", full_name="管理员", role="admin",
        is_superuser=True, organization_id=5,
    )


def _plain_user():
    return SimpleNamespace(
        id=2, username="bob", role="user", is_superuser=False, organization_id=None,
    )


@pytest.fixture
def ctx():
    """构建依赖注入环境，返回可配置上下文。"""
    from app.main import app
    from app.api.v1.data.data.data_packages import (
        get_history_service,
        get_package_service,
        get_permission_service,
    )

    svc = MagicMock(name="svc")
    svc.db = MagicMock(name="svc_db")
    hist = MagicMock(name="hist")
    perm = MagicMock(name="perm")
    perm.can_access_organization = MagicMock(return_value=True)
    db = MagicMock(name="db")
    state = {
        "svc": svc, "hist": hist, "perm": perm, "db": db, "user": _admin(),
    }

    def _get(key):
        return lambda: state[key]

    app.dependency_overrides[get_current_user] = _get("user")
    app.dependency_overrides[get_package_service] = _get("svc")
    app.dependency_overrides[get_history_service] = _get("hist")
    app.dependency_overrides[get_permission_service] = _get("perm")
    app.dependency_overrides[get_db] = _get("db")
    tc = TestClient(app, raise_server_exceptions=False)
    state["client"] = tc
    yield state
    for dep in (get_current_user, get_package_service, get_history_service,
                get_permission_service, get_db):
        app.dependency_overrides.pop(dep, None)


# ==================== 纯函数单测 ====================


class TestSafeWriteWorkLog:
    def test_log_failure_degrades(self):
        # 覆盖 data_packages.py:106-107 —— 写审计日志异常仅告警不阻断
        with patch.object(dp, "write_work_log", side_effect=RuntimeError("log down")):
            dp._safe_write_work_log(MagicMock(), "export", 1, "pkg", _admin())  # 不抛


class TestReceivedPackageToDict:
    def test_bad_json_data_types_wrapped(self):
        # 覆盖 data_packages.py:276-277 —— data_types 非法 JSON → [原字符串]
        pkg = SimpleNamespace(
            id=1, package_code="RCV1", file_name="f.zip", file_size=10,
            record_count=2, data_types="not-json{", manifest=None,
            status="received", created_at=datetime(2026, 1, 1),
            imported_at=None, importer=None,
        )
        result = dp._received_package_to_dict(pkg)
        assert result["data_types"] == ["not-json{"]
        assert result["imported_by"] is None

    def test_dict_data_types_passthrough(self):
        pkg = SimpleNamespace(
            id=2, package_code="RCV2", file_name="g.zip", file_size=1,
            record_count=0, data_types=["villages"], manifest={"org_code": "ORG"},
            status="imported", created_at=datetime(2026, 1, 1),
            imported_at=datetime(2026, 1, 2),
            importer=SimpleNamespace(full_name="导入员"),
        )
        result = dp._received_package_to_dict(pkg)
        assert result["data_types"] == ["villages"]
        assert result["imported_by"] == "导入员"
        assert result["org_code"] == "ORG"


class TestComputePackageDiffStats:
    def test_unknown_dtype_skipped(self, tmp_path):
        # 覆盖 data_packages.py:650 —— manifest 含未知 dtype（无 model）→ continue
        zpath = tmp_path / "pkg.zip"
        with zipfile.ZipFile(zpath, "w") as zf:
            zf.writestr("manifest.json", json.dumps({"data_types": ["unknown-type"]}))
        stats = dp._compute_package_diff_stats(MagicMock(), str(zpath))
        assert stats == {}


# ==================== detect-changes 端点 ====================


class _FakeOrgIdModel:
    """有 org_id 属性 + 完整时间戳列（触发 714-715 分支）"""
    id = 1
    org_id = 1
    updated_at = datetime(2026, 1, 1)
    created_at = datetime(2026, 1, 1)
    is_active = 1


class _FakeNoUpdatedAtModel:
    """有 organization_id 属性但无 updated_at（触发 717-718 全 0 分支）"""
    id = 1
    organization_id = 1


class TestDetectChanges:
    URL = "/api/v1/data-packages/incremental/detect-changes"

    def test_no_org_400(self, ctx):
        # 覆盖 data_packages.py:696 —— 用户未绑定组织且无活跃组织 → 400
        with patch.object(dp, "get_org_with_fallback", return_value=None):
            resp = ctx["client"].post(f"{self.URL}?base_package_id=1&data_types=villages")
        assert resp.status_code == 400
        assert "未绑定组织" in resp.json()["detail"]

    def test_no_permission_403(self, ctx):
        # 覆盖 data_packages.py:697-698 —— 无权访问组织 → 403
        ctx["perm"].can_access_organization.return_value = False
        with patch.object(dp, "get_org_with_fallback", return_value=5):
            resp = ctx["client"].post(f"{self.URL}?base_package_id=1&data_types=villages")
        assert resp.status_code == 403

    def test_mixed_models_branches(self, ctx):
        # 覆盖 710（未知类型 continue）/ 714-715（org_id 过滤）/ 717-718（无 updated_at 全 0）
        ctx["svc"].get_package.return_value = SimpleNamespace(created_at=datetime(2026, 1, 1))
        q = MagicMock(name="query")
        q.filter.return_value = q
        q.scalar.side_effect = [10, 3, 2]  # changed / added / deleted
        ctx["svc"].db.query.return_value = q

        fake_models = {"fake-org": _FakeOrgIdModel, "fake-noupdated": _FakeNoUpdatedAtModel}
        with (
            patch.object(dp, "get_org_with_fallback", return_value=5),
            patch("app.services.data_package_service.DATA_TYPE_MODELS", fake_models),
        ):
            resp = ctx["client"].post(
                f"{self.URL}?base_package_id=1&data_types=fake-org"
                f"&data_types=fake-noupdated&data_types=unknown"
            )
        assert resp.status_code == 200
        by_type = resp.json()["data"]["summary"]["by_type"]
        assert by_type["fake-org"] == {"added": 3, "modified": 5, "deleted": 2, "total": 10}
        assert by_type["fake-noupdated"] == {"added": 0, "modified": 0, "deleted": 0, "total": 0}
        assert "unknown" not in by_type


# ==================== incremental/export 端点 ====================


class TestIncrementalExport:
    URL = "/api/v1/data-packages/incremental/export"

    def _post(self, ctx, svc=None):
        ctx["svc"].get_package.return_value = SimpleNamespace(created_at=datetime(2026, 1, 1))
        return ctx["client"].post(
            self.URL, json={"base_package_id": 1, "data_types": ["villages"]}
        )

    def test_no_org_400(self, ctx):
        # 覆盖 data_packages.py:770 —— 未绑定组织 → 400
        with patch.object(dp, "get_org_with_fallback", return_value=None):
            resp = self._post(ctx)
        assert resp.status_code == 400

    def test_no_permission_403(self, ctx):
        # 覆盖 data_packages.py:772 —— 无权访问组织 → 403
        ctx["perm"].can_access_organization.return_value = False
        with patch.object(dp, "get_org_with_fallback", return_value=5):
            resp = self._post(ctx)
        assert resp.status_code == 403

    def test_history_failure_degrades(self, ctx):
        # 覆盖 data_packages.py:808-809 —— 记录导出历史失败仅告警
        ctx["svc"].export_package = AsyncMock(return_value=SimpleNamespace(
            package_id=9, file_name="inc.zip", file_size=100, package_code="PKG9",
            manifest=SimpleNamespace(record_counts={"villages": 3}),
        ))
        ctx["hist"].record_export.side_effect = RuntimeError("hist down")
        with patch.object(dp, "get_org_with_fallback", return_value=5):
            resp = self._post(ctx)
        assert resp.status_code == 200
        assert resp.json()["data"]["total_records"] == 3

    def test_business_error_400(self, ctx):
        # 覆盖 data_packages.py:827-828 —— BusinessError → 400
        ctx["svc"].export_package = AsyncMock(side_effect=BusinessError("配额不足"))
        with patch.object(dp, "get_org_with_fallback", return_value=5):
            resp = self._post(ctx)
        assert resp.status_code == 400

    def test_generic_error_500(self, ctx):
        # 覆盖 data_packages.py:829-831 —— 通用异常 → 500
        ctx["svc"].export_package = AsyncMock(side_effect=RuntimeError("boom"))
        with patch.object(dp, "get_org_with_fallback", return_value=5):
            resp = self._post(ctx)
        assert resp.status_code == 500


# ==================== incremental/import 端点 ====================


class TestIncrementalImport:
    URL = "/api/v1/data-packages/incremental/import"

    def test_package_missing_404(self, ctx):
        # 覆盖 data_packages.py:853 —— 数据包不存在 → 404
        ctx["svc"].get_package.return_value = None
        resp = ctx["client"].post(self.URL, json={"package_id": 9})
        assert resp.status_code == 404

    def test_no_permission_403(self, ctx, tmp_path):
        # 覆盖 data_packages.py:859 —— 无权导入该组织的数据包 → 403
        pkg_file = tmp_path / "p.zip"
        pkg_file.write_bytes(b"PK")
        ctx["svc"].get_package.return_value = SimpleNamespace(
            file_path=str(pkg_file), file_name="p.zip", org_id=5,
        )
        ctx["perm"].can_access_organization.return_value = False
        resp = ctx["client"].post(self.URL, json={"package_id": 9})
        assert resp.status_code == 403

    def test_diff_stats_failure_500(self, ctx, tmp_path):
        # 覆盖 data_packages.py:863-865 —— 差异统计失败 → 500
        pkg_file = tmp_path / "p.zip"
        pkg_file.write_bytes(b"PK")
        ctx["svc"].get_package.return_value = SimpleNamespace(
            file_path=str(pkg_file), file_name="p.zip", org_id=None,
        )
        with patch.object(dp, "_compute_package_diff_stats", side_effect=Exception("bad zip")):
            resp = ctx["client"].post(self.URL, json={"package_id": 9})
        assert resp.status_code == 500
        assert "差异统计失败" in resp.json()["detail"]

    def test_apply_success_with_history_failure(self, ctx, tmp_path):
        # 覆盖 data_packages.py:927-928 —— 记录导入历史失败仅告警，导入仍成功
        pkg_file = tmp_path / "p.zip"
        pkg_file.write_bytes(b"PK")
        ctx["svc"].get_package.return_value = SimpleNamespace(
            file_path=str(pkg_file), file_name="p.zip", org_id=None,
        )
        ctx["svc"].import_package = AsyncMock(return_value=SimpleNamespace(package_id=11))
        ctx["svc"].confirm_import = AsyncMock(return_value=SimpleNamespace(success=True))
        ctx["hist"].record_import.side_effect = RuntimeError("hist down")
        with patch.object(
            dp, "_compute_package_diff_stats",
            return_value={"villages": {"added": 1, "modified": 2, "deleted": 0, "total": 3}},
        ):
            resp = ctx["client"].post(self.URL, json={"package_id": 9, "apply_changes": True})
        assert resp.status_code == 200
        assert resp.json()["message"] == "导入成功"

    def test_apply_business_error_400(self, ctx, tmp_path):
        # 覆盖 data_packages.py:946-947 —— 应用导入 BusinessError → 400
        pkg_file = tmp_path / "p.zip"
        pkg_file.write_bytes(b"PK")
        ctx["svc"].get_package.return_value = SimpleNamespace(
            file_path=str(pkg_file), file_name="p.zip", org_id=None,
        )
        ctx["svc"].import_package = AsyncMock(side_effect=BusinessError("格式不支持"))
        with patch.object(
            dp, "_compute_package_diff_stats",
            return_value={"villages": {"added": 0, "modified": 0, "deleted": 0, "total": 0}},
        ):
            resp = ctx["client"].post(self.URL, json={"package_id": 9, "apply_changes": True})
        assert resp.status_code == 400

    def test_apply_generic_error_500(self, ctx, tmp_path):
        # 覆盖 data_packages.py:948-950 —— 应用导入通用异常 → 500
        pkg_file = tmp_path / "p.zip"
        pkg_file.write_bytes(b"PK")
        ctx["svc"].get_package.return_value = SimpleNamespace(
            file_path=str(pkg_file), file_name="p.zip", org_id=None,
        )
        ctx["svc"].import_package = AsyncMock(side_effect=RuntimeError("boom"))
        with patch.object(
            dp, "_compute_package_diff_stats",
            return_value={"villages": {"added": 0, "modified": 0, "deleted": 0, "total": 0}},
        ):
            resp = ctx["client"].post(self.URL, json={"package_id": 9, "apply_changes": True})
        assert resp.status_code == 500


# ==================== 版本管理端点 ====================


def _q(**kw):
    q = MagicMock(name="q")
    q.filter.return_value = q
    q.order_by.return_value = q
    q.first.return_value = kw.get("first")
    q.all.return_value = kw.get("all", [])
    return q


class TestVersionEndpoints:
    def test_non_admin_no_org_access_404(self, ctx):
        # 覆盖 data_packages.py:1520-1524 —— 非管理员无权访问组织 → 404（不泄露存在性）
        ctx["user"] = _plain_user()
        ctx["perm"].can_access_organization.return_value = False
        pkg = SimpleNamespace(org_id=5)
        ctx["db"].query.return_value = _q(first=pkg)
        resp = ctx["client"].get("/api/v1/data-packages/1/versions")
        assert resp.status_code == 404

    def test_compare_version1_missing_404(self, ctx):
        # 覆盖 data_packages.py:1628-1629 —— 版本1 不存在 → 404
        # （异常处理路径还会额外消费一次 db.query，故 side_effect 需 3 个元素）
        pkg = SimpleNamespace(org_id=5)
        ctx["db"].query = MagicMock(
            side_effect=[_q(first=pkg), _q(first=None), _q(first=None)]
        )
        resp = ctx["client"].get(
            "/api/v1/data-packages/1/versions/compare?version1=1.0&version2=2.0"
        )
        assert resp.status_code == 404
        assert "版本 1.0 不存在" in resp.json()["detail"]

    def test_version_detail_missing_404(self, ctx):
        # 覆盖 data_packages.py:1695-1696 —— 版本不存在 → 404
        pkg = SimpleNamespace(org_id=5)
        ctx["db"].query = MagicMock(side_effect=[_q(first=pkg), _q(first=None)])
        resp = ctx["client"].get("/api/v1/data-packages/1/versions/9")
        assert resp.status_code == 404
        assert "版本不存在" in resp.json()["detail"]

    def test_delete_version_missing_404(self, ctx):
        # 覆盖 data_packages.py:1722-1723 —— 删除时版本不存在 → 404
        pkg = SimpleNamespace(org_id=5)
        ctx["db"].query = MagicMock(side_effect=[_q(first=pkg), _q(first=None)])
        resp = ctx["client"].delete("/api/v1/data-packages/1/versions/9")
        assert resp.status_code == 404
        assert "版本不存在" in resp.json()["detail"]
