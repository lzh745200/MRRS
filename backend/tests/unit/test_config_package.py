"""
Tests for config_package.py — system config package management API.
"""
import json
import pytest
from unittest.mock import MagicMock, patch

BASE = "/api/v1/system/config-packages"


class TestListConfigPackages:
    """GET /api/v1/system/config-packages"""

    def test_requires_auth(self, client):
        resp = client.get(BASE)
        assert resp.status_code == 401

    def test_success(self, client_with_mocked_auth):
        packages = [
            {"name": "pkg1", "description": "desc1", "config_count": 5, "created_at": "2024-01-01T00:00:00"},
            {"name": "pkg2", "description": "desc2", "config_count": 3, "created_at": "2024-01-02T00:00:00"},
        ]
        with patch("app.api.v1.system.config_package.SystemConfigService") as MockSvc:
            mock_svc = MagicMock()
            mock_svc.get_config_packages.return_value = packages
            MockSvc.return_value = mock_svc

            resp = client_with_mocked_auth.get(BASE)
            assert resp.status_code == 200
            data = resp.json()
            assert data["success"] is True
            assert data["data"]["packages"] == packages
            assert data["data"]["total"] == 2

    def test_empty(self, client_with_mocked_auth):
        with patch("app.api.v1.system.config_package.SystemConfigService") as MockSvc:
            mock_svc = MagicMock()
            mock_svc.get_config_packages.return_value = []
            MockSvc.return_value = mock_svc

            resp = client_with_mocked_auth.get(BASE)
            assert resp.status_code == 200
            data = resp.json()
            assert data["success"] is True
            assert data["data"]["packages"] == []
            assert data["data"]["total"] == 0

    def test_no_get_config_packages_method_fallback(self, client_with_mocked_auth):
        with patch("app.api.v1.system.config_package.SystemConfigService") as MockSvc:
            svc = MagicMock(spec_set=[])
            MockSvc.return_value = svc

            resp = client_with_mocked_auth.get(BASE)
            data = resp.json()
            assert data["success"] is True
            assert data["data"]["packages"] == []

    def test_server_error(self, client_with_mocked_auth):
        with patch("app.api.v1.system.config_package.SystemConfigService") as MockSvc:
            mock_svc = MagicMock()
            mock_svc.get_config_packages.side_effect = Exception("DB error")
            MockSvc.return_value = mock_svc

            resp = client_with_mocked_auth.get(BASE)
            assert resp.status_code == 500
            assert "获取配置包列表失败" in resp.json()["detail"]


