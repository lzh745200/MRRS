"""W18-offline P0-2：Linux/麒麟数据根与备份目录的显式环境变量优先级。

背景（历史 P0 缺陷）：
    ``get_app_data_dir()`` 的 Linux/打包分支固定回退 ``Path.home() / ".bumofu"``。
    麒麟 standalone 以服务用户运行、``HOME`` 被 systemd 指向 ``/opt/安装目录``（只读）
    → 数据/密钥/备份全部落到不可写目录（备份全废、PII 读取 500）；而
    ``kylin.env`` 下发的 ``BACKUP_DIR`` 虽然被 ``get_backup_path()`` 读取，但其
    兜底仍派生自同一个不可写数据根。

本模块锁定目标契约：
    1. Linux/打包数据根：``BUMOFU_DATA_DIR`` → ``XDG_DATA_HOME/bumofu`` →
       ``~/.local/share/bumofu``（**不再**回退 ``~/.bumofu``）；
    2. ``BUMOFU_DEV_MODE`` 语义保持不变（开发态仍指向 backend 项目目录）；
    3. ``get_backup_path()``：``BACKUP_DIR`` 环境变量优先、不校验存在性（首次恢复
       由调用方创建），未设时回退 ``<app_data_dir>/backups``；
    4. Windows 分支行为不变（``LOCALAPPDATA/bumofu-assistance``）。

全部使用 ``tmp_path`` + monkeypatch ``is_linux``/``is_bundled``/``Path.home``，
不写真实 ``/opt``、``/var/lib`` 或用户家目录。
"""
from pathlib import Path

import pytest

from app.utils import paths as paths_module
from app.utils.paths import (
    PathTraversalError,
    get_app_data_dir,
    get_backup_path,
    get_cache_path,
)


@pytest.fixture
def linux_production(monkeypatch, tmp_path):
    """模拟 Linux 生产/standalone（非打包、无 BUMOFU_DEV_MODE）。"""
    monkeypatch.setattr(paths_module, "is_linux", lambda: True)
    monkeypatch.setattr(paths_module, "is_bundled", lambda: False)
    monkeypatch.delenv("BUMOFU_DEV_MODE", raising=False)
    monkeypatch.delenv("BUMOFU_DATA_DIR", raising=False)
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)
    monkeypatch.delenv("BACKUP_DIR", raising=False)
    fake_home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: fake_home)
    return fake_home


@pytest.fixture
def windows_bundled(monkeypatch, tmp_path):
    """模拟 Windows 打包态（行为必须与改动前完全一致）。"""
    monkeypatch.setattr(paths_module, "is_linux", lambda: False)
    monkeypatch.setattr(paths_module, "is_bundled", lambda: True)
    local = tmp_path / "local"
    monkeypatch.setenv("LOCALAPPDATA", str(local))
    monkeypatch.delenv("APPDATA", raising=False)
    return local


# ==================== 数据根优先级 ====================


class TestAppDataDirEnvPriority:
    def test_bumofu_data_dir_wins(self, linux_production, monkeypatch, tmp_path):
        data_dir = tmp_path / "var-lib-assistance"
        monkeypatch.setenv("BUMOFU_DATA_DIR", str(data_dir))
        monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "xdg"))
        result = get_app_data_dir()
        assert result == data_dir
        assert result.is_dir()  # 目录必须被创建

    def test_xdg_data_home_fallback(self, linux_production, monkeypatch, tmp_path):
        xdg = tmp_path / "xdg"
        monkeypatch.setenv("XDG_DATA_HOME", str(xdg))
        assert get_app_data_dir() == xdg / "bumofu"

    def test_default_is_local_share(self, linux_production):
        assert get_app_data_dir() == linux_production / ".local" / "share" / "bumofu"

    def test_never_falls_back_to_dot_bumofu(self, linux_production):
        assert get_app_data_dir() != linux_production / ".bumofu"

    def test_bundled_linux_still_env_first(self, monkeypatch, tmp_path):
        monkeypatch.setattr(paths_module, "is_linux", lambda: True)
        monkeypatch.setattr(paths_module, "is_bundled", lambda: True)
        monkeypatch.delenv("BUMOFU_DEV_MODE", raising=False)
        monkeypatch.delenv("XDG_DATA_HOME", raising=False)
        data_dir = tmp_path / "bundled-data"
        monkeypatch.setenv("BUMOFU_DATA_DIR", str(data_dir))
        assert get_app_data_dir() == data_dir

    def test_dev_mode_semantics_unchanged(self, monkeypatch, tmp_path):
        """BUMOFU_DEV_MODE 仍走开发分支（项目 backend 目录），BUMOFU_DATA_DIR 不生效。"""
        monkeypatch.setattr(paths_module, "is_linux", lambda: True)
        monkeypatch.setattr(paths_module, "is_bundled", lambda: False)
        monkeypatch.setenv("BUMOFU_DEV_MODE", "1")
        monkeypatch.setenv("BUMOFU_DATA_DIR", str(tmp_path / "ignored"))
        monkeypatch.setattr(paths_module, "get_project_backend_dir", lambda: tmp_path / "backend")
        assert get_app_data_dir() == tmp_path / "backend"

    def test_blank_env_values_are_ignored(self, linux_production, monkeypatch):
        monkeypatch.setenv("BUMOFU_DATA_DIR", "   ")
        monkeypatch.setenv("XDG_DATA_HOME", "  ")
        assert get_app_data_dir() == linux_production / ".local" / "share" / "bumofu"


