# -*- coding: utf-8 -*-
"""pii_col_width_001 迁移的收口证据（2026-10-29 审计，Critical）。

为什么需要这个测试：空库 `alembic upgrade head` 时该迁移报 `widened 0 column(s)`
—— 因为库是 `001_baseline` 的 `create_all()` 用**当前模型**建的，列宽一开始就是 256。
也就是说**迁移逻辑在标准演练里根本不会被执行**（这正是审计项 C1「迁移基线自证」）。
所以要直接构造「旧库」状态（VARCHAR(20)）来验证迁移真的能改宽。
"""
import importlib.util
from pathlib import Path

from sqlalchemy import create_engine

# alembic/versions 不是包（无 __init__.py），按文件路径加载迁移模块
_MIG_PATH = Path(__file__).resolve().parents[2] / "alembic" / "versions" / "pii_col_width_001.py"
_spec = importlib.util.spec_from_file_location("pii_col_width_001", _MIG_PATH)
mig = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mig)


def _table_info(conn, table):
    return {r[1]: r[2] for r in conn.exec_driver_sql(f"PRAGMA table_info({table})")}


def test_widens_narrow_column_to_256(tmp_path):
    """旧库 VARCHAR(20) → 迁移后必须是 VARCHAR(256)。"""
    db = tmp_path / "legacy.db"
    engine = create_engine(f"sqlite:///{db}")
    with engine.begin() as conn:
        conn.exec_driver_sql(
            "CREATE TABLE users (id INTEGER PRIMARY KEY, phone VARCHAR(20))"
        )
        conn.exec_driver_sql("INSERT INTO users (id, phone) VALUES (1, '13800138000')")

    # 直接驱动迁移里的 _widen（不经 alembic op 上下文，需要一个 bind）
    from alembic.migration import MigrationContext
    from alembic.operations import Operations

    with engine.begin() as conn:
        ctx = MigrationContext.configure(conn)
        with Operations.context(ctx):
            changed = mig._widen(conn, "users", "phone", mig.TARGET_LENGTH)
        assert changed is True

    with engine.connect() as conn:
        info = _table_info(conn, "users")
        assert info["phone"] == "VARCHAR(256)", info
        # 数据不丢
        assert conn.exec_driver_sql("SELECT phone FROM users").scalar() == "13800138000"


def test_idempotent_when_already_wide(tmp_path):
    """已经 256 的列不得重复改（迁移可重入）。"""
    db = tmp_path / "wide.db"
    engine = create_engine(f"sqlite:///{db}")
    with engine.begin() as conn:
        conn.exec_driver_sql("CREATE TABLE users (id INTEGER PRIMARY KEY, phone VARCHAR(256))")

    from alembic.migration import MigrationContext
    from alembic.operations import Operations

    with engine.begin() as conn:
        ctx = MigrationContext.configure(conn)
        with Operations.context(ctx):
            assert mig._widen(conn, "users", "phone", mig.TARGET_LENGTH) is False


def test_missing_table_or_column_is_skipped(tmp_path):
    """历史库可能缺表/缺列：必须跳过而不是炸。"""
    db = tmp_path / "missing.db"
    engine = create_engine(f"sqlite:///{db}")

    from alembic.migration import MigrationContext
    from alembic.operations import Operations

    with engine.begin() as conn:
        ctx = MigrationContext.configure(conn)
        with Operations.context(ctx):
            assert mig._widen(conn, "no_such_table", "phone", 256) is False

    with engine.begin() as conn:
        conn.exec_driver_sql("CREATE TABLE users (id INTEGER PRIMARY KEY)")
        from alembic.migration import MigrationContext as MC2
        from alembic.operations import Operations as Op2

        ctx2 = MC2.configure(conn)
        with Op2.context(ctx2):
            assert mig._widen(conn, "users", "no_such_col", 256) is False


def test_target_length_fits_measured_ciphertext():
    """收口证据：实测最长密文 115 字符，目标列宽必须放得下。"""
    import os

    os.environ.setdefault("ENCRYPTION_KEY", "evidence-probe-key-0123456789abcdef")
    from app.core.pii_crypto import encrypt_pii

    longest = max(
        len(encrypt_pii(t))
        for t in ("522701199001011234", "5" * 64, "13800138000", "1" * 50)
    )
    assert longest <= mig.TARGET_LENGTH, f"密文 {longest} 超出目标列宽 {mig.TARGET_LENGTH}"