"""覆盖 `app.main._run_alembic_upgrade` 的「未知 revision」前置校验（R57 备份兼容引入）。

旧程序打开更高版本备份时，库里的 alembic revision 不在当前迁移链上；原实现由
alembic 抛 `CommandError`，日志只有堆栈。新增守卫必须在开发/测试环境记录明确
错误并返回，在生产环境 fail-loud 抛出可读消息。
"""
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app import main as app_main
from app.core.config import settings


class _ConnCtx:
    def __enter__(self):
        return object()

    def __exit__(self, *exc_info):
        return False


def _patch_migration_environment():
    """让 alembic 读取到「库 revision 不在脚本链上」的假环境。"""
    script_dir = SimpleNamespace(
        get_current_head=lambda: "rev_head",
        walk_revisions=lambda: [SimpleNamespace(revision="rev_head")],
    )
    migration_ctx = SimpleNamespace(get_current_revision=lambda: "rev_from_future")
    engine = MagicMock()
    engine.connect.return_value = _ConnCtx()
    return [
        patch("alembic.script.ScriptDirectory.from_config", return_value=script_dir),
        patch("alembic.runtime.migration.MigrationContext.configure", return_value=migration_ctx),
        patch("app.core.database.engine", engine),
    ]


@pytest.fixture()
def restore_migration_status():
    saved = dict(app_main._migration_status)
    yield
    app_main._migration_status.clear()
    app_main._migration_status.update(saved)


class TestUnknownRevisionGuard:
    def test_dev_records_unknown_revision_and_returns(
        self, monkeypatch, restore_migration_status, caplog
    ):
        monkeypatch.setattr(settings, "ENVIRONMENT", "test", raising=False)
        patches = _patch_migration_environment()
        try:
            for item in patches:
                item.start()
            app_main._run_alembic_upgrade()
        finally:
            for item in reversed(patches):
                item.stop()

        assert app_main._migration_status["at_head"] is False
        assert app_main._migration_status["error_type"] == "UnknownRevision"
        assert "不在当前程序的迁移链上" in caplog.text

    def test_production_raises_with_actionable_message(
        self, monkeypatch, restore_migration_status
    ):
        monkeypatch.setattr(settings, "ENVIRONMENT", "production", raising=False)
        patches = _patch_migration_environment()
        try:
            for item in patches:
                item.start()
            with pytest.raises(RuntimeError, match="更高版本的程序"):
                app_main._run_alembic_upgrade()
        finally:
            for item in reversed(patches):
                item.stop()

        assert app_main._migration_status["at_head"] is False
        # 抛出后由外层 except 统一记录异常类名，故此处是 RuntimeError（消息仍为可操作文案）。
        assert app_main._migration_status["error_type"] == "RuntimeError"
