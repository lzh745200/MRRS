# -*- coding: utf-8 -*-
# 固化自 2026-09 深度探测循环（r1 轮）。
# 运行：python backend/tests/probe/probe_r1_passcode_register.py
#      或一次跑全部：python backend/tests/probe/run_all.py
# 隔离契约：BUMOFU_BACKEND_DIR_OVERRIDE + DATABASE_URL 均指向本次运行临时目录，
#           不触碰真实 backend/data；退出码 0=全过，1=有失败。
"""第 1 轮模块深探 v2（修正取值形态）"""
import io
import os
import sys
import tempfile
import time
import zipfile

TMP = tempfile.mkdtemp(prefix="probe_r1v2_")
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
    print(("PASS" if cond else "FAIL"), name, "" if cond else str(detail)[:240])



def safe_json(r):
    try:
        return r.json()
    except Exception:
        return {"_non_json": True, "_status": r.status_code, "_len": len(r.content)}

def unwrap(j):
    """信封体: code/data/message(+顶层 refresh_token)；裸响应: 原样。"""
    return j.get("data") if isinstance(j, dict) and j.get("code") == 200 and isinstance(j.get("data"), (dict, list)) else j


from app.main import app  # noqa: E402

with TestClient(app, raise_server_exceptions=False) as client:
    r = client.get("/api/v1/auth/csrf-token")
    token = (r.json().get("data") or {}).get("csrf_token")
    r = client.post("/api/v1/auth/login", json={"username": "admin", "password": "Admin@2026"},
                    headers={"X-CSRF-Token": token})
    lj = r.json()
    at = (lj.get("data") or {}).get("access_token")
    rt = lj.get("refresh_token")
    check("管理员登录(access+refresh)", bool(at and rt), lj)
    AUTH = {"Authorization": f"Bearer {at}", "X-CSRF-Token": token}

    # ═══ 链路 1：组织通行码注册 ═══
    r = client.post("/api/v1/organizations", json={"name": "探针下级组织", "code": "PROBE-ORG-1"}, headers=AUTH)
    oj = r.json()
    org_id = (oj.get("data") or oj).get("id") or (oj.get("data") or oj).get("organization_id")
    check("创建组织", bool(org_id), oj)

    r = client.get(f"/api/v1/machine-code/organization/{org_id}/verification-code", headers=AUTH)
    vj = r.json()
    vcode = (vj.get("data") or vj).get("verification_code")
    check("获取组织校验码", bool(vcode), vj)

    r = client.post("/api/v1/machine-code/organization/create",
                    json={"organization_id": org_id, "verification_code": vcode, "allow_subordinate_generation": False},
                    headers=AUTH)
    pj = r.json()
    pass_code = (pj.get("data") or pj).get("pass_code")
    check("生成组织通行码", bool(pass_code), pj)

    r = client.post("/api/v1/machine-code/organization/create",
                    json={"organization_id": org_id, "verification_code": "0000"}, headers=AUTH)
    check("错误校验码被拒(400)", r.status_code == 400, (r.status_code, str(r.json())[:140]))

    r = client.post("/api/v1/auth/register",
                    json={"username": "probe_user1", "password": "Pr0be!Passw0rd#2026",
                          "pass_code": pass_code, "full_name": "探针用户"},
                    headers={"X-CSRF-Token": token})
    rj = r.json()
    check("通行码注册成功", r.status_code == 200 and bool((rj.get("data") or {}).get("access_token")), rj)

    r = client.post("/api/v1/auth/login",
                    json={"username": "probe_user1", "password": "Pr0be!Passw0rd#2026"},
                    headers={"X-CSRF-Token": token})
    lj2 = r.json()
    uat = (lj2.get("data") or {}).get("access_token")
    urt = lj2.get("refresh_token")
    check("新用户可登录", bool(uat and urt), lj2)

    r = client.post("/api/v1/auth/register",
                    json={"username": "probe_user2", "password": "Pr0be!Passw0rd#2026", "pass_code": pass_code},
                    headers={"X-CSRF-Token": token})
    check("通行码不可复用", r.status_code in (400, 409), (r.status_code, str(r.json())[:140]))

    # ═══ 链路 2：refresh 轮换（admin 的 rt）═══
    r = client.post("/api/v1/auth/refresh", json={"token": rt}, headers={"X-CSRF-Token": token})
    nj = r.json()
    new_at = (nj.get("data") or {}).get("access_token")
    new_rt = nj.get("refresh_token")
    check("refresh 换新令牌对", bool(new_at and new_rt), nj)

    r = client.post("/api/v1/auth/refresh", json={"token": rt}, headers={"X-CSRF-Token": token})
    check("旧 refresh 已吊销(401)", r.status_code == 401, (r.status_code, str(r.json())[:120]))

    r = client.post("/api/v1/auth/refresh", json={"token": new_rt}, headers={"X-CSRF-Token": token})
    check("新 refresh 可继续轮换", r.status_code == 200, (r.status_code, str(r.json())[:120]))

    r = client.post("/api/v1/auth/refresh", json={"token": at}, headers={"X-CSRF-Token": token})
    check("access 不能当 refresh(401)", r.status_code == 401, r.status_code)

    # ═══ 链路 3：异步导出任务链 ═══
    r = client.get("/api/v1/async-export/tasks", headers=AUTH)
    check("异步导出任务列表", r.status_code == 200, r.status_code)

    r = client.post("/api/v1/async-export/villages", json={}, headers=AUTH)
    ct = r.headers.get("content-type", "")
    if ct.startswith("application/vnd"):
        check("villages 导出(同步 xlsx)", len(r.content) > 500, len(r.content))
    else:
        tj = r.json()
        task_id = (tj.get("data") or tj).get("task_id") or (tj.get("data") or tj).get("id")
        check("villages 异步任务创建", bool(task_id), tj)
        sd = {}
        for _ in range(30):
            r = client.get(f"/api/v1/async-export/status/{task_id}", headers=AUTH)
            sd = (r.json().get("data") or r.json())
            if str(sd.get("status")) in ("completed", "success", "failed", "cancelled"):
                break
            time.sleep(0.3)
        check("异步任务到达终态", str(sd.get("status")) in ("completed", "success"), sd)
        if str(sd.get("status")) in ("completed", "success"):
            r = client.get(f"/api/v1/async-export/download/{task_id}", headers=AUTH)
            check("异步导出可下载", r.status_code == 200 and len(r.content) > 500, (r.status_code, len(r.content)))

    # reports 导出（直接返回 xlsx 二进制流）
    r = client.post("/api/v1/async-export/reports",
                    json={"report_type": "villages", "format": "xlsx"}, headers=AUTH)
    check("reports 导出", r.status_code == 200 and len(r.content) > 500,
          (r.status_code, r.headers.get("content-type"), len(r.content)))

    # ═══ 链路 4：权限包 导出→下载→导入预览→确认落库 ═══
    r = client.post("/api/v1/permission-packages/export",
                    json={"include_users": True, "include_roles": True, "include_permissions": True},
                    headers=AUTH)
    exj = r.json()
    pkg_name = (exj.get("data") or exj).get("file_name")
    check("权限包导出", bool(pkg_name), exj)

    r = client.get(f"/api/v1/permission-packages/download/{pkg_name}", headers=AUTH)
    pkg_bytes = r.content
    check("权限包可下载", r.status_code == 200 and len(pkg_bytes) > 100, (r.status_code, r.headers.get("content-type"), len(pkg_bytes)))

    r = client.post("/api/v1/permission-packages/import",
                    files={"file": (pkg_name, pkg_bytes, "application/zip")}, headers=AUTH)
    imj = safe_json(r)
    imd = imj.get("data") or imj
    imp_ok = r.status_code == 200 and (imd.get("success") is not False)
    check("权限包导入预览", imp_ok, imj)
    preview_name = imd.get("file_name") or imd.get("saved_file_name") or pkg_name

    r = client.post(f"/api/v1/permission-packages/confirm/{preview_name}", headers=AUTH)
    cfj = safe_json(r)
    cfd = cfj.get("data") or cfj
    check("权限包确认落库", r.status_code == 200 and cfd.get("success") is not False, cfj)

    # ═══ 链路 5：数据同步导出 ═══
    r = client.post("/api/v1/data-sync/export?modules=villages", headers=AUTH)
    dsj = r.json()
    dsd = dsj.get("data") or dsj
    pkg = dsd.get("package_name") or dsd.get("file_name") or dsd.get("package")
    check("数据同步导出", r.status_code == 200 and bool(pkg), dsj)

    if pkg:
        r = client.get(f"/api/v1/data-sync/export/download/{pkg}", headers=AUTH)
        check("数据包可下载(ZIP)", r.status_code == 200 and len(r.content) > 100, (r.status_code, r.headers.get("content-type"), len(r.content)))

    r = client.post("/api/v1/data-sync/export-encrypted?modules=villages",
                    json={"password": "Sync@2026#Key"}, headers=AUTH)
    ej = r.json()
    epkg = (ej.get("data") or ej).get("package_name") or (ej.get("data") or ej).get("file_name")
    check("加密数据同步导出", r.status_code == 200 and bool(epkg), ej)

    r = client.get("/api/v1/data-sync/logs", headers=AUTH)
    check("同步日志", r.status_code == 200, r.status_code)
    r = client.get("/api/v1/sync/dashboard", headers=AUTH)
    check("同步 dashboard", r.status_code == 200, r.status_code)
    r = client.get("/api/v1/sync/status", headers=AUTH)
    check("sync status", r.status_code == 200, r.status_code)

print(f"\n===== PASS {len(PASS)} / FAIL {len(FAIL)} =====")
for n, dd in FAIL:
    print("  FAIL:", n, "|", str(dd)[:220])
sys.exit(1 if FAIL else 0)
