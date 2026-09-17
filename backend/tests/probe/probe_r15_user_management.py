# -*- coding: utf-8 -*-
# 固化自 2026-09-14 用户域安全修复 + 用户接口收敛：
#   1) 无组织 admin 可跨组织枚举全部用户（get_data_scope 未 fail-closed）；
#   2) 无组织管理员无数据边界 -> 产品决策：禁止创建（创建/更新双守卫）；
#   3) /user-management 与 /users 两套并行实现 -> 已下线前者，本探针只覆盖 /users 族。
# 运行：python backend/tests/probe/probe_r15_user_management.py
# 隔离契约：BUMOFU_BACKEND_DIR_OVERRIDE + DATABASE_URL 均指向本次运行临时目录，
#           不触碰真实 backend/data；退出码 0=全过，1=有失败。
"""第 15 轮：用户域全链路（列表/新增/编辑/删除/重置密码/分配角色/人员列表/
数据范围收口/越权边界/管理员组织必填），含数据库真实读写与前端消费契约校验。"""
import os
import sqlite3
import sys
import tempfile

TMP = tempfile.mkdtemp(prefix="probe_r15_")
os.chdir(TMP)
os.environ["BUMOFU_BACKEND_DIR_OVERRIDE"] = TMP
os.environ["DATABASE_URL"] = "sqlite:///" + TMP + "/probe.db"
os.environ["ENVIRONMENT"] = "test"
os.environ["SECRET_KEY"] = "x" * 40
os.environ["UPLOAD_DIR"] = TMP + "/uploads"
os.environ["BACKUP_ENABLED"] = "false"

BACKEND_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, BACKEND_ROOT)

from fastapi.testclient import TestClient  # noqa: E402

PASS, FAIL = [], []


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append((name, detail))
    print(("PASS" if cond else "FAIL"), name, "" if cond else str(detail)[:240])


def payload(j):
    """兼容统一信封 {code,data} 与页面在用的 {success,data} 两种形态。"""
    if not isinstance(j, dict):
        return {}
    if isinstance(j.get("data"), (dict, list)):
        return j["data"]
    return j


DB_PATH = TMP + "/probe.db"


def db_rows(sql, args=()):
    con = sqlite3.connect("file:" + DB_PATH + "?mode=ro", uri=True)
    try:
        return con.execute(sql, args).fetchall()
    finally:
        con.close()


US = "/api/v1/users"
GOOD_PWD = "Probe@2026abc"   # 满足 PasswordPolicy（>=12 位 + 四类字符）
SHORT_PWD = "Short@2026x"    # 11 位：必须被后端拒绝

from app.main import app  # noqa: E402


def login(client, username, password):
    r = client.get("/api/v1/auth/csrf-token")
    tok = (r.json().get("data") or {}).get("csrf_token")
    r = client.post("/api/v1/auth/login", json={"username": username, "password": password},
                    headers={"X-CSRF-Token": tok})
    token = (r.json().get("data") or {}).get("access_token")
    return token, {"Authorization": "Bearer " + str(token), "X-CSRF-Token": str(tok)}, r


def hdrs(client, token):
    """变更请求头：CSRF 令牌随会话轮换，每次重新获取。"""
    r = client.get("/api/v1/auth/csrf-token")
    csrf = (r.json().get("data") or {}).get("csrf_token")
    return {"Authorization": "Bearer " + str(token), "X-CSRF-Token": str(csrf)}


