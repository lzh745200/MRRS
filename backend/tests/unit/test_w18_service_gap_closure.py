"""W18 收口：backup_service 覆盖率缺口（版本前置校验 / 快照移入 pre_restore）。

对应 coverage 实测缺口：
  651         迁移链 head 读取结果为空 → 跳过版本比对
  654->exit   backup revision 在当前迁移链上 → 放行（函数正常退出）
  758->766    快照已位于 pre_restore（源/目标同路径）→ 无需移动
  759->760    目标位置已有同名快照 → 先清理再替换
  760-764     清理旧同名快照失败（文件被占用）→ 退回带时间戳的新文件名
  810         回滚分支 `if replaced:` 为不可达的假弧（见 app/services/backup_service.py
              同行 pragma 理由：replace/copy 成功才置 True，双失败已 raise）
"""
import os
import sqlite3
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def svc(tmp_path):
    from app.services.backup_service import BackupService

    with patch("os.getenv", side_effect=lambda key, default=None: default):
        service = BackupService(db=MagicMock(name="db"), backup_dir=str(tmp_path / "backups"))
    service.database_path = str(tmp_path / "data" / "rural_revitalization.db")
    service.uploads_dir = str(tmp_path / "uploads")
    return service


def _make_backup_db(path: Path, revision) -> str:
    conn = sqlite3.connect(str(path))
    try:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS alembic_version (version_num VARCHAR(32) NOT NULL)"
        )
        if revision:
            conn.execute("INSERT INTO alembic_version VALUES (?)", (revision,))
        conn.commit()
    finally:
        conn.close()
    return str(path)


class TestBackupSchemaVersionBranches:
    def test_missing_head_skips_comparison(self, svc, tmp_path):
        """迁移链无 head（空仓库/配置未注入）→ 直接返回，不做版本比对。"""
        import alembic.script as alembic_script

        backup_db = _make_backup_db(tmp_path / "backup.db", "rev-any")
        fake_script_dir = MagicMock()
        fake_script_dir.get_current_head.return_value = None

        with patch.object(alembic_script, "ScriptDirectory") as mock_sd:
            mock_sd.from_config.return_value = fake_script_dir
            svc._validate_backup_schema_version(backup_db)   # 不得抛出

    def test_known_revision_accepted(self, svc, tmp_path):
        """revision 在当前迁移链上 → 放行（654 假弧 → 函数正常退出）。"""
        import alembic.script as alembic_script

        backup_db = _make_backup_db(tmp_path / "backup-known.db", "rev-known")
        fake_script_dir = MagicMock()
        fake_script_dir.get_current_head.return_value = "rev-head"
        fake_script_dir.walk_revisions.return_value = [
            SimpleNamespace(revision="rev-known"),
            SimpleNamespace(revision="rev-head"),
        ]

        with patch.object(alembic_script, "ScriptDirectory") as mock_sd:
            mock_sd.from_config.return_value = fake_script_dir
            svc._validate_backup_schema_version(backup_db)   # 不得抛出


class TestPreserveSnapshotBranches:
    def _patch_pre_dir(self, monkeypatch, pre_dir):
        import app.utils.paths as paths_mod

        monkeypatch.setattr(paths_mod, "get_backup_path", lambda sub="": pre_dir)

    def test_snapshot_already_in_pre_restore_is_not_moved(self, svc, tmp_path, monkeypatch):
        """源/目标同路径（快照已在 pre_restore）→ 跳过 os.replace（758->766 假弧）。"""
        pre_dir = tmp_path / "backups" / "pre_restore"
        pre_dir.mkdir(parents=True)
        snapshot = pre_dir / "snap.db"
        snapshot.write_bytes(b"snapshot")
        self._patch_pre_dir(monkeypatch, pre_dir)

        result = svc._preserve_snapshot(str(snapshot))

        assert os.path.abspath(result) == os.path.abspath(str(snapshot))
        assert snapshot.read_bytes() == b"snapshot"

    def test_existing_stale_target_replaced(self, svc, tmp_path, monkeypatch):
        """目标位置已有同名旧快照 → 先 unlink 再替换（759->760 / 760-761）。"""
        pre_dir = tmp_path / "pre_restore"
        pre_dir.mkdir()
        stale = pre_dir / "snap.db"
        stale.write_bytes(b"stale")
        snapshot = tmp_path / "snap.db"
        snapshot.write_bytes(b"fresh")
        self._patch_pre_dir(monkeypatch, pre_dir)

        result = svc._preserve_snapshot(str(snapshot))

        assert Path(result) == stale
        assert stale.read_bytes() == b"fresh"

    def test_locked_stale_target_falls_back_to_timestamped_name(self, svc, tmp_path, monkeypatch):
        """旧同名快照 unlink 失败 → 改用 `<stem>_<ts>.db`（760-764）。"""
        import app.services.backup_service as backup_mod

        pre_dir = tmp_path / "pre_restore"
        pre_dir.mkdir()
        stale = pre_dir / "snap.db"
        stale.write_bytes(b"stale")
        snapshot = tmp_path / "snap.db"
        snapshot.write_bytes(b"fresh")
        self._patch_pre_dir(monkeypatch, pre_dir)

        real_unlink = os.unlink
        stale_abs = os.path.abspath(str(stale))

        def _flaky_unlink(path, *args, **kwargs):
            if os.path.abspath(str(path)) == stale_abs:
                raise OSError("file locked")
            return real_unlink(path, *args, **kwargs)

        monkeypatch.setattr(backup_mod.os, "unlink", _flaky_unlink)
        result = svc._preserve_snapshot(str(snapshot))

        target_name = os.path.basename(result)
        assert target_name.startswith("snap_")
        assert target_name.endswith(".db")
        assert Path(result).read_bytes() == b"fresh"
        assert stale.read_bytes() == b"stale"       # 旧文件未被误删
        assert not snapshot.exists()                # 快照已移走
