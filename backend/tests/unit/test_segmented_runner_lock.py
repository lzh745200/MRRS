# -*- coding: utf-8 -*-
"""分段执行器「单实例锁」回归用例。

背景（2026-10-28 实测两次）：两个会话同时跑 12 段时，后启动的一方在清理阶段重置
`.coverage`，先启动那次覆盖率判定就从 100% 掉成 28%/53% —— 现象是「12 段全 PASS
但覆盖率门禁红」，排查成本极高。`acquire_run_lock` 用 O_CREAT|O_EXCL + pid 存活探测
保证同一时刻只有一个分段全量在跑，并自动接管崩溃遗留的陈旧锁。
"""

import importlib.util
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "run_backend_tests_segmented.py"


def _load_runner():
    spec = importlib.util.spec_from_file_location("run_backend_tests_segmented", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _dead_pid() -> int:
    """取一个确定已退出的进程 pid（用于伪造陈旧锁）。"""
    proc = subprocess.Popen([sys.executable, "-c", "pass"])
    proc.wait(timeout=30)
    return proc.pid


def test_acquire_writes_pid_and_release_removes_lock(tmp_path):
    runner = _load_runner()
    lock = tmp_path / "run.lock"

    assert runner.acquire_run_lock(lock) is True
    assert lock.read_text(encoding="ascii").strip() == str(__import__("os").getpid())

    runner.release_run_lock(lock)
    assert not lock.exists()


def test_second_acquire_is_rejected_while_first_is_alive(tmp_path):
    runner = _load_runner()
    lock = tmp_path / "run.lock"

    assert runner.acquire_run_lock(lock) is True
    try:
        assert runner.acquire_run_lock(lock) is False, "同一时刻必须只允许一个分段全量"
    finally:
        runner.release_run_lock(lock)


def test_stale_lock_from_dead_process_is_taken_over(tmp_path):
    runner = _load_runner()
    lock = tmp_path / "run.lock"
    lock.write_text(str(_dead_pid()), encoding="ascii")

    assert runner.acquire_run_lock(lock) is True, "进程已退出的陈旧锁必须自动接管"
    runner.release_run_lock(lock)


def test_wait_lock_times_out_and_returns_false(tmp_path):
    runner = _load_runner()
    lock = tmp_path / "run.lock"

    assert runner.acquire_run_lock(lock) is True
    try:
        assert runner.acquire_run_lock(lock, wait_seconds=1) is False
    finally:
        runner.release_run_lock(lock)


def test_release_is_idempotent_when_lock_missing(tmp_path):
    runner = _load_runner()
    missing = tmp_path / "never-existed.lock"

    runner.release_run_lock(missing)  # 不得抛错
    assert not missing.exists()
