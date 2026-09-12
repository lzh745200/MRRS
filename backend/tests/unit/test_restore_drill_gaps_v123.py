# -*- coding: utf-8 -*-
"""恢复演练 / 调度任务 6 行覆盖缺口的行为断言（v1.12.3 门禁：99.98% → 100%）。

背景：架构评估 C1（月度备份恢复演练）落地后，全量 pytest 为
**10978 passed / 0 failed，但覆盖率 99.98%** —— 以下 4 处未被触达，
`.coveragerc` fail_under=100 门禁因此变红：

| 位置 | 未覆盖行 |
|---|---|
| `services/backup_scheduler.py` | 484-485（提醒发送失败的兜底）、493-494（任务级异常兜底） |
| `services/restore_drill_service.py` | 121（integrity_check 非 "ok"）、184（非加密 RuntimeError 上抛） |

这 4 处都是**真实存在且值得断言的行为**，故补行为断言而非 `# pragma: no cover`：

* 121：`integrity_check` 返回非 "ok" → 抛 DatabaseError → 演练记为 `fail`；
* 184：zip 成员解压抛**非加密** RuntimeError → 必须上抛，
  **不得**被误判成 `skipped_encrypted` 而把一个坏备份"放过去"；
* 484-485：演练失败时的管理员提醒**发送失败**只告警，不改变结论、不打断任务；
* 493-494：任务级异常必须被吞掉（调度器线程不被单个任务拖死）。

附带发现（一并修正）：既有 `test_restore_drill.py::TestSchedulerJob` 里有
**失效的 patch 目标** —— `backup_scheduler` 在模块级绑定名字
（`from app.services.system_config_service import get_config` /
`from app.core.transaction import get_db_context`），patch 源模块属性
不会影响已绑定名，导致 `test_job_exception_is_swallowed` 从未真正注入异常
（测试"通过"却什么都没断言）。本文件用正确目标（patch 绑定处）断言同一行为。
"""

import os
import sqlite3
import zipfile
from unittest.mock import MagicMock, patch

import pytest

from app.services import backup_scheduler, restore_drill_service
from app.services.restore_drill_service import RESTORE_DRILL_STATUS, run_restore_drill

_DB_MEMBER = "data/rural_revitalization.db"
_STATUS_DEFAULTS = {
    "status": "never",
    "checked_at": None,
    "backup_file": None,
    "error_type": None,
    "tables_checked": 0,
}


@pytest.fixture(autouse=True)
def _isolate_status():
    RESTORE_DRILL_STATUS.update(_STATUS_DEFAULTS)
    yield
    RESTORE_DRILL_STATUS.update(_STATUS_DEFAULTS)


def _make_backup_zip(path: str) -> None:
    """写一个内含真实 SQLite 库的备份包（与 backup_service 的成员名一致）。"""
    tmp_db = path + ".tmpdb"
    conn = sqlite3.connect(tmp_db)
    try:
        conn.execute("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY)")
        conn.execute("INSERT INTO users (id) VALUES (1)")
        conn.commit()
    finally:
        conn.close()
    with open(tmp_db, "rb") as fh:
        payload = fh.read()
    os.remove(tmp_db)
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr(_DB_MEMBER, payload)


def _ctx(db):
    ctx = MagicMock()
    ctx.__enter__ = MagicMock(return_value=db)
    ctx.__exit__ = MagicMock(return_value=False)
    return ctx