class TestExportConfigPackage:
    """POST /api/v1/system/config-packages/export"""

    URL = f"{BASE}/export"

    def test_requires_auth(self, client):
        resp = client.post(self.URL, json={})
        assert resp.status_code == 401

    def test_success_with_all_params(self, client_with_mocked_auth):
        export_data = {"theme": "dark", "locale": "zh-CN"}
        with patch("app.api.v1.system.config_package.SystemConfigService") as MockSvc:
            mock_svc = MagicMock()
            mock_svc.export_config.return_value = json.dumps(export_data, ensure_ascii=False)
            MockSvc.return_value = mock_svc

            resp = client_with_mocked_auth.post(
                self.URL,
                json={"name": "my-package", "description": "my desc", "include_defaults": True},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["success"] is True
            assert data["data"]["name"] == "my-package"
            assert data["data"]["description"] == "my desc"
            assert data["data"]["include_defaults"] is True
            assert data["data"]["config_count"] == 2
            assert data["data"]["configs"] == export_data
            assert data["data"]["version"] == "1.0"
            mock_svc.set.assert_called_once()

    def test_success_with_defaults(self, client_with_mocked_auth):
        export_data = {"key": "val"}
        with patch("app.api.v1.system.config_package.SystemConfigService") as MockSvc:
            mock_svc = MagicMock()
            mock_svc.export_config.return_value = json.dumps(export_data)
            MockSvc.return_value = mock_svc

            resp = client_with_mocked_auth.post(self.URL, json={})
            assert resp.status_code == 200
            data = resp.json()
            assert data["success"] is True
            assert data["data"]["name"].startswith("config_package_")
            assert data["data"]["config_count"] == 1

    def test_server_error(self, client_with_mocked_auth):
        with patch("app.api.v1.system.config_package.SystemConfigService") as MockSvc:
            mock_svc = MagicMock()
            mock_svc.export_config.side_effect = Exception("Export failed")
            MockSvc.return_value = mock_svc

            resp = client_with_mocked_auth.post(self.URL, json={})
            assert resp.status_code == 500
            assert "导出配置包失败" in resp.json()["detail"]


class TestImportConfigPackage:
    """POST /api/v1/system/config-packages/import"""

    URL = f"{BASE}/import"

    def test_requires_auth(self, client):
        resp = client.post(self.URL, json={"data": "{}"})
        assert resp.status_code == 401

    def test_regular_user_forbidden(self, client_with_regular_user_auth):
        resp = client_with_regular_user_auth.post(
            self.URL, json={"data": '{"configs": {"key": "val"}}'}
        )
        assert resp.status_code == 403

    def test_success_overwrite_true(self, client_with_mocked_auth):
        from app.core.package_integrity import sign_manifest

        # W27：配置包导入强制 checksum 校验 —— 测试数据须由 sign_manifest 封装
        package_data = json.dumps(sign_manifest({
            "name": "test-pkg", "version": "1.0",
            "configs": {"k1": "v1", "k2": "v2"},
        }, None))
        with patch("app.api.v1.system.config_package.SystemConfigService") as MockSvc:
            mock_svc = MagicMock()
            mock_svc.get.return_value = None
            MockSvc.return_value = mock_svc

            resp = client_with_mocked_auth.post(
                self.URL, json={"data": package_data, "overwrite": True},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["success"] is True
            assert data["data"]["imported_count"] == 2
            assert data["data"]["skipped_count"] == 0
            assert data["data"]["package_name"] == "test-pkg"
            assert mock_svc.set.call_count == 2

    def test_success_overwrite_false_skips_existing(self, client_with_mocked_auth):
        from app.core.package_integrity import sign_manifest

        package_data = json.dumps(sign_manifest({
            "name": "pkg", "version": "1.0",
            "configs": {"new_key": "val", "existing_key": "old_val"},
        }, None))
        with patch("app.api.v1.system.config_package.SystemConfigService") as MockSvc:
            mock_svc = MagicMock()
            def mock_get(key):
                return "found" if key == "existing_key" else None
            mock_svc.get.side_effect = mock_get
            MockSvc.return_value = mock_svc

            resp = client_with_mocked_auth.post(
                self.URL, json={"data": package_data, "overwrite": False},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["data"]["imported_count"] == 1
            assert data["data"]["skipped_count"] == 1

    def test_invalid_json_data(self, client_with_mocked_auth):
        resp = client_with_mocked_auth.post(
            self.URL, json={"data": "not valid json"},
        )
        assert resp.status_code == 400

    def test_empty_configs(self, client_with_mocked_auth):
        resp = client_with_mocked_auth.post(
            self.URL, json={"data": '{"configs": {}}'},
        )
        assert resp.status_code == 400

    def test_missing_configs_key(self, client_with_mocked_auth):
        resp = client_with_mocked_auth.post(
            self.URL, json={"data": '{"name": "nope"}'},
        )
        assert resp.status_code == 400

    def test_empty_configs_after_integrity_check(self, client_with_mocked_auth):
        """通过完整性校验但 configs 为空 → 400（W27：补 package_integrity 后的空集分支）。"""
        from app.core.package_integrity import sign_manifest

        sealed = json.dumps(sign_manifest({"name": "empty", "configs": {}}, None))
        with patch("app.api.v1.system.config_package.SystemConfigService"):
            resp = client_with_mocked_auth.post(self.URL, json={"data": sealed})
        assert resp.status_code == 400
        assert "没有配置数据" in resp.json().get("detail", "")

    def test_server_error(self, client_with_mocked_auth):
        from app.core.package_integrity import sign_manifest

        # W27：数据须先通过完整性校验，才能进入服务层并触发 500
        sealed = json.dumps(sign_manifest({"configs": {"k": "v"}}, None))
        with patch("app.api.v1.system.config_package.SystemConfigService") as MockSvc:
            mock_svc = MagicMock()
            mock_svc.get.side_effect = Exception("Import failed")
            MockSvc.return_value = mock_svc

            resp = client_with_mocked_auth.post(
                self.URL, json={"data": sealed},
            )
            assert resp.status_code == 500


class TestDeleteConfigPackage:
    """DELETE /api/v1/system/config-packages/{package_name}"""

    def test_requires_auth(self, client):
        resp = client.delete(f"{BASE}/test-pkg")
        assert resp.status_code == 401

    def test_regular_user_forbidden(self, client_with_regular_user_auth):
        resp = client_with_regular_user_auth.delete(f"{BASE}/test-pkg")
        assert resp.status_code == 403

    def test_success(self, client_with_mocked_auth):
        with patch("app.api.v1.system.config_package.SystemConfigService") as MockSvc:
            mock_svc = MagicMock()
            mock_svc.get.return_value = '{"data": "exists"}'
            MockSvc.return_value = mock_svc

            resp = client_with_mocked_auth.delete(f"{BASE}/my-pkg")
            assert resp.status_code == 200
            data = resp.json()
            assert data["success"] is True
            assert "my-pkg" in data["message"]
            mock_svc.delete.assert_called_once_with("config_package_my-pkg")

    def test_not_found(self, client_with_mocked_auth):
        with patch("app.api.v1.system.config_package.SystemConfigService") as MockSvc:
            mock_svc = MagicMock()
            mock_svc.get.return_value = None
            MockSvc.return_value = mock_svc

            resp = client_with_mocked_auth.delete(f"{BASE}/nonexistent")
            assert resp.status_code == 404
            mock_svc.delete.assert_not_called()

    def test_server_error(self, client_with_mocked_auth):
        with patch("app.api.v1.system.config_package.SystemConfigService") as MockSvc:
            mock_svc = MagicMock()
            mock_svc.get.side_effect = Exception("Delete failed")
            MockSvc.return_value = mock_svc

            resp = client_with_mocked_auth.delete(f"{BASE}/my-pkg")
            assert resp.status_code == 500