with TestClient(app, raise_server_exceptions=False) as client:
    at, _AUTH, r = login(client, "admin", "Admin@2026")
    check("管理员登录", bool(at), r.text[:160])

    org_a = payload(client.post("/api/v1/organizations", json={"name": "探针组织甲"},
                                headers=hdrs(client, at)).json()).get("id")
    org_b = payload(client.post("/api/v1/organizations", json={"name": "探针组织乙"},
                                headers=hdrs(client, at)).json()).get("id")
    check("建立两个组织", bool(org_a) and bool(org_b), (org_a, org_b))

    # ── U1 列表 ──
    r = client.get(US, params={"page": 1, "page_size": 20}, headers={"Authorization": "Bearer " + at})
    body = payload(r.json())
    check("U1 列表 200 且 items/total 可解析",
          r.status_code == 200 and isinstance(body.get("items"), list) and isinstance(body.get("total"), int),
          "%s %s" % (r.status_code, r.text[:160]))

    # ── U2 新增（页面载荷同款）──
    uname = "probe_r15_user"
    r = client.post(US, json={"username": uname, "full_name": "探针用户", "password": GOOD_PWD,
                              "email": "r15@example.com", "phone": "13800000015",
                              "department": "测试部门", "role": "user", "data_scope": "org",
                              "organization_id": org_a, "is_active": True},
                    headers=hdrs(client, at))
    ub = payload(r.json())
    uid = ub.get("id") or ub.get("user", {}).get("id")
    check("U2 新增用户成功", r.status_code in (200, 201) and bool(uid),
          "%s %s" % (r.status_code, r.text[:200]))
    rows = db_rows("SELECT username, full_name, department, role, is_active FROM users WHERE username=?", (uname,))
    check("U2b 新增已落库且字段正确",
          len(rows) == 1 and rows[0] == (uname, "探针用户", "测试部门", "user", 1), rows)

    # ── U3 密码策略 ──
    r = client.post(US, json={"username": "probe_r15_short", "password": SHORT_PWD, "role": "user"},
                    headers=hdrs(client, at))
    check("U3 短密码(11位)被拒 400", r.status_code == 400 and "12" in r.text,
          "%s %s" % (r.status_code, r.text[:160]))
    check("U3b 短密码未落库",
          db_rows("SELECT COUNT(*) FROM users WHERE username=?", ("probe_r15_short",))[0][0] == 0)

    # ── U4 重名 ──
    r = client.post(US, json={"username": uname, "password": GOOD_PWD, "role": "user"}, headers=hdrs(client, at))
    check("U4 重名用户名被拒(400)", r.status_code == 400, "%s %s" % (r.status_code, r.text[:120]))

    # ── U5 管理员组织必填（产品决策）──
    r = client.post(US, json={"username": "probe_r15_orgless_admin", "password": GOOD_PWD, "role": "admin"},
                    headers=hdrs(client, at))
    check("U5 无组织管理员被拒 400", r.status_code == 400 and "组织" in r.text,
          "%s %s" % (r.status_code, r.text[:200]))
    check("U5b 未落库",
          db_rows("SELECT COUNT(*) FROM users WHERE username=?", ("probe_r15_orgless_admin",))[0][0] == 0)
    r = client.post(US, json={"username": "probe_r15_org_admin", "password": GOOD_PWD,
                              "role": "admin", "organization_id": org_a}, headers=hdrs(client, at))
    check("U5c 有组织管理员创建成功", r.status_code in (200, 201), "%s %s" % (r.status_code, r.text[:200]))

    # ── U6 编辑 ──
    r = client.put(US + "/" + str(uid), json={"full_name": "探针用户-改", "department": "新部门"},
                   headers=hdrs(client, at))
    rows = db_rows("SELECT full_name, department FROM users WHERE id=?", (int(uid),))
    check("U6 编辑已落库", r.status_code == 200 and rows and rows[0] == ("探针用户-改", "新部门"),
          (r.status_code, rows))
    admin_row = db_rows("SELECT id FROM users WHERE username=?", ("probe_r15_org_admin",))
    if admin_row:
        r = client.put(US + "/" + str(admin_row[0][0]), json={"organization_id": None}, headers=hdrs(client, at))
        check("U6b 管理员改为无组织被拒 400", r.status_code == 400 and "组织" in r.text,
              "%s %s" % (r.status_code, r.text[:200]))
    else:
        check("U6b 管理员改为无组织被拒 400", False, "管理员未创建成功")

    # ── U7 分配角色（PUT /users/{id}/permissions）──
    r = client.put(US + "/" + str(uid) + "/permissions", json={"role": "viewer"}, headers=hdrs(client, at))
    rows = db_rows("SELECT role FROM users WHERE id=?", (int(uid),))
    check("U7 分配角色已落库", r.status_code == 200 and rows and rows[0][0] == "viewer", (r.status_code, rows))

    # ── U8 重置密码 ──
    r = client.post(US + "/" + str(uid) + "/admin-reset-password", json={"new_password": "Reset@2026zzz"},
                    headers=hdrs(client, at))
    check("U8 管理员重置密码成功", r.status_code == 200, "%s %s" % (r.status_code, r.text[:160]))
    _, _, r = login(client, uname, "Reset@2026zzz")
    check("U8b 重置后新密码可登录", r.status_code == 200, "%s %s" % (r.status_code, r.text[:160]))

    # ── U9 人员列表（审批转交/任务分配数据源）──
    r = client.get(US + "/staff-list", params={"page": 1, "page_size": 50, "keyword": uname},
                   headers={"Authorization": "Bearer " + at})
    items = payload(r.json()).get("items") or []
    check("U9 人员列表关键词检索命中",
          r.status_code == 200 and any(i.get("username") == uname for i in items),
          "%s %s" % (r.status_code, r.text[:160]))

    # ── U10 数据范围收口（端到端）：乙组织成员不应被甲组织管理员看到 ──
    r = client.post(US, json={"username": "probe_r15_user_b", "password": GOOD_PWD,
                              "role": "user", "organization_id": org_b}, headers=hdrs(client, at))
    check("U10a 乙组织成员创建成功", r.status_code in (200, 201), r.text[:160])
    nat_admin, _, r = login(client, "probe_r15_org_admin", GOOD_PWD)
    if nat_admin:
        r = client.get(US, params={"page": 1, "page_size": 50},
                       headers={"Authorization": "Bearer " + nat_admin})
        names = {i["username"] for i in payload(r.json()).get("items") or []}
        check("U10b 甲组织管理员看不到乙组织成员",
              r.status_code == 200 and "probe_r15_user_b" not in names, (r.status_code, sorted(names)))
        check("U10c 甲组织管理员能看到本组织成员", "probe_r15_user" in names, sorted(names))
    else:
        check("U10 部门级管理员看不到他组织用户", False, r.text[:160])

    # ── U11 越权边界 ──
    nat, USER_AUTH, r = login(client, uname, "Reset@2026zzz")
    if nat:
        r = client.get(US, headers={"Authorization": "Bearer " + nat})
        check("U11 普通用户访问用户列表 403", r.status_code == 403, "%s %s" % (r.status_code, r.text[:120]))
        r = client.post(US, json={"username": "should_not_create", "password": GOOD_PWD}, headers=hdrs(client, nat))
        check("U11b 普通用户新增用户 403", r.status_code in (401, 403), "%s %s" % (r.status_code, r.text[:120]))
        check("U11c 越权新增未落库",
              db_rows("SELECT COUNT(*) FROM users WHERE username=?", ("should_not_create",))[0][0] == 0)
        r = client.get(US + "/staff-list", params={"page_size": 50}, headers={"Authorization": "Bearer " + nat})
        sl = [i["username"] for i in payload(r.json()).get("items") or []]
        check("U11d 普通用户人员列表仅见自己", r.status_code == 200 and sl == [uname], sl)
    else:
        check("U11 普通用户登录", False, r.text[:160])

    # ── U12 其它用户端点回归 ──
    ah = {"Authorization": "Bearer " + at}
    for path, label in [("/api/v1/users/me", "users/me"),
                        ("/api/v1/users/pending/list", "pending/list"),
                        ("/api/v1/users/roles/options", "roles/options"),
                        ("/api/v1/users/permissions/options", "permissions/options"),
                        ("/api/v1/users/data-scopes/options", "data-scopes/options"),
                        ("/api/v1/rbac/roles", "rbac/roles")]:
        r = client.get(path, headers=ah)
        check("U12 %s 正常" % label, r.status_code == 200, r.status_code)

    # ── U13 删除 + 关联清理 + 幂等 ──
    r = client.delete(US + "/" + str(uid), headers=hdrs(client, at))
    check("U13 删除用户成功", r.status_code in (200, 204), "%s %s" % (r.status_code, r.text[:160]))
    check("U13b 删除已落库", db_rows("SELECT COUNT(*) FROM users WHERE id=?", (int(uid),))[0][0] == 0)
    check("U13c 关联角色表已清理",
          db_rows("SELECT COUNT(*) FROM rbac_user_roles WHERE user_id=?", (int(uid),))[0][0] == 0)
    r = client.delete(US + "/" + str(uid), headers=hdrs(client, at))
    check("U13d 重复删除返回 404（幂等边界）", r.status_code == 404, r.status_code)

print("")
print("=" * 60)
print("PASS %d / FAIL %d" % (len(PASS), len(FAIL)))
for name, detail in FAIL:
    print("  FAIL:", name, detail)
sys.exit(1 if FAIL else 0)
