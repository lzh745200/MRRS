"""app.api.v1.system.system_config 覆盖率攻坚测试

覆盖全部 8 个端点的成功与拒绝分支：
- get_all_configs / get_config(404+成功) / update_config / batch_update_configs
- delete_config(默认400+不存在404+成功) / export_configs / import_configs(400+成功)
- get_default_configs
"""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

import app.api.v1.system.system_config as sc


def _admin():
    return SimpleNamespace(id=1, username="admin", role="admin", is_superuser=True)


@pytest.fixture
def svc():
    with patch.object(sc, "SystemConfigService") as m:
        inst = MagicMock()
        inst.DEFAULT_CONFIGS = {"site_name": {"value": "系统", "description": "站点名"}}
        m.return_value = inst
        yield inst


class TestGetAllConfigs:
    async def test_all(self, svc):
        svc.get_all.return_value = {"site_name": "系统", "custom": "v"}
        result = await sc.get_all_configs(MagicMock(), _admin())
        assert result["success"] is True
        assert result["data"]["total"] == 2
        items = {i["key"]: i for i in result["data"]["items"]}
        assert items["site_name"]["description"] == "站点名"
        assert items["custom"]["description"] == ""


class TestGetConfig:
    async def test_found(self, svc):
        svc.get.return_value = "系统"
        result = await sc.get_config("site_name", MagicMock(), _admin())
        assert result["data"]["value"] == "系统"
        assert result["data"]["description"] == "站点名"

    async def test_not_found_404(self, svc):
        svc.get.return_value = None
        with pytest.raises(HTTPException) as exc_info:
            await sc.get_config("missing", MagicMock(), _admin())
        assert exc_info.value.status_code == 404


class TestUpdateConfig:
    async def test_update(self, svc):
        result = await sc.update_config("site_name", "新值", "说明", MagicMock(), _admin())
        assert result["success"] is True
        svc.set.assert_called_once_with("site_name", "新值", "说明")

    async def test_non_admin_forbidden(self, svc):
        user = SimpleNamespace(id=2, username="u", role="user", is_superuser=False)
        with pytest.raises(HTTPException):
            await sc.update_config("k", "v", None, MagicMock(), user)


class TestBatchUpdate:
    async def test_batch(self, svc):
        batch = sc.ConfigBatchUpdate(
            configs=[
                sc.ConfigItem(key="a", value="1"),
                sc.ConfigItem(key="b", value="2", description="d"),
            ]
        )
        result = await sc.batch_update_configs(batch, MagicMock(), _admin())
        assert result["data"]["updated_keys"] == ["a", "b"]
        assert svc.set.call_count == 2


class TestDeleteConfig:
    async def test_default_key_400(self, svc):
        with pytest.raises(HTTPException) as exc_info:
            await sc.delete_config("site_name", MagicMock(), _admin())
        assert exc_info.value.status_code == 400

    async def test_missing_404(self, svc):
        svc.delete.return_value = False
        with pytest.raises(HTTPException) as exc_info:
            await sc.delete_config("custom", MagicMock(), _admin())
        assert exc_info.value.status_code == 404

    async def test_success(self, svc):
        svc.delete.return_value = True
        result = await sc.delete_config("custom", MagicMock(), _admin())
        assert result["success"] is True

    async def test_delete_writes_audit_log(self, svc):
        """删除配置必须记录审计日志（问题19）"""
        svc.delete.return_value = True
        from unittest.mock import patch as _patch
        with _patch("app.api.v1.system.system_config.write_work_log") as mock_log:
            await sc.delete_config("custom", MagicMock(), _admin())
            mock_log.assert_called_once()
            args, kwargs = mock_log.call_args
            assert args[1] == "system_config"
            assert args[2] == "delete"
            assert "custom" in args[4]


class TestExportImport:
    async def test_export(self, svc):
        svc.export_config.return_value = '{"a": "1"}'
        result = await sc.export_configs(MagicMock(), _admin())
        assert result["data"]["format"] == "json"
        assert result["data"]["content"] == '{"a": "1"}'

    async def test_import_success(self, svc):
        svc.import_config.return_value = True
        body = sc.ConfigExportImport(data='{"a": "1"}')
        result = await sc.import_configs(body, MagicMock(), _admin())
        assert result["success"] is True

    async def test_import_invalid_400(self, svc):
        svc.import_config.return_value = False
        body = sc.ConfigExportImport(data="not json")
        with pytest.raises(HTTPException) as exc_info:
            await sc.import_configs(body, MagicMock(), _admin())
        assert exc_info.value.status_code == 400


class TestDefaults:
    async def test_defaults(self):
        result = await sc.get_default_configs()
        assert result["success"] is True
        assert result["data"]["total"] == len(result["data"]["defaults"])
