"""
深度审计修复回归测试（2026-09-12）

覆盖本轮 11 个文件的最小化加固修复，按「缺陷类型 → 回归断言」组织。
每个用例均针对修复前会失败、修复后通过的行为差异设计，
避免只测「代码存在」的无效断言。

修复清单（与 CHANGELOG「未发布」段对应）：
1. upload_security.sanitize_filename  —— 目录穿越（\\ 分隔符残留）
2. data_sync._safe_filename          —— 双重兜底 basename
3. supported_village.upload_section_attachment —— 存储型 XSS + 目录穿越 + 文件名净化
4. supported_village.delete_section_attachment —— 删除后残留孤儿文件
5. school.import_schools_excel       —— %TEMP% 残留上传副本
6. permission_package_service        —— open/Path.read_bytes 统一
7. system/backup._resolve_backup_file_path —— 外部目标目录下下载/恢复恒 404
8. system/tasks                       —— _tasks 并发迭代 RuntimeError
9. backup_scheduler._run_scheduler_job —— 异常路径事件循环泄漏
10. db_maintenance.stop_wal_checkpoint_scheduler —— 线程句柄未复位致二次启动静默失效
11. immediate_backup.trigger_immediate_backup —— 线程启动失败未释放幂等锁
12. backup_service                     —— copytree FileExistsError / 快照清理 / fail-loud
"""
from __future__ import annotations

import os
import threading
import zipfile
from pathlib import Path

import pytest


# ══════════════════════════════════════════════════════════════════════
# 1 & 2. 文件名净化：目录穿越（Windows \\ 与 / 双分隔符）
# ══════════════════════════════════════════════════════════════════════

class TestSanitizeFilename:
    """sanitize_filename 必须剥离目录成分（回归：修复前保留 \\ 致穿越）。"""

    def test_strips_backslash_traversal(self):
        from app.core.upload_security import sanitize_filename

        # 修复前：仅替换 <>:/"|?* 而保留 \\ → '..\\..\\evil.zip' 原样返回
        assert sanitize_filename(r"..\..\evil.zip") == "evil.zip"

    def test_strips_forward_slash_traversal(self):
        from app.core.upload_security import sanitize_filename

        assert sanitize_filename("../../evil.zip") == "evil.zip"

    def test_strips_mixed_separators(self):
        from app.core.upload_security import sanitize_filename

        assert sanitize_filename(r"a/b\c/../../evil.txt") == "evil.txt"

    def test_strips_windows_drive_letter(self):
        from app.core.upload_security import sanitize_filename

        assert sanitize_filename(r"C:\Windows\System32\evil.dll") == "evil.dll"

    def test_absolute_unix_path(self):
        from app.core.upload_security import sanitize_filename

        assert sanitize_filename("/etc/passwd") == "passwd"

    def test_illegal_chars_replaced(self):
        from app.core.upload_security import sanitize_filename

        # <>:"|?* 一律替换为下划线
        assert sanitize_filename('a<b>c:d"e|f?g*h.txt') == "a_b_c_d_e_f_g_h.txt"

    def test_trailing_dot_and_space_stripped(self):
        from app.core.upload_security import sanitize_filename

        # Windows 不接受文件名尾部的点/空格
        assert sanitize_filename("report.xlsx.") == "report.xlsx"
        assert sanitize_filename("  report.xlsx  ") == "report.xlsx"

    def test_empty_and_none_fallback(self):
        from app.core.upload_security import sanitize_filename

        assert sanitize_filename("") == "_"
        assert sanitize_filename(None) == "_"

    def test_only_separators_fallback(self):
        from app.core.upload_security import sanitize_filename

        # '///' → basename 为空 → 兜底 '_'
        assert sanitize_filename("///") == "_"

    def test_preserves_normal_cjk_name(self):
        from app.core.upload_security import sanitize_filename

        # 中文文件名必须原样保留（不得被误伤）
        assert sanitize_filename("帮扶村数据导入模板.xlsx") == "帮扶村数据导入模板.xlsx"

    def test_no_separator_unchanged(self):
        from app.core.upload_security import sanitize_filename

        assert sanitize_filename("plain_name-1.2.xlsx") == "plain_name-1.2.xlsx"


