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
    def test_occupied_database_file_raises_and_preserves_snapshot(self, tmp_path, monkeypatch):
        """W18-D11 订正：replace 与 copy2 都失败 → fail-loud + 快照移入 pre_restore。

        旧契约（unlink 失败即 fail-loud）锁定的是缺陷本身：unlink+copy 两步在
        Windows 占用下会产生"旧文件已删、新文件没就位"的半恢复态，且快照困死
        %TEMP%。新契约：os.replace 原子换名（无中间态）→ copy2 兜底 → 全失败时
        快照移入 backup_dir/pre_restore 并把路径写进异常（重启后可自救）。
        """
        import app.services.backup_service as bs
        import app.utils.paths as paths_mod

        db_path = tmp_path / "data" / "rural_revitalization.db"
        db_path.parent.mkdir()
        db_path.write_bytes(b"current-db")
        snapshot = tmp_path / "snapshot.db"
        snapshot.write_bytes(b"snapshot-db")

        svc = _make_svc(str(tmp_path / "backups"))
        svc.database_path = str(db_path)
        svc.uploads_dir = str(tmp_path / "uploads")

        def _fail(src, dst):
            raise OSError("file is in use by another process")

        monkeypatch.setattr(bs.os, "replace", _fail)
        monkeypatch.setattr(bs.shutil, "copy2", _fail)
        # _preserve_snapshot 走原函数（其 os.replace 同样失败 → 原地保留快照）
        with pytest.raises(RuntimeError) as exc:
            svc._rollback_to_snapshots(str(snapshot), None)

        message = str(exc.value)
        assert "数据库文件被占用" in message
        assert "快照已保留" in message                       # 自救路径写进异常
        assert isinstance(exc.value.__cause__, OSError)      # 原始失败原因不被吞掉
        assert db_path.read_bytes() == b"current-db"         # 未用 copy 写出半截库
        assert snapshot.read_bytes() == b"snapshot-db"       # 快照必须保留

    def test_snapshot_cleanup_failure_only_warns(self, tmp_path, monkeypatch):
        """W18-D11 订正：回滚（os.replace）成功但快照清理失败 → 仅 warning。"""
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

        # os.replace 会把快照换名为 prod.db；让**替换后的快照路径**（即 prod.db
        # 已不存在于原位）的 unlink 失败不可构造 —— 新实现 replace 成功即消费快照。
        # 语义等价物：回滚后快照原位 unlink 失败 → 让 replace 失败而 copy2 成功，
        # copy2 成功后 unlink 快照失败 → 残留 + warning。
        real_copy2 = backup_service.shutil.copy2

        def _replace_fail_then_copy(src, dst):
            if str(src) == str(snapshot):
                raise OSError("locked for replace")
            return real_copy2(src, dst)

        monkeypatch.setattr(backup_service.os, "replace", _replace_fail_then_copy)
        monkeypatch.setattr(
            backup_service.shutil, "copy2",
            lambda src, dst: real_copy2(src, dst),
        )
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
