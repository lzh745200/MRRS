"""API-02（2026-11-01 审计）：数据包确认导入的异步边界。

原实现是 ``async def confirm_import``，但函数体全部同步 —— zip 解析、逐行 upsert
以及 ``db_coordinator.exclusive_write(timeout=120)`` 都在事件循环线程里执行，
一次大包导入可让整个进程（含 /health 与所有用户请求）最长冻结 120 秒。

修法：async 门面只做 ``await run_in_thread(self._confirm_import_sync, ...)``。
本文件只验证「同步主体确实跑在 worker 线程」，不重复导入业务用例。
"""

import asyncio
import threading

from app.services.data_package_service import DataPackageService


def _service_with_stub(name: str, result):
    """构造只带桩方法的服务实例：本用例只验证线程边界。"""
    service = DataPackageService.__new__(DataPackageService)
    seen = {}

    def stub(*args, **kwargs):
        seen["ident"] = threading.get_ident()
        seen["args"] = args
        seen["kwargs"] = kwargs
        return result

    setattr(service, name, stub)
    return service, seen


def test_confirm_import_runs_in_worker_thread():
    service, seen = _service_with_stub("_confirm_import_sync", "result")
    main_thread = threading.get_ident()

    result = asyncio.run(service.confirm_import(7, 42, overwrite_existing=True))

    assert result == "result"
    assert seen["ident"] != main_thread, "confirm_import 的同步主体仍在事件循环线程执行"
    assert seen["args"] == (7, 42, True, None, False)


def test_confirm_import_with_conflict_resolution_runs_in_worker_thread():
    service, seen = _service_with_stub(
        "_confirm_import_with_conflict_resolution_sync", {"success": True}
    )
    main_thread = threading.get_ident()

    result = asyncio.run(
        service.confirm_import_with_conflict_resolution(3, "OVERWRITE", "pwd")
    )

    assert result == {"success": True}
    assert seen["ident"] != main_thread
    assert seen["args"] == (3, "OVERWRITE", "pwd")