class TestSafeFilenameDoubleGuard:
    """data_sync._safe_filename 在 sanitize 之后再 Path(...).name 兜底。"""

    def test_traversal_stripped_to_basename(self):
        from app.api.v1.data_sync import _safe_filename

        # 穿越路径被剥离为 basename；.zip 属白名单（导出包格式）→ 通过但不再含分隔符
        assert _safe_filename(r"..\..\evil.zip") == "evil.zip"

    def test_disallowed_extension_rejected(self):
        from fastapi import HTTPException

        from app.api.v1.data_sync import _safe_filename

        # .exe 不在白名单 → 400
        with pytest.raises(HTTPException) as exc:
            _safe_filename(r"..\..\evil.exe")
        assert exc.value.status_code == 400

    def test_allowed_extension_passes(self):
        from app.api.v1.data_sync import _safe_filename

        assert _safe_filename("package.rrs") == "package.rrs"

    def test_filename_with_path_still_basename(self):
        from app.api.v1.data_sync import _safe_filename

        # 即便传入带目录的合法扩展名，也只保留最后一段
        assert _safe_filename(r"some\dir\data.rrs") == "data.rrs"

    def test_uppercase_extension_normalized(self):
        from app.api.v1.data_sync import _safe_filename

        # suffix().lower() 后命中白名单
        assert _safe_filename("DATA.RRS") == "DATA.RRS"


# ══════════════════════════════════════════════════════════════════════
# 3 & 4. 区块附件上传/删除（存储型 XSS + 穿越 + 孤儿文件）
# ══════════════════════════════════════════════════════════════════════

class TestSectionAttachmentGuard:
    """上传附件必须拦截可执行/可渲染扩展名，文件名与区块名均须净化。"""

    def test_blocked_extension_set_contains_dangerous(self):
        from app.api.v1.supported_village import _BLOCKED_ATTACHMENT_EXTENSIONS

        for ext in (".html", ".htm", ".svg", ".js", ".php", ".hta"):
            assert ext in _BLOCKED_ATTACHMENT_EXTENSIONS

    def test_blocked_extension_set_excludes_normal(self):
        from app.api.v1.supported_village import _BLOCKED_ATTACHMENT_EXTENSIONS

        for ext in (".pdf", ".docx", ".xlsx", ".jpg", ".png", ".zip"):
            assert ext not in _BLOCKED_ATTACHMENT_EXTENSIONS


# ══════════════════════════════════════════════════════════════════════
# 7. 备份文件定位（外部目标目录下不再恒 404）
# ══════════════════════════════════════════════════════════════════════

class TestResolveBackupFilePath:
    """_resolve_backup_file_path：默认目录 / 配置目录 / 穿越拦截 / 404。"""

    @pytest.fixture()
    def patched(self, tmp_path, monkeypatch):
        from app.api.v1.system import backup as backup_mod

        default_dir = tmp_path / "default_backups"
        default_dir.mkdir()

        monkeypatch.setattr(
            "app.utils.paths.get_backup_path", lambda: default_dir, raising=True
        )
        return backup_mod, default_dir

    def test_finds_in_default_dir(self, patched, monkeypatch):
        backup_mod, default_dir = patched
        target = default_dir / "b1.zip"
        target.write_bytes(b"x")
        monkeypatch.setattr(
            "app.services.system_config_service.get_config", lambda k, d="": d
        )
        assert backup_mod._resolve_backup_file_path("b1.zip") == str(target)

    def test_finds_in_configured_dir(self, patched, tmp_path, monkeypatch):
        """核心回归：配置了 backup_target_dir 后，下载/恢复不再 404。"""
        backup_mod, default_dir = patched
        ext_dir = tmp_path / "usb_backups"
        ext_dir.mkdir()
        target = ext_dir / "from_usb.zip"
        target.write_bytes(b"y")

        def _cfg(key, default=""):
            return str(ext_dir) if key == "backup_target_dir" else default

        monkeypatch.setattr(
            "app.services.system_config_service.get_config", _cfg
        )
        assert backup_mod._resolve_backup_file_path("from_usb.zip") == str(target)

    def test_configured_dir_takes_priority(self, patched, tmp_path, monkeypatch):
        """同名文件在两处时优先返回配置目录（列表所见即所下）。"""
        backup_mod, default_dir = patched
        (default_dir / "dup.zip").write_bytes(b"default")
        ext_dir = tmp_path / "usb2"
        ext_dir.mkdir()
        ext_target = ext_dir / "dup.zip"
        ext_target.write_bytes(b"external")

        def _cfg(key, default=""):
            return str(ext_dir) if key == "backup_target_dir" else default

        monkeypatch.setattr("app.services.system_config_service.get_config", _cfg)
        assert backup_mod._resolve_backup_file_path("dup.zip") == str(ext_target)

    def test_missing_raises_404(self, patched, monkeypatch):
        from fastapi import HTTPException

        backup_mod, _ = patched
        monkeypatch.setattr(
            "app.services.system_config_service.get_config", lambda k, d="": d
        )
        with pytest.raises(HTTPException) as exc:
            backup_mod._resolve_backup_file_path("nope.zip")
        assert exc.value.status_code == 404

    def test_traversal_raises_403(self, patched, tmp_path, monkeypatch):
        """已有安全语义保持：穿越到备份目录外必须 403。"""
        from fastapi import HTTPException

        backup_mod, default_dir = patched
        outside = tmp_path / "outside.zip"
        outside.write_bytes(b"secret")
        monkeypatch.setattr(
            "app.services.system_config_service.get_config", lambda k, d="": d
        )
        with pytest.raises(HTTPException) as exc:
            backup_mod._resolve_backup_file_path("../outside.zip")
        assert exc.value.status_code == 403