class TestRestoreDrillVerifyGaps:
    def test_integrity_check_not_ok_is_recorded_as_fail(self, tmp_path):
        """121 行：库可读但 integrity_check 非 "ok" → fail，绝不静默通过。"""
        backup_dir = tmp_path / "backups"
        backup_dir.mkdir()
        _make_backup_zip(str(backup_dir / "backup_100.zip"))

        class _BrokenConn:
            def execute(self, _sql):
                return self

            def fetchone(self):
                return ("row 1 missing from index idx_users",)

            def close(self):
                pass

        with patch.object(
            restore_drill_service.sqlite3, "connect", return_value=_BrokenConn()
        ), patch("app.services.system_config_service.set_config"):
            result = run_restore_drill(backup_dir=str(backup_dir))

        assert result["status"] == "fail"
        assert result["error_type"] == "DatabaseError"
        assert result["backup_file"] == "backup_100.zip"

    def test_non_encrypted_extract_error_is_not_skipped(self, tmp_path):
        """184 行：非加密 RuntimeError 上抛 → fail（不得记 skipped_encrypted）。"""
        backup_dir = tmp_path / "backups"
        backup_dir.mkdir()
        _make_backup_zip(str(backup_dir / "backup_200.zip"))

        with patch.object(
            zipfile.ZipFile, "extract", side_effect=RuntimeError("bad compressed data")
        ), patch("app.services.system_config_service.set_config"):
            result = run_restore_drill(backup_dir=str(backup_dir))

        assert result["status"] == "fail"
        assert result["error_type"] == "RuntimeError"


class TestMissingBackupDirFallback:
    """`backup_dir` 缺省时的两级回退（restore_drill_service 153-154 / 158-160）。

    这两行此前的覆盖是"意外得来"的：既有 `test_job_exception_is_swallowed`
    因 patch 目标失效而**真的**跑了一次真实演练（测试环境无备份 → no_backup），
    顺带走到了回退路径。修正 patch 目标后该测试才真正断言异常吞掉，
    回退路径必须由本类**显式**覆盖，不再依赖测试环境的副作用。
    """

    def test_config_read_failure_falls_back_to_default_path(self, tmp_path):
        """153-154（配置读取失败降级为空）+ 158-160（退回默认备份目录）。"""
        empty_dir = tmp_path / "empty_backups"  # 不创建：模拟"目录不存在/无备份"
        with patch(
            "app.services.system_config_service.get_config",
            side_effect=RuntimeError("config store down"),
        ), patch("app.utils.paths.get_backup_path", return_value=empty_dir), patch(
            "app.services.system_config_service.set_config"
        ):
            result = run_restore_drill()  # backup_dir=None → 走回退链

        assert result["status"] == "no_backup"
        assert result["backup_file"] is None


class TestSchedulerJobGaps:
    """注意 patch 目标：必须打在 `backup_scheduler` 的绑定处（模块级 import）。"""

    @pytest.mark.asyncio
    async def test_job_logs_non_fail_non_ok_status(self):
        """492 行：状态非 fail/ok（如 no_backup）时只记录，不发"演练失败"提醒。"""
        with patch.object(backup_scheduler, "get_config", return_value="30"), \
             patch.object(backup_scheduler, "get_db_context", return_value=_ctx(MagicMock())), \
             patch("app.services.restore_drill_service.is_drill_due", return_value=True), \
             patch(
                 "app.services.restore_drill_service.run_restore_drill",
                 return_value={"status": "no_backup"},
             ), \
             patch.object(backup_scheduler, "_send_backup_reminder") as mock_send:
            await backup_scheduler.restore_drill_job()

        assert mock_send.called is False  # 仅 fail 才打扰管理员

    @pytest.mark.asyncio
    async def test_job_swallows_unexpected_error(self):
        """493-494 行：任务级异常被吞掉（调度线程不被单个任务拖死）。"""
        with patch.object(backup_scheduler, "get_config", side_effect=RuntimeError("boom")):
            await backup_scheduler.restore_drill_job()  # 不应抛出

    @pytest.mark.asyncio
    async def test_reminder_failure_does_not_break_job(self):
        """484-485 行：提醒发送失败只告警，不改变演练结论、不打断任务。"""
        with patch.object(backup_scheduler, "get_config", return_value="30"), \
             patch.object(backup_scheduler, "get_db_context", return_value=_ctx(MagicMock())), \
             patch("app.services.restore_drill_service.is_drill_due", return_value=True), \
             patch(
                 "app.services.restore_drill_service.run_restore_drill",
                 return_value={
                     "status": "fail",
                     "backup_file": "b.zip",
                     "error_type": "BadZipFile",
                 },
             ), \
             patch.object(
                 backup_scheduler, "_send_backup_reminder",
                 side_effect=RuntimeError("notification channel down"),
             ):
            await backup_scheduler.restore_drill_job()  # 不应抛出
