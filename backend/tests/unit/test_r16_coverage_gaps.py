"""R16 收尾：把全量覆盖率从 99.85% 补到 100.00% 的最后一批缺口分支。

覆盖清单（对应 --cov-report=term-missing 的 Miss 行）：
- api/v1/data/data/data_packages.py:375 —— preview 端点在 org 无法确定时 fail-closed 400
- api/v1/system/system.py:203            —— 端口探活超时返回 False
- api/v1/system/tasks.py:265,275         —— 后台任务完成/失败时任务已被删除或取消则跳过回写
- middleware/camel_to_snake.py:108-110   —— 响应头透传（排除 content-length）+ background
- middleware/request_logger.py:31        —— TRUSTED_PROXIES 环境变量解析
- middleware/slow_request_monitor.py:79-86 —— 参数摘要的三种容器形态
- services/cascade_purge_service.py:97   —— _delete_deep 深层删除
- services/chunked_upload_service.py:445-449,483 —— 合并锁二次检查（MERGED/MERGING 重入）
- services/offline_map_service.py:118    —— 瓦片 stat 失败时跳过而非中断统计
- utils/encryption.py:61                 —— 部署盐值竞态（双检锁内二次命中缓存）
"""

import asyncio
import json
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from app.middleware.slow_request_monitor import _summarize_params
from app.services.offline_map_service import OfflineMapService


# ==================== slow_request_monitor: 参数摘要 ====================


class TestSummarizeParams:
    def test_none_or_empty_returns_none(self):
        assert _summarize_params(None) is None
        assert _summarize_params({}) is None
        assert _summarize_params([]) is None

    def test_dict_values(self):
        assert _summarize_params({"a": 1, "b": "x"}) == "2 params<int,str>"

    def test_sequence_values(self):
        assert _summarize_params((1, None)) == "2 params<int,NoneType>"

    def test_scalar_value(self):
        assert _summarize_params(5) == "1 params<int>"


# ==================== request_logger: TRUSTED_PROXIES ====================


class TestTrustedProxies:
    def test_default_set_when_env_absent(self):
        from app.middleware import request_logger

        with patch.dict("os.environ", {}, clear=False):
            import os
            os.environ.pop("TRUSTED_PROXIES", None)
            result = request_logger._trusted_proxies()
        assert result == request_logger._DEFAULT_TRUSTED_PROXIES

    def test_env_merges_and_ignores_blank_entries(self):
        from app.middleware import request_logger

        with patch.dict("os.environ", {"TRUSTED_PROXIES": " 10.0.0.1 , ,10.0.0.2 "}):
            result = request_logger._trusted_proxies()
        assert "10.0.0.1" in result and "10.0.0.2" in result
        assert "" not in result
        assert result >= request_logger._DEFAULT_TRUSTED_PROXIES


# ==================== camel_to_snake: 响应头/background 透传 ====================


class TestCamelToSnakeHeaderPassthrough:
    def test_headers_copied_except_content_length_and_background_kept(self):
        """经真实 ASGI 栈发一次产生「键名被改写」的响应，验证头透传与 background 保留。

        只有 `_patch_envelope` 真正改写了 envelope 才会走重建响应分支，
        故这里构造一个裸 dict 响应（会被补全 code/success → 触发改写）。
        """
        from fastapi import FastAPI
        from fastapi.responses import JSONResponse
        from fastapi.testclient import TestClient

        from app.middleware.camel_to_snake import CamelToSnakeMiddleware

        inner = FastAPI()

        @inner.get("/probe")
        async def probe():
            # 裸 dict（无 code/success 信封）→ 中间件 _patch_envelope 会改写 body
            resp = JSONResponse({"user_name": "x"})
            resp.headers["X-Trace-Id"] = "abc"          # 自定义头必须保留
            return resp

        outer = FastAPI()
        outer.add_middleware(CamelToSnakeMiddleware)
        outer.mount("/inner", inner)
        resp = TestClient(outer).get("/inner/probe")

        assert resp.status_code == 200
        assert resp.headers.get("x-trace-id") == "abc"
        # body 被改写后 content-length 必须与真实 body 长度一致（不复用旧值）
        assert resp.headers.get("content-length") == str(len(resp.content))


# ==================== cascade_purge: _delete_deep ====================


