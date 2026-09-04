"""app.main._run_alembic_upgrade 生产环境 fail-loud 分支补测（task#20）。

覆盖 main.py 行 500-504：ENVIRONMENT=production 时迁移失败必须记录 critical
并重新抛出（中止启动），而非静默降级。此前该分支未被任何测试触及。
"""
from unittest.mock import patch

import pytest

from app import main as app_main
from app.core.config import settings


class TestRunAlembicUpgradeProductionFailLoud:
    def test_production_migration_failure_reraises(self, monkeypatch):
        """生产环境迁移失败 → 记录 critical + raise（行 499-504）。"""
        monkeypatch.setattr(settings, "ENVIRONMENT", "production", raising=False)
        saved = dict(app_main._migration_status)
        try:
            # 令 sa_inspect(engine) 抛异常，模拟迁移过程失败
            with patch("sqlalchemy.inspect", side_effect=RuntimeError("migration boom")):
                with pytest.raises(RuntimeError, match="migration boom"):
                    app_main._run_alembic_upgrade()
            # 迁移状态应标记为未达 head，且只记录异常类名（不泄漏原文）
            assert app_main._migration_status["at_head"] is False
            assert app_main._migration_status["error_type"] == "RuntimeError"
        finally:
            app_main._migration_status.clear()
            app_main._migration_status.update(saved)

    def test_non_production_migration_failure_degrades(self, monkeypatch):
        """开发/测试环境迁移失败 → 记录 warning 后不抛出（行 505-507）。"""
        monkeypatch.setattr(settings, "ENVIRONMENT", "test", raising=False)
        saved = dict(app_main._migration_status)
        try:
            with patch("sqlalchemy.inspect", side_effect=RuntimeError("migration boom")):
                # 不应抛出——保持启动韧性
                app_main._run_alembic_upgrade()
            assert app_main._migration_status["at_head"] is False
            assert app_main._migration_status["error_type"] == "RuntimeError"
        finally:
            app_main._migration_status.clear()
            app_main._migration_status.update(saved)
