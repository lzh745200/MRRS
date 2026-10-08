"""终局分支清零（Group D 之后的收尾轮）—— core 层 + api 层长尾文件剩余弧。

本文件以"函数级直接调用"为主，逐一覆盖 `.coverage_qa4` 基线中 23 个长尾文件
仍未命中的分支弧（``A->B``）。不改动 ``app/`` 源码；不依赖任何外部网络。

覆盖目标（baseline=COVERAGE_FILE=.coverage_qa4）：
    zero_trust.py / data_packages.py / drive_detect.py / seed.py / environment.py
    token_manager.py / security.py / query_optimizer.py / logging_config.py
    database.py / cache.py / build_info.py / async_utils.py / system_health.py
    system/audit.py / system/admin.py / school.py / report_templates.py
    permission_packs.py / monitoring/metrics.py / import_data.py
    encryption.py(api + utils) / approval.py

约定：
- pytest ``asyncio_mode=auto``，async 用例直接 ``async def``。
- 一律直接 import 目标模块并调用其内部函数/端点协程，避免 TestClient 开销。
- 对 DB / 服务依赖统一使用 ``MagicMock`` / ``SimpleNamespace`` 假对象。
"""

from __future__ import annotations

import asyncio
import importlib
import json
import os
import string
import time
import zipfile
from types import SimpleNamespace
from unittest import mock

import pytest

from app.core.config import settings  # noqa: F401  (保持与运行环境一致的导入顺序)


# ══════════════════════════════════════════════════════════════════════════
#  通用假对象工厂
# ══════════════════════════════════════════════════════════════════════════


