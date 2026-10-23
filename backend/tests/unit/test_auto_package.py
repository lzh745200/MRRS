"""单机自动打包(T1.4): auto_package_job 间隔/目录/复制/记录"""
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.asyncio
async def test_auto_package_disabled():
    from app.services.backup_scheduler import auto_package_job

    with patch("app.services.backup_scheduler.get_db_context"):
        with patch("app.services.backup_scheduler.get_config", return_value="false") as mk:
            await auto_package_job()
            mk.assert_called_once_with("auto_package_enabled", "false")


@pytest.mark.asyncio
async def test_auto_package_no_target_dir():
    """未配置目标目录 → 直接返回，不得实例化打包服务。"""
    from app.services.backup_scheduler import auto_package_job

    def cfg(key, default=None):
        values = {"auto_package_enabled": "true", "auto_package_dir": ""}
        return values.get(key, default)

    with patch("app.services.backup_scheduler.get_db_context"):
        with patch("app.services.backup_scheduler.get_config", side_effect=cfg):
            with patch(
                "app.services.data_package_service.DataPackageService"
            ) as mk_svc:
                await auto_package_job()
                mk_svc.assert_not_called()


@pytest.mark.asyncio
async def test_auto_package_target_not_writable():
    """目标盘不可写 → 不打包（不抛异常）。"""
    from app.services.backup_scheduler import auto_package_job

    def cfg(key, default=None):
        values = {"auto_package_enabled": "true", "auto_package_dir": "Z:\\x", "auto_package_interval_months": "1"}
        return values.get(key, default)

    with patch("app.services.backup_scheduler.get_db_context"):
        with patch("app.services.backup_scheduler.get_config", side_effect=cfg):
            with patch("app.utils.drive_detect.ensure_target_dir", return_value=False):
                with patch(
                    "app.services.data_package_service.DataPackageService"
                ) as mk_svc:
                    await auto_package_job()
                    mk_svc.assert_not_called()


@pytest.mark.asyncio
async def test_auto_package_within_interval_skips():
    from app.services.backup_scheduler import auto_package_job

    def cfg(key, default=None):
        values = {
            "auto_package_enabled": "true",
            "auto_package_dir": "C:\\pkg",
            "auto_package_interval_months": "1",
        }
        return values.get(key, default)

    last_row = MagicMock()
    last_row.value = datetime.now(timezone.utc).isoformat()

    from app.models.system_config import SystemConfig
    from app.models.organization import Organization

    def _query(model):
        if model is SystemConfig:
            q = MagicMock()
            q.filter.return_value.first.return_value = last_row
            return q
        if model is Organization:
            q = MagicMock()
            q.order_by.return_value.first.return_value = None
            return q
        return MagicMock()

    mock_db = MagicMock()
    mock_db.query.side_effect = _query

    with patch("app.services.backup_scheduler.get_db_context", return_value=MagicMock(__enter__=MagicMock(return_value=mock_db))):
        with patch("app.services.backup_scheduler.get_config", side_effect=cfg):
            with patch("app.utils.drive_detect.ensure_target_dir", return_value=True):
                with patch("app.services.data_package_service.DataPackageService") as mk_svc:
                    await auto_package_job()
                    mk_svc.assert_not_called()


@pytest.mark.asyncio
async def test_auto_package_success_copies_and_records():
    from app.services.backup_scheduler import auto_package_job

    def cfg(key, default=None):
        values = {
            "auto_package_enabled": "true",
            "auto_package_dir": "C:\\pkg",
            "auto_package_interval_months": "1",
        }
        return values.get(key, default)

    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = None
    org = MagicMock()
    org.id = 1
    mock_db.query.return_value.order_by.return_value.first.return_value = org

    svc = AsyncMock()
    result = MagicMock()
    result.file_path = "C:\\pkg\\pkg_x.zip"
    result.total_records = 42
    svc.export_package.return_value = result

    with patch("app.services.backup_scheduler.get_db_context", return_value=MagicMock(__enter__=MagicMock(return_value=mock_db))):
        with patch("app.services.backup_scheduler.get_config", side_effect=cfg):
            with patch("app.utils.drive_detect.ensure_target_dir", return_value=True):
                with patch("app.services.data_package_service.DataPackageService", return_value=svc):
                    with patch("app.services.data_package_service.shutil.copy2") as mk_copy:
                        with patch("os.path.exists", return_value=True):
                            with patch("app.services.system_config_service.set_config") as mk_set:
                                await auto_package_job()
                                svc.export_package.assert_called_once()
                                mk_copy.assert_called_once()
                                mk_set.assert_called_once()


@pytest.mark.asyncio
async def test_auto_package_no_org():
    from app.services.backup_scheduler import auto_package_job

    def cfg(key, default=None):
        values = {
            "auto_package_enabled": "true",
            "auto_package_dir": "C:\\pkg",
            "auto_package_interval_months": "1",
        }
        return values.get(key, default)

    from app.models.system_config import SystemConfig
    from app.models.organization import Organization

    def _query(model):
        if model is SystemConfig:
            q = MagicMock()
            q.filter.return_value.first.return_value = None
            return q
        if model is Organization:
            q = MagicMock()
            q.order_by.return_value.first.return_value = None
            return q
        return MagicMock()

    mock_db = MagicMock()
    mock_db.query.side_effect = _query

    with patch("app.services.backup_scheduler.get_db_context", return_value=MagicMock(__enter__=MagicMock(return_value=mock_db))):
        with patch("app.services.backup_scheduler.get_config", side_effect=cfg):
            with patch("app.utils.drive_detect.ensure_target_dir", return_value=True):
                with patch("app.services.data_package_service.DataPackageService") as mk_svc:
                    await auto_package_job()
                    mk_svc.assert_not_called()


@pytest.mark.asyncio
async def test_auto_package_exception_safe(caplog):
    """数据库上下文获取失败 → 异常被吞并记日志，不向上冒泡（调度器不可崩）。"""
    import logging

    from app.services.backup_scheduler import auto_package_job

    with caplog.at_level(logging.ERROR):
        with patch(
            "app.services.backup_scheduler.get_db_context",
            side_effect=RuntimeError("boom"),
        ):
            result = await auto_package_job()

    assert result is None                      # 无返回值，调用方（调度器）不受影响
    # 日志内容（caplog.text 已做过 args 插值，避免手工 % 格式化踩参数类型）
    assert "boom" in caplog.text
