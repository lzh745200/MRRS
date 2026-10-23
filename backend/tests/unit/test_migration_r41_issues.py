"""W27 P1 回归：死表 ``issues`` 清理迁移（``r41_drop_issues_001``）。

## 背景
``Issue``（表 ``issues``）是**只做了一半的功能骨架**：无任何端点/服务使用、
前端无对应页面，它自带的 6 个扩展字段（重现步骤/期望行为/实际行为/发现版本/
修复版本/负责人）本就零引用。

处置是**删表**而非只删字段 —— 剩下的字段也没有任何写入路径，保留一张永远
为空的表只会让人误以为"问题追踪"功能可用。

## 本文件锁定
1. **三分支契约**（沿用 r35/r36/r37/r38）：不存在→跳过；0 行→DROP；
   有数据→改名 ``legacy_issues`` 归档（一行不丢）；归档已存在→不覆盖；
2. **ORM 已移除**：`app.models` 不再导出 `Issue`，`issue_tracking` 模块只剩
   `Feedback`；
3. **Feedback 必须仍在** —— 它是**活的功能**（``/api/v1/feedback`` 已注册）；
   且它的未接线扩展字段（rating/device_info/responded_at/responded_by）
   是"可扩展点"而**不是死字段**，不得误删；
4. 演练清单已登记；单 head 链正确（r40 → r41）。
"""

import importlib.util
import json
import pathlib

import pytest
import sqlalchemy as sa

ROOT = pathlib.Path(__file__).resolve().parents[2]
MIGRATION_PATH = ROOT / "alembic" / "versions" / "r41_drop_issues_001.py"
MANIFEST_PATH = ROOT / "scripts" / "gate_baselines" / "upgrade_legacy_tables.json"
TABLE = "issues"
ARCHIVE = "legacy_issues"


def load_migration():
    spec = importlib.util.spec_from_file_location("r41_drop_issues_001", MIGRATION_PATH)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture()
def bind():
    engine = sa.create_engine("sqlite:///:memory:")
    with engine.connect() as conn:
        yield conn
    engine.dispose()


def _create_table(conn, with_rows=0):
    conn.execute(sa.text(
        f'CREATE TABLE "{TABLE}" (id INTEGER PRIMARY KEY, title TEXT, status TEXT)'
    ))
    for i in range(with_rows):
        conn.execute(sa.text(f'INSERT INTO "{TABLE}" (title, status) VALUES (\'t{i}\', \'open\')'))


class TestThreeBranchContract:
    def test_absent_table_is_skipped(self, bind):
        mod = load_migration()
        result = mod.apply_cleanup(bind)
        assert result["skipped"] == [TABLE]
        assert result["dropped"] == []
        assert result["archived"] == []

    def test_empty_table_is_dropped(self, bind):
        mod = load_migration()
        _create_table(bind, with_rows=0)
        result = mod.apply_cleanup(bind)
        assert result["dropped"] == [TABLE]
        assert not sa.inspect(bind).has_table(TABLE)

    def test_table_with_rows_is_archived_not_lost(self, bind):
        mod = load_migration()
        _create_table(bind, with_rows=5)
        result = mod.apply_cleanup(bind)
        assert result["archived"] == [TABLE]
        assert not sa.inspect(bind).has_table(TABLE)
        assert sa.inspect(bind).has_table(ARCHIVE)
        assert bind.execute(sa.text(f'SELECT COUNT(*) FROM "{ARCHIVE}"')).scalar() == 5

    def test_existing_archive_is_not_overwritten(self, bind):
        mod = load_migration()
        _create_table(bind, with_rows=2)
        bind.execute(sa.text(f'CREATE TABLE "{ARCHIVE}" (id INTEGER PRIMARY KEY, title TEXT)'))
        bind.execute(sa.text(f'INSERT INTO "{ARCHIVE}" (title) VALUES (\'old\')'))
        result = mod.apply_cleanup(bind)
        assert result["skipped"] == [TABLE]
        assert sa.inspect(bind).has_table(TABLE)
        assert bind.execute(sa.text(f'SELECT COUNT(*) FROM "{ARCHIVE}"')).scalar() == 1

    def test_idempotent_second_run(self, bind):
        mod = load_migration()
        _create_table(bind, with_rows=0)
        mod.apply_cleanup(bind)
        assert mod.apply_cleanup(bind)["skipped"] == [TABLE]


class TestModelSide:
    def test_issue_model_removed(self):
        import app.models as models

        for name in models.__all__:
            try:
                getattr(models, name)
            except Exception:
                pass
        assert not hasattr(models, "Issue")
        assert "Issue" not in models.__all__

    def test_issue_tracking_module_has_only_feedback(self):
        from app.models import issue_tracking as mod

        assert not hasattr(mod, "Issue")
        assert hasattr(mod, "Feedback")

    def test_feedback_model_keeps_extensible_columns(self):
        """Feedback 的未接线扩展字段是**可扩展点**，不得被当成死字段删掉。"""
        from app.models.issue_tracking import Feedback

        cols = {c.name for c in Feedback.__table__.columns}
        assert {"rating", "device_info", "responded_at", "responded_by"} <= cols

    def test_feedback_endpoint_still_registered(self):
        """Feedback 是活功能：/api/v1/feedback 端点必须仍在。"""
        from app.api.v1 import feedback as fb

        paths = {r.path for r in fb.router.routes}
        assert any(p.startswith("/feedback") for p in paths), paths


class TestManifestContract:
    def test_manifest_lists_issues(self):
        payload = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        assert TABLE in payload.get("legacy_tables", [])
        for earlier in ("rural_tasks", "budget_records", "annual_income"):
            assert earlier in payload.get("legacy_tables", []), f"清单丢了历史表 {earlier}"

    def test_migration_chain(self):
        mod = load_migration()
        assert mod.down_revision == "r40_prune_annual_industry_cols_001"
        assert mod.revision == "r41_drop_issues_001"
