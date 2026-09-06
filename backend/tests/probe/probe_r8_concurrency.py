# -*- coding: utf-8 -*-
# 固化自 2026-09 深度探测循环（r8 轮）。
# 运行：python backend/tests/probe/probe_r8_concurrency.py
#      或一次跑全部：python backend/tests/probe/run_all.py
# 隔离契约：BUMOFU_BACKEND_DIR_OVERRIDE + DATABASE_URL 均指向本次运行临时目录，
#           不触碰真实 backend/data；退出码 0=全过，1=有失败。
"""第 8 轮并发场景探测（真实 HTTP 多线程）：
同记录并发写 / 审批竞态 / 并发备份 / 并发注册（通行码单用竞态）/ 并发导入"""
import io
import os
import sys
import tempfile
import threading
import zipfile
from concurrent.futures import ThreadPoolExecutor

TMP = tempfile.mkdtemp(prefix="probe_r8_")
os.chdir(TMP)
os.environ["BUMOFU_BACKEND_DIR_OVERRIDE"] = TMP
os.environ["DATABASE_URL"] = f"sqlite:///{TMP}/probe.db"
os.environ["ENVIRONMENT"] = "test"
os.environ["SECRET_KEY"] = "x" * 40
os.environ["UPLOAD_DIR"] = f"{TMP}/uploads"
os.environ["BACKUP_ENABLED"] = "false"

BACKEND_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, BACKEND_ROOT)

from fastapi.testclient import TestClient  # noqa: E402

PASS, FAIL = [], []


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append((name, detail))
    print(("PASS" if cond else "FAIL"), name, "" if cond else str(detail)[:260])


def unwrap(j):
    if isinstance(j, dict) and isinstance(j.get("data"), (dict, list)):
        if j.get("code") == 200 or j.get("success") is True:
            return j["data"]
    return j


ERRORS = []
TLS = threading.local()


MAIN_CSRF_COOKIE = {}  # name → signed value（主线程登录后的 CSRF cookie）


def get_client():
    """每线程独立 TestClient，复用主线程令牌对（复制 CSRF cookie 配对）。"""
    if not hasattr(TLS, "client"):
        c = TestClient(app, raise_server_exceptions=False)
        for name, value in MAIN_CSRF_COOKIE.items():
            c.cookies.set(name, value)
        TLS.client = c
    return TLS.client


def auth():
    get_client()
    return AUTH


from app.main import app  # noqa: E402