# ==================== 备份目录 ====================


class TestBackupPathEnvPriority:
    def test_backup_dir_env_wins_without_existence_check(
        self, linux_production, monkeypatch, tmp_path
    ):
        backup_dir = tmp_path / "backups-not-created-yet"
        monkeypatch.setenv("BUMOFU_DATA_DIR", str(tmp_path / "data-root"))
        monkeypatch.setenv("BACKUP_DIR", str(backup_dir))
        assert get_backup_path() == backup_dir
        # 环境变量优先且**不校验/不创建**：首次恢复由调用方创建
        assert not backup_dir.exists()

    def test_backup_dir_env_sub_path(self, linux_production, monkeypatch, tmp_path):
        backup_dir = tmp_path / "backups"
        monkeypatch.setenv("BACKUP_DIR", str(backup_dir))
        assert get_backup_path("daily/x.zip") == (backup_dir / "daily" / "x.zip").resolve()

    def test_backup_falls_back_under_app_data_dir(
        self, linux_production, monkeypatch, tmp_path
    ):
        data_dir = tmp_path / "data-root"
        monkeypatch.setenv("BUMOFU_DATA_DIR", str(data_dir))
        assert get_backup_path() == data_dir / "backups"

    def test_backup_blank_env_ignored(self, linux_production, monkeypatch, tmp_path):
        monkeypatch.setenv("BUMOFU_DATA_DIR", str(tmp_path / "data-root"))
        monkeypatch.setenv("BACKUP_DIR", "   ")
        assert get_backup_path() == tmp_path / "data-root" / "backups"

    def test_backup_traversal_still_blocked(self, linux_production, monkeypatch, tmp_path):
        monkeypatch.setenv("BACKUP_DIR", str(tmp_path / "backups"))
        with pytest.raises(PathTraversalError):
            get_backup_path("../escape.zip")


# ==================== 缓存目录对齐（Linux 跟随数据根） ====================


class TestCachePathAlignment:
    def test_linux_cache_follows_bumofu_data_dir(self, linux_production, monkeypatch, tmp_path):
        data_dir = tmp_path / "data-root"
        monkeypatch.setenv("BUMOFU_DATA_DIR", str(data_dir))
        assert get_cache_path() == data_dir / "cache"

    def test_linux_cache_default_under_local_share(self, linux_production):
        assert get_cache_path() == linux_production / ".local" / "share" / "bumofu" / "cache"

    def test_linux_cache_no_dot_bumofu(self, linux_production):
        assert get_cache_path() != linux_production / ".bumofu" / "cache"


# ==================== Windows 分支保持不变 ====================


class TestWindowsBranchUnchanged:
    def test_app_data_dir_localappdata(
        self, windows_bundled, monkeypatch, tmp_path
    ):
        # 即便设置了 Linux 专用变量，Windows 分支也不得受影响
        monkeypatch.setenv("BUMOFU_DATA_DIR", str(tmp_path / "linux-only"))
        assert get_app_data_dir() == windows_bundled / "bumofu-assistance"

    def test_cache_dir_localappdata(self, windows_bundled, monkeypatch, tmp_path):
        monkeypatch.setenv("BUMOFU_DATA_DIR", str(tmp_path / "linux-only"))
        assert get_cache_path() == windows_bundled / "bumofu-assistance" / "cache"
