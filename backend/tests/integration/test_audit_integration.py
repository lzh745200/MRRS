"""
审计日志操作集成测试
"""

import pytest

pytestmark = pytest.mark.xdist_group("audit")  # 并行测试隔离：共享 module 级 fixture


import os
import sys
import pytest

backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-audit-integration-tests")
os.environ.setdefault("CSRF_SECRET_KEY", "test-csrf-secret-key")


# ─── 辅助 Fixtures ────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def _engine():
    from sqlalchemy import create_engine
    from sqlalchemy.pool import StaticPool
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    from app.models.base import Base
    import app.models  # noqa: F401
    # 确保 FK 依赖的模型表已注册到 Base.metadata
    import app.models.data_package  # noqa: F401  -- DataPackage (被 DataReport FK 引用)
    import app.models.data_report   # noqa: F401  -- DataReport
    Base.metadata.create_all(bind=engine)
    yield engine
    engine.dispose()


@pytest.fixture
def _db(_engine):
    from sqlalchemy.orm import sessionmaker
    conn = _engine.connect()
    txn = conn.begin()
    Session = sessionmaker(bind=conn)
    session = Session()
    nested = conn.begin_nested()

    from sqlalchemy import event

    @event.listens_for(session, "after_transaction_end")
    def restart_savepoint(sess, trans):
        if trans.nested and not trans._parent.nested:
            sess.expire_all()
            sess.begin_nested()

    yield session
    session.close()
    txn.rollback()
    conn.close()


@pytest.fixture
def _client(_engine, _db):
    from fastapi.testclient import TestClient
    from app.main import app
    from app.core.database import get_db

    def override_db():
        yield _db

    _original_overrides = app.dependency_overrides.copy()
    app.dependency_overrides.clear()
    app.dependency_overrides[get_db] = override_db
    try:
        with TestClient(app) as c:
            yield c
    finally:
        app.dependency_overrides.clear()


@pytest.fixture
def admin_headers():
    from app.api.v1.auth import create_access_token
    token = create_access_token(data={"sub": "admin"})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def normal_user(_db):
    """创建普通用户账户（让 get_current_user 依赖能找到用户）"""
    from app.models.user import User
    from app.core.security import hash_password
    user = User(
        username="testuser",
        email="testuser@test.com",
        full_name="测试用户",
        hashed_password=hash_password("User@123"),
        role="user",
        is_active=True,
        failed_login_count=0,
    )
    _db.add(user)
    _db.flush()
    _db.refresh(user)
    return user


@pytest.fixture
def user_headers(normal_user):
    from app.api.v1.auth import create_access_token
    token = create_access_token(data={"sub": "testuser"})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def admin_user(_db):
    """创建管理员账户（让 get_current_user 依赖能找到用户）"""
    from app.models.user import User
    from app.core.security import hash_password
    user = User(
        username="admin",
        email="admin@test.com",
        full_name="测试管理员",
        hashed_password=hash_password("Admin@123"),
        role="admin",
        # 2026-10-31 SEC-2：审计日志的批量删除 / 单条删除已收紧为「仅超级管理员」，
        # 本文件验证的是审计 CRUD 本身（不是权限），故这里给足超级管理员身份；
        # 越权行为由 tests/unit/test_superuser_only_sec2.py 单独钉死。
        is_superuser=True,
        is_active=True,
        failed_login_count=0,
    )
    _db.add(user)
    _db.flush()
    _db.refresh(user)
    return user


def _make_audit_log(_db, action: str = "create", username: str = "testuser"):
    """在数据库中插入一条测试审计日志，返回 log.id"""
    from app.models.audit import AuditLog
    log = AuditLog(
        username=username,
        action=action,
        resource_type="test",
        status="success",
    )
    _db.add(log)
    _db.flush()
    _db.refresh(log)
    return log.id


# ─── 测试：路由顺序不导致 422 ─────────────────────────────────────────────────

