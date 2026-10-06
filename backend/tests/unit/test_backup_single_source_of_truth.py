"""备份「单一事实源」收敛（2026-10-06）。

历史形态（两套事实源并存）：
- Electron 主进程固定 24h 直调 ``POST /system/backup``，既不读 ``auto_backup``
  开关也不看 ``backup_interval_days`` → 配置说 30 天、实际每天备；
  且每次备份刷新 ``last_backup_time``，把后端 02:00 调度的间隔判定长期顶在
  "跳过"，使后端自己的保留清理永久不可达；
- 清理逻辑则两端各写一套（Electron 硬编码 7 天 vs 后端 ``backup_retention_days``）。

现在：节奏（``trigger=auto`` 时由后端判定）与保留（备份成功后统一按配置清理）
都以配置为唯一来源；Electron 只按固定频率轮询、不再自带策略。
"""
from unittest.mock import MagicMock, patch

import pytest

from app.api.v1.system.backup import _auto_backup_skip_reason

BASE = "/api/v1/system/backup"


def _cfg(mapping):
    """get_config 替身：按 key 命中，未命中返回调用方给的默认值。"""

    def _get(key, default=None):
        return mapping.get(key, default)

    return _get


def _override_actor(client, actor="admin"):
    from app.api.v1.system.backup import _authenticate_backup_request

    client.app.dependency_overrides[_authenticate_backup_request] = lambda: actor


class TestSkipReason:
    """`_auto_backup_skip_reason`：自动触发时是否该落盘。"""

    def test_disabled_switch_skips(self):
        assert _auto_backup_skip_reason(_cfg({"auto_backup": "false"})) == "auto_backup_disabled"

    def test_no_last_backup_proceeds(self):
        assert _auto_backup_skip_reason(_cfg({"backup_interval_days": "1"})) is None

    def test_interval_not_reached(self):
        from datetime import datetime

        reason = _auto_backup_skip_reason(
            _cfg({"backup_interval_days": "30", "last_backup_time": datetime.now().isoformat()})
        )
        assert reason == "interval_not_reached:30"

    def test_interval_elapsed_proceeds(self):
        from datetime import datetime, timedelta

        old = (datetime.now() - timedelta(days=40)).isoformat()
        assert _auto_backup_skip_reason(
            _cfg({"backup_interval_days": "30", "last_backup_time": old})
        ) is None

    def test_invalid_interval_falls_back_to_one_day(self):
        from datetime import datetime, timedelta

        # 非法 interval → 按 1 天算，40 天前的备份应当放行
        old = (datetime.now() - timedelta(days=40)).isoformat()
        assert _auto_backup_skip_reason(
            _cfg({"backup_interval_days": "abc", "last_backup_time": old})
        ) is None

    def test_corrupt_timestamp_proceeds(self):
        """时间戳损坏按"该备份了"处理，避免脏数据把自动备份永久卡死。"""
        assert _auto_backup_skip_reason(
            _cfg({"backup_interval_days": "30", "last_backup_time": "not-an-iso"})
        ) is None

    def test_non_string_timestamp_proceeds(self):
        assert _auto_backup_skip_reason(
            _cfg({"backup_interval_days": "30", "last_backup_time": 12345})
        ) is None


