"""备份包跨版本兼容回归（m12417）。

目标契约：**以往版本产生的备份包必须能恢复**，包括：
- 旧版库文件名/路径（``data/assistance.db`` 等，见 ``_locate_backup_db``）；
- 旧版 ``backup_info.json``（缺 ``format_version`` / 缺 PII 指纹）；
- 极老备份无 ``alembic_version`` 表；
- 恢复后自动迁移到当前 head，数据不丢。

同时保留安全边界：来自**更高版本**（revision 不在当前迁移链）的备份包
必须在覆盖生产库之前被拒绝，现场库一个字节都不改。
"""

import json
import sqlite3
import zipfile
from unittest.mock import MagicMock, patch

import pytest

from app.services.backup_service import BackupRestoreError, BackupService


def _build_modern_db(path) -> None:
    """按当前模型建一个「现代 schema」库，并写入标记数据与一个遗留表。"""
    from sqlalchemy import create_engine

    import app.models  # noqa: F401 - 注册全部模型
    from app.models.base import Base

    engine = create_engine(f"sqlite:///{path}")
    try:
        Base.metadata.create_all(bind=engine)
    finally:
        engine.dispose()

    conn = sqlite3.connect(str(path))
    try:
        # 模拟「上一版本还没有的新表」：恢复时应按模型补齐
        conn.execute("DROP TABLE IF EXISTS account_package_receipts")
        conn.execute("CREATE TABLE compat_marker (id INTEGER PRIMARY KEY, note TEXT)")
        conn.execute("INSERT INTO compat_marker (id, note) VALUES (1, 'legacy-data')")
        # 无 alembic_version → 走「表齐全 → 补表补列 + stamp head」分支
        conn.execute("DROP TABLE IF EXISTS alembic_version")
        conn.commit()
    finally:
        conn.close()


def _zip_legacy_backup(zip_path, db_path, db_member="data/assistance.db", backup_info=None) -> str:
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.write(db_path, db_member)
        if backup_info is not None:
            zf.writestr("backup_info.json", json.dumps(backup_info))
    return str(zip_path)


def _make_service(tmp_path) -> BackupService:
    svc = BackupService(db=MagicMock(), backup_dir=str(tmp_path / "backups"))
    svc.database_path = str(tmp_path / "prod.db")
    svc.uploads_dir = str(tmp_path / "uploads")
    return svc


def _current_head() -> str:
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    backend_dir = __import__("pathlib").Path(__file__).resolve().parents[2]
    cfg = Config(str(backend_dir / "alembic.ini"))
    cfg.set_main_option("script_location", str(backend_dir / "alembic"))
    return ScriptDirectory.from_config(cfg).get_current_head()


class TestLegacyBackupRestore:
    """旧格式备份包 → 恢复成功 + 自动升级 + 数据保留。"""

    def test_legacy_name_without_info_restores_and_upgrades(self, tmp_path):
        donor = tmp_path / "donor.db"
        _build_modern_db(donor)
        zip_path = _zip_legacy_backup(
            tmp_path / "legacy.zip", donor,
            db_member="data/assistance.db",          # 历史库文件名
            backup_info=None,                         # 历史包没有 backup_info.json
        )
        # 生产库先放一个现代库，确保快照可用
        prod = tmp_path / "prod.db"
        _build_modern_db(prod)
        svc = _make_service(tmp_path)

        result = svc._restore_backup_impl(zip_path, password=None, allow_key_mismatch=True)

        assert result["success"] is True
        assert result["database_restored"] is True
        # 备份不含 uploads → 必须提示核对附件
        assert result["uploads_restored"] is False
        assert result["attachments_need_review"] is True

        conn = sqlite3.connect(str(prod))
        try:
            tables = {r[0] for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
            assert "compat_marker" in tables                       # 数据保留
            assert conn.execute("SELECT note FROM compat_marker").fetchone()[0] == "legacy-data"
            assert "account_package_receipts" in tables            # 缺表已按模型补齐
            rev = conn.execute("SELECT version_num FROM alembic_version").fetchone()
            assert rev and rev[0] == _current_head()               # 已迁移到 head
            assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        finally:
            conn.close()

    def test_old_backup_info_without_format_version_is_tolerated(self, tmp_path):
        """旧版 backup_info（无 format_version / 无指纹）不得阻断恢复。"""
        donor = tmp_path / "donor.db"
        _build_modern_db(donor)
        zip_path = _zip_legacy_backup(
            tmp_path / "old-info.zip", donor,
            db_member="data/assistance.db",
            backup_info={"timestamp": "20250101_000000", "description": "old", "include_uploads": False},
        )
        prod = tmp_path / "prod.db"
        _build_modern_db(prod)
        svc = _make_service(tmp_path)

        result = svc._restore_backup_impl(zip_path, password=None, allow_key_mismatch=True)

        assert result["success"] is True
        assert "key_mismatch" not in result  # 无指纹 → 不做密钥强制标记

    def test_root_level_db_name_is_located(self, tmp_path):
        """历史包把库放在压缩包根目录（无 data/ 前缀）也要能恢复。"""
        donor = tmp_path / "donor.db"
        _build_modern_db(donor)
        zip_path = _zip_legacy_backup(
            tmp_path / "root-db.zip", donor,
            db_member="rural_revitalization.db",
        )
        prod = tmp_path / "prod.db"
        _build_modern_db(prod)
        svc = _make_service(tmp_path)

        result = svc._restore_backup_impl(zip_path, password=None, allow_key_mismatch=True)
        assert result["success"] is True


class TestForwardCompatibilityGuard:
    """来自更高版本的备份包：必须在覆盖生产库前拒绝。"""

    def test_future_revision_rejected_without_touching_prod(self, tmp_path):
        donor = tmp_path / "future.db"
        conn = sqlite3.connect(str(donor))
        try:
            conn.execute("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)")
            conn.execute("INSERT INTO alembic_version VALUES ('zzz_future_revision_999')")
            conn.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT)")
            conn.commit()
        finally:
            conn.close()
        zip_path = _zip_legacy_backup(tmp_path / "future.zip", donor)

        prod = tmp_path / "prod.db"
        _build_modern_db(prod)
        before = prod.read_bytes()
        svc = _make_service(tmp_path)

        real_backend = __import__("pathlib").Path(__file__).resolve().parents[2]
        with patch("app.utils.paths.get_project_backend_dir", return_value=str(real_backend)):
            with pytest.raises(BackupRestoreError) as ei:
                svc._restore_backup_impl(zip_path, password=None, allow_key_mismatch=True)

        assert "更高版本" in str(ei.value) or "升级" in str(ei.value)
        assert prod.read_bytes() == before, "未替换生产库前失败不得改动现场数据"