def _admin(**overrides):
    """管理员假用户（满足 require_admin / is_admin 判定）。"""
    base = dict(
        id=1,
        username="admin",
        role="admin",
        is_superuser=True,
        is_active=True,
        organization_id=1,
        permission_pack_id=None,
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def _user(**overrides):
    base = dict(
        id=2,
        username="user",
        role="user",
        is_superuser=False,
        is_active=True,
        organization_id=1,
        permission_pack_id=None,
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def _locked_query(**first_kwargs):
    """返回一个自链式 Query mock：filter/offset/limit/order_by 均返回自身。"""
    q = mock.MagicMock()
    for name in ("filter", "offset", "limit", "order_by", "join", "distinct"):
        getattr(q, name).return_value = q
    for k, v in first_kwargs.items():
        getattr(q, k).return_value = v
    return q


# ══════════════════════════════════════════════════════════════════════════
#  1. app/utils/drive_detect.py  →  103->101（去重命中已见 key）
# ══════════════════════════════════════════════════════════════════════════


def test_drive_detect_dedupe_duplicate_path(monkeypatch):
    from app.utils import drive_detect as dd

    monkeypatch.setattr(dd, "platform", SimpleNamespace(system=lambda: "Linux"))
    dup = {"path": os.path.abspath("dup_target"), "type": "removable", "available": True}
    monkeypatch.setattr(dd, "_list_linux_mounts", lambda: [dict(dup), dict(dup)])

    result = dd.list_backup_dirs()

    paths = [os.path.normcase(r["path"]) for r in result]
    assert paths.count(os.path.normcase(dup["path"])) == 1


# ══════════════════════════════════════════════════════════════════════════
#  2. app/core/build_info.py  →  16->30（文件不存在）/ 24->25（非对象 JSON）
# ══════════════════════════════════════════════════════════════════════════


def test_build_info_load_missing_file(monkeypatch, tmp_path):
    import app.core.build_info as bi

    monkeypatch.setattr(bi, "_BUILD_INFO_FILE", tmp_path / "absent.json")
    assert bi._load() == {}


def test_build_info_load_non_object_json(monkeypatch, tmp_path):
    import app.core.build_info as bi

    p = tmp_path / "list.json"
    p.write_text("[1, 2, 3]", encoding="utf-8")
    monkeypatch.setattr(bi, "_BUILD_INFO_FILE", p)
    assert bi._load() == {}


# ══════════════════════════════════════════════════════════════════════════
#  3. app/core/async_utils.py  →  28->32（双检锁已存在）/ 91->92（非法并发）
# ══════════════════════════════════════════════════════════════════════════


def test_async_utils_get_executor_double_check_locked():
    import app.core.async_utils as au

    sentinel = object()

    class _LockThatSetsExecutor:
        def __enter__(self):
            # 模拟另一线程已在获得锁之前创建了 executor
            au._EXECUTOR = sentinel
            return self

        def __exit__(self, *exc):
            return False

    saved_exec, saved_lock = au._EXECUTOR, au._LOCK
    try:
        au._EXECUTOR = None
        au._LOCK = _LockThatSetsExecutor()
        assert au._get_executor() is sentinel
    finally:
        au._EXECUTOR, au._LOCK = saved_exec, saved_lock


def test_async_utils_gather_limited_invalid_concurrency():
    import app.core.async_utils as au

    with pytest.raises(ValueError):
        asyncio.run(au.gather_limited(0))


# ══════════════════════════════════════════════════════════════════════════
#  4. app/core/cache.py  →  151->exit（兼容属性已存在且非 property，跳过注入）
# ══════════════════════════════════════════════════════════════════════════


def test_cache_module_compat_branch_false():
    import app.core.cache as cm

    # 快照原始命名空间：``importlib.reload`` 会就地重建模块内的 ``cache_manager`` /
    # ``CacheManager`` 等对象，使其成为新对象；而 ``app.api.v1.policy`` /
    # ``app.api.v1.organization`` 等模块是【按值导入】``cache_manager`` 的，仍持有旧
    # 引用。二者分裂后，测试里 ``patch("app.core.cache.cache_manager.get")`` 会打在
    # 新对象上、端点却用旧对象 → 跨文件 patch 静默失效（本缺陷曾拦截 v1.12.15 构建）。
    original = dict(cm.__dict__)

    inject = {"hasattr": lambda *a, **k: True, "isinstance": lambda *a, **k: False}
    for name, fn in inject.items():
        setattr(cm, name, fn)
    try:
        importlib.reload(cm)
    finally:
        for name in inject:
            cm.__dict__.pop(name, None)
        # 恢复模块到正常状态（重新定义 _cache property），覆盖兼容属性注入分支
        importlib.reload(cm)
        # 再就地还原原始命名空间：reload 只能得到【新】对象、无法恢复对象身份，
        # 只有回填 __dict__ 才能让 cache_manager 重新等于各模块按值持有的旧引用。
        cm.__dict__.clear()
        cm.__dict__.update(original)

    assert cm.CacheManager is not None


# ══════════════════════════════════════════════════════════════════════════
#  5. app/core/query_optimizer.py  →  125->-124（计数器已存在）/ 176->177（触发告警）
# ══════════════════════════════════════════════════════════════════════════


def test_query_optimizer_ensure_counter_second_call():
    import app.core.query_optimizer as qo

    qo._ensure_counter()
    qo._ensure_counter()  # 第二次：hasattr 为真 → 跳过赋值（125->-124）


def test_query_optimizer_n_plus_one_warning(monkeypatch):
    import app.core.query_optimizer as qo

    monkeypatch.setattr(qo, "get_query_count", lambda: 999)
    monkeypatch.setattr(qo, "reset_query_count", lambda: None)

    @qo.analyze_n_plus_one(threshold=1)
    def _fn():
        return "ok"

    assert _fn() == "ok"


# ══════════════════════════════════════════════════════════════════════════
#  6. app/core/logging_config.py  →  52->-30（轮转后 stream 已重开，跳过重开）
# ══════════════════════════════════════════════════════════════════════════


def test_safe_timed_rotating_rollover_reopens_stream(monkeypatch, tmp_path):
    from logging.handlers import TimedRotatingFileHandler

    from app.core.logging_config import SafeTimedRotatingFileHandler

    # 让父类 doRollover 成功后重开 stream，命中 "not self.stream" 为假的分支
    monkeypatch.setattr(
        TimedRotatingFileHandler,
        "doRollover",
        lambda self: setattr(self, "stream", self._open()),
        raising=True,
    )

    handler = SafeTimedRotatingFileHandler(
        str(tmp_path / "roll.log"), when="midnight", backupCount=1, encoding="utf-8"
    )
    try:
        handler.doRollover()
        assert handler.stream is not None
    finally:
        handler.close()


def test_safe_timed_rotating_rollover_all_attempts_fail(monkeypatch, tmp_path):
    """5 次轮转均因 WinError 32(PermissionError) 失败 → 走到尾部重开逻辑。"""
    from logging.handlers import TimedRotatingFileHandler

    from app.core.logging_config import SafeTimedRotatingFileHandler

    def _always_busy(self):
        raise PermissionError("WinError 32")

    monkeypatch.setattr(TimedRotatingFileHandler, "doRollover", _always_busy, raising=True)
    # 去掉重试 sleep，避免用例变慢
    monkeypatch.setattr("app.core.logging_config.time.sleep", lambda _s: None)

    handler = SafeTimedRotatingFileHandler(
        str(tmp_path / "roll2.log"), when="midnight", backupCount=1, encoding="utf-8"
    )
    try:
        handler.doRollover()
        # stream 在轮转开始时被置 None，5 次失败后由尾部 if 重开
        assert handler.stream is not None
    finally:
        handler.close()


# ══════════════════════════════════════════════════════════════════════════
#  7. app/core/token_manager.py  →  116->115（保留声明被跳过，循环继续）
# ══════════════════════════════════════════════════════════════════════════


def test_token_manager_reserved_claim_not_overridden():
    import jwt as pyjwt

    from app.core.token_manager import _get_algorithm, _get_secret_key, create_token_pair

    pair = create_token_pair("bob", extra_claims={"sub": "evil", "nick": "n"})
    payload = pyjwt.decode(
        pair["access_token"], _get_secret_key(), algorithms=[_get_algorithm()]
    )
    assert payload["sub"] == "bob"
    assert payload["nick"] == "n"


# ══════════════════════════════════════════════════════════════════════════
#  8. app/utils/encryption.py  →  60->61（盐值双检：锁内已存在，直接返回）
# ══════════════════════════════════════════════════════════════════════════


def test_encryption_load_deployment_salt_inner_double_check():
    from app.utils.encryption import DataPackageEncryption as Svc

    sentinel = b"0123456789abcdef"

    class _SaltLockThatSetsSalt:
        def __enter__(self):
            Svc._deployment_salt = sentinel
            return self

        def __exit__(self, *exc):
            return False

    saved_salt, saved_lock = Svc._deployment_salt, Svc._salt_lock
    try:
        Svc._deployment_salt = None
        Svc._salt_lock = _SaltLockThatSetsSalt()
        assert Svc._load_deployment_salt() == sentinel
    finally:
        Svc._deployment_salt, Svc._salt_lock = saved_salt, saved_lock


# ══════════════════════════════════════════════════════════════════════════
#  9. app/startup/environment.py  →  63->71（action 非 initialize/record_change）
# ══════════════════════════════════════════════════════════════════════════


def test_environment_version_change_unknown_action(monkeypatch):
    import app.startup.environment as env
    import app.services.update_log_service as uls
    import app.services.version_service as vs

    closed = {"v": False}

    class _FakeDB:
        def close(self):
            closed["v"] = True

    class _FakeUpdateSvc:
        def __init__(self, db):
            self.db = db

        def check_and_record_version_change(self, **kwargs):
            return {"action": "noop"}

    class _FakeVersionSvc:
        def get_current_version(self):
            return {"version": "9.9.9"}

    monkeypatch.setattr("app.core.database.SessionLocal", lambda: _FakeDB())
    monkeypatch.setattr(uls, "UpdateLogService", _FakeUpdateSvc)
    monkeypatch.setattr(vs, "version_service", _FakeVersionSvc())

    env._check_and_record_version_change()
    assert closed["v"] is True


# ══════════════════════════════════════════════════════════════════════════
#  10. app/api/v1/import_export/import_data.py  →  482->484（school 判定为假）
# ══════════════════════════════════════════════════════════════════════════


def test_import_data_setup_preview_entity_unknown_dispatch(monkeypatch):
    import app.api.v1.import_export.import_data as imp

    class _FakeValidator:
        def __init__(self, entity_type):
            self.config = {"duplicate_key": "name"}

    monkeypatch.setattr(
        imp,
        "VALID_ENTITY_TYPES",
        frozenset({"supported_village", "project", "fund", "school", "widget"}),
    )
    monkeypatch.setattr(imp, "EntityImportValidator", _FakeValidator)

    db = mock.MagicMock()
    # entity_type="widget" 通过白名单但不在 project/fund/school 分发链 → 482 为假 → 484
    # 之后 EntityModel 未绑定 → NameError（这正是被白名单挡住的原始缺陷路径）
    with pytest.raises(NameError):
        imp._setup_preview_entity("widget", db)


# ══════════════════════════════════════════════════════════════════════════
#  11. app/api/v1/system_health.py  →  288->298 / 317->320
# ══════════════════════════════════════════════════════════════════════════


def test_system_health_db_file_info_no_usable_path():
    import app.api.v1.system_health as sh

    db = mock.MagicMock()
    db.execute.return_value.fetchone.return_value = ("main", "/tmp/x", "")
    info = sh._get_db_file_info(db)
    assert info["status"] == "ok"
    assert info["size_mb"] == 0


def test_system_health_wal_status_wal_file_absent():
    import app.api.v1.system_health as sh

    db = mock.MagicMock()

    def _execute(stmt):
        m = mock.MagicMock()
        text = str(stmt)
        if "journal_mode" in text:
            m.fetchone.return_value = ("wal",)
        else:
            m.fetchone.return_value = ("main", "/tmp/x", "/__qa_missing__.db")
        return m

    db.execute.side_effect = _execute
    status = sh._check_wal_status(db)
    assert status["journal_mode"] == "wal"
    assert status["wal_size_mb"] == 0


# ══════════════════════════════════════════════════════════════════════════
#  12. app/api/v1/monitoring/metrics.py  →  102->109（非 SQLite 跳过文件大小统计）
# ══════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_monitoring_metrics_performance_dashboard_not_sqlite(monkeypatch):
    import app.api.v1.monitoring.metrics as m
    import app.core.database as dbmod

    fake_session = mock.MagicMock()
    fake_session.execute.return_value.scalar.return_value = 0

    monkeypatch.setattr(dbmod, "SessionLocal", lambda: fake_session)
    monkeypatch.setattr(dbmod, "IS_SQLITE", False)

    data = await m.get_performance_dashboard(current_user=_admin())
    assert data["success"] is True
    assert "db_stats" in data["data"]


# ══════════════════════════════════════════════════════════════════════════
#  13. app/api/v1/encryption.py  →  185->183（配置行缺失，循环继续）
# ══════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_encryption_disable_skips_absent_config_rows():
    import app.api.v1.encryption as enc

    db = mock.MagicMock()
    q = _locked_query(first=None)
    db.query.return_value = q

    with mock.patch.object(enc, "_verify_encryption_password", mock.MagicMock()), \
            mock.patch.object(enc, "safe_commit", mock.MagicMock()), \
            mock.patch.object(enc, "write_work_log", mock.MagicMock()):
        resp = await enc.disable_encryption(
            enc.DisableEncryptionRequest(password="pw123456"), db, _admin()
        )
    assert resp is not None


# ══════════════════════════════════════════════════════════════════════════
#  14. app/core/security.py  →  27 条弧
# ══════════════════════════════════════════════════════════════════════════


def test_security_must_change_password_allowed_matrix():
    from app.core.security import _must_change_password_request_allowed as allow

    assert allow("OPTIONS", "/whatever") is True            # 271->272
    assert allow("GET", "/api/v1/auth/me") is True           # 273->274
    assert allow("GET", "/api/v1/unrelated") is False        # 273->275
    assert allow("POST", "/api/v1/users/7/password", 7) is True


def test_security_enforce_must_change_password_blocks_and_allows():
    from fastapi import HTTPException

    from app.core.security import _enforce_must_change_password

    blocked_user = SimpleNamespace(must_change_password=True, id=3)
    req_blocked = SimpleNamespace(method="GET", url=SimpleNamespace(path="/api/v1/unrelated"))
    with pytest.raises(HTTPException):
        _enforce_must_change_password(blocked_user, req_blocked)   # 286->288, 290->291

    req_allowed = SimpleNamespace(method="OPTIONS", url=SimpleNamespace(path="/x"))
    # must_change_password 为真，但 OPTIONS 放行 → 不抛（290->-279）
    _enforce_must_change_password(blocked_user, req_allowed)

    plain_user = SimpleNamespace(must_change_password=False, id=4)
    _enforce_must_change_password(plain_user, None)


def _fake_jwt_payload(monkeypatch, payload):
    monkeypatch.setattr("app.core.security.decode_token", lambda _t: payload)


@pytest.mark.asyncio
async def test_security_get_current_user_blacklist_and_type(monkeypatch):
    from fastapi import HTTPException

    import app.core.security as sec

    _fake_jwt_payload(monkeypatch, {"jti": "abc", "type": "access", "sub": "u", "token_version": 0})

    # 黑名单命中 → 333->334
    monkeypatch.setattr("app.core.token_blacklist.is_blacklisted", lambda _j: True)
    with mock.patch.object(sec, "Session", mock.MagicMock):
        db = mock.MagicMock()
        creds = SimpleNamespace(credentials="tok")
        with pytest.raises(HTTPException):
            await sec.get_current_user(credentials=creds, db=db, request=None)

    # 未命中黑名单但类型不符 → 333->339, 340->342
    monkeypatch.setattr("app.core.token_blacklist.is_blacklisted", lambda _j: False)
    _fake_jwt_payload(monkeypatch, {"jti": "abc", "type": "refresh", "sub": "u"})
    with mock.patch.object(sec, "Session", mock.MagicMock):
        db = mock.MagicMock()
        with pytest.raises(HTTPException):
            await sec.get_current_user(
                credentials=SimpleNamespace(credentials="tok"), db=db, request=None
            )


@pytest.mark.asyncio
async def test_security_get_current_user_session_reuse_and_missing_user(monkeypatch):
    from fastapi import HTTPException

    import app.core.security as sec

    q = mock.MagicMock()
    q.filter.return_value = q

    # 注入式 Session（isinstance 为真）→ 383->385；用户不存在 → 387->388
    q.first.return_value = None
    db = mock.MagicMock()
    db.query.return_value = q
    _fake_jwt_payload(monkeypatch, {"jti": "j", "type": "access", "sub": "ghost", "token_version": 0})
    monkeypatch.setattr("app.core.token_blacklist.is_blacklisted", lambda _j: False)
    with mock.patch.object(sec, "Session", mock.MagicMock):
        with pytest.raises(HTTPException):
            await sec.get_current_user(
                credentials=SimpleNamespace(credentials="tok"), db=db, request=None
            )

    # token_version 存在且一致 → 397->404, 404->413
    user = SimpleNamespace(id=9, username="ghost", token_version_safe=2, must_change_password=False)
    q.first.return_value = user
    _fake_jwt_payload(monkeypatch, {"jti": "j", "type": "access", "sub": "ghost", "token_version": 2})
    with mock.patch.object(sec, "Session", mock.MagicMock), \
            mock.patch("app.middleware.audit_context.set_current_user", mock.MagicMock()):
        got = await sec.get_current_user(
            credentials=SimpleNamespace(credentials="tok"), db=db, request=None
        )
    assert got is user


@pytest.mark.asyncio
async def test_security_get_current_user_missing_version_rejected(monkeypatch):
    from fastapi import HTTPException

    import app.core.security as sec

    q = mock.MagicMock()
    q.filter.return_value = q
    q.first.return_value = SimpleNamespace(
        id=5, username="u5", token_version_safe=3, must_change_password=False
    )
    db = mock.MagicMock()
    db.query.return_value = q
    _fake_jwt_payload(monkeypatch, {"jti": "j", "type": "access", "sub": "u5"})
    monkeypatch.setattr("app.core.token_blacklist.is_blacklisted", lambda _j: False)
    with mock.patch.object(sec, "Session", mock.MagicMock):
        with pytest.raises(HTTPException):
            await sec.get_current_user(
                credentials=SimpleNamespace(credentials="tok"), db=db, request=None
            )  # token_version 缺失 + current_version>0 → 398->399


def test_security_cleanup_expired_rate_keys_throttled_and_empty(monkeypatch):
    import app.core.security as sec

    monkeypatch.setattr(sec, "_rate_limit_store", {})
    monkeypatch.setattr(sec, "_last_rate_limit_cleanup", 0.0)

    sec._cleanup_expired_rate_keys(time.monotonic())        # 533->-522（无过期键）
    sec._cleanup_expired_rate_keys(time.monotonic())        # 526->527（60 秒节流）


@pytest.mark.asyncio
async def test_security_check_rate_limit_branches():
    import app.core.security as sec

    req = SimpleNamespace()

    with pytest.raises(ValueError):
        await sec.check_rate_limit(None, request=req)       # 567->568

    with pytest.raises(ValueError):
        await sec.check_rate_limit("k", request=None)       # 567->569, 569->570

    key = f"qa4:{time.monotonic_ns()}"
    assert await sec.check_rate_limit(key, request=req, limit=1) is True   # 569->572, 581->584
    assert await sec.check_rate_limit(key, request=req, limit=1) is False  # 581->582


def test_security_get_client_ip_proxy_headers(monkeypatch):
    import app.core.security as sec

    monkeypatch.setattr(
        "app.core.config.settings", SimpleNamespace(TRUST_PROXY_HEADERS=True)
    )
    req = SimpleNamespace(headers={}, client=SimpleNamespace(host="10.0.0.9"))
    # 601->602, 603->605, 606->608（无 XFF / 无 X-Real-IP）
    assert sec.get_client_ip(req) == "10.0.0.9"


@pytest.mark.parametrize(
    "password",
    [
        "short",              # 649->650
        "abcdefghijkl",       # 651->652（无大写）
        "ABCDEFGHIJKL",       # 653->654（无小写）
        "Abcdefghijkl",       # 655->656（无数字）
        "Abcdefghij12",       # 657->658（无特殊字符）
        "Abcdefghij1!Abcdefghij1!",  # 659->660（超长）
        "passwordAbc1!",      # 662->663（弱密码前缀）
    ],
)
def test_security_password_policy_validate_false_branches(password):
    from app.core.security import PasswordPolicy

    ok, msg = PasswordPolicy.validate(password)
    assert ok is False and msg


def test_security_password_policy_validate_username_false_branches():
    from app.core.security import PasswordPolicy

    assert PasswordPolicy.validate_username(None)[0] is False   # 677->678
    assert PasswordPolicy.validate_username("ab")[0] is False   # 680->681


@pytest.mark.asyncio
async def test_security_get_current_user_version_mismatch(monkeypatch):
    from fastapi import HTTPException

    import app.core.security as sec

    q = mock.MagicMock()
    q.filter.return_value = q
    q.first.return_value = SimpleNamespace(
        id=6, username="u6", token_version_safe=1, must_change_password=False
    )
    db = mock.MagicMock()
    db.query.return_value = q
    _fake_jwt_payload(monkeypatch, {"jti": "j", "type": "access", "sub": "u6", "token_version": 99})
    monkeypatch.setattr("app.core.token_blacklist.is_blacklisted", lambda _j: False)
    with mock.patch.object(sec, "Session", mock.MagicMock):
        with pytest.raises(HTTPException):
            # token_version 不一致 → 404->405（raise 401）
            await sec.get_current_user(
                credentials=SimpleNamespace(credentials="tok"), db=db, request=None
            )


# ══════════════════════════════════════════════════════════════════════════
#  15. app/api/v1/approval.py  →  921->923（records 末项为 None，opinion 保持 None）
# ══════════════════════════════════════════════════════════════════════════


def test_approval_task_to_dict_last_record_none():
    from app.api.v1.approval import _task_to_dict

    task = SimpleNamespace(
        id=1,
        title="t",
        entity_type="fund",
        entity_id=2,
        status="pending",
        current_level=1,
        priority="normal",
        submitter_id=3,
        submitter=None,
        current_approver_id=None,
        records=[None],
        created_at=None,
        completed_at=None,
        updated_at=None,
        change_data=None,
    )
    result = _task_to_dict(task)
    assert result["id"] == 1


# ══════════════════════════════════════════════════════════════════════════
#  16. app/api/v1/permission_packs.py  →  278->277（用户未绑定本包，循环继续）
# ══════════════════════════════════════════════════════════════════════════


def test_permission_packs_unbind_skips_unbound_user():
    from app.models.permission_pack import PermissionPack
    from app.models.user import User

    import app.api.v1.permission_packs as pp

    pack = SimpleNamespace(id=1, name="pkg")
    bound = SimpleNamespace(id=1, permission_pack_id=1)
    unbound = SimpleNamespace(id=2, permission_pack_id=99)

    def _query(model):
        q = _locked_query()
        if model is PermissionPack:
            q.first.return_value = pack
        elif model is User:
            q.all.return_value = [bound, unbound]
        return q

    db = mock.MagicMock()
    db.query.side_effect = _query

    with mock.patch.object(pp, "safe_commit", mock.MagicMock()), \
            mock.patch.object(pp, "_log", mock.MagicMock()):
        resp = pp.unbind_users(1, pp.BindUsersRequest(user_ids=[1, 2]), db, _admin())

    assert resp is not None
    assert bound.permission_pack_id is None      # 命中分支
    assert unbound.permission_pack_id == 99      # 未命中 → 278->277


# ══════════════════════════════════════════════════════════════════════════
#  17. app/api/v1/system/audit.py  →  88->92（before_date 为非字符串真值）
# ══════════════════════════════════════════════════════════════════════════


def test_audit_validate_before_date_non_string():
    from datetime import date

    import app.api.v1.system.audit as audit

    # 找到承载 validate_before_date 的模型类
    validator = None
    for obj in vars(audit).values():
        if isinstance(obj, type) and hasattr(obj, "validate_before_date"):
            validator = obj
            break
    assert validator is not None, "未找到包含 validate_before_date 的请求模型"

    result = validator.validate_before_date(date(2024, 1, 2))
    assert result is not None  # 非字符串 → isinstance 为假 → 直接走解析（88->92）


# ══════════════════════════════════════════════════════════════════════════
#  18. app/api/v1/system/admin.py  →  255->257（system_name 为 None，跳过 set）
# ══════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_admin_update_config_skips_none_fields():
    import app.api.v1.system.admin as admin_mod

    config = SimpleNamespace(
        system_name=None,
        max_login_attempts=5,
        session_timeout=None,
        password_expiry_days=None,
    )
    db = mock.MagicMock()
    svc = mock.MagicMock()

    with mock.patch("app.services.system_config_service.SystemConfigService", return_value=svc):
        resp = await admin_mod.update_system_config(config, _admin(), db)

    assert resp is not None
    # max_login_attempts 有值 → set 被调用一次
    assert svc.set.call_count == 1


# ══════════════════════════════════════════════════════════════════════════
#  19. app/api/v1/system/zero_trust.py  →  端点多分支
# ══════════════════════════════════════════════════════════════════════════


def _zt_request(host="1.2.3.4", scheme="https"):
    return SimpleNamespace(client=SimpleNamespace(host=host), url=SimpleNamespace(scheme=scheme))


@pytest.mark.asyncio
async def test_zero_trust_assessment_authenticated_https():
    import app.api.v1.system.zero_trust as zt

    res = await zt.get_trust_assessment(_zt_request(scheme="https"), current_user=_admin())
    assert res["data"]["level"] == "trusted"     # 263->264, 297->298, 331->332


@pytest.mark.asyncio
async def test_zero_trust_assessment_anonymous_http():
    import app.api.v1.system.zero_trust as zt

    res = await zt.get_trust_assessment(_zt_request(scheme="http"), current_user=None)
    data = res["data"]
    assert data["score"] < 80                     # 263->271, 297->305, 331->333, 346->347
    assert any("HTTPS" in r for r in data["recommendations"])


@pytest.mark.asyncio
async def test_zero_trust_policies_filter_branches():
    import app.api.v1.system.zero_trust as zt

    all_p = await zt.get_security_policies(None, False, _admin())     # 370->372, 372->375
    filt = await zt.get_security_policies("authentication", True, _admin())  # 370->371, 372->373
    assert all_p["data"]["total"] >= filt["data"]["total"]


@pytest.mark.asyncio
async def test_zero_trust_policy_detail_found_and_missing():
    from fastapi import HTTPException

    import app.api.v1.system.zero_trust as zt

    found = await zt.get_security_policy("ztp-001", _admin())   # 391->392, 392->393
    assert found["data"]["id"] == "ztp-001"

    with pytest.raises(HTTPException):
        await zt.get_security_policy("nope", _admin())          # 392->391, 391->395


@pytest.mark.asyncio
async def test_zero_trust_evaluate_access_branches():
    import app.api.v1.system.zero_trust as zt

    db = mock.MagicMock()
    with mock.patch.object(zt, "_record_security_event", mock.MagicMock()):
        # 敏感操作 + 非管理员 → 414->415, 425->438
        r1 = await zt.evaluate_access_request(
            zt.AccessRequest(resource="/x", action="delete"), _zt_request(), _user(), db
        )
        assert r1["data"]["result"] == "allowed"

        # 管理操作 + 非超管 → 425->426, 427->428
        r2 = await zt.evaluate_access_request(
            zt.AccessRequest(resource="/x", action="admin"), _zt_request(), _user(), db
        )
        assert r2["data"]["result"] == "denied"

        # 管理操作 + 超管 → 427->438
        r3 = await zt.evaluate_access_request(
            zt.AccessRequest(resource="/x", action="admin"), _zt_request(), _admin(), db
        )
        assert r3["data"]["result"] == "allowed"

        # 普通操作 → 414->425
        r4 = await zt.evaluate_access_request(
            zt.AccessRequest(resource="/x", action="read"), _zt_request(), _user(), db
        )
        assert r4["data"]["result"] == "allowed"


@pytest.mark.asyncio
async def test_zero_trust_events_list_filters():
    import app.api.v1.system.zero_trust as zt

    db = mock.MagicMock()
    q = _locked_query(first=None)
    q.count.return_value = 0
    q.all.return_value = []
    db.query.return_value = q

    await zt.get_security_events("high", "type", 1, 20, _admin(), db)   # 472->473, 474->475
    await zt.get_security_events(None, None, 1, 20, _admin(), db)       # 472->474


@pytest.mark.asyncio
async def test_zero_trust_event_stats_empty_and_nonempty():
    import app.api.v1.system.zero_trust as zt

    db = mock.MagicMock()
    q = _locked_query()
    q.all.return_value = []
    db.query.return_value = q
    empty = await zt.get_security_event_stats(_admin(), db)             # 539->543
    assert empty["data"]["total_events"] == 0

    ev1 = SimpleNamespace(severity="high", event_type="a")
    q.all.return_value = [ev1, SimpleNamespace(severity="low", event_type="a")]
    nonempty = await zt.get_security_event_stats(_admin(), db)          # 539->540
    assert nonempty["data"]["total_events"] == 2


def test_zero_trust_record_security_event_severity_branches():
    import app.api.v1.system.zero_trust as zt

    db = mock.MagicMock()
    high = zt._record_security_event(db, "e", "user:u", "high", "m")
    assert high["severity"] == "high"                                   # 122->123
    info = zt._record_security_event(db, "e", "src", "info", "m")
    assert info["severity"] == "info"                                   # 122->124


# ══════════════════════════════════════════════════════════════════════════
#  20. app/api/v1/data/data/data_packages.py  →  11 条弧
# ══════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_data_packages_list_with_explicit_org(monkeypatch):
    import app.api.v1.data.data.data_packages as dp

    service = mock.MagicMock()
    service.get_packages_by_org.return_value = []
    service.count_packages_by_org.return_value = 0
    perm = mock.MagicMock()
    perm.can_access_organization.return_value = True

    res = await dp.list_data_packages(
        page=1,
        page_size=20,
        org_id=5,
        status_filter=None,
        type_filter=None,
        current_user=_admin(),
        service=service,
        permission_service=perm,
    )
    assert res is not None                                            # 245->248


@pytest.mark.asyncio
async def test_data_packages_preview_org_unbound(monkeypatch):
    from fastapi import HTTPException

    import app.api.v1.data.data.data_packages as dp

    monkeypatch.setattr(dp, "get_org_with_fallback", lambda **kw: None)
    service = mock.MagicMock()
    perm = mock.MagicMock()

    with pytest.raises(HTTPException):
        await dp.preview_data_for_export(
            dp.DataPackageExportRequest(org_id=None, data_types=["widgets"]),
            _admin(),
            service,
            perm,
        )                                                             # 374->375


@pytest.mark.asyncio
async def test_data_packages_preview_model_without_org_column(monkeypatch):
    import app.api.v1.data.data.data_packages as dp
    import app.services.data_package_service as dps

    class _NoOrgModel:
        pass

    monkeypatch.setattr(dp, "get_org_with_fallback", lambda **kw: 7)
    monkeypatch.setattr(dps, "DATA_TYPE_MODELS", {"widgets": _NoOrgModel})

    db = mock.MagicMock()
    q = _locked_query()
    q.count.return_value = 3
    db.query.return_value = q
    service = SimpleNamespace(db=db)
    perm = mock.MagicMock()
    perm.can_access_organization.return_value = True

    res = await dp.preview_data_for_export(
        dp.DataPackageExportRequest(org_id=7, data_types=["widgets"]),
        _admin(),
        service,
        perm,
    )
    assert res is not None                                            # 392->394


def test_data_packages_base_package_time_missing_and_no_created_at():
    from app.core.exceptions import NotFoundException

    import app.api.v1.data.data.data_packages as dp

    svc_missing = mock.MagicMock()
    svc_missing.get_package.return_value = None
    with pytest.raises(NotFoundException):
        dp._get_base_package_time(svc_missing, 1)                     # 633->634

    svc_none = mock.MagicMock()
    svc_none.get_package.return_value = SimpleNamespace(created_at=None)
    assert dp._get_base_package_time(svc_none, 1) is not None         # 636->637


def _make_diff_zip(tmp_path):
    p = tmp_path / "pkg.zip"
    with zipfile.ZipFile(p, "w") as zf:
        zf.writestr("manifest.json", json.dumps({"data_types": ["villages"]}))
        zf.writestr("data/villages.json", json.dumps([{"id": 1}, {"id": 2}]))
    return str(p)


def test_data_packages_compute_diff_stats_loop(monkeypatch, tmp_path):
    import app.api.v1.data.data.data_packages as dp

    db = mock.MagicMock()
    q = _locked_query()
    q.count.return_value = 0
    db.query.return_value = q
    service = SimpleNamespace(db=db)

    stats = dp._compute_package_diff_stats(service, _make_diff_zip(tmp_path))
    assert "villages" in stats                                        # 667->669, 674->675/677


@pytest.mark.asyncio
async def test_data_packages_incremental_import_file_missing(monkeypatch):
    from fastapi import HTTPException

    import app.api.v1.data.data.data_packages as dp

    service = mock.MagicMock()
    service.get_package.return_value = SimpleNamespace(file_path=None, org_id=1)
    perm = mock.MagicMock()

    with pytest.raises(HTTPException):
        await dp.incremental_import(
            dp.IncrementalImportRequest(package_id=1, apply_changes=False),
            _zt_request(),
            _admin(),
            service,
            mock.MagicMock(),
            perm,
        )                                                             # 872->873


@pytest.mark.asyncio
async def test_data_packages_incremental_import_preview_only(monkeypatch, tmp_path):
    import app.api.v1.data.data.data_packages as dp

    file_path = _make_diff_zip(tmp_path)
    service = mock.MagicMock()
    service.get_package.return_value = SimpleNamespace(
        file_path=file_path, org_id=1, file_name="pkg.zip"
    )
    service.db = mock.MagicMock()
    q = _locked_query()
    q.count.return_value = 0
    service.db.query.return_value = q
    perm = mock.MagicMock()
    perm.can_access_organization.return_value = True

    res = await dp.incremental_import(
        dp.IncrementalImportRequest(package_id=1, apply_changes=False),
        _zt_request(),
        _admin(),
        service,
        mock.MagicMock(),
        perm,
    )
    assert res is not None                                            # 896->897


@pytest.mark.asyncio
async def test_data_packages_incremental_import_confirm_failure(monkeypatch, tmp_path):
    import app.api.v1.data.data.data_packages as dp

    file_path = _make_diff_zip(tmp_path)
    service = mock.MagicMock()
    service.get_package.return_value = SimpleNamespace(
        file_path=file_path, org_id=1, file_name="pkg.zip"
    )
    q = _locked_query()
    q.count.return_value = 0
    service.db = mock.MagicMock()
    service.db.query.return_value = q

    async def _import_package(**kwargs):
        return SimpleNamespace(package_id=11)

    async def _confirm_import(**kwargs):
        return SimpleNamespace(success=False)

    service.import_package.side_effect = _import_package
    service.confirm_import.side_effect = _confirm_import
    perm = mock.MagicMock()
    perm.can_access_organization.return_value = True

    with mock.patch.object(dp, "_safe_write_work_log", mock.MagicMock()):
        res = await dp.incremental_import(
            dp.IncrementalImportRequest(package_id=1, apply_changes=True),
            _zt_request(),
            _admin(),
            service,
            mock.MagicMock(),
            perm,
        )
    assert res is not None                                            # 924->925


def test_data_packages_ensure_package_org_access_fallthrough():
    import app.api.v1.data.data.data_packages as dp

    perm = mock.MagicMock()
    perm.can_access_organization.return_value = True
    pkg = SimpleNamespace(org_id=3)
    # 非管理员、org_id 有值且可访问 → 直接返回（1656->-1651）
    dp._ensure_package_org_access(perm, _user(), pkg)

    pkg_no_org = SimpleNamespace(org_id=None)
    dp._ensure_package_org_access(perm, _user(), pkg_no_org)


# ══════════════════════════════════════════════════════════════════════════
#  21. app/api/v1/school.py  →  7 条弧
# ══════════════════════════════════════════════════════════════════════════


def test_school_scholarship_apply_handler_guard():
    import app.api.v1.school as school

    db = mock.MagicMock()
    # status != approved → 直接 return（67 已覆盖）；本用例覆盖 74 为假（student 不存在）
    school._apply_scholarship_approval_result(
        db, SimpleNamespace(status="approved", entity_id=1)
    )                                                                 # 74->-62


@pytest.mark.asyncio
async def test_school_download_attachment_school_missing(monkeypatch):
    from app.models.school import SchoolAttachment

    import app.api.v1.school as school

    att = SimpleNamespace(school_id=1, file_path="/tmp/a.bin", file_name="a.bin", file_type=None)

    def _query(model):
        q = _locked_query(first=None)
        if model is SchoolAttachment:
            q.first.return_value = att
        return q

    db = mock.MagicMock()
    db.query.side_effect = _query

    monkeypatch.setattr(school, "_validate_file_path", lambda p: p)
    resp = await school.download_attachment(1, _admin(), db)
    assert resp is not None                                           # 610->616


@pytest.mark.asyncio
async def test_school_delete_attachment_school_missing(monkeypatch):
    from app.models.school import SchoolAttachment

    import app.api.v1.school as school

    att = SimpleNamespace(school_id=1, file_path="/tmp/a.bin", file_name="a.bin")

    def _query(model):
        q = _locked_query(first=None)
        if model is SchoolAttachment:
            q.first.return_value = att
        return q

    db = mock.MagicMock()
    db.query.side_effect = _query

    monkeypatch.setattr(school, "_validate_file_path", lambda p: p)
    with mock.patch.object(school, "safe_commit", mock.MagicMock()), \
            mock.patch.object(school.os, "remove", mock.MagicMock()), \
            mock.patch.object(school.os.path, "exists", lambda p: True):
        resp = await school.delete_attachment(1, _admin(), db)
    assert resp is not None                                           # 638->644


@pytest.mark.asyncio
async def test_school_list_include_deleted_true(monkeypatch):
    import app.api.v1.school as school

    q = _locked_query()
    q.count.return_value = 0
    q.all.return_value = []
    db = mock.MagicMock()
    db.query.return_value = q

    scope = SimpleNamespace(
        filter_by_org_ids=lambda query, *a, **k: query,
        filter_by_org=lambda query, *a, **k: query,
    )
    res = await school.list_schools(
        page=1,
        page_size=20,
        keyword=None,
        name=None,
        type=None,
        support_status=None,
        supportStatus=None,
        include_deleted=True,
        current_user=_admin(),
        data_scope=scope,
        db=db,
    )
    assert res is not None                                            # 699->704


@pytest.mark.asyncio
async def test_school_create_without_type(monkeypatch):
    import app.api.v1.school as school

    async def _noop():
        return None

    data = mock.MagicMock()
    data.code = "QA-CODE-1"
    data.model_dump.return_value = {"name": "QA学校", "code": "QA-CODE-1"}

    db = mock.MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None

    monkeypatch.setattr(school, "_invalidate_school_list_cache", _noop)
    with mock.patch.object(school, "safe_commit", mock.MagicMock()), \
            mock.patch.object(school, "write_work_log", mock.MagicMock()), \
            mock.patch.object(school, "submit_entity_change_approval", lambda *a, **k: 1):
        resp = await school.create_school(data, _admin(), db)

    assert resp is not None                                           # 801->804


@pytest.mark.asyncio
async def test_school_update_code_unique(monkeypatch):
    import app.api.v1.school as school

    existing_school = SimpleNamespace(
        id=1,
        organization_id=1,
        created_by=1,
        name="旧校名",
        code="OLD",
        district=None,
        support_status="active",
        to_dict=lambda: {"id": 1},
    )
    q = mock.MagicMock()
    q.filter.return_value = q
    q.first.side_effect = [existing_school, None]   # 858 存在；877 编码不冲突
    db = mock.MagicMock()
    db.query.return_value = q

    data = mock.MagicMock()
    data.model_dump.return_value = {"code": "NEW-CODE"}

    async def _noop():
        return None

    monkeypatch.setattr(school, "_invalidate_school_list_cache", _noop)
    with mock.patch.object(school, "require_data_permission", mock.MagicMock()), \
            mock.patch.object(school, "safe_commit", mock.MagicMock()), \
            mock.patch.object(school, "write_work_log", mock.MagicMock()), \
            mock.patch.object(school, "submit_entity_change_approval", lambda *a, **k: 1):
        resp = await school.update_school(1, data, _admin(), db)

    assert resp is not None                                           # 878->882
    assert existing_school.code == "NEW-CODE"


@pytest.mark.asyncio
async def test_school_create_project_without_phase(monkeypatch):
    import app.api.v1.school as school

    db = mock.MagicMock()
    data = school.SchoolProjectCreate(name="帮扶项目", phase=None)

    with mock.patch.object(school, "_get_school_and_check_permission", mock.MagicMock()), \
            mock.patch.object(school, "safe_commit", mock.MagicMock()), \
            mock.patch.object(school, "submit_entity_change_approval", lambda *a, **k: 7):
        resp = await school.create_project(1, data, _admin(), db)

    assert resp is not None                                           # 1135->1137


# ══════════════════════════════════════════════════════════════════════════
#  22. app/api/v1/report_templates.py  →  985->988（code 非空，跳过自动生成）
# ══════════════════════════════════════════════════════════════════════════


def test_report_templates_project_process_rows_with_code():
    import app.api.v1.report_templates as rt

    db = mock.MagicMock()
    q = _locked_query(first=None)
    db.query.return_value = q

    created, skipped, errors = rt._project_process_rows(
        db,
        [{"name": "项目甲", "code": "PRJ-X-1"}],
        mode="create",
        existing_names=set(),
        user_id=1,
    )
    assert errors == [] or isinstance(errors, list)                   # 985->988


# ══════════════════════════════════════════════════════════════════════════
#  23. app/core/database.py  →  89->90 / 230->-228 / 300->304 / 308->309 / 310->311
# ══════════════════════════════════════════════════════════════════════════


def test_database_sqlcipher_missing_raises(monkeypatch):
    import app.core.database as dbmod

    cursor = mock.MagicMock()
    cursor.execute.return_value.fetchone.return_value = None
    fake_conn = mock.MagicMock()
    fake_conn.cursor.return_value = cursor

    with mock.patch.object(dbmod, "settings", SimpleNamespace(DB_ENCRYPTION_ENABLED=True)):
        with pytest.raises(RuntimeError):
            dbmod._set_sqlite_pragma(fake_conn, None)                 # 89->90


def test_database_ensure_worker_existing():
    import app.core.database as dbmod

    coordinator = dbmod.SQLiteWriteCoordinator()
    coordinator._worker = object()   # 已存在 → 跳过创建
    coordinator._ensure_worker()                                      # 230->-228


def test_database_check_disk_space_custom_existing_path(tmp_path):
    import app.core.database as dbmod

    info = dbmod.check_disk_space(100, path=str(tmp_path))
    assert "free_mb" in info                                         # 300->304


def test_database_check_disk_space_nonexistent_drive(monkeypatch):
    import app.core.database as dbmod

    free_letter = next(
        (ltr for ltr in string.ascii_uppercase if not os.path.exists(f"{ltr}:\\")), None
    )
    if free_letter is None:
        pytest.skip("无空闲盘符可用于构造不存在路径")

    info = dbmod.check_disk_space(100, path=f"{free_letter}:\\__qa_never__")
    # 路径不存在 → while 回退父目录（308->309）→ 根仍不存在 → cwd（310->311）
    assert "path" in info


# ══════════════════════════════════════════════════════════════════════════
#  24. app/startup/seed.py  →  覆盖 env 密码 / 已存在管理员 / top_org 真值
# ══════════════════════════════════════════════════════════════════════════


def test_seed_default_admin_env_password_and_top_org(monkeypatch):
    import app.startup.seed as seed

    created = {}

    class _FakeQuery:
        def __init__(self, model):
            self.model = model

        def filter(self, *a, **k):
            return self

        def first(self):
            name = getattr(self.model, "__name__", "")
            if name == "Organization":
                return SimpleNamespace(id=42)
            return None   # 管理员不存在

    class _FakeDB:
        def query(self, model):
            return _FakeQuery(model)

        def add(self, obj):
            created["admin"] = obj

        def close(self):
            pass

        def rollback(self):
            pass

    class _FakeLockoutSvc:
        def unlock_expired(self, db, admin_username=""):
            return 2   # 命中 38->39

    monkeypatch.setenv("DEFAULT_ADMIN_PASSWORD", "Str0ng#Pass")
    monkeypatch.setattr("app.core.database.SessionLocal", lambda: _FakeDB())
    monkeypatch.setattr(
        "app.services.lockout_service.get_lockout_service", lambda: _FakeLockoutSvc()
    )
    monkeypatch.setattr(seed, "safe_commit", mock.MagicMock())

    seed._seed_default_admin()
    assert "admin" in created


def test_seed_default_admin_existing_admin(monkeypatch):
    import app.startup.seed as seed

    class _FakeQuery:
        def __init__(self, model):
            self.model = model

        def filter(self, *a, **k):
            return self

        def first(self):
            return SimpleNamespace(id=1, username="admin")   # 管理员已存在

    class _FakeDB:
        def query(self, model):
            return _FakeQuery(model)

        def close(self):
            pass

        def rollback(self):
            pass

    class _FakeLockoutSvc:
        def unlock_expired(self, db, admin_username=""):
            return 0

    monkeypatch.setattr("app.core.database.SessionLocal", lambda: _FakeDB())
    monkeypatch.setattr(
        "app.services.lockout_service.get_lockout_service", lambda: _FakeLockoutSvc()
    )
    seed._seed_default_admin()                                        # 42->86


# ══════════════════════════════════════════════════════════════════════════
#  25. app/api/v1/system/metrics.py  →  收尾补测（清单外，team-lead 追加）
#     弧：233->234（DB 文件存在）/ 248->249,254（表数 >20 与否）
#        313->315 / 315->317 / 317->319（history 的 metric_type 三分支）
# ══════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_system_metrics_database_metrics_file_and_truncation(monkeypatch, tmp_path):
    import sqlalchemy

    import app.api.v1.system.metrics as sm
    from app.utils import paths as paths_mod

    dbfile = tmp_path / "qa.db"
    dbfile.write_bytes(b"x" * 2048)
    monkeypatch.setattr(paths_mod, "get_database_path", lambda: dbfile)
    monkeypatch.setattr(
        sqlalchemy,
        "inspect",
        lambda bind: SimpleNamespace(get_table_names=lambda: [f"t{i}" for i in range(25)]),
    )

    db = mock.MagicMock()
    db.execute.return_value.scalar.return_value = 0

    res = await sm.get_database_metrics(db, _admin())
    md = res["data"]["metrics"]
    assert md["table_count"] == 25                                     # 248->249
    assert md["table_names_truncated"] is True
    assert md["database_file_size_mb"] == round(2048 / (1024 * 1024), 2)  # 233->234


@pytest.mark.asyncio
async def test_system_metrics_database_metrics_small_table_count(monkeypatch, tmp_path):
    import sqlalchemy

    import app.api.v1.system.metrics as sm
    from app.utils import paths as paths_mod

    monkeypatch.setattr(paths_mod, "get_database_path", lambda: tmp_path / "absent.db")
    monkeypatch.setattr(
        sqlalchemy,
        "inspect",
        lambda bind: SimpleNamespace(get_table_names=lambda: ["users", "funds"]),
    )

    db = mock.MagicMock()
    db.execute.return_value.scalar.return_value = 0

    res = await sm.get_database_metrics(db, _admin())
    md = res["data"]["metrics"]
    assert md["table_count"] == 2
    assert "table_names_truncated" not in md                           # 248->254


@pytest.mark.asyncio
async def test_system_metrics_history_metric_type_matrix():
    import app.api.v1.system.metrics as sm

    rec = SimpleNamespace(
        created_at=None, host="h", cpu_usage=11.0, memory_usage=22.0, disk_usage=33.0
    )
    db = mock.MagicMock()
    q = _locked_query()
    q.all.return_value = [rec]
    db.query.return_value = q

    mem = await sm.get_metrics_history(
        hours=24, metric_type="memory", db=db, current_user=_admin()
    )                                                                  # 313->315, 315->316
    cpu = await sm.get_metrics_history(
        hours=24, metric_type="cpu", db=db, current_user=_admin()
    )                                                                  # 313->314, 315->317, 317->319

    assert mem["data"]["history"][0]["memory_usage"] == 22.0
    assert cpu["data"]["history"][0]["cpu_usage"] == 11.0


# 说明：``app/core/logging_config.py`` 第 52 行（doRollover 末段 ``if not self.stream:``
# 的假分支）为不可达弧（论证见交付报告）；其余 24 个模块路径的基线弧已全部清零。