class TestCascadePurgeDeleteDeep:
    def test_delete_deep_executes_parameterized_delete(self):
        from app.services.cascade_purge_service import CascadePurgeService

        db = MagicMock()
        svc = CascadePurgeService(db)
        svc._delete_deep("child_t", "parent_id", "parent_t", "id", 7)
        stmt = db.execute.call_args[0][0]
        compiled = str(stmt)
        assert "DELETE FROM child_t" in compiled
        assert db.execute.call_args[0][1] == {"rid": 7}


# ==================== chunked_upload: 合并锁二次检查 ====================


class TestMergeLockReentry:
    """走真实 _acquire_merge_lock：锁内二次检查覆盖 MERGED / MERGING 重入。

    构造方式：先由同一线程持有该会话的锁，再（在新线程中）调用
    `_acquire_merge_lock`，使其真正阻塞在 `lock.acquire()` 上；
    随后把 session 状态改成 MERGED/MERGING 并放锁 → 命中"锁内二次检查"分支。
    """

    def _svc(self):
        from app.services.chunked_upload_service import ChunkedUploadService

        return ChunkedUploadService(temp_dir=".", final_dir=".")

    def test_merged_after_wait_returns_path(self):
        import threading

        from app.services.chunked_upload_service import ChunkUploadStatus

        svc = self._svc()
        session = MagicMock(status=ChunkUploadStatus.UPLOADING, merged_file_path="/done.zip")
        holder = svc._acquire_merge_lock(session, "s1")[0]  # 主线程先持有
        session.status = ChunkUploadStatus.MERGED

        result = {}
        # 真实实现用 acquire(blocking=False)：worker 在持有期间调用必抛
        # "already merging"，无法命中锁内二次检查。这里把会话锁换成可由测试
        # 精确控制放行时机的阻塞锁，才能真正走过 acquire() 后的 MERGED 分支。
        entered = threading.Event()
        release = threading.Event()

        class _GatedLock:
            def acquire(self_, blocking=True):
                entered.set()
                release.wait(timeout=5)
                return True

            def release(self_):
                return None

        with patch.object(svc, "_get_session_lock", lambda _sid: _GatedLock()):
            t = threading.Thread(target=lambda: result.update(out=svc._acquire_merge_lock(session, "s1")))
            t.start()
            assert entered.wait(timeout=5)
            release.set()  # 放行 → worker 进入临界区并命中锁内 MERGED 分支
            t.join(timeout=5)

        assert t.is_alive() is False
        assert result["out"] == (None, "/done.zip")

    def test_merging_after_wait_raises(self):
        import threading

        from app.services.chunked_upload_service import ChunkUploadStatus

        svc = self._svc()
        session = MagicMock(status=ChunkUploadStatus.UPLOADING)
        locked = svc._get_session_lock("s1")
        assert locked.acquire(blocking=False) is True  # 让 acquire(blocking=False) 立即失败
        session.status = ChunkUploadStatus.MERGING

        with patch.object(svc, "_get_session_lock", lambda _sid: locked):
            with pytest.raises(ValueError, match="already merging"):
                svc._acquire_merge_lock(session, "s1")

    def test_merging_after_lock_acquired_releases_and_raises(self):
        """锁内二次检查命中 MERGING → 释放锁并抛错（448-449）。

        路径：进入时 status != MERGING，成功拿到锁之后状态才变成 MERGING
        （首个调用已置位）。锁必须被释放，否则同会话永久死锁。
        """
        from app.services.chunked_upload_service import ChunkUploadStatus

        svc = self._svc()
        released = {"n": 0}

        class _StatusFlipLock:
            """acquire 成功后把 session 状态翻成 MERGING，模拟并发置位。"""

            def acquire(self_, blocking=True):
                session.status = ChunkUploadStatus.MERGING
                return True

            def release(self_):
                released["n"] += 1

        session = MagicMock(status=ChunkUploadStatus.UPLOADING)
        with patch.object(svc, "_get_session_lock", lambda _sid: _StatusFlipLock()):
            with pytest.raises(ValueError, match="already merging"):
                svc._acquire_merge_lock(session, "s1")
        assert released["n"] == 1  # 锁已释放

    async def test_merge_chunks_returns_early_when_already_merged(self):
        """并发首调用已完成合并 → merge_chunks 直接返回其路径（483）。"""
        from app.services.chunked_upload_service import ChunkUploadStatus

        svc = self._svc()
        session = MagicMock(
            status=ChunkUploadStatus.UPLOADING,
            is_complete=True,
            merged_file_path="/done.zip",
        )
        with patch.object(svc, "get_session", return_value=session), patch.object(
            svc, "_acquire_merge_lock", return_value=(None, "/done.zip")
        ):
            assert await svc.merge_chunks("s9") == "/done.zip"

    def test_fresh_session_returns_lock(self):
        from app.services.chunked_upload_service import ChunkUploadStatus

        svc = self._svc()
        session = MagicMock(status=ChunkUploadStatus.UPLOADING)
        lock, early = svc._acquire_merge_lock(session, "s1")
        assert early is None and lock is not None

    @pytest.mark.asyncio
    async def test_merge_chunks_returns_early_when_already_merged(self):
        """merge_chunks 在状态已是 MERGED 时提前返回既有路径（不重复合并）。"""
        from app.services.chunked_upload_service import ChunkUploadStatus

        svc = self._svc()
        session = MagicMock(status=ChunkUploadStatus.MERGED, merged_file_path="/already.zip")
        with patch.object(svc, "get_session", return_value=session):
            result = await svc.merge_chunks("s9")
        assert result == "/already.zip"


