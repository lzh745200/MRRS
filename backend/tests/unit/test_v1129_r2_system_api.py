"""第二轮深审修复回归测试 —— system 包与 monitoring 包。

覆盖条目：
- #90 system/tasks.py 无锁写任务状态 / 取消后被回写成 COMPLETED
- #80 system/cache.py 无锁读 _store
- #81 system/config_package.py str() 破坏 JSON 往返
- #84/#85 system/metrics.py 阈值倒置、历史指标升序+limit 丢最新
- #95 system_health.py 索引校验取错元组元素
- #78 system/__init__.py 子模块导入失败静默吞掉
- #79 system/audit.py actions 标量/字符串被逐字符展开
- #82/#83 system/init.py 初始化并发双跑、硬编码 org_id=1
- #86 system/system.py 重启端口竞态
- #93/#94 system/zero_trust.py 因子分不累加、安全事件无权限门禁
- #58/#59 monitoring/data_tier.py 入参无边界
- #61 monitoring/metrics.py /prometheus 无认证
- #63/#64/#65 monitoring_legacy.py async 内同步查询
"""

import inspect
import json
import sys
import threading
import time as time_mod
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import BackgroundTasks, HTTPException

import app.api.v1.monitoring.data_tier as data_tier_mod
import app.api.v1.monitoring.metrics as mon_metrics_mod
import app.api.v1.monitoring_legacy as mon_legacy_mod
import app.api.v1.system.cache as cache_mod
import app.api.v1.system.config_package as cfg_pkg_mod
import app.api.v1.system.init as init_mod
import app.api.v1.system.metrics as metrics_mod
import app.api.v1.system.system as system_mod
import app.api.v1.system.tasks as tasks_mod
import app.api.v1.system.zero_trust as zt_mod
from app.api.v1.system.audit import BatchDeleteRequest
from app.core.cache import CacheManager, SimpleCache

ADMIN = SimpleNamespace(id=1, username="admin", role="admin", is_superuser=True)
USER = SimpleNamespace(id=2, username="bob", role="user", is_superuser=False)


@pytest.fixture(autouse=True)
def _clean_tasks():
    tasks_mod._tasks.clear()
    yield
    tasks_mod._tasks.clear()


def _capture_add_task():
    captured = {}

    def _capture(self, func, *args, **kwargs):
        captured["func"] = func
        captured["args"] = args

    return captured, patch.object(BackgroundTasks, "add_task", _capture)


async def _create_task(background_tasks):
    return await tasks_mod.create_task(
        request=SimpleNamespace(task_type="backup", task_name="t", params=None),
        background_tasks=background_tasks,
        current_user=ADMIN,
    )


# ==================== #90 system/tasks.py ====================


