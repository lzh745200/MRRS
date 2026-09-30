"""app.api.v1.control_package 覆盖补全 — 导入 system_config.json 时新键的 db.add 分支 (line 241)."""
import io
import json
import zipfile
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from app.api.v1.control_package import import_control_package


def _zip_bytes(files: dict) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, payload in files.items():
            zf.writestr(name, payload)
    return buf.getvalue()


class TestImportControlPackage:
    async def test_new_system_config_key_is_added(self):
        """白名单内的新配置键 → db.add 新建（v1.12.9 起仅允许白名单键交换）"""
        content = _zip_bytes({
            "manifest.json": json.dumps({"package_type": "control"}),
            "system_config.json": json.dumps({"organization_name": 123}),
        })
        file = SimpleNamespace(filename="pkg.zip", read=AsyncMock(return_value=content))

        db = MagicMock(name="db")
        q = MagicMock(name="query")
        q.filter.return_value = q
        q.first.return_value = None  # 配置键不存在 → 走 db.add 分支
        db.query.return_value = q

        user = SimpleNamespace(id=1, username="admin", role="admin", is_superuser=False)

        with patch("app.api.v1.control_package.write_work_log"):
            resp = await import_control_package(file=file, db=db, current_user=user)

        db.add.assert_called_once()
        added = db.add.call_args[0][0]
        assert added.key == "organization_name"
        assert added.value == "123"
        assert resp["code"] == 200
        assert resp["data"]["applied_configs"] == 1

    async def test_non_whitelisted_system_config_key_skipped(self):
        """非白名单键（可覆盖安全/路径配置）必须跳过并计入 skipped_configs。"""
        content = _zip_bytes({
            "manifest.json": json.dumps({"package_type": "control"}),
            "system_config.json": json.dumps({"brand_new_key": 123, "encryption_salt": "evil"}),
        })
        file = SimpleNamespace(filename="pkg.zip", read=AsyncMock(return_value=content))

        db = MagicMock(name="db")
        q = MagicMock(name="query")
        q.filter.return_value = q
        q.first.return_value = None
        db.query.return_value = q

        user = SimpleNamespace(id=1, username="admin", role="admin", is_superuser=False)

        with patch("app.api.v1.control_package.write_work_log"):
            resp = await import_control_package(file=file, db=db, current_user=user)

        db.add.assert_not_called()
        assert resp["data"]["applied_configs"] == 0
        assert set(resp["data"]["skipped_configs"]) == {"brand_new_key", "encryption_salt"}
