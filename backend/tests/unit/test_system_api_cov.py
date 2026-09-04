"""app.api.v1.system.system 覆盖率攻坚测试（补充 test_system_system_api.py 未覆盖分支）

覆盖点：
- get_system_info：DATABASE_URL 检测 PostgreSQL/MySQL/异常降级
- get_system_status：数据库断开、缓存不可用分支
- shutdown_system：触发 + _shutdown 后台函数（缓存关闭异常降级 + os._exit）
- restart_system：触发 + _restart 后台函数（win32 分支 + 缓存关闭异常降级）
- get_environment_info：包版本查询异常 → "未安装"
"""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

import app.api.v1.system.system as sy


def _admin():
    return SimpleNamespace(id=1, username="admin", role="admin", is_superuser=True)


class _RaisingSettings:
    @property
    def DATABASE_URL(self):
        raise RuntimeError("no settings")


class TestSystemInfoDbType:
    async def test_postgresql(self, monkeypatch):
        monkeypatch.setattr(sy.settings, "DATABASE_URL", "postgresql://u:p@h/db")
        result = await sy.get_system_info(MagicMock(), _admin())
        assert result["data"]["database_type"] == "PostgreSQL"

    async def test_mysql(self, monkeypatch):
        monkeypatch.setattr(sy.settings, "DATABASE_URL", "mysql://u:p@h/db")
        result = await sy.get_system_info(MagicMock(), _admin())
        assert result["data"]["database_type"] == "MySQL"

    async def test_detection_exception_degrades(self, monkeypatch):
        monkeypatch.setattr(sy, "settings", _RaisingSettings())
        result = await sy.get_system_info(MagicMock(), _admin())
        assert result["data"]["database_type"] == "SQLite"


class TestSystemStatus:
    async def test_db_disconnected_cache_unavailable(self):
        engine = MagicMock()
        engine.connect.side_effect = RuntimeError("db down")
        cache_manager = MagicMock()
        cache_manager.get.side_effect = RuntimeError("cache down")
        with (
            patch("app.core.database.engine", engine),
            patch("app.core.cache.cache_manager", cache_manager),
        ):
            result = await sy.get_system_status(_admin())
        services = {s["name"]: s for s in result["data"]["services"]}
        assert services["database"]["status"] == "disconnected"
        assert "db down" in services["database"]["error"]
        assert services["cache"]["status"] == "unavailable"


class TestShutdownRestart:
    async def test_shutdown_trigger_and_task(self):
        bg = MagicMock()
        with patch("app.core.cache.cache_manager", MagicMock()):
            result = await sy.shutdown_system(bg, 0, _admin())
        assert result["success"] is True
        func = bg.add_task.call_args.args[0]
        # 驱动后台函数：缓存关闭异常降级 + os._exit
        with (
            patch.object(sy.time, "sleep"),
            patch("app.core.cache.cache_manager") as m_cm,
            patch.object(sy.os, "_exit") as m_exit,
        ):
            m_cm.close.side_effect = RuntimeError("close boom")
            func()
        m_exit.assert_called_once_with(0)

    async def test_restart_trigger_and_task(self):
        bg = MagicMock()
        with patch("app.core.cache.cache_manager", MagicMock()):
            result = await sy.restart_system(bg, 0, _admin())
        assert result["success"] is True
        func = bg.add_task.call_args.args[0]
        # 显式钉死 win32 分支：_restart 内 `if sys.platform == "win32"` 走
        # subprocess.Popen，否则（Linux）走 os.execv —— 而 os.execv 会**替换当前
        # 进程镜像**，在 xdist worker 内即 gw3 崩溃（nightly #13 的真因，此前被整条
        # skipif 掩盖：它 patch 了 Popen/_exit 却漏了 execv）。这里把 platform 钉成
        # win32 走 Popen 分支，并**额外** patch os.execv 兜底：即便平台判断意外落空，
        # 真实 execv 也绝不会执行。
        with (
            patch.object(sy.time, "sleep"),
            patch("app.core.cache.cache_manager") as m_cm,
            patch.object(sy.sys, "platform", "win32"),
            patch("subprocess.Popen") as m_popen,
            patch.object(sy.os, "execv") as m_execv,
            patch.object(sy.os, "_exit") as m_exit,
        ):
            m_cm.close.side_effect = RuntimeError("close boom")
            func()
        m_popen.assert_called_once()
        m_execv.assert_not_called()
        m_exit.assert_called_once_with(0)


class TestEnvironmentInfo:
    async def test_package_version_missing(self):
        import importlib.metadata

        real_version = importlib.metadata.version

        def fake_version(name):
            if name == "openpyxl":
                raise RuntimeError("not found")
            return real_version(name)

        with patch("importlib.metadata.version", side_effect=fake_version):
            result = await sy.get_environment_info(_admin())
        assert result["data"]["packages"]["openpyxl"] == "未安装"
        assert result["data"]["packages"]["fastapi"] != "未安装"