# 主线程登录拿 AUTH（用于串行准备步骤）
with TestClient(app, raise_server_exceptions=False) as main_client:
    r = main_client.get("/api/v1/auth/csrf-token")
    token = (r.json().get("data") or {}).get("csrf_token")
    r = main_client.post("/api/v1/auth/login", json={"username": "admin", "password": "Admin@2026"},
                         headers={"X-CSRF-Token": token})
    AUTH = {"Authorization": f"Bearer {(r.json().get('data') or {}).get('access_token')}",
            "X-CSRF-Token": token}
    check("主线程登录", "Bearer" in AUTH["Authorization"])
    from app.middleware.csrf_middleware import CSRF_COOKIE_NAME
    MAIN_CSRF_COOKIE[CSRF_COOKIE_NAME] = main_client.cookies.get(CSRF_COOKIE_NAME)

    # ── 准备：一个村庄、一个待审批经费、一个通行码 ──
    r = main_client.post("/api/v1/supported-villages",
                         json={"village_name": "并发村", "province": "贵州省"}, headers=AUTH)
    vid = (unwrap(r.json()) or {}).get("id")
    check("准备村庄", bool(vid))

    r = main_client.post("/api/v1/funds",
                         json={"name": "并发经费", "planned_amount": 10000}, headers=AUTH)
    fund_id = (unwrap(r.json()) or {}).get("id")
    r = main_client.post(f"/api/v1/funds/{fund_id}/attachments?category=contract",
                         files={"file": ("c.pdf", b"%PDF", "application/pdf")}, headers=AUTH)
    check("准备经费(含附件)", r.status_code == 200)

    r = main_client.post("/api/v1/organizations", json={"name": "并发组织", "code": "CONC-1"}, headers=AUTH)
    org_id = (unwrap(r.json()) or {}).get("id")
    r = main_client.get(f"/api/v1/machine-code/organization/{org_id}/verification-code", headers=AUTH)
    vcode = (unwrap(r.json()) or {}).get("verification_code")
    r = main_client.post("/api/v1/machine-code/organization/create",
                         json={"organization_id": org_id, "verification_code": vcode}, headers=AUTH)
    pass_code = (unwrap(r.json()) or {}).get("pass_code")
    check("准备通行码", bool(pass_code))

    # ═══ 并发场景 1：同记录并发写（10 线程同改一个村名）═══
    def write_village(i):
        try:
            c = get_client()
            r = c.put(f"/api/v1/supported-villages/{vid}",
                      json={"village_name": f"并发村-v{i}"}, headers=auth())
            return r.status_code
        except Exception as e:
            ERRORS.append(f"write:{e}")
            return -1

    with ThreadPoolExecutor(max_workers=10) as ex:
        codes = list(ex.map(write_village, range(10)))
    ok = all(c == 200 for c in codes)
    r = main_client.get(f"/api/v1/supported-villages/{vid}", headers=AUTH)
    final_name = str(r.json())
    check("同记录 10 并发写: 全 200 无 500", ok, codes)
    check("最终态为其中一次写入且可读", f"并发村-v" in final_name, final_name[:120])

    # ═══ 并发场景 2：审批竞态（同一经费双线程同时 approve）═══
    def approve():
        try:
            c = get_client()
            r = c.post(f"/api/v1/funds/{fund_id}/approve", headers=auth())
            return r.status_code
        except Exception as e:
            ERRORS.append(f"approve:{e}")
            return -1

    with ThreadPoolExecutor(max_workers=2) as ex:
        codes = list(ex.map(lambda _: approve(), range(2)))
    r = main_client.get(f"/api/v1/funds/{fund_id}", headers=AUTH)
    st = (unwrap(r.json()) or {}).get("status")
    check("双并发审批: 无 500 且终态 approved", sorted(codes)[0] >= 200 and st == "approved"
          and 500 not in codes, (codes, st))

    # ═══ 并发场景 3：并发备份（同秒多备份，R3 修复回归）═══
    def backup(_):
        try:
            c = get_client()
            r = c.post("/api/v1/system/backup",
                       json={"description": "并发备份", "include_uploads": False}, headers=auth())
            return r.status_code
        except Exception as e:
            ERRORS.append(f"backup:{e}")
            return -1

    with ThreadPoolExecutor(max_workers=3) as ex:
        codes = list(ex.map(backup, range(3)))
    check("并发备份: 全 200（同秒不冲突）", all(c == 200 for c in codes), codes)

    # ═══ 并发场景 4：同一通行码并发注册（单用竞态）═══
    def register(_):
        try:
            c = get_client()
            r = c.post("/api/v1/auth/register",
                       json={"username": f"race_user_{threading.get_ident()}",
                             "password": "Pr0be!R8#Passw0rd", "pass_code": pass_code},
                       headers={"X-CSRF-Token": token})
            return r.status_code
        except Exception as e:
            ERRORS.append(f"register:{e}")
            return -1

    with ThreadPoolExecutor(max_workers=2) as ex:
        codes = list(ex.map(register, range(2)))
    check("同通行码并发注册: 恰好一成功一拒绝", sorted(codes) in ([200, 400], [200, 409]), codes)
    r = main_client.get("/api/v1/users", params={"keyword": "race_user_"}, headers=AUTH)
    users = unwrap(r.json()) or []
    if isinstance(users, dict):
        users = users.get("items") or []
    check("竞态后仅创建一个用户", len(users) == 1, len(users))

    # ═══ 并发场景 5：并发数据包导入（同包双线程）═══
    r = main_client.post("/api/v1/data-packages/export",
                         json={"data_types": ["villages"], "org_id": org_id}, headers=AUTH)
    ed = unwrap(r.json()) or {}
    pkg_path = ed.get("file_path")
    check("准备数据包", bool(pkg_path) and os.path.exists(pkg_path), ed)

    def import_pkg(_):
        try:
            c = get_client()
            r = c.post("/api/v1/data-packages/import",
                       files={"file": (os.path.basename(pkg_path), open(pkg_path, "rb").read(),
                                       "application/zip")},
                       params={"org_id": org_id}, headers=AUTH)
            return r.status_code
        except Exception as e:
            ERRORS.append(f"import:{e}")
            return -1

    with ThreadPoolExecutor(max_workers=2) as ex:
        codes = list(ex.map(import_pkg, range(2)))
    check("并发导入: 无 500", 500 not in codes and -1 not in codes, codes)

    if ERRORS:
        print("线程异常样本:", ERRORS[:3])

print(f"\n===== PASS {len(PASS)} / FAIL {len(FAIL)} =====")
for n, dd in FAIL:
    print("  FAIL:", n, "|", str(dd)[:220])
sys.exit(1 if FAIL else 0)