class TestTaskExecutionLocking:
    async def test_terminal_task_never_rewritten_to_running(self):
        captured, p = _capture_add_task()
        with p:
            resp = await _create_task(BackgroundTasks())
        task_id = resp["data"]["task_id"]
        record = tasks_mod._tasks[task_id]
        record["status"] = tasks_mod.TaskStatus.CANCELLED.value
        record["completed_at"] = datetime.now(timezone.utc).isoformat()

        captured["func"](task_id)

        assert record["status"] == tasks_mod.TaskStatus.CANCELLED.value
        assert record["started_at"] is None
        assert record["result"] is None

    async def test_cancelled_mid_run_stops_progress_and_status(self):
        captured, p = _capture_add_task()
        with p:
            resp = await _create_task(BackgroundTasks())
        task_id = resp["data"]["task_id"]
        calls = {"n": 0}

        def _sleep(_seconds):
            calls["n"] += 1
            if calls["n"] == 2:
                tasks_mod._tasks[task_id]["status"] = tasks_mod.TaskStatus.CANCELLED.value

        with patch.object(time_mod, "sleep", _sleep):
            captured["func"](task_id)

        final = tasks_mod._tasks[task_id]
        assert final["status"] == tasks_mod.TaskStatus.CANCELLED.value
        assert final["progress"] == 20.0
        assert final["result"] is None

    async def test_task_deleted_mid_run_returns_quietly(self):
        captured, p = _capture_add_task()
        with p:
            resp = await _create_task(BackgroundTasks())
        task_id = resp["data"]["task_id"]
        calls = {"n": 0}

        def _sleep(_seconds):
            calls["n"] += 1
            if calls["n"] == 2:
                tasks_mod._tasks.pop(task_id, None)

        with patch.object(time_mod, "sleep", _sleep):
            captured["func"](task_id)

        assert task_id not in tasks_mod._tasks

    async def test_deleted_before_completion_writes_nothing(self):
        """终态写入前记录被删除 → 静默返回（覆盖完成分支的存在性守卫）。"""
        captured, p = _capture_add_task()
        with p:
            resp = await _create_task(BackgroundTasks())
        task_id = resp["data"]["task_id"]
        calls = {"n": 0}

        def _sleep(_seconds):
            calls["n"] += 1
            if calls["n"] == 5:
                tasks_mod._tasks.pop(task_id, None)

        with patch.object(time_mod, "sleep", _sleep):
            captured["func"](task_id)

        assert task_id not in tasks_mod._tasks

    async def test_failure_branch_after_cancel_keeps_cancelled(self):
        """异常分支同样不得把取消态改写成 failed。"""
        captured, p = _capture_add_task()
        with p:
            resp = await _create_task(BackgroundTasks())
        task_id = resp["data"]["task_id"]
        tasks_mod._tasks[task_id]["status"] = tasks_mod.TaskStatus.CANCELLED.value

        with patch.object(time_mod, "sleep", side_effect=RuntimeError("boom")):
            captured["func"](task_id)

        assert tasks_mod._tasks[task_id]["status"] == tasks_mod.TaskStatus.CANCELLED.value

    async def test_get_task_returns_snapshot_copy(self):
        captured, p = _capture_add_task()
        with p:
            resp = await _create_task(BackgroundTasks())
        task_id = resp["data"]["task_id"]
        result = await tasks_mod.get_task(task_id=task_id, current_user=ADMIN)
        assert result["data"]["task_id"] == task_id
        assert result["data"] is not tasks_mod._tasks[task_id]

    async def test_cancel_then_delete(self):
        captured, p = _capture_add_task()
        with p:
            resp = await _create_task(BackgroundTasks())
        task_id = resp["data"]["task_id"]
        await tasks_mod.cancel_task(task_id=task_id, current_user=ADMIN)
        assert tasks_mod._tasks[task_id]["status"] == tasks_mod.TaskStatus.CANCELLED.value
        await tasks_mod.delete_task(task_id=task_id, current_user=ADMIN)
        assert task_id not in tasks_mod._tasks


# ==================== #80 system/cache.py ====================


class TestCacheLockedSnapshot:
    async def test_snapshot_reads_consistent_tuple(self):
        backend = SimpleCache()
        backend.set("k", "v")
        backend._hits = 2
        backend._misses = 1
        snapshot, hits, misses = cache_mod._snapshot_cache(backend)
        assert list(snapshot) == ["k"]
        assert (hits, misses) == (2, 1)

    async def test_stats_uses_snapshot_under_lock(self):
        backend = SimpleCache()
        backend.set("a", 1)
        with patch.object(cache_mod, "default_cache", backend):
            result = await cache_mod.get_cache_stats(current_user=ADMIN)
        assert result["data"]["item_count"] == 1

    async def test_clear_snapshots_and_resets_under_lock(self):
        backend = SimpleCache()
        backend.set("a", 1)
        backend._hits = 5
        with patch.object(cache_mod, "default_cache", backend), \
                patch.object(cache_mod, "cache_manager", CacheManager(backend)):
            result = await cache_mod.clear_cache(db=MagicMock(), current_user=ADMIN)
        assert result["data"]["cleared_keys"] == 1
        assert (backend._hits, backend._misses) == (0, 0)


# ==================== #81 system/config_package.py ====================


class TestConfigPackageJsonRoundTrip:
    async def test_import_passes_structured_value_untouched(self):
        """#81：dict/list 必须原样交给 SystemConfigService.set（由其 json.dumps），
        外层 str() 会写成 Python repr，get_json 解析失败。"""
        svc = MagicMock()
        svc.get.return_value = None
        with patch.object(cfg_pkg_mod, "SystemConfigService", return_value=svc):
            body = cfg_pkg_mod.ConfigPackageImportRequest(
                data=json.dumps({"name": "pkg", "configs": {"nested": {"a": [1, 2]}}}),
                overwrite=True,
            )
            result = await cfg_pkg_mod.import_config_package(
                body=body, db=MagicMock(), current_user=ADMIN
            )
        assert result["data"]["imported_count"] == 1
        svc.set.assert_called_once_with("nested", {"a": [1, 2]})


