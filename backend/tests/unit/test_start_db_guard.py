"""W1-T7 安全回归：启动自检不得静默删除数据库。

工单 .scratch/w1-security-redline/007
历史缺陷：integrity_check 失败且无备份时自动 os.remove 现库——WAL 活动下
可能误报，造成不可逆数据丢失。
"""

import sqlite3

import pytest

import start as start_module


@pytest.fixture
def db_env(tmp_path, monkeypatch):
    """构造：一个"损坏"库 + 独立 backups 目录 + 隔离 cwd。"""
    db_path = tmp_path / "rural_revitalization.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute("CREATE TABLE t (id INTEGER)")
    conn.commit()
    conn.close()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("BACKUP_DIR", str(tmp_path / "backups"))
    monkeypatch.delenv("ALLOW_DB_RESET", raising=False)
    return db_path


class TestDbAutoDeleteGuard:
    def test_no_backup_default_preserves_db(self, db_env):
        """无备份 + 默认配置：必须保留现场并停止启动（SystemExit）。"""
        with pytest.raises(SystemExit) as exc:
            start_module._try_restore_from_backup(str(db_env))
        assert exc.value.code == 1
        assert db_env.exists(), "默认路径下绝不允许删除现库"

    def test_allow_db_reset_escape_hatch(self, db_env, monkeypatch):
        """显式 ALLOW_DB_RESET=1 时保留原删库重建逃生门。"""
        monkeypatch.setenv("ALLOW_DB_RESET", "1")
        start_module._try_restore_from_backup(str(db_env))
        assert not db_env.exists()

    def test_restore_from_backup_success(self, db_env):
        """存在有效备份时正常恢复，不触发守卫。"""
        import shutil

        backup_dir = db_env.parent / "backups"
        backup_dir.mkdir(exist_ok=True)
        src = db_env.parent / "good.db"
        conn = sqlite3.connect(str(src))
        conn.execute("CREATE TABLE marker (v TEXT)")
        conn.execute("INSERT INTO marker VALUES ('restored')")
        conn.commit()
        conn.close()
        shutil.copy2(str(src), str(backup_dir / "20260823_120000.db"))

        start_module._try_restore_from_backup(str(db_env))  # 不应抛 SystemExit

        conn = sqlite3.connect(str(db_env))
        row = conn.execute("SELECT v FROM marker").fetchone()
        conn.close()
        assert row and row[0] == "restored"

    def test_corrupted_snapshot_always_kept(self, db_env, monkeypatch):
        """无论哪条路径，.corrupted 现场快照都必须保留。"""
        monkeypatch.setenv("ALLOW_DB_RESET", "1")
        start_module._try_restore_from_backup(str(db_env))
        assert (db_env.parent / (db_env.name + ".corrupted")).exists()