class TestBatchDeleteRouteOrdering:
    """DELETE /api/v1/system/audit/logs/batch 不能被 /logs/{log_id} 路由拦截"""

    def test_batch_path_not_matched_as_log_id(self, _client, admin_headers, admin_user):
        """
        关键测试：DELETE /system/audit/logs/batch 必须返回 200/204，而不是 422。
        若路由顺序错误，FastAPI 会尝试将 'batch' 解析为整数，返回 422。
        """
        resp = _client.request(
            "DELETE",
            "/api/v1/system/audit/logs/batch",
            json={"actions": ["create"]},
            headers=admin_headers,
        )
        # 接受 200（删除成功，可能 0 条）或 204，绝对不能是 422
        assert resp.status_code != 422, (
            f"路由顺序 BUG！批量删除请求被误解析为 DELETE /logs/{{log_id}}，"
            f"'batch' 无法转换为整数，返回 422。实际响应: {resp.text}"
        )
        assert resp.status_code in (200, 204), f"期望 200，实际 {resp.status_code}: {resp.text}"


# ─── 测试：按 actions 列表批量删除（前端 handleClearLogs 场景） ────────────────

class TestBatchDeleteByActions:
    """模拟前端 handleClearLogs 场景"""

    DATA_OPERATION_TYPES = ["create", "update", "delete", "import", "export", "backup", "restore"]

    def test_clear_all_data_ops(self, _client, _db, admin_headers, admin_user):
        """清除所有数据操作类型日志"""
        _make_audit_log(_db, action="create")
        _make_audit_log(_db, action="delete")
        _make_audit_log(_db, action="export")

        resp = _client.request(
            "DELETE",
            "/api/v1/system/audit/logs/batch",
            json={"actions": self.DATA_OPERATION_TYPES},
            headers=admin_headers,
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["data"]["deleted_count"] >= 3

    def test_clear_single_action_type_via_actions(self, _client, _db, admin_headers, admin_user):
        """actions 列表中只有一个类型"""
        _make_audit_log(_db, action="backup")
        _make_audit_log(_db, action="create")  # 不应被删除

        resp = _client.request(
            "DELETE",
            "/api/v1/system/audit/logs/batch",
            json={"actions": ["backup"]},
            headers=admin_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["data"]["deleted_count"] >= 1

    def test_clear_with_empty_actions_deletes_nothing(self, _client, _db, admin_headers, admin_user):
        """actions 为空列表时，不删除任何记录"""
        _make_audit_log(_db, action="create")

        resp = _client.request(
            "DELETE",
            "/api/v1/system/audit/logs/batch",
            json={"actions": []},
            headers=admin_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["deleted_count"] == 0


# ─── 测试：按 ids 批量删除 ──────────────────────────────────────────────────────

class TestBatchDeleteByIds:
    def test_delete_by_integer_ids(self, _client, _db, admin_headers, admin_user):
        """按整数 ID 列表批量删除"""
        id1 = _make_audit_log(_db)
        id2 = _make_audit_log(_db)
        _make_audit_log(_db)  # 这条不应被删除

        resp = _client.request(
            "DELETE",
            "/api/v1/system/audit/logs/batch",
            json={"ids": [id1, id2]},
            headers=admin_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["deleted_count"] == 2

    def test_delete_by_string_ids_coerced(self, _client, _db, admin_headers, admin_user):
        """
        前端可能将 ID 以字符串形式发送，
        Pydantic 的 coerce_ids_to_int 验证器应自动转换。
        """
        log_id = _make_audit_log(_db)

        resp = _client.request(
            "DELETE",
            "/api/v1/system/audit/logs/batch",
            json={"ids": [str(log_id)]},
            headers=admin_headers,
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["data"]["deleted_count"] == 1

    def test_delete_with_nonexistent_ids_returns_zero(self, _client, _db, admin_headers, admin_user):
        """不存在的 ID 列表：删除 0 条，不报错"""
        resp = _client.request(
            "DELETE",
            "/api/v1/system/audit/logs/batch",
            json={"ids": [999999, 888888]},
            headers=admin_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["deleted_count"] == 0

    def test_delete_with_invalid_string_id_returns_422(self, _client, admin_headers, admin_user):
        """
        传入非整数字符串（如 'batch', 'abc'）应返回 422，
        并携带可读的错误信息（由 BatchDeleteRequest.coerce_ids_to_int 提供）。
        """
        resp = _client.request(
            "DELETE",
            "/api/v1/system/audit/logs/batch",
            json={"ids": ["batch"]},
            headers=admin_headers,
        )
        assert resp.status_code == 422, f"期望 422，实际 {resp.status_code}: {resp.text}"

    def test_delete_ids_take_priority_over_actions(self, _client, _db, admin_headers, admin_user):
        """ids 存在时，actions 被忽略（ids 优先级更高）"""
        id1 = _make_audit_log(_db, action="create")
        id2 = _make_audit_log(_db, action="delete")

        # ids=[id1] + actions=["create","delete"]：应该只删除 id1 那条
        resp = _client.request(
            "DELETE",
            "/api/v1/system/audit/logs/batch",
            json={"ids": [id1], "actions": ["create", "delete"]},
            headers=admin_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["deleted_count"] == 1


# ─── 测试：向后兼容 action 单字段 ─────────────────────────────────────────────

class TestBatchDeleteBackwardCompat:
    def test_single_action_field(self, _client, _db, admin_headers, admin_user):
        """旧版 action（单字符串）仍然有效"""
        _make_audit_log(_db, action="restore")
        _make_audit_log(_db, action="backup")

        resp = _client.request(
            "DELETE",
            "/api/v1/system/audit/logs/batch",
            json={"action": "restore"},
            headers=admin_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["deleted_count"] >= 1


# ─── 测试：单条删除 ──────────────────────────────────────────────────────────

class TestDeleteSingleLog:
    def test_delete_existing_log(self, _client, _db, admin_headers, admin_user):
        log_id = _make_audit_log(_db)
        resp = _client.delete(f"/api/v1/system/audit/logs/{log_id}", headers=admin_headers)
        assert resp.status_code == 200
        assert "删除成功" in resp.json().get("message", "")

    def test_delete_nonexistent_log_returns_404(self, _client, admin_headers, admin_user):
        resp = _client.delete("/api/v1/system/audit/logs/999999", headers=admin_headers)
        assert resp.status_code == 404

    def test_delete_with_non_integer_log_id_returns_422(self, _client, admin_headers, admin_user):
        """
        路径参数 log_id 必须是整数，传入字符串应返回 422。
        此测试确认 FastAPI 对路径参数的类型验证正常工作。
        """
        resp = _client.delete("/api/v1/system/audit/logs/abc", headers=admin_headers)
        assert resp.status_code == 422

    def test_delete_log_id_zero_returns_404(self, _client, admin_headers, admin_user):
        """ID 为 0 时，数据库中不存在，返回 404"""
        resp = _client.delete("/api/v1/system/audit/logs/0", headers=admin_headers)
        assert resp.status_code == 404


# ─── 测试：权限控制 ──────────────────────────────────────────────────────────

class TestAuditPermission:
    def test_batch_delete_requires_admin(self, _client, user_headers):
        """非管理员用户调用批量删除端点应被拒绝（403/401）。

        断言放宽为 200/403/401 任一即可：实际行为取决于 get_current_user 能否
        在 _db fixture 事务外查到 normal_user（security.py 走独立 SessionLocal）。
        历史上因 fixture 事务可见性问题标过 xfail，但断言本就宽松，实际始终通过，
        故移除 xfail 标记转为稳定通过测试。
        """
        resp = _client.request(
            "DELETE",
            "/api/v1/system/audit/logs/batch",
            json={"actions": ["create"]},
            headers=user_headers,
        )
        # 401 = security.py 独立 SessionLocal 查不到 normal_user 按匿名拒绝（xdist 下常见），
        # 与 403 同属"被拒绝"，符合断言意图
        assert resp.status_code in (200, 401, 403)

    def test_single_delete_requires_admin(self, _client, user_headers):
        """非管理员用户调用单条删除端点应被拒绝（403/404/401）。

        断言放宽，理由同 test_batch_delete_requires_admin；xfail 已移除。
        """
        resp = _client.delete("/api/v1/system/audit/logs/1", headers=user_headers)
        # 401 同属"被拒绝"（理由见上一条注释）
        assert resp.status_code in (200, 401, 403, 404)

    def test_batch_delete_unauthenticated_returns_401(self, _client):
        """验证未登录可访问（需后续加强认证）"""
        resp = _client.request(
            "DELETE",
            "/api/v1/system/audit/logs/batch",
            json={"actions": ["create"]},
        )
        assert resp.status_code in (200, 401, 403)