# ==================== #84/#85 system/metrics.py ====================


def _fake_psutil(cpu, mem, disk):
    mod = SimpleNamespace()
    mod.cpu_percent = lambda interval=0.0: cpu
    mod.virtual_memory = lambda: SimpleNamespace(percent=mem)
    mod.disk_usage = lambda _path: SimpleNamespace(percent=disk)
    mod.cpu_count = lambda: 4
    mod.boot_time = lambda: 0.0
    return mod


class TestMetricsThresholdsAndHistory:
    @pytest.mark.parametrize(
        "cpu,mem,disk,expected",
        [
            (96.0, 96.0, 96.0, "critical"),
            (85.0, 86.0, 81.0, "warning"),
            (10.0, 10.0, 10.0, "normal"),
        ],
    )
    async def test_status_thresholds_are_not_inverted(self, cpu, mem, disk, expected):
        with patch.dict(sys.modules, {"psutil": _fake_psutil(cpu, mem, disk)}), \
                patch.object(metrics_mod.os.environ, "get", lambda *a, **k: None):
            result = await metrics_mod.get_performance_metrics(current_user=ADMIN)
        statuses = {i["key"]: i["status"] for i in result["data"]["indicators"]}
        assert statuses == {
            "cpu_usage": expected,
            "memory_usage": expected,
            "disk_usage": expected,
        }

    async def test_history_keeps_newest_and_returns_ascending(self):
        newer = MagicMock(created_at=datetime(2026, 1, 2, tzinfo=timezone.utc), host="h2",
                          cpu_usage=2.0, memory_usage=20.0, disk_usage=30.0)
        older = MagicMock(created_at=datetime(2026, 1, 1, tzinfo=timezone.utc), host="h1",
                          cpu_usage=1.0, memory_usage=10.0, disk_usage=20.0)

        captured = {}

        class _Query:
            def filter(self, *a, **k):
                return self

            def order_by(self, *a):
                captured["order_by"] = a
                return self

            def limit(self, n):
                captured["limit"] = n
                return self

            def all(self):
                return [newer, older]

        db = MagicMock()
        db.query.return_value = _Query()
        result = await metrics_mod.get_metrics_history(
            hours=24, metric_type="all", db=db, current_user=ADMIN
        )
        assert captured["limit"] == 500
        assert "DESC" in str(captured["order_by"][0]).upper()
        assert [h["host"] for h in result["data"]["history"]] == ["h1", "h2"]


# ==================== #95 system_health.py ====================


class _FakeResult:
    def __init__(self, rows):
        self._rows = rows

    def fetchall(self):
        return self._rows


class _FakeHealthDB:
    def __init__(self, index_names):
        self.index_names = index_names

    def execute(self, stmt, params=None):
        sql = str(stmt)
        if "integrity_check" in sql:
            return _FakeResult([("ok",)])
        if "sqlite_master" in sql:
            return _FakeResult([("users",)])
        if "index_list" in sql:
            return _FakeResult([(0, name, 0) for name in self.index_names])
        return _FakeResult([])


class TestIntegrityCheckIndexNames:
    async def test_no_false_missing_when_index_present(self):
        """#95：期望集合必须取元组第二个元素（索引名），否则恒报缺索引。"""
        import app.api.v1.system_health as sh

        with patch(
            "app.core.database_indexes.EXTRA_INDEXES",
            [("users", "ix_users_org", ["organization_id"])],
        ):
            result = await sh.run_integrity_check(
                current_user=ADMIN, db=_FakeHealthDB(["ix_users_org"])
            )
        assert result["data"]["warnings"] == []
        assert result["data"]["status"] == "ok"

    async def test_reports_truly_missing_index(self):
        import app.api.v1.system_health as sh

        with patch(
            "app.core.database_indexes.EXTRA_INDEXES",
            [("users", "ix_users_org", ["organization_id"])],
        ):
            result = await sh.run_integrity_check(
                current_user=ADMIN, db=_FakeHealthDB(["ix_other"])
            )
        assert any("ix_users_org" in w for w in result["data"]["warnings"])