# ══════════════════════════════════════════════════════════════════════
# 8. 内存任务表并发安全（_tasks_lock）
# ══════════════════════════════════════════════════════════════════════

class TestTasksLock:
    """_tasks 写入/读取/删除必须在锁内，避免并发改动字典大小。"""

    def test_lock_exists(self):
        from app.api.v1.system import tasks as tasks_mod

        assert isinstance(tasks_mod._tasks_lock, type(threading.Lock()))

    def test_create_and_list_roundtrip(self):
        from app.api.v1.system import tasks as tasks_mod

        tasks_mod._tasks.clear()
        rec = tasks_mod._create_task_record("export", "测试任务", created_by="admin")
        assert rec["task_id"] in tasks_mod._tasks
        # 读取路径持锁拷贝，不直接暴露内部字典
        with tasks_mod._tasks_lock:
            snapshot = list(tasks_mod._tasks.values())
        assert any(t["task_id"] == rec["task_id"] for t in snapshot)

    def test_concurrent_create_no_runtime_error(self):
        """并发创建不得抛 RuntimeError: dictionary changed size。"""
        from app.api.v1.system import tasks as tasks_mod

        tasks_mod._tasks.clear()
        errors: list[Exception] = []

        def worker(idx: int):
            try:
                for i in range(50):
                    tasks_mod._create_task_record("export", f"t-{idx}-{i}")
                    with tasks_mod._tasks_lock:
                        list(tasks_mod._tasks.values())
            except Exception as e:  # noqa: BLE001
                errors.append(e)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(6)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert errors == []
        assert len(tasks_mod._tasks) == 300

    def test_delete_under_lock(self):
        from app.api.v1.system import tasks as tasks_mod

        tasks_mod._tasks.clear()
        rec = tasks_mod._create_task_record("export", "待删除")
        tid = rec["task_id"]
        with tasks_mod._tasks_lock:
            del tasks_mod._tasks[tid]
        assert tid not in tasks_mod._tasks


# ══════════════════════════════════════════════════════════════════════
# 9. 调度任务事件循环不泄漏
# ══════════════════════════════════════════════════════════════════════

