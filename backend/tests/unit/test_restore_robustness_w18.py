"""W18-D7/D11 回归：恢复的版本前置校验 + 回滚原子化与快照自救。

D7：备份库 alembic 版本高于当前代码 → 恢复前拒绝（原实现覆盖后启动即永久崩溃）。
D11：回滚改 os.replace 原子换名；失败时快照移入 backup_dir/pre_restore（不再困死 %TEMP%）。
"""
import sqlite3

import pytest


@pytest.fixture
def db():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    from app.models import Base

    Base.metadata.create_all(bind=engine)
    session = sessionmaker(autocommit=False, autoflush=False, bind=engine)()
    yield session
    session.close()
    engine.dispose()


@pytest.fixture
def svc(db, tmp_path):
    from app.services.backup_service import BackupService

    s = BackupService(db)
    s.database_path = str(tmp_path / "prod.db")
    s.uploads_dir = str(tmp_path / "uploads")
    os.makedirs(s.uploads_dir, exist_ok=True)
    return s


import os


class TestSchemaVersionPrecheck:
    """D7：恢复前置版本校验。"""

    def _make_backup_db(self, tmp_path, revision):
        p = tmp_path / "backup.db"
        conn = sqlite3.connect(str(p))
        try:
            conn.execute("CREATE TABLE IF NOT EXISTS alembic_version (version_num VARCHAR(32) NOT NULL)")
            if revision:
                conn.execute("INSERT INTO alembic_version VALUES (?)", (revision,))
            conn.commit()
        finally:
            conn.close()
        return str(p)

    def test_unknown_revision_rejected(self, svc, tmp_path, monkeypatch):
        """核心：备份 revision 不在当前迁移链上 → 拒绝（不碰生产库）。"""
        from app.services.backup_service import BackupRestoreError

        # 测试环境 BUMOFU_BACKEND_DIR_OVERRIDE 指向 pytest tmp（无 alembic/），
        # 而生产该目录必有迁移链 —— patch 源头 app.utils.paths 以驱动真实校验
        # （backup_service 在函数内 import，需 patch 源模块属性才生效）
        real_backend = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        import app.utils.paths as paths_mod

        monkeypatch.setattr(paths_mod, "get_project_backend_dir", lambda: real_backend)

        backup_db = self._make_backup_db(tmp_path, "zzz_future_revision_999")
        with pytest.raises(BackupRestoreError) as ei:
            svc._validate_backup_schema_version(backup_db)
        assert "更高版本" in str(ei.value) or "升级" in str(ei.value)

    def test_known_revision_accepted(self, svc, tmp_path, monkeypatch):
        """备份 revision 在迁移链上（旧版本）→ 放行（可 upgrade）。"""
        from alembic.config import Config as AlembicConfig
        from alembic.script import ScriptDirectory

        backend_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__),
        ))))
        cfg = AlembicConfig(os.path.join(backend_dir, "alembic.ini"))
        cfg.set_main_option("script_location", os.path.join(backend_dir, "alembic"))
        head = ScriptDirectory.from_config(cfg).get_current_head()
        if not head:
            pytest.skip("alembic 链不可用")
        backup_db = self._make_backup_db(tmp_path, head)
        # 不应抛出
        svc._validate_backup_schema_version(backup_db)

    def test_no_version_table_accepted(self, svc, tmp_path):
        """无 alembic_version 表（极老备份）→ 按可升级处理。"""
        p = tmp_path / "old.db"
        conn = sqlite3.connect(str(p))
        conn.execute("CREATE TABLE t (x INT)")
        conn.commit()
        conn.close()
        svc._validate_backup_schema_version(str(p))   # 不抛

    def test_missing_file_is_noop(self, svc, tmp_path):
        """缺文件 → 直接返回（由调用方按缺库处理）。"""
        svc._validate_backup_schema_version(str(tmp_path / "nope.db"))   # 不抛


class TestRollbackAtomicity:
    """D11：回滚原子化与快照自救。"""

    def test_rollback_success_replaces_database(self, svc, tmp_path):
        snapshot = tmp_path / "snap.db"
        snapshot.write_bytes(b"snapshot-data")
        svc.database_path = str(tmp_path / "prod.db")
        svc.database_path and open(svc.database_path, "wb").write(b"broken-data")

        svc._rollback_to_snapshots(str(snapshot), None)

        assert open(svc.database_path, "rb").read() == b"snapshot-data"
        assert not snapshot.exists()            # 快照已消费

    def test_rollback_failure_preserves_snapshot_in_backup_dir(self, svc, tmp_path, monkeypatch):
        """核心：replace/copy 都失败 → 快照移入 pre_restore 且异常带路径。"""
        from app.services.backup_service import BackupRestoreError

        snapshot = tmp_path / "snap.db"
        snapshot.write_bytes(b"snapshot-data")
        prod = tmp_path / "prod.db"
        prod.write_bytes(b"broken")
        svc.database_path = str(prod)

        # 让 os.replace 与 shutil.copy2 都失败（模拟文件被独占）
        import app.services.backup_service as bs

        def _fail_replace(src, dst):
            raise OSError("locked")

        monkeypatch.setattr(bs.os, "replace", _fail_replace)
        monkeypatch.setattr(bs.shutil, "copy2", _fail_replace)
        # _preserve_snapshot 内部也用 os.replace —— 让它走 fallback 原地保留
        with pytest.raises(RuntimeError) as ei:
            svc._rollback_to_snapshots(str(snapshot), None)
        assert "快照已保留" in str(ei.value)
        assert snapshot.exists()               # 快照未丢

    def test_preserve_snapshot_moves_into_pre_restore(self, svc, tmp_path, monkeypatch):
        """_preserve_snapshot 把快照移入 backup_dir/pre_restore。"""
        snapshot = tmp_path / "snap.db"
        snapshot.write_bytes(b"snapshot")
        pre = tmp_path / "backups" / "pre_restore"

        import app.utils.paths as paths_mod

        monkeypatch.setattr(paths_mod, "get_backup_path",
                            lambda sub="": tmp_path / "backups" / sub)
        # BackupService 里是函数内 import，直接 patch 模块属性
        import app.services.backup_service as bs

        monkeypatch.setattr(
            bs, "get_backup_path", lambda sub="": tmp_path / "backups" / sub,
            raising=False,
        )
        result = svc._preserve_snapshot(str(snapshot))
        assert str(pre) in result
        assert not snapshot.exists()
        assert os.path.exists(result)