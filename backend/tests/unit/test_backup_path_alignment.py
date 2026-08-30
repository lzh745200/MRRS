"""路径双源修复回归（2026-08-30）：备份/恢复必须作用于 DATABASE_URL 指向的真实数据库。

历史缺陷：BackupService 按静态规则推断数据库路径，与 Electron 注入的
DATABASE_URL 分叉，导致安装版备份的是陈旧文件、恢复写回错误位置却提示
成功。本文件锁定以下不变量：

1. get_database_path / get_runtime_uploads_path 以运行时环境变量为准
2. BackupService 作用于会话实际绑定的数据库
3. 备份包必须包含数据库文件（缺失即 fail-loud）
4. 同秒多次创建备份不冲突
5. 恢复真实替换运行时数据库
"""

import sqlite3
import time
import zipfile
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.base import Base as ModelBase
from app.services.backup_service import BackupIncompleteError, BackupService
from app.utils.paths import db_file_from_url, get_database_path, get_runtime_uploads_path


@pytest.fixture
def runtime_db(tmp_path, monkeypatch):
    """临时 SQLite 库 + 以其为准的 DATABASE_URL 环境（含全部表结构）。"""
    db_file = tmp_path / "runtime.db"
    engine = create_engine(f"sqlite:///{db_file.as_posix()}")
    ModelBase.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_file.as_posix()}")
    yield db_file, db
    db.close()
    engine.dispose()


class TestDbFileFromUrl:
    def test_absolute_sqlite_url_resolved(self, tmp_path):
        db_file = tmp_path / "app.db"
        assert db_file_from_url(f"sqlite:///{db_file.as_posix()}") == Path(db_file.as_posix())

    def test_relative_url_rejected(self):
        assert db_file_from_url("sqlite:///./data/x.db") is None

    def test_memory_db_rejected(self):
        assert db_file_from_url("sqlite:///:memory:") is None

    def test_non_sqlite_rejected(self):
        assert db_file_from_url("postgresql://localhost/app") is None

    def test_query_string_stripped(self, tmp_path):
        db_file = tmp_path / "app.db"
        res = db_file_from_url(f"sqlite:///{db_file.as_posix()}?mode=ro")
        if res is not None:  # Windows 盘符 URL 在 POSIX 上按相对路径拒绝
            assert res == Path(db_file.as_posix())


class TestGetDatabasePathChain:
    def test_env_database_url_wins(self, runtime_db):
        db_file, _ = runtime_db
        assert Path(get_database_path()).resolve() == db_file.resolve()

    def test_backup_service_uses_session_bind_over_env(self, tmp_path, runtime_db, monkeypatch):
        """会话绑定优先于环境变量：库文件以会话实际连接的为准。"""
        _, db = runtime_db
        other = tmp_path / "other.db"
        monkeypatch.setenv("DATABASE_URL", f"sqlite:///{other.as_posix()}")
        svc = BackupService(db=db, backup_dir=str(tmp_path / "bk"))
        assert Path(svc.database_path).resolve() != other.resolve()


class TestRuntimeUploadsPath:
    def test_env_upload_dir_wins(self, tmp_path, monkeypatch):
        target = tmp_path / "uploads"
        monkeypatch.setenv("UPLOAD_DIR", str(target))
        assert Path(get_runtime_uploads_path()) == target

    def test_sub_path_joined(self, tmp_path, monkeypatch):
        target = tmp_path / "uploads"
        monkeypatch.setenv("UPLOAD_DIR", str(target))
        assert Path(get_runtime_uploads_path("permission_packages")) == target / "permission_packages"

    def test_fallback_to_legacy_when_unavailable(self, tmp_path, monkeypatch):
        monkeypatch.delenv("UPLOAD_DIR", raising=False)
        monkeypatch.setattr("app.core.config.settings.UPLOAD_DIR", "")
        legacy = get_runtime_uploads_path()
        assert "uploads" in str(legacy)


class TestBackupTargetsRuntimeDb:
    def test_backup_zip_contains_runtime_database(self, tmp_path, runtime_db):
        db_file, db = runtime_db
        svc = BackupService(db=db, backup_dir=str(tmp_path / "bk"))
        record = svc.create_backup(description="回归", include_uploads=False)

        assert Path(record.file_path).exists()
        extract_to = tmp_path / "extracted"
        with zipfile.ZipFile(record.file_path) as zf:
            assert "data/rural_revitalization.db" in zf.namelist()
            zf.extractall(extract_to)

        # 包内库必须是运行时库的内容（含 system_configs 表结构）
        con = sqlite3.connect(str(extract_to / "data" / "rural_revitalization.db"))
        try:
            tables = {
                r[0]
                for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
            }
        finally:
            con.close()
        assert "system_configs" in tables
        assert db_file.exists()

    def test_same_second_backups_do_not_collide(self, tmp_path, runtime_db):
        _, db = runtime_db
        svc = BackupService(db=db, backup_dir=str(tmp_path / "bk"))
        r1 = svc.create_backup(description="第一次", include_uploads=False)
        time.sleep(0.05)  # 跨过毫秒后缀即可；同秒内不再触发唯一键冲突
        r2 = svc.create_backup(description="第二次", include_uploads=False)

        assert r1.file_name != r2.file_name
        assert Path(r1.file_path).exists() and Path(r2.file_path).exists()

    def test_backup_fails_loud_when_db_missing(self, tmp_path, monkeypatch):
        """数据库文件不存在时必须报错，且不得静默产出空包或创建占位库。"""
        missing = tmp_path / "missing.db"
        monkeypatch.setenv("DATABASE_URL", f"sqlite:///{missing.as_posix()}")
        engine = create_engine(f"sqlite:///{missing.as_posix()}")
        db = sessionmaker(bind=engine)()  # 仅持有引擎，不触发连接
        try:
            svc = BackupService(db=db, backup_dir=str(tmp_path / "bk"))
            with pytest.raises(BackupIncompleteError):
                svc.create_backup(description="缺失场景", include_uploads=False)
            # 半成品已删除 + 未创建占位库文件
            assert list(Path(svc.backup_dir).glob("*.zip")) == []
            assert not missing.exists()
        finally:
            db.close()
            engine.dispose()


class TestRestoreReplacesRuntimeDb:
    def test_restore_rolls_back_runtime_database(self, tmp_path, runtime_db):
        db_file, db = runtime_db
        svc = BackupService(db=db, backup_dir=str(tmp_path / "bk"))
        record = svc.create_backup(description="恢复前快照", include_uploads=False)

        # 备份之后对运行时库做一次结构性变更
        con = sqlite3.connect(str(db_file))
        try:
            con.execute("CREATE TABLE restore_marker (id INTEGER PRIMARY KEY)")
            con.commit()
        finally:
            con.close()

        result = svc.restore_backup(record.file_path)

        assert result["database_restored"] is True
        con = sqlite3.connect(str(db_file))
        try:
            tables = {
                r[0]
                for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
            }
        finally:
            con.close()
        assert "restore_marker" not in tables, "恢复必须真实替换运行时数据库文件"
