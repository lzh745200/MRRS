"""app.services.backup_service 回滚快照两条分支补口（.coveragerc fail_under=100）。

缺失行（均为"难以自然构造"的故障注入路径，用最小假体直击）：
- 696-708：回滚时删除原数据库文件 os.unlink 抛 OSError（Windows 上文件仍被占用
  ERROR_SHARING_VIOLATION）→ 记 error 并 raise RuntimeError。**不得**退回
  shutil.copy 原地覆盖：目标被占用时复制会失败或写出半截库，并把真正的失败原因
  掩盖成另一个异常；快照必须保留，交给用户手工恢复。
- 712-713：回滚成功（数据库已还原）后清理快照文件失败 → 仅 warning，
  快照残留不影响回滚结论。
"""

import os
from unittest.mock import MagicMock, patch

import pytest

from app.services import backup_service
from app.services.backup_service import BackupService


def _make_svc(backup_dir: str) -> BackupService:
    """与 test_backup_service_gaps_r31 同构：最小构造（MagicMock db + tmp 备份目录）。"""
    with patch("os.getenv", side_effect=lambda k, d=None: d):
        return BackupService(db=MagicMock(name="db"), backup_dir=backup_dir)


def _flaky_unlink(target: str, exc: OSError):
    """只对 target 路径抛 exc，其余委托真实 os.unlink。"""
    real_unlink = os.unlink
    target_abs = os.path.abspath(target)

    def _unlink(path, *args, **kwargs):
        if os.path.abspath(str(path)) == target_abs:
            raise exc
        return real_unlink(path, *args, **kwargs)

    return _unlink


class TestRollbackSnapshotFailures:
    def test_occupied_database_file_raises_and_preserves_snapshot(self, tmp_path):
        """696-708 行：原库删除失败（被占用）→ fail-loud，快照保留、不做半截覆盖。"""
        backup_dir = tmp_path / "backups"
        backup_dir.mkdir()
        db_path = tmp_path / "data" / "rural_revitalization.db"
        db_path.parent.mkdir()
        db_path.write_bytes(b"current-db")
        snapshot = tmp_path / "snapshot.db"
        snapshot.write_bytes(b"snapshot-db")

        svc = _make_svc(str(backup_dir))
        svc.database_path = str(db_path)
        svc.uploads_dir = str(tmp_path / "uploads")

        with patch.object(
            backup_service.os,
            "unlink",
            side_effect=_flaky_unlink(str(db_path), OSError("file is in use by another process")),
        ):
            with pytest.raises(RuntimeError) as exc:
                svc._rollback_to_snapshots(str(snapshot), None)

        message = str(exc.value)
        assert "数据库文件被占用" in message
        assert str(snapshot) in message                      # 手工恢复所需的快照位置
        assert isinstance(exc.value.__cause__, OSError)      # 原始失败原因不被吞掉
        assert db_path.read_bytes() == b"current-db"         # 未用 copy 写出半截库
        assert snapshot.read_bytes() == b"snapshot-db"       # 快照必须保留

    def test_snapshot_cleanup_failure_only_warns(self, tmp_path):
        """712-713 行：快照清理失败（被占用/权限）→ 仅 warning，回滚结论不变。"""
        backup_dir = tmp_path / "backups"
        backup_dir.mkdir()
        db_path = tmp_path / "data" / "rural_revitalization.db"
        db_path.parent.mkdir()
        db_path.write_bytes(b"current-db")
        snapshot = tmp_path / "snapshot.db"
        snapshot.write_bytes(b"snapshot-db")

        svc = _make_svc(str(backup_dir))
        svc.database_path = str(db_path)
        svc.uploads_dir = str(tmp_path / "uploads")

        with patch.object(
            backup_service.os,
            "unlink",
            side_effect=_flaky_unlink(str(snapshot), OSError("snapshot is locked")),
        ), patch.object(backup_service, "logger") as mock_logger:
            svc._rollback_to_snapshots(str(snapshot), None)   # 不得抛出

        assert db_path.read_bytes() == b"snapshot-db"         # 回滚已生效
        assert snapshot.exists()                              # 清理失败 → 残留
        mock_logger.warning.assert_called_once()
        mock_logger.error.assert_not_called()

    def test_rollback_happy_path_removes_snapshot(self, tmp_path):
        """对照组：正常回滚 → 库还原且快照被清理。"""
        backup_dir = tmp_path / "backups"
        backup_dir.mkdir()
        db_path = tmp_path / "data" / "rural_revitalization.db"
        db_path.parent.mkdir()
        db_path.write_bytes(b"current-db")
        snapshot = tmp_path / "snapshot.db"
        snapshot.write_bytes(b"snapshot-db")

        svc = _make_svc(str(backup_dir))
        svc.database_path = str(db_path)
        svc.uploads_dir = str(tmp_path / "uploads")

        svc._rollback_to_snapshots(str(snapshot), None)

        assert db_path.read_bytes() == b"snapshot-db"
        assert not snapshot.exists()
