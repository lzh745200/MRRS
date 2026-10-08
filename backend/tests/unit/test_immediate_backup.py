"""单机即时备份(T1.5): trigger_immediate_backup 幂等/后台执行/备份创建"""
import threading
from unittest.mock import MagicMock, patch

import pytest


class _FakeLock:
    def __init__(self, acquire_ok):
        self._acquire_ok = acquire_ok
        self.released = False
        self.acquire_count = 0

    def acquire(self, blocking=False):
        self.acquire_count += 1
        return self._acquire_ok

    def release(self):
        self.released = True


def _get_ib():
    import app.services.immediate_backup as ib
    return ib


def test_trigger_immediate_backup_queues_thread():
    from app.services.immediate_backup import trigger_immediate_backup

    captured = {}

    class FakeThread:
        def __init__(self, *a, **kw):
            captured["target"] = kw.get("target")
            captured["daemon"] = kw.get("daemon")
            captured["name"] = kw.get("name")

        def start(self):
            captured["started"] = True

    with patch.object(_get_ib(), "_triggered_once", _FakeLock(True)):
        with patch("app.services.immediate_backup.threading.Thread", FakeThread):
            ok = trigger_immediate_backup("测试备份", delay=0)
    assert ok is True
    assert captured["started"] is True
    assert captured["daemon"] is True
    assert captured["name"] == "immediate-backup"
    assert callable(captured["target"])


def test_trigger_immediate_backup_skip_when_busy():
    from app.services.immediate_backup import trigger_immediate_backup

    with patch.object(_get_ib(), "_triggered_once", _FakeLock(False)):
        with patch("app.services.immediate_backup.threading.Thread") as mk:
            ok = trigger_immediate_backup("测试")
    assert ok is False
    mk.assert_not_called()


def test_thread_target_creates_backup_and_releases_lock():
    """线程 target 执行: 创建备份 + 释放锁"""
    from app.services.immediate_backup import trigger_immediate_backup

    captured = {}

    class FakeThread:
        def __init__(self, *a, **kw):
            captured["target"] = kw["target"]

        def start(self):
            pass

    with patch.object(_get_ib(), "_triggered_once", _FakeLock(True)):
        with patch("app.services.immediate_backup.threading.Thread", FakeThread):
            trigger_immediate_backup("线程测试", delay=0)

    svc = MagicMock()
    record = MagicMock()
    record.file_name = "bk.zip"
    svc.create_backup.return_value = record
    mock_db = MagicMock()

    ctx = MagicMock()
    ctx.__enter__.return_value = mock_db

    with patch("app.core.transaction.get_db_context", return_value=ctx):
        with patch("app.services.backup_service.BackupService", return_value=svc) as mk_svc:
            with patch("app.services.system_config_service.get_config", return_value=""):
                fake_lock = _FakeLock(True)
                with patch.object(_get_ib(), "_triggered_once", fake_lock):
                    captured["target"]()
                    svc.create_backup.assert_called_once()
                    assert fake_lock.released is True
                    # 无 target_dir 时使用默认 BackupService(db)
                    assert mk_svc.call_args.args[0] is mock_db


def test_thread_target_uses_target_dir():
    from app.services.immediate_backup import trigger_immediate_backup

    captured = {}

    class FakeThread:
        def __init__(self, *a, **kw):
            captured["target"] = kw["target"]

        def start(self):
            pass

    with patch.object(_get_ib(), "_triggered_once", _FakeLock(True)):
        with patch("app.services.immediate_backup.threading.Thread", FakeThread):
            trigger_immediate_backup("目标目录", delay=0)

    svc = MagicMock()
    mock_db = MagicMock()
    ctx = MagicMock()
    ctx.__enter__.return_value = mock_db

    with patch("app.core.transaction.get_db_context", return_value=ctx):
        with patch("app.services.backup_service.BackupService", return_value=svc) as mk_svc:
            with patch("app.services.system_config_service.get_config", return_value="E:\\bk"):
                fake_lock = _FakeLock(True)
                with patch.object(_get_ib(), "_triggered_once", fake_lock):
                    captured["target"]()
                    _, kwargs = mk_svc.call_args
                    assert kwargs["backup_dir"] == "E:\\bk"
                    assert fake_lock.released is True


def test_thread_target_error_releases_lock():
    from app.services.immediate_backup import trigger_immediate_backup

    captured = {}

    class FakeThread:
        def __init__(self, *a, **kw):
            captured["target"] = kw["target"]

        def start(self):
            pass

    with patch.object(_get_ib(), "_triggered_once", _FakeLock(True)):
        with patch("app.services.immediate_backup.threading.Thread", FakeThread):
            trigger_immediate_backup("异常", delay=0)

    ctx = MagicMock()
    ctx.__enter__.side_effect = RuntimeError("db down")

    with patch("app.core.transaction.get_db_context", return_value=ctx):
        fake_lock = _FakeLock(True)
        with patch.object(_get_ib(), "_triggered_once", fake_lock):
            captured["target"]()  # 不应抛异常
            assert fake_lock.released is True


# ---------------------------------------------------------------------------
# R20：wait=True 的真实成败语义（retention fail-closed 依赖此返回值）
# ---------------------------------------------------------------------------