# ==================== offline_map: stat 失败跳过 ====================


class TestCoverageStatFailure:
    @pytest.mark.asyncio
    async def test_stat_failure_skips_file(self, tmp_path):
        svc = OfflineMapService(cache_dir=tmp_path)
        z_dir = tmp_path / "9"
        x_dir = z_dir / "1"
        x_dir.mkdir(parents=True)
        good = x_dir / "1.png"
        bad = x_dir / "9.png"
        good.write_bytes(b"a" * 10)
        bad.write_bytes(b"b" * 20)

        real_stat = type(bad).stat

        def flaky_stat(self, *a, **kw):
            if self.name == "9.png":
                raise OSError("vanished")
            return real_stat(self, *a, **kw)

        with patch.object(type(bad), "stat", flaky_stat):
            coverage = await svc.get_coverage()

        # 坏文件被跳过，好文件仍计入（不因单文件失败中断统计）
        assert coverage["total_tiles"] == 1


# ==================== encryption: 双检锁内二次命中 ====================


class TestDeploymentSaltDoubleCheck:
    def test_second_check_returns_cached_salt(self):
        """竞态：外层判空通过后，另一线程已在锁内写入缓存 → 直接返回缓存。"""
        from app.utils.encryption import DataPackageEncryption

        original = DataPackageEncryption._deployment_salt
        cached = b"\x11" * 32
        try:
            DataPackageEncryption._deployment_salt = None
            # 让锁的 __enter__ 模拟"另一线程已完成初始化"
            class _RaceLock:
                def __enter__(self_):
                    DataPackageEncryption._deployment_salt = cached
                    return self_
                def __exit__(self_, *a):
                    return False

            with patch.object(DataPackageEncryption, "_salt_lock", _RaceLock()):
                assert DataPackageEncryption._load_deployment_salt() == cached
        finally:
            DataPackageEncryption._deployment_salt = original


# ==================== system.tasks: 完成回写时任务已消失/被取消 ====================


