"""P2-2 FileBlob 模型 + Alembic 迁移 + SingleHead 锁定测试。

覆盖：
- ``FileBlob`` 表结构（内容寻址主键、引用计数、时间戳）与模型注册；
- 迁移脚本 ``upgrade`` / ``downgrade``（幂等）；
- 迁移链 **SingleHead**（严禁分叉，历史事故：分叉导致打包实例启动失败）。
"""

import importlib.util
from pathlib import Path

from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.operations import Operations
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

_BACKEND = Path(__file__).resolve().parents[2]
_MIGRATION_PATH = _BACKEND / "alembic" / "versions" / "file_blob_001_add_file_blobs.py"


def _load_migration():
    spec = importlib.util.spec_from_file_location("file_blob_001", _MIGRATION_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestFileBlobModel:
    def test_tablename_and_primary_key(self):
        from app.models.file_blob import FileBlob

        assert FileBlob.__tablename__ == "file_blobs"
        assert FileBlob.__table__.primary_key.columns.keys() == ["sha256"]

    def test_columns_present(self):
        from app.models.file_blob import FileBlob

        cols = {c.name for c in FileBlob.__table__.columns}
        assert {"sha256", "path", "size", "ref_count", "created_at"} <= cols

    def test_lazy_model_map(self):
        import app.models as models

        assert "FileBlob" in models._MODULE_MAP
        from app.models import FileBlob as Lazy  # noqa: N813

        assert Lazy.__tablename__ == "file_blobs"


class TestFileBlobMigration:
    def test_revision_chain(self):
        mod = _load_migration()
        assert mod.revision == "file_blob_001"
        assert mod.down_revision == "index_dedup_001"

    def test_upgrade_creates_table_idempotently_and_downgrade_drops(self):
        mod = _load_migration()
        engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        conn = engine.connect()
        ctx = MigrationContext.configure(conn)
        mod.op = Operations(ctx)

        def _exists() -> bool:
            row = conn.exec_driver_sql(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='file_blobs'"
            ).fetchone()
            return row is not None

        assert not _exists()
        mod.upgrade()
        assert _exists()
        mod.upgrade()  # 幂等：重复执行不报错
        assert _exists()
        mod.downgrade()
        assert not _exists()
        mod.downgrade()  # 幂等：重复 downgrade 不报错
        conn.close()

    def test_table_columns_match_model(self):
        mod = _load_migration()
        engine = create_engine("sqlite:///:memory:", poolclass=StaticPool)
        conn = engine.connect()
        mod.op = Operations(MigrationContext.configure(conn))
        mod.upgrade()
        cols = {
            row[1]
            for row in conn.exec_driver_sql("PRAGMA table_info(file_blobs)").fetchall()
        }
        assert cols == {"sha256", "path", "size", "ref_count", "created_at"}
        conn.close()


class TestSingleHead:
    def test_alembic_has_exactly_one_head(self):
        cfg = Config(str(_BACKEND / "alembic.ini"))
        cfg.set_main_option("script_location", str(_BACKEND / "alembic"))
        heads = list(ScriptDirectory.from_config(cfg).get_heads())
        assert len(heads) == 1, f"Alembic 出现分叉（多 head）：{heads}"