class _FakeThreadBase:
    """可控线程替身：start 可同步执行 target，is_alive 返回值可配置。"""

    run_on_start = True
    alive_after_start = False

    def __init__(self, *a, **kw):
        self._target = kw.get("target")

    def start(self):
        if self.run_on_start:
            try:
                self._target()
            except BaseException:  # pragma: no cover - 替身不透传真实线程异常
                pass

    def join(self, timeout=None):
        self.joined_timeout = timeout

    def is_alive(self):
        return self.alive_after_start


def _fake_thread_cls(run_on_start=True, alive_after_start=False):
    class _T(_FakeThreadBase):
        pass

    _T.run_on_start = run_on_start
    _T.alive_after_start = alive_after_start
    return _T


def _backup_ctx_ok():
    """返回可成功执行 _run 的上下文补丁（get_db_context / BackupService / get_config）。"""
    svc = MagicMock()
    mock_db = MagicMock()
    ctx = MagicMock()
    ctx.__enter__.return_value = mock_db
    return (
        patch("app.core.transaction.get_db_context", return_value=ctx),
        patch("app.services.backup_service.BackupService", return_value=svc),
        patch("app.services.system_config_service.get_config", return_value=""),
        svc,
    )


def test_wait_true_success_returns_true():
    from app.services.immediate_backup import trigger_immediate_backup

    p_ctx, p_svc, p_cfg, svc = _backup_ctx_ok()
    with patch.object(_get_ib(), "_triggered_once", _FakeLock(True)):
        with patch("app.services.immediate_backup.threading.Thread", _fake_thread_cls()):
            with p_ctx, p_svc, p_cfg:
                ok = trigger_immediate_backup("同步成功", wait=True, wait_timeout=1.0)
    assert ok is True
    svc.create_backup.assert_called_once()


def test_wait_true_timeout_returns_false():
    """join 超时后线程仍存活（t.is_alive()）→ 按失败处理返回 False。"""
    from app.services.immediate_backup import trigger_immediate_backup

    fake_lock = _FakeLock(True)
    with patch.object(_get_ib(), "_triggered_once", fake_lock):
        with patch(
            "app.services.immediate_backup.threading.Thread",
            _fake_thread_cls(run_on_start=False, alive_after_start=True),
        ):
            ok = trigger_immediate_backup("超时", wait=True, wait_timeout=0.01)
    assert ok is False


def test_wait_true_backup_error_returns_false():
    """wait=True 且备份内部抛错 → 真实结果 False（原实现会误报 True）。"""
    from app.services.immediate_backup import trigger_immediate_backup

    ctx = MagicMock()
    ctx.__enter__.side_effect = RuntimeError("db down")
    with patch.object(_get_ib(), "_triggered_once", _FakeLock(True)):
        with patch("app.services.immediate_backup.threading.Thread", _fake_thread_cls()):
            with patch("app.core.transaction.get_db_context", return_value=ctx):
                ok = trigger_immediate_backup("同步失败", wait=True, wait_timeout=1.0)
    assert ok is False


def test_wait_false_backup_error_still_reports_queued():
    """wait=False 原语义不变：只要成功排队即返回 True，不关心备份实际成败。"""
    from app.services.immediate_backup import trigger_immediate_backup

    ctx = MagicMock()
    ctx.__enter__.side_effect = RuntimeError("db down")
    with patch.object(_get_ib(), "_triggered_once", _FakeLock(True)):
        with patch("app.services.immediate_backup.threading.Thread", _fake_thread_cls()):
            with patch("app.core.transaction.get_db_context", return_value=ctx):
                ok = trigger_immediate_backup("异步失败", wait=False)
    assert ok is True


def test_thread_start_failure_returns_false_and_releases_lock():
    from app.services.immediate_backup import trigger_immediate_backup

    fake_lock = _FakeLock(True)

    class BoomThread(_FakeThreadBase):
        def start(self):
            raise RuntimeError("can't start new thread")

    with patch.object(_get_ib(), "_triggered_once", fake_lock):
        with patch("app.services.immediate_backup.threading.Thread", BoomThread):
            ok = trigger_immediate_backup("线程启动失败", wait=True, wait_timeout=1.0)
    assert ok is False
    assert fake_lock.released is True


def test_wait_true_skip_when_busy_returns_false():
    """幂等锁被占用时，无论 wait 与否都返回 False 且不启动线程。"""
    from app.services.immediate_backup import trigger_immediate_backup

    with patch.object(_get_ib(), "_triggered_once", _FakeLock(False)):
        with patch("app.services.immediate_backup.threading.Thread") as mk:
            ok = trigger_immediate_backup("忙", wait=True, wait_timeout=1.0)
    assert ok is False
    mk.assert_not_called()


def test_positive_delay_sleeps_before_backup():
    """delay>0 时线程体先 sleep(delay) 再执行备份（覆盖 time.sleep 分支）。"""
    from app.services.immediate_backup import trigger_immediate_backup

    p_ctx, p_svc, p_cfg, svc = _backup_ctx_ok()
    with patch.object(_get_ib(), "_triggered_once", _FakeLock(True)):
        with patch("app.services.immediate_backup.threading.Thread", _fake_thread_cls()):
            with patch("time.sleep") as mk_sleep, p_ctx, p_svc, p_cfg:
                ok = trigger_immediate_backup("延迟备份", delay=1.5, wait=True, wait_timeout=1.0)
    assert ok is True
    mk_sleep.assert_called_once_with(1.5)
    svc.create_backup.assert_called_once()
