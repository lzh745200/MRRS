"""W18-offline P0-2 回归：麒麟部署的数据目录契约。

缺陷（.scratch/w18-deep-probe/02-offline-runtime.md P0-2）
  1. systemd service 未设 HOME → 进程 HOME 落在 useradd 指定的 /opt（只读）
     → paths.py 用 HOME 派生数据目录 → 备份/密钥/上传全部写进 /opt 或失败；
  2. kylin.env 一直下发 BACKUP_DIR，但代码从未接收（"配了不生效"）。

修复口径：service 注入 HOME=/var/lib/...；postinst home-dir 改 DATA_DIR；
get_backup_path 优先尊重 BACKUP_DIR 环境变量。
"""
import os

import pytest


REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


class TestServiceUnitHome:
    def test_service_sets_home_to_writable_dir(self):
        """systemd unit 必须注入 HOME 指向 /var/lib（可写数据目录）。"""
        unit = os.path.join(
            REPO, "deploy", "kylin", "systemd", "assistance-management-system.service"
        )
        src = open(unit, encoding="utf-8", errors="replace").read()
        assert "Environment=HOME=/var/lib/assistance-management-system" in src

    def test_service_readwrite_paths_cover_data_dir(self):
        """ReadWritePaths 必须包含数据目录（sandbox 下可写）。"""
        unit = os.path.join(
            REPO, "deploy", "kylin", "systemd", "assistance-management-system.service"
        )
        src = open(unit, encoding="utf-8", errors="replace").read()
        assert "ReadWritePaths=/var/lib/assistance-management-system" in src


class TestPostinstHomeDir:
    def test_useradd_home_is_data_dir_not_install_dir(self):
        """useradd --home-dir 不得指向只读的 /opt 安装目录。"""
        postinst = os.path.join(REPO, "deploy", "kylin", "DEBIAN", "postinst")
        src = open(postinst, encoding="utf-8", errors="replace").read()
        assert "--home-dir ${DATA_DIR}" in src
        assert "--home-dir ${INSTALL_DIR}" not in src

    def test_postinst_creates_backup_dir(self):
        """BACKUP_DIR 指向的目录必须由 postinst 创建并赋权。"""
        postinst = os.path.join(REPO, "deploy", "kylin", "DEBIAN", "postinst")
        src = open(postinst, encoding="utf-8", errors="replace").read()
        assert "backups" in src      # mkdir -p ${DATA_DIR}/{...,backups}


class TestBackupDirEnv:
    def test_get_backup_path_respects_env(self, monkeypatch, tmp_path):
        """BACKUP_DIR 环境变量优先于默认数据目录（kylin.env 契约）。"""
        from app.utils.paths import get_backup_path

        target = tmp_path / "backups"
        monkeypatch.setenv("BACKUP_DIR", str(target))
        result = get_backup_path()
        assert result == target

    def test_get_backup_path_with_subpath_under_env(self, monkeypatch, tmp_path):
        """子路径安全拼接：逃逸仍被拒绝。"""
        from app.utils.paths import PathTraversalError, get_backup_path

        target = tmp_path / "backups"
        monkeypatch.setenv("BACKUP_DIR", str(target))
        ok = get_backup_path("sub/file.db")
        assert str(target) in str(ok)
        with pytest.raises(PathTraversalError):
            get_backup_path("../../etc/passwd")

    def test_get_backup_path_falls_back_without_env(self, monkeypatch):
        """未设 BACKUP_DIR 时回退默认（既有行为不变）。"""
        from app.utils.paths import get_backup_path

        monkeypatch.delenv("BACKUP_DIR", raising=False)
        result = get_backup_path()
        assert result.name == "backups"

    def test_kylin_env_declares_backup_dir(self):
        """kylin.env 与代码契约对齐：BACKUP_DIR 必须能被接收。"""
        env_file = os.path.join(REPO, "deploy", "kylin", "config", "kylin.env")
        src = open(env_file, encoding="utf-8", errors="replace").read()
        assert "BACKUP_DIR=/var/lib/assistance-management-system/backups" in src
        # 且代码里有对应接收
        paths_py = os.path.join(REPO, "backend", "app", "utils", "paths.py")
        code = open(paths_py, encoding="utf-8", errors="replace").read()
        assert 'os.environ.get("BACKUP_DIR")' in code