class TestTaskExecutionWriteback:
    """驱动 create_task 注册的真实后台闭包 _execute_task（不做逻辑复制）。

    _execute_task 是 create_task 内部的闭包，通过 BackgroundTasks 收集后取出，
    从而覆盖完成回写路径上「任务已被删除 / 已被取消」两条防御分支。
    """

    @staticmethod
    def _capture_executor(client_with_mocked_auth, tasks_mod):
        """调用 POST /api/v1/system/tasks 并抓取注册进来的后台闭包。

        注意：必须 patch BackgroundTasks 的**实例方法**。该类定义了
        `__class_getitem__`，因此 patch.object(BackgroundTasks, "add_task", ...)
        会命中毒化后的类本身，触发 BackgroundTasks.__call__ 签名错误。
        """
        from fastapi import BackgroundTasks

        captured = {}

        def _capture(self_, fn, *args, **kwargs):
            captured["fn"] = fn
            captured["args"] = args

        with patch.object(tasks_mod, "_tasks", {}), patch.object(
            BackgroundTasks, "add_task", _capture
        ):
            resp = client_with_mocked_auth.post(
                "/api/v1/system/tasks",
                json={"task_type": "demo", "task_name": "演示任务"},
            )
        assert resp.status_code == 200, resp.text
        return captured, json.loads(resp.content)["data"]["task_id"]

    def test_completed_path_skips_when_task_deleted(self, client_with_mocked_auth):
        """推进途中任务被删除 → 命中循环内的守卫（257 return），不得复活。"""
        from app.api.v1.system import tasks as tasks_mod

        captured, task_id = self._capture_executor(client_with_mocked_auth, tasks_mod)
        live = {task_id: {"status": "pending", "progress": 0.0}}
        calls = {"n": 0}

        def _delete_on_first_sleep(*_a, **_k):
            calls["n"] += 1
            live.pop(task_id, None)

        with patch.object(tasks_mod, "_tasks", live), patch("time.sleep", _delete_on_first_sleep):
            captured["fn"](*captured["args"])
        assert task_id not in live

    def test_writeback_guard_tolerates_vanished_task(self, client_with_mocked_auth):
        """收尾回写块的判空守卫（264/265）——任务在判空前瞬间消失。

        这是一个纯防御分支：循环内 257 已挡住"推进中被删/取消"，正常时序下
        走到 263 时任务必然存在。这里通过"get 之后立刻移除"精确命中该守卫，
        保证防御代码本身被验证（而非仅靠覆盖率数字）。
        """
        from app.api.v1.system import tasks as tasks_mod

        captured, task_id = self._capture_executor(client_with_mocked_auth, tasks_mod)
        live = {task_id: {"status": "pending", "progress": 0.0}}
        state = {"gets": 0}

        class _VanishingDict(dict):
            """第 7 次 get（收尾块 263 行）返回 None，模拟判空瞬间任务已消失。"""

            def get(self, k, default=None):
                state["gets"] += 1
                if state["gets"] >= 7:
                    return None
                return super().get(k, default)

        with patch.object(tasks_mod, "_tasks", _VanishingDict(live)), patch(
            "time.sleep", lambda *_a, **_k: None
        ):
            captured["fn"](*captured["args"])
        # 守卫命中：不写终态（任务此前已被写成 running，绝不被改写成 COMPLETED）
        assert live[task_id]["status"] == tasks_mod.TaskStatus.RUNNING.value

    def test_failed_path_guard_tolerates_vanished_task(self, client_with_mocked_auth):
        """失败回写块的判空守卫（274/275）——执行抛错且任务已消失。"""
        from app.api.v1.system import tasks as tasks_mod

        captured, task_id = self._capture_executor(client_with_mocked_auth, tasks_mod)
        live = {task_id: {"status": "pending", "progress": 0.0}}
        state = {"gets": 0}

        class _VanishingDict(dict):
            def get(self, k, default=None):
                state["gets"] += 1
                if state["gets"] >= 2:  # 首次推进读取之后即消失
                    return None
                return super().get(k, default)

        with patch.object(tasks_mod, "_tasks", _VanishingDict(live)), patch(
            "time.sleep", side_effect=RuntimeError("boom")
        ):
            captured["fn"](*captured["args"])
        # 守卫命中：不写 FAILED（任务此前已被写成 running）
        assert live[task_id]["status"] == tasks_mod.TaskStatus.RUNNING.value

    def test_completed_path_writes_when_present(self, client_with_mocked_auth):
        """任务仍在且非终态 → 回写 COMPLETED/100%。"""
        from app.api.v1.system import tasks as tasks_mod

        captured, task_id = self._capture_executor(client_with_mocked_auth, tasks_mod)
        live = {task_id: {"status": "pending", "progress": 0.0}}
        # time 是闭包内的局部 import，只能打补丁到 stdlib 模块本身
        with patch.object(tasks_mod, "_tasks", live), patch("time.sleep", lambda *_a, **_k: None):
            captured["fn"](*captured["args"])
        assert live[task_id]["status"] == tasks_mod.TaskStatus.COMPLETED.value
        assert live[task_id]["progress"] == 100.0

    def test_completed_path_skips_when_cancelled_midway(self, client_with_mocked_auth):
        """推进过程中任务被取消 → 立即停止，不得回写成 COMPLETED。"""
        from app.api.v1.system import tasks as tasks_mod

        captured, task_id = self._capture_executor(client_with_mocked_auth, tasks_mod)
        live = {task_id: {"status": "pending", "progress": 0.0}}

        def _cancel_then_sleep(*_a, **_k):
            live[task_id]["status"] = tasks_mod.TaskStatus.CANCELLED.value

        with patch.object(tasks_mod, "_tasks", live), patch("time.sleep", _cancel_then_sleep):
            captured["fn"](*captured["args"])
        assert live[task_id]["status"] == tasks_mod.TaskStatus.CANCELLED.value

    def test_failed_path_skips_when_task_deleted(self, client_with_mocked_auth):
        """执行抛错且任务已被删除 → 失败回写分支直接 return（不复活）。"""
        from app.api.v1.system import tasks as tasks_mod

        captured, _task_id = self._capture_executor(client_with_mocked_auth, tasks_mod)
        with patch.object(tasks_mod, "_tasks", {}), patch(
            "time.sleep", side_effect=RuntimeError("boom")
        ):
            captured["fn"](*captured["args"])