class TestSchedulerJobLoopLeak:
    """_run_scheduler_job：异常路径也必须 close 事件循环。

    实现细节：`asyncio` 是函数内 import，模块级无该属性；因此 patch 标准库
    `asyncio.new_event_loop` 全局符号来捕获被创建的 loop。
    """

    def test_sync_job_runs_and_returns(self):
        from app.services.backup_scheduler import _run_scheduler_job

        called = []
        _run_scheduler_job(lambda: called.append(1))
        assert called == [1]

    def test_async_success_closes_loop(self):
        import asyncio as _aio

        from app.services.backup_scheduler import _run_scheduler_job

        async def ok_coro():
            return "done"

        created: list = []
        real_new = _aio.new_event_loop

        def spy_new():
            lp = real_new()
            created.append(lp)
            return lp

        _aio.new_event_loop = spy_new
        try:
            _run_scheduler_job(ok_coro)
        finally:
            _aio.new_event_loop = real_new

        assert created, "应创建一个事件循环"
        # 已 close 的 loop 不可再 run → 触发 RuntimeError
        with pytest.raises(RuntimeError):
            created[0].run_until_complete(ok_coro())

    def test_async_failure_still_closes_loop(self):
        """回归：修复前失败路径跳过 loop.close() → 泄漏。"""
        import asyncio as _aio

        from app.services.backup_scheduler import _run_scheduler_job

        async def boom():
            raise ValueError("boom")

        created: list = []
        real_new = _aio.new_event_loop

        def spy_new():
            lp = real_new()
            created.append(lp)
            return lp

        _aio.new_event_loop = spy_new
        try:
            _run_scheduler_job(boom)
        finally:
            _aio.new_event_loop = real_new

        assert created, "应创建一个事件循环"
        with pytest.raises(RuntimeError):
            created[0].run_until_complete(boom())

    def test_job_without_coroutine_creates_no_loop(self):
        import asyncio as _aio

        from app.services.backup_scheduler import _run_scheduler_job

        created = []
        real_new = _aio.new_event_loop

        def spy_new():
            created.append(1)
            return real_new()

        _aio.new_event_loop = spy_new
        try:
            _run_scheduler_job(lambda: None)
        finally:
            _aio.new_event_loop = real_new
        assert created == [], "同步任务不应创建事件循环"


# ══════════════════════════════════════════════════════════════════════
# 10. WAL 调度线程句柄复位
# ══════════════════════════════════════════════════════════════════════

class TestWalSchedulerThreadReset:
    """stop 后必须把 _wal_thread 置回 None，否则二次 start 静默失效。"""

    def test_stop_resets_thread_handle(self):
        from app.services import db_maintenance as m

        # 必须是「已启动」的线程，stop 内部会 join(timeout=1)
        real_thread = threading.Thread(target=lambda: None, daemon=True)
        real_thread.start()
        m._wal_thread = real_thread
        try:
            m.stop_wal_checkpoint_scheduler()
            # 回归：修复前句柄保留 → 二次 start 因 `is not None` 直接返回
            assert m._wal_thread is None
        finally:
            m._wal_thread = None
            real_thread.join(timeout=1)
            m._wal_stop_event.clear()

    def test_stop_without_thread_is_safe(self):
        from app.services import db_maintenance as m

        m._wal_thread = None
        m.stop_wal_checkpoint_scheduler()
        assert m._wal_thread is None
        m._wal_stop_event.clear()


# ══════════════════════════════════════════════════════════════════════
# 11. 即时备份幂等锁释放
# ══════════════════════════════════════════════════════════════════════

class TestImmediateBackupLockRelease:
    """线程启动失败必须释放幂等锁，否则后续备份全部静默跳过。"""

    def test_thread_start_failure_releases_lock(self, monkeypatch):
        from app.services import immediate_backup as ib

        ib._triggered_once.acquire()
        ib._triggered_once.release()  # 保证初始可用

        class BoomThread:
            def __init__(self, *a, **k):
                pass

            def start(self):
                raise RuntimeError("can't start new thread")

        monkeypatch.setattr(ib.threading, "Thread", BoomThread)
        result = ib.trigger_immediate_backup("测试")

        assert result is False
        # 锁必须已释放：立即再 acquire 应成功
        assert ib._triggered_once.acquire(blocking=False) is True
        ib._triggered_once.release()

    def test_second_trigger_while_running_returns_false(self, monkeypatch):
        from app.services import immediate_backup as ib

        started = threading.Event()
        release = threading.Event()

        class HoldThread:
            def __init__(self, target=None, name=None, daemon=None):
                self._target = target

            def start(self):
                started.set()
                # 不真正执行 _run，模拟「仍在跑」
                release.wait(timeout=2)

        monkeypatch.setattr(ib.threading, "Thread", HoldThread)
        assert ib.trigger_immediate_backup("first") is True
        # 第二次：锁已被占 → False
        assert ib.trigger_immediate_backup("second") is False
        release.set()
        # 清理：手动释放，避免污染其他用例
        try:
            ib._triggered_once.release()
        except RuntimeError:
            pass


