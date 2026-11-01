"""长期项 4（2026-11-01）：``exclusive_write`` 的并发互斥与超时语义。

`SQLiteWriteCoordinator.exclusive_write` 是「数据包 confirm 期间独占写锁」的
唯一实现，此前没有任何并发用例覆盖它。这里锁死两条契约：

1. **互斥**：A 线程持有写锁期间，B 线程只能在 A 释放后进入临界区（不得交叉）；
2. **超时**：锁被占用超过 ``timeout`` 时抛 ``TimeoutError``，由调用方转 409/400，
   绝不允许静默降级成「没拿到锁也继续写」。

非 SQLite 构建（PG/MySQL）本就 ``yield`` 放行，不在本文件范围内。
"""

import threading
import time

import pytest

from app.core import database as db_module


def test_non_sqlite_build_passes_through(monkeypatch):
    monkeypatch.setattr(db_module, "IS_SQLITE", False)
    coordinator = db_module.SQLiteWriteCoordinator()

    entered = False
    with coordinator.exclusive_write(timeout=0.01):
        entered = True
    assert entered is True
    # 放行分支不持有锁：可以立即再次进入
    with coordinator.exclusive_write(timeout=0.01):
        pass


def test_write_lock_is_mutually_exclusive(monkeypatch):
    monkeypatch.setattr(db_module, "IS_SQLITE", True)
    coordinator = db_module.SQLiteWriteCoordinator()

    order: list[str] = []
    first_inside = threading.Event()
    release_first = threading.Event()

    def first() -> None:
        with coordinator.exclusive_write(timeout=2.0):
            order.append("a-enter")
            first_inside.set()
            assert release_first.wait(2.0)
            order.append("a-exit")

    def second() -> None:
        assert first_inside.wait(2.0)
        with coordinator.exclusive_write(timeout=2.0):
            order.append("b-enter")

    t1 = threading.Thread(target=first)
    t2 = threading.Thread(target=second)
    t1.start()
    t2.start()
    assert first_inside.wait(2.0)
    # B 已经尝试进入，但 A 未释放 → 不得出现 b-enter
    time.sleep(0.1)
    assert "b-enter" not in order
    release_first.set()
    t1.join(3.0)
    t2.join(3.0)

    assert order == ["a-enter", "a-exit", "b-enter"]


def test_timeout_raises_instead_of_silently_proceeding(monkeypatch):
    monkeypatch.setattr(db_module, "IS_SQLITE", True)
    coordinator = db_module.SQLiteWriteCoordinator()

    with coordinator.exclusive_write(timeout=1.0):
        # 同一线程重入：threading.Lock 非可重入 → 必须超时，而不是嵌套放行
        with pytest.raises(TimeoutError):
            with coordinator.exclusive_write(timeout=0.05):
                pytest.fail("锁被占用时不得进入临界区")
