"""W24 viewer 只读中间件端到端验收（真实 app + 真实 JWT + 共享内存库）。

验收矩阵（Lead 决策）：
- viewer 写业务接口 → 403（supported-villages / policies / funds 三类各一）；
- viewer 自服务白名单放行（登出 / 改密 / 通知偏好 / 反馈）；
- user / admin / super_admin 写不受影响；
- 未认证请求不被中间件拦截（仍由端点返回 401）；
- 被拒请求落审计（action=viewer_write_denied）。
"""

import pytest

from app.core.security import _rate_limit_store, hash_password

PASSWORD = "Probe#Pass2026w24"


@pytest.fixture
def api(client_with_db):
    client, db = client_with_db
    from app.models.user import User

    def add_user(username, role, is_superuser=False):
        user = User(
            username=username,
            email=username + "@viewer-probe.local",
            hashed_password=hash_password(PASSWORD),
            full_name=username,
            role=role,
            is_active=True,
            is_superuser=is_superuser,
            must_change_password=False,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user

    def login(username):
        _rate_limit_store.clear()
        resp = client.post(
            "/api/v1/auth/login",
            json={"username": username, "password": PASSWORD},
        )
        assert resp.status_code == 200, resp.text[:400]
        token = resp.json()["data"]["access_token"]
        return {"Authorization": "Bearer " + token}

    return client, db, add_user, login


def test_viewer_write_supported_villages_denied(api):
    client, db, add_user, login = api
    from app.models.supported_village import SupportedVillage

    add_user("v_village", "viewer")
    headers = login("v_village")
    before = db.query(SupportedVillage).count()
    resp = client.post(
        "/api/v1/supported-villages", headers=headers,
        json={"village_name": "viewer 不该创建成功的村"},
    )
    assert resp.status_code == 403, resp.text[:400]
    body = resp.json()
    assert body["code"] == 403
    assert body["success"] is False
    assert "viewer" in body["message"]
    assert db.query(SupportedVillage).count() == before


def test_viewer_write_policies_denied(api):
    client, db, add_user, login = api
    from app.models.policy import Policy

    add_user("v_policy", "viewer")
    headers = login("v_policy")
    before = db.query(Policy).count()
    resp = client.post(
        "/api/v1/policies", headers=headers,
        json={"title": "viewer 政策", "content": "x", "policy_type": "other"},
    )
    assert resp.status_code == 403, resp.text[:400]
    assert db.query(Policy).count() == before


def test_viewer_write_funds_denied(api):
    client, db, add_user, login = api

    add_user("v_fund", "viewer")
    headers = login("v_fund")
    resp = client.post("/api/v1/funds", headers=headers, json={})
    assert resp.status_code == 403, resp.text[:400]


def test_viewer_delete_is_blocked(api):
    client, db, add_user, login = api

    add_user("v_delete", "viewer")
    headers = login("v_delete")
    resp = client.delete("/api/v1/supported-villages/1", headers=headers)
    assert resp.status_code == 403


def test_viewer_self_service_whitelist_passes(api):
    client, db, add_user, login = api
    viewer = add_user("v_self", "viewer")
    headers = login("v_self")

    # 首登改密链路：白名单放行，端点自身校验旧密码（400 而非 403 = 已穿透中间件）
    resp = client.put(
        "/api/v1/users/" + str(viewer.id) + "/password", headers=headers,
        json={"old_password": "wrong-old", "new_password": "Strong#Passw0rd2026"},
    )
    assert resp.status_code == 400, resp.text[:300]
    assert "当前密码错误" in resp.text

    # 个人通知偏好（白名单：非 403 即可，端点/校验自行决定 200/4xx）
    resp = client.put("/api/v1/notifications/preferences", headers=headers, json={})
    assert resp.status_code != 403, resp.text[:300]
    assert resp.status_code < 500

    # 意见反馈（白名单）
    resp = client.post("/api/v1/feedback", headers=headers, json={"content": "viewer 反馈"})
    assert resp.status_code == 200, resp.text[:300]

    # 登出（认证自服务）必须最后执行：logout 会吊销当前 access token 并递增
    # token_version，之后再用同一 token 发请求会 401 而非穿透中间件。
    resp = client.post("/api/v1/auth/logout", headers=headers)
    assert resp.status_code == 200, resp.text[:300]


def test_user_role_write_still_allowed(api):
    client, db, add_user, login = api

    add_user("u_write", "user")
    headers = login("u_write")
    resp = client.post(
        "/api/v1/supported-villages", headers=headers,
        json={"village_name": "普通用户可创建"},
    )
    assert resp.status_code == 200, resp.text[:400]


def test_admin_role_write_still_allowed(api):
    client, db, add_user, login = api

    add_user("a_write", "admin")
    headers = login("a_write")
    resp = client.post(
        "/api/v1/policies", headers=headers,
        json={"title": "管理员政策", "content": "x", "policy_type": "other"},
    )
    assert resp.status_code == 200, resp.text[:400]


def test_super_admin_write_still_allowed(api):
    client, db, add_user, login = api

    add_user("s_write", "super_admin", is_superuser=True)
    headers = login("s_write")
    resp = client.post(
        "/api/v1/supported-villages", headers=headers,
        json={"village_name": "超管可创建"},
    )
    assert resp.status_code == 200, resp.text[:400]


def test_unauthenticated_write_not_blocked_by_middleware(api):
    client, db, add_user, login = api

    resp = client.post("/api/v1/supported-villages", json={"village_name": "匿名村"})
    assert resp.status_code == 401, resp.text[:400]
    assert "未提供认证凭证" in resp.text


def test_viewer_read_requests_still_allowed(api):
    client, db, add_user, login = api

    add_user("v_read", "viewer")
    headers = login("v_read")
    resp = client.get("/api/v1/supported-villages", headers=headers)
    assert resp.status_code == 200, resp.text[:400]
    resp = client.get("/api/v1/policies", headers=headers)
    assert resp.status_code == 200, resp.text[:400]


def test_viewer_write_denied_is_audited(api):
    client, db, add_user, login = api
    add_user("v_audit", "viewer")
    headers = login("v_audit")

    resp = client.post(
        "/api/v1/supported-villages", headers=headers,
        json={"village_name": "审计村"},
    )
    assert resp.status_code == 403

    # 审计落库经独立 SessionLocal（生产库）完成；本用例的共享库是内存库，
    # 用户 id 在独立库中不存在会触发 audit_logs.user_id 外键失败（测试基建差异，
    # 非产品缺陷），故此处断言「审计调用」而不查库；审计内容正确性由
    # tests/unit/middleware/test_viewer_readonly.py 与 test_audit.py 覆盖。
    from unittest.mock import patch

    with patch("app.utils.audit_logger.AuditLogger.log") as audit:
        resp = client.post(
            "/api/v1/supported-villages", headers=headers,
            json={"village_name": "审计村2"},
        )
    assert resp.status_code == 403
    audit.assert_called_once()
    kwargs = audit.call_args.kwargs
    assert kwargs["action"] == "viewer_write_denied"
    assert kwargs["details"] == {"method": "POST", "path": "/api/v1/supported-villages"}


def test_login_access_token_carries_role_and_uid_claims(api):
    """中间件只读判定依赖令牌内 role/uid 声明：登录签发的 access token 必须带齐。

    历史缺陷：令牌只有 sub/token_version，中间件不查库就拿不到角色 ——
    本用例锁定 core.security.build_auth_claims 的发放入口，防止声明漂移。
    """
    client, db, add_user, login = api
    from app.core.security import decode_token

    viewer = add_user("v_claims", "viewer")
    headers = login("v_claims")
    token = headers["Authorization"].split(" ", 1)[1]
    payload = decode_token(token)
    assert payload["role"] == "viewer"
    assert payload["uid"] == viewer.id
    assert payload["is_superuser"] is False
    assert "token_version" in payload


def test_refresh_token_rotation_keeps_role_claim(api):
    """refresh 轮换签发的新 access token 仍带 role 声明（否则刷新后只读失效）。"""
    client, db, add_user, login = api
    from app.core.security import _rate_limit_store, decode_token

    add_user("v_refresh", "viewer")
    _rate_limit_store.clear()
    resp = client.post(
        "/api/v1/auth/login",
        json={"username": "v_refresh", "password": PASSWORD},
    )
    assert resp.status_code == 200, resp.text[:300]
    refresh_token = resp.json()["refresh_token"]

    _rate_limit_store.clear()
    resp = client.post("/api/v1/auth/refresh", json={"token": refresh_token})
    assert resp.status_code == 200, resp.text[:300]
    new_access = resp.json()["data"]["access_token"]
    assert decode_token(new_access)["role"] == "viewer"


def test_viewer_with_must_change_password_not_deadlocked(api):
    """首登强制改密 + viewer 只读不得死锁：改自己密码必须放行。

    若中间件不把 /users/{id}/password 列入白名单，must_change_password=True 的
    viewer 将既不能写业务数据、也不能完成强制改密 —— 账号被永久锁死。
    """
    client, db, add_user, login = api
    viewer = add_user("v_first_login", "viewer")
    viewer.must_change_password = True
    db.commit()

    _rate_limit_store.clear()
    resp = client.post(
        "/api/v1/auth/login",
        json={"username": "v_first_login", "password": PASSWORD},
    )
    assert resp.status_code == 200, resp.text[:300]
    assert resp.json()["must_change_password"] is True
    headers = {"Authorization": "Bearer " + resp.json()["data"]["access_token"]}

    # 业务写仍被拒（需求：只读）
    resp = client.post(
        "/api/v1/supported-villages", headers=headers,
        json={"village_name": "首登 viewer 村"},
    )
    assert resp.status_code == 403

    # 改自己密码必须放行（否则死锁）
    resp = client.put(
        "/api/v1/users/" + str(viewer.id) + "/password", headers=headers,
        json={"old_password": PASSWORD, "new_password": "Stronger#Pass26"},
    )
    assert resp.status_code == 200, resp.text[:400]