class TestAutoTriggerEndpoint:
    """端点按 trigger 决定是否真的落盘，并在备份成功后统一执行保留清理。"""

    def _mock_record(self):
        rec = MagicMock()
        rec.backup_id = 1
        rec.file_name = "backup_2026.zip"
        rec.file_path = "/backups/backup_2026.zip"
        rec.file_size = 1024
        rec.description = "备份"
        rec.created_at = MagicMock()
        rec.created_at.isoformat.return_value = "2026-01-01T00:00:00"
        return rec

    @pytest.mark.parametrize(
        "override_cfg,expect_reason",
        [
            ({"auto_backup": "false", "backup_interval_days": "1"}, "auto_backup_disabled"),
            ({"backup_interval_days": "30", "last_backup_time": "__NOW__"}, "interval_not_reached:30"),
        ],
    )
    def test_auto_trigger_skips_without_creating(
        self, client_with_mocked_auth, override_cfg, expect_reason
    ):
        """未到间隔 / 已禁用 → 返回 skipped 且**不产生备份文件**。"""
        from datetime import datetime

        cfg = dict(override_cfg)
        if cfg.get("last_backup_time") == "__NOW__":
            cfg["last_backup_time"] = datetime.now().isoformat()

        with patch("app.services.system_config_service.get_config", _cfg(cfg)), \
             patch("app.api.v1.system.backup.get_backup_service") as mock_get_svc:
            mock_svc = MagicMock()
            mock_svc.create_backup.return_value = self._mock_record()
            mock_get_svc.return_value = mock_svc
            _override_actor(client_with_mocked_auth)
            resp = client_with_mocked_auth.post(
                BASE, json={"description": "自动", "trigger": "auto"}
            )

        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["skipped"] is True
        assert body["data"]["reason"] == expect_reason
        mock_svc.create_backup.assert_not_called()

    def test_auto_trigger_proceeds_when_due_and_cleans_up(self, client_with_mocked_auth):
        """到点了：落盘 + 按 backup_retention_days 清理（单一事实源）。"""
        with patch(
            "app.services.system_config_service.get_config",
            _cfg({"backup_interval_days": "1", "backup_retention_days": "9"}),
        ), patch("app.api.v1.system.backup.get_backup_service") as mock_get_svc:
            mock_svc = MagicMock()
            mock_svc.create_backup.return_value = self._mock_record()
            mock_svc.cleanup_by_retention_days.return_value = 2
            mock_get_svc.return_value = mock_svc
            _override_actor(client_with_mocked_auth)
            resp = client_with_mocked_auth.post(
                BASE, json={"description": "自动", "trigger": "auto"}
            )

        assert resp.status_code == 200
        assert resp.json()["data"].get("skipped") is None
        mock_svc.create_backup.assert_called_once()
        mock_svc.cleanup_by_retention_days.assert_called_once_with(9)

    def test_manual_trigger_ignores_interval(self, client_with_mocked_auth):
        """手动备份不受间隔约束（刚备过也能再备）。"""
        from datetime import datetime

        with patch(
            "app.services.system_config_service.get_config",
            _cfg({"backup_interval_days": "30", "last_backup_time": datetime.now().isoformat(),
                  "backup_retention_days": "7"}),
        ), patch("app.api.v1.system.backup.get_backup_service") as mock_get_svc:
            mock_svc = MagicMock()
            mock_svc.create_backup.return_value = self._mock_record()
            mock_svc.cleanup_by_retention_days.return_value = 0
            mock_get_svc.return_value = mock_svc
            _override_actor(client_with_mocked_auth)
            resp = client_with_mocked_auth.post(BASE, json={"description": "手动"})

        assert resp.status_code == 200
        mock_svc.create_backup.assert_called_once()

    def test_retention_cleanup_failure_does_not_fail_backup(self, client_with_mocked_auth):
        """保留清理失败不得让已成功的备份变成 500。"""
        with patch(
            "app.services.system_config_service.get_config",
            _cfg({"backup_interval_days": "1", "backup_retention_days": "7"}),
        ), patch("app.api.v1.system.backup.get_backup_service") as mock_get_svc:
            mock_svc = MagicMock()
            mock_svc.create_backup.return_value = self._mock_record()
            mock_svc.cleanup_by_retention_days.side_effect = RuntimeError("disk boom")
            mock_get_svc.return_value = mock_svc
            _override_actor(client_with_mocked_auth)
            resp = client_with_mocked_auth.post(BASE, json={"description": "手动"})

        assert resp.status_code == 200
        assert resp.json()["success"] is True