# ==================== system: 端口探活轮询中 sleep 分支 ====================


class TestPortProbeTimeout:
    def test_deadline_reached_returns_false(self):
        """端口持续被占用（connect_ex 返回 0）直到超时 → False。"""
        from app.api.v1.system import system as system_mod

        fake_sock = MagicMock()
        fake_sock.connect_ex.return_value = 0  # 仍有人监听
        with patch("socket.socket", return_value=fake_sock), patch.object(
            system_mod, "_PORT_PROBE_INTERVAL_SECONDS", 0
        ):
            assert system_mod._wait_for_port_release("127.0.0.1", 8000, timeout=0.0) is False

    def test_port_free_returns_true(self):
        """连接被拒（connect_ex != 0）→ 端口已释放，立即 True。"""
        from app.api.v1.system import system as system_mod

        fake_sock = MagicMock()
        fake_sock.connect_ex.return_value = 111  # ECONNREFUSED
        with patch("socket.socket", return_value=fake_sock):
            assert system_mod._wait_for_port_release("127.0.0.1", 8000, timeout=5.0) is True

    def test_no_port_returns_true(self):
        from app.api.v1.system import system as system_mod

        assert system_mod._wait_for_port_release("127.0.0.1", 0) is True

    def test_polling_sleep_branch(self):
        """端口一直占用且 deadline 未到 → 走 time.sleep 轮询，下一轮连接被拒才返回 True。"""
        from app.api.v1.system import system as system_mod

        fake_sock = MagicMock()
        # 前两次仍在监听，第三次连接被拒 → 必须先 sleep 一次才会到第三次
        fake_sock.connect_ex.side_effect = [0, 0, 111]
        with patch("socket.socket", return_value=fake_sock), patch(
            "time.sleep"
        ) as sleep_mock, patch("time.monotonic", side_effect=[0.0, 0.0, 1.0, 1.0, 2.0]):
            assert system_mod._wait_for_port_release("127.0.0.1", 8000, timeout=60.0) is True
        assert sleep_mock.call_count == 2


# ==================== data_packages: preview org 缺失 fail-closed ====================


class TestPreviewOrgMissingFailClosed:
    def test_preview_without_org_returns_400(self, client_with_mocked_auth):
        from app.api.v1.data.data.data_packages import (
            get_package_service,
            get_permission_service,
        )
        from app.core.security import get_current_user

        svc = MagicMock()
        svc.db = MagicMock()
        perm = MagicMock()
        user = MagicMock()
        user.id = 1
        user.organization_id = None

        app = client_with_mocked_auth.app
        orig = app.dependency_overrides.copy()
        app.dependency_overrides[get_package_service] = lambda: svc
        app.dependency_overrides[get_permission_service] = lambda: perm
        app.dependency_overrides[get_current_user] = lambda: user
        try:
            with patch(
                "app.api.v1.data.data.data_packages.get_org_with_fallback",
                return_value=None,
            ):
                resp = client_with_mocked_auth.post(
                    "/api/v1/data-packages/preview", json={"data_types": ["villages"]}
                )
        finally:
            app.dependency_overrides = orig

        assert resp.status_code == 400