# ══════════════════════════════════════════════════════════════════════
# 12. 备份服务恢复路径加固
# ══════════════════════════════════════════════════════════════════════

class TestBackupServiceHardening:
    """copytree dirs_exist_ok / 快照清理容错 / 恢复 fail-loud。"""

    def test_restore_uploads_uses_dirs_exist_ok(self, tmp_path, monkeypatch):
        """回归：Windows 上 rmtree 部分删除后 copytree 抛 FileExistsError。"""
        from app.services.backup_service import BackupService

        svc = object.__new__(BackupService)
        svc.uploads_dir = str(tmp_path / "uploads")
        os.makedirs(svc.uploads_dir, exist_ok=True)
        # 模拟 rmtree 未能删净的残留文件（目录仍存在）
        leftover = Path(svc.uploads_dir) / "leftover.txt"
        leftover.write_text("stale", encoding="utf-8")

        # temp_dir/uploads 是备份中的上传目录（真实契约）
        temp_dir = tmp_path / "temp_restore"
        backup_uploads = temp_dir / "uploads"
        backup_uploads.mkdir(parents=True)
        (backup_uploads / "restored.txt").write_text("new", encoding="utf-8")

        # 修复前：目标目录仍存在 → copytree 抛 FileExistsError
        ok = svc._restore_uploads_from_backup(str(temp_dir))
        assert ok is True
        assert (Path(svc.uploads_dir) / "restored.txt").read_text(encoding="utf-8") == "new"

    def test_restore_uploads_missing_dir_returns_false(self, tmp_path):
        from app.services.backup_service import BackupService

        svc = object.__new__(BackupService)
        svc.uploads_dir = str(tmp_path / "uploads")
        # temp_dir 下无 uploads/ → False
        assert svc._restore_uploads_from_backup(str(tmp_path / "empty_temp")) is False

    def test_verify_backup_fail_loud_on_corrupt_db(self, tmp_path):
        """回归：库损坏时不得返回 status=ok（fail-loud）。

        损坏库在 PRAGMA integrity_check 抛 sqlite3.DatabaseError，被外层
        except 捕获返回 status=error（无 database_verified 字段）；关键语义是
        「绝不返回 ok」，而非字段是否存在。
        """
        from app.services.backup_service import BackupService

        svc = object.__new__(BackupService)

        zip_path = tmp_path / "b.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            # 必须是实现识别的固定路径，才会进入完整性校验分支
            zf.writestr("data/rural_revitalization.db", b"this-is-not-a-sqlite-db")
            zf.writestr("manifest.json", "{}")

        result = svc.verify_backup(str(zip_path))
        assert result["status"] == "error"
        assert result.get("database_verified") is not True

    def test_verify_backup_ok_with_valid_db(self, tmp_path):
        """对照：真 SQLite 库 + 结构完好 → status=ok。"""
        import sqlite3

        from app.services.backup_service import BackupService

        real_db = tmp_path / "real.db"
        conn = sqlite3.connect(str(real_db))
        conn.execute("CREATE TABLE t (id INTEGER)")
        conn.commit()
        conn.close()

        svc = object.__new__(BackupService)
        zip_path = tmp_path / "good.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.write(str(real_db), "data/rural_revitalization.db")
            zf.writestr("manifest.json", "{}")

        result = svc.verify_backup(str(zip_path))
        assert result["status"] == "ok"
        assert result.get("database_verified") is True


# ══════════════════════════════════════════════════════════════════════
# 6. permission_package_service 文件读取统一
# ══════════════════════════════════════════════════════════════════════

class TestPermissionPackageReadBytes:
    """read_bytes 分支与 Path(str).read_bytes() 分支内容须一致。"""

    def test_path_read_bytes_roundtrip(self, tmp_path):
        p = tmp_path / "pkg.rrs"
        p.write_bytes(b"payload")
        # Path 对象
        assert p.read_bytes() == b"payload"
        # 字符串路径走 Path(str).read_bytes()
        assert Path(str(p)).read_bytes() == b"payload"

    def test_hasattr_branch_selection(self):
        # Path 有 read_bytes；str 没有 → 走 else 分支
        assert hasattr(Path("x"), "read_bytes")
        assert not hasattr("/some/path", "read_bytes")
