"""
系统管理员功能测试
测试系统信息、备份恢复、系统配置等功能
"""

from fastapi.testclient import TestClient
from pathlib import Path

class TestSystemAdmin:
    """系统管理员功能测试类"""

    def test_get_system_info(self, client: TestClient, admin_token_headers: dict):
        """测试获取系统信息"""
        response = client.get(
            "/api/v1/system/admin/info", headers=admin_token_headers
        )
        # W4-T3：管理员访问必须是 200（原"接受任意状态码"让 500 也算通过）
        assert response.status_code == 200, response.text
        data = response.json()
        assert "version" in data
        assert "database_size" in data
        assert "user_count" in data

    def test_create_backup(self, client: TestClient, admin_token_headers: dict, tmp_path: Path):
        """测试创建备份（复用 BackupService：默认平台密钥加密 + 审计）。"""
        from datetime import datetime
        from types import SimpleNamespace
        from unittest.mock import patch

        backup_dir = tmp_path / "backups"
        backup_dir.mkdir(parents=True, exist_ok=True)

        record = SimpleNamespace(
            file_name="backup_20261101_120000_000_abc123.zip",
            file_size=1024,
            created_at=datetime(2026, 11, 1, 12, 0, 0),
        )
        with patch("app.api.v1.system.admin.get_backup_directory", return_value=backup_dir), \
             patch("app.services.backup_service.BackupService") as backup_service, \
             patch("app.api.v1.system.backup._resolve_auto_backup_password", return_value="platform-key"):
            backup_service.return_value.create_backup.return_value = record
            response = client.post(
                "/api/v1/system/admin/backup", headers=admin_token_headers
            )
        assert response.status_code == 200, response.text
        data = response.json()
        assert data.get("success") is True
        assert data.get("data", {}).get("filename") == record.file_name
        # 缺省口令必须使用平台密钥（不再 shutil.copy2 明文落盘）
        assert backup_service.return_value.create_backup.call_args.kwargs["password"] == "platform-key"

    def test_list_backups(self, client: TestClient, admin_token_headers: dict):
        """测试获取备份列表"""
        response = client.get(
            "/api/v1/system/admin/backups", headers=admin_token_headers
        )
        assert response.status_code == 200, response.text
        data = response.json()
        assert data.get("success") is True
        assert "items" in data.get("data", {})

    def test_get_system_config(self, client: TestClient, admin_token_headers: dict):
        """测试获取系统配置"""
        response = client.get(
            "/api/v1/system/admin/config", headers=admin_token_headers
        )
        assert response.status_code == 200, response.text

    def test_update_system_config(self, client: TestClient, admin_token_headers: dict):
        """测试更新系统配置"""
        config_data = {
            "system_name": "测试系统",
            "max_login_attempts": 3,
            "session_timeout": 600,
        }

        response = client.put(
            "/api/v1/system/admin/config",
            json=config_data,
            headers=admin_token_headers,
        )
        assert response.status_code == 200, response.text

    def test_clear_cache(self, client: TestClient, admin_token_headers: dict):
        """测试清理缓存"""
        response = client.post(
            "/api/v1/system/admin/clear-cache", headers=admin_token_headers
        )
        assert response.status_code == 200, response.text

    def test_get_system_logs(self, client: TestClient, admin_token_headers: dict):
        """测试获取系统日志"""
        response = client.get(
            "/api/v1/system/admin/logs", headers=admin_token_headers
        )
        assert response.status_code == 200, response.text

    def test_non_admin_cannot_access_system_info(
        self, client: TestClient, operator_token_headers: dict
    ):
        """测试非管理员无法访问系统信息"""
        response = client.get(
            "/api/v1/system/admin/info", headers=operator_token_headers
        )
        # W4-T3：越权访问必须被拒（原"接受 200"让越权也算通过）
        assert response.status_code in (401, 403), response.text

    def test_non_admin_cannot_create_backup(
        self, client: TestClient, operator_token_headers: dict
    ):
        """测试非管理员无法创建备份"""
        response = client.post(
            "/api/v1/system/admin/backup", headers=operator_token_headers
        )
        assert response.status_code in (401, 403), response.text

    def test_non_admin_cannot_update_config(
        self, client: TestClient, operator_token_headers: dict
    ):
        """测试非管理员无法更新配置"""
        config_data = {"system_name": "测试系统"}

        response = client.put(
            "/api/v1/system/admin/config",
            json=config_data,
            headers=operator_token_headers,
        )
        assert response.status_code in (401, 403), response.text
