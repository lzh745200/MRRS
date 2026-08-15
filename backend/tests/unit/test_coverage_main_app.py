# -*- coding: utf-8 -*-
"""
补测 app/main.py 缺失分支：lifespan 关闭钩子（行 83-87）。

现有 test_main_app.py 的 test_lifespan_enter_and_exit 仅 patch 了部分停止函数，
且未 patch task_queue 的 start/stop，关闭半段中
_stop_backup_scheduler / _stop_wal_checkpoint_scheduler / _stop_approval_reminder /
_stop_resource_monitoring / _stop_database_health_monitoring 未被真实执行，
导致 app/main.py 行 83-87 缺覆盖。此处通过完整驱动 lifespan 的 enter/exit，
让 5 个停止函数（均带 try/except 兜底）真实执行。
"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import app.main as m


class TestLifespanShutdown:
    @pytest.mark.asyncio
    async def test_shutdown_executes_stop_functions(self):
        # 所有启动侧函数 patch 为 MagicMock，避免真实副作用（建表/alembic/线程调度器）
        start_funcs = [
            "_init_database_tables",
            "_load_token_blacklist",
            "_check_and_record_version_change",
            "_seed_default_admin",
            "_check_required_packages",
            "_verify_file_integrity",
            "_start_resource_monitoring",
            "_start_database_health_monitoring",
            "_run_database_startup_check",
            "_start_approval_reminder",
            "_start_wal_checkpoint_scheduler",
            "_start_backup_scheduler",
        ]
        patchers = [patch.object(m, name, MagicMock()) for name in start_funcs]

        # task_queue 在 lifespan 内部按需导入，patch 为 async mock
        import app.services.task_queue as tq_module

        fake_tq = MagicMock()
        fake_tq.start = AsyncMock()
        fake_tq.stop = AsyncMock()
        patchers.append(patch.object(tq_module, "task_queue", fake_tq))

        for p in patchers:
            p.start()
        try:
            async with m.lifespan(m.app):
                pass
        finally:
            for p in reversed(patchers):
                p.stop()

        # 关闭半段应真实调用 5 个停止函数（未 patch，走真实实现）
        assert fake_tq.stop.await_count == 1