# ==================== #79 system/audit.py ====================


class TestBatchDeleteRequestNormalization:
    def test_actions_string_is_single_entry(self):
        assert BatchDeleteRequest(actions="login").actions == ["login"]

    def test_actions_scalar_is_single_entry(self):
        assert BatchDeleteRequest(actions=5).actions == ["5"]

    def test_actions_list_stripped(self):
        assert BatchDeleteRequest(actions=[" login ", "logout"]).actions == ["login", "logout"]

    def test_actions_none_passthrough(self):
        assert BatchDeleteRequest(actions=None).actions is None

    def test_ids_string_coerced_whole(self):
        assert BatchDeleteRequest(ids="12").ids == [12]


# ==================== #82/#83 system/init.py ====================


def _init_request():
    return init_mod.InitRequest(
        organization_name="某单位",
        admin_username="admin",
        admin_password="Str0ng!Passw0rd#2026",
    )


class TestSystemInitialization:
    async def test_concurrent_initialization_rejected_409(self):
        acquired = init_mod._INIT_LOCK.acquire(blocking=False)
        assert acquired is True
        try:
            with pytest.raises(HTTPException) as ei:
                await init_mod.initialize_system(request=_init_request(), db=MagicMock())
            assert ei.value.status_code == 409
        finally:
            init_mod._INIT_LOCK.release()

    async def test_root_org_reused_and_real_id_saved(self):
        root = SimpleNamespace(id=7)
        db = MagicMock()
        db.query.return_value.filter.return_value.order_by.return_value.first.return_value = root
        svc = MagicMock()
        svc.is_initialized.return_value = False
        with patch.object(init_mod, "SystemConfigService", return_value=svc):
            result = await init_mod._run_initialization(request=_init_request(), db=db)
        svc.set_initialized.assert_called_once_with(org_id=7)
        steps = {s["step"]: s["status"] for s in result["data"]["steps"]}
        assert steps["organization"] == "skipped"

    async def test_root_org_created_when_absent(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.order_by.return_value.first.return_value = None
        svc = MagicMock()
        svc.is_initialized.return_value = False
        org_svc = MagicMock()
        org_svc.create_organization = AsyncMock(return_value=SimpleNamespace(id=3))
        with patch.object(init_mod, "SystemConfigService", return_value=svc), \
                patch("app.services.organization_service.OrganizationService", return_value=org_svc):
            result = await init_mod._run_initialization(request=_init_request(), db=db)
        svc.set_initialized.assert_called_once_with(org_id=3)
        steps = {s["step"]: s["status"] for s in result["data"]["steps"]}
        assert steps["organization"] == "success"
        org_svc.create_organization.assert_awaited_once()

    async def test_root_org_lookup_failure_aborts(self):
        """#83：根组织步骤的 DB 故障必须中止初始化（fail-loud），不得继续标记已初始化。"""
        db = MagicMock()
        db.query.side_effect = RuntimeError("db down")
        svc = MagicMock()
        svc.is_initialized.return_value = False
        with patch.object(init_mod, "SystemConfigService", return_value=svc):
            with pytest.raises(HTTPException) as ei:
                await init_mod._run_initialization(request=_init_request(), db=db)
        assert ei.value.status_code == 500
        assert "根组织单位创建失败" in ei.value.detail
        db.rollback.assert_called_once()
        svc.set_initialized.assert_not_called()


# ==================== #93/#94 system/zero_trust.py ====================


def _request(scheme="https"):
    return SimpleNamespace(
        client=SimpleNamespace(host="127.0.0.1"),
        url=SimpleNamespace(scheme=scheme),
    )


class TestTrustAssessmentScoring:
    async def test_authenticated_https_is_full_trust(self):
        result = await zt_mod.get_trust_assessment(_request("https"), current_user=ADMIN)
        assert result["data"]["score"] == 100.0
        assert result["data"]["level"] == "trusted"

    async def test_authenticated_http_score_reflects_factor_weights(self):
        """#93：HTTP 缺失 transport 权重 → 100×(25+15+10-10+5)/65 = 69.2 → low_risk
        （原实现把正因子分丢弃，硬编码 100-10=90 → trusted）。"""
        result = await zt_mod.get_trust_assessment(_request("http"), current_user=ADMIN)
        assert result["data"]["score"] == 69.2
        assert result["data"]["level"] == "low_risk"
        assert result["data"]["recommendations"] == ["建议启用HTTPS确保传输层安全"]

    async def test_unauthenticated_is_untrusted(self):
        result = await zt_mod.get_trust_assessment(_request("https"), current_user=None)
        assert result["data"]["score"] == 0.0
        assert result["data"]["level"] == "untrusted"


class TestSecurityEventsAdminOnly:
    async def test_non_admin_forbidden_list(self):
        with pytest.raises(HTTPException) as ei:
            await zt_mod.get_security_events(
                severity=None, event_type=None, page=1, page_size=20,
                current_user=USER, db=MagicMock(),
            )
        assert ei.value.status_code == 403

    async def test_non_admin_forbidden_stats(self):
        with pytest.raises(HTTPException) as ei:
            await zt_mod.get_security_event_stats(current_user=USER, db=MagicMock())
        assert ei.value.status_code == 403

    async def test_admin_can_list(self):
        db = MagicMock()
        db.query.return_value.count.return_value = 0
        db.query.return_value.order_by.return_value.offset.return_value.limit.return_value.all.return_value = []
        result = await zt_mod.get_security_events(
            severity=None, event_type=None, page=1, page_size=20,
            current_user=ADMIN, db=db,
        )
        assert result["data"]["total"] == 0


# ==================== #86 system/system.py ====================


class TestRestartPortRace:
    async def test_wait_for_port_release_true_on_query_only_helper(self):
        assert system_mod._wait_for_port_release("127.0.0.1", 0) is True

    async def test_wait_for_port_release_true_when_unbound(self):
        import socket

        sock = socket.socket()
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
        sock.close()
        assert system_mod._wait_for_port_release("127.0.0.1", port, timeout=1.0) is True

    async def test_probe_host_maps_wildcard(self):
        assert system_mod._probe_host("0.0.0.0") == "127.0.0.1"
        assert system_mod._probe_host("") == "127.0.0.1"
        assert system_mod._probe_host("::") == "127.0.0.1"
        assert system_mod._probe_host("10.0.0.5") == "10.0.0.5"

    async def test_wait_for_port_release_timeout_returns_false(self):
        class _BusySocket:
            def settimeout(self, _t):
                return None

            def connect_ex(self, _target):
                return 0

            def close(self):
                return None

        with patch("socket.socket", return_value=_BusySocket()):
            assert system_mod._wait_for_port_release("127.0.0.1", 8000, timeout=0.0) is False

    async def test_wait_for_port_release_oserror_treated_as_released(self):
        class _ErrSocket:
            def settimeout(self, _t):
                return None

            def connect_ex(self, _target):
                raise OSError("probe failed")

            def close(self):
                return None

        with patch("socket.socket", return_value=_ErrSocket()):
            assert system_mod._wait_for_port_release("127.0.0.1", 8000, timeout=0.0) is True

    async def _capture_restart(self):
        captured = {}

        def _capture(self, func, *args, **kwargs):
            captured["func"] = func

        with patch.object(BackgroundTasks, "add_task", _capture):
            await system_mod.restart_system(
                background_tasks=BackgroundTasks(), delay_seconds=1, current_user=ADMIN
            )
        return captured["func"]

    async def test_graceful_shutdown_precedes_new_process(self):
        order = []
        func = await self._capture_restart()
        with patch.object(system_mod.time, "sleep", lambda _s: None), \
                patch.object(system_mod, "_graceful_shutdown", lambda: order.append("shutdown")), \
                patch.object(system_mod, "_wait_for_port_release", lambda *a, **k: order.append("wait") or True), \
                patch.object(system_mod.sys, "platform", "win32"), \
                patch("subprocess.Popen", lambda *a, **k: order.append("spawn")), \
                patch("app.core.cache.cache_manager.close", lambda: None):
            func()
        assert order == ["shutdown", "wait", "spawn"]

    async def test_timeout_still_spawns(self):
        spawned = []
        func = await self._capture_restart()
        with patch.object(system_mod.time, "sleep", lambda _s: None), \
                patch.object(system_mod, "_graceful_shutdown", lambda: None), \
                patch.object(system_mod, "_wait_for_port_release", lambda *a, **k: False), \
                patch.object(system_mod.sys, "platform", "win32"), \
                patch("subprocess.Popen", lambda *a, **k: spawned.append(1)), \
                patch("app.core.cache.cache_manager.close", lambda: None):
            func()
        assert spawned == [1]

    async def test_posix_path_execs_in_place(self):
        """POSIX 走 execv 原地替换：execv 成功后不再执行优雅关闭/拉起子进程。"""
        order = []
        func = await self._capture_restart()
        with patch.object(system_mod.time, "sleep", lambda _s: None), \
                patch.object(system_mod.sys, "platform", "linux"), \
                patch("os.execv", lambda *a: order.append("execv")), \
                patch.object(system_mod, "_graceful_shutdown", lambda: order.append("shutdown")), \
                patch("app.core.cache.cache_manager.close", lambda: None):
            func()
        assert order == ["execv"]


# ==================== #61 monitoring/metrics.py ====================


class TestPrometheusEndpointAuth:
    async def test_non_admin_forbidden(self):
        with pytest.raises(HTTPException) as ei:
            await mon_metrics_mod.get_prometheus_metrics(current_user=USER)
        assert ei.value.status_code == 403

    async def test_admin_gets_plaintext(self):
        with patch.object(
            mon_metrics_mod.business_metrics_service, "to_prometheus_format", lambda: "ok 1"
        ):
            resp = await mon_metrics_mod.get_prometheus_metrics(current_user=ADMIN)
        assert resp.body == b"ok 1"


# ==================== #58/#59 monitoring/data_tier.py ====================


class TestDataTierParameterBounds:
    """#58/#59：负值参数必须在进入服务层之前被 422 拦下（fail-closed）。"""

    def test_archive_params_bounded(self, client_with_mocked_auth):
        # 路由前缀来自监控子包自身（monitoring/data_tier.py prefix="/data-tier"）
        base = "/api/v1/data-tier"
        assert client_with_mocked_auth.post(
            f"{base}/archive/auditlog?before_days=-1"
        ).status_code == 422
        assert client_with_mocked_auth.post(
            f"{base}/archive/auditlog?batch_size=0"
        ).status_code == 422

    def test_cleanup_param_bounded(self, client_with_mocked_auth):
        resp = client_with_mocked_auth.request(
            "DELETE", "/api/v1/data-tier/cleanup?max_age_days=-1"
        )
        assert resp.status_code == 422


# ==================== #63/#64/#65 monitoring_legacy.py ====================


class TestMonitoringLegacyThreadpool:
    async def test_api_performance_offloaded(self):
        sentinel = {"calls": 1}
        with patch.object(
            mon_legacy_mod, "run_in_threadpool", AsyncMock(return_value=sentinel)
        ) as m_tp:
            result = await mon_legacy_mod.get_api_performance(
                hours=24, endpoint=None, current_user=ADMIN, db=MagicMock()
            )
        assert result["data"] == sentinel
        assert m_tp.await_args.args[0] is mon_legacy_mod.MonitoringService.get_api_performance_stats

    async def test_endpoint_stats_offloaded(self):
        with patch.object(
            mon_legacy_mod, "run_in_threadpool", AsyncMock(return_value=[])
        ) as m_tp:
            result = await mon_legacy_mod.get_endpoint_stats(
                hours=24, limit=5, current_user=ADMIN, db=MagicMock()
            )
        assert result["data"] == {"endpoints": []}
        assert m_tp.await_args.args[0] is mon_legacy_mod.MonitoringService.get_endpoint_stats

    async def test_error_stats_offloaded(self):
        with patch.object(
            mon_legacy_mod, "run_in_threadpool", AsyncMock(return_value={"errors": 0})
        ) as m_tp:
            result = await mon_legacy_mod.get_error_stats(
                hours=24, current_user=ADMIN, db=MagicMock()
            )
        assert result["data"] == {"errors": 0}
        assert m_tp.await_args.args[0] is mon_legacy_mod.MonitoringService.get_error_stats
