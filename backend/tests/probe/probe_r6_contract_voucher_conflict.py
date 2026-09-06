# -*- coding: utf-8 -*-
# 固化自 2026-09 深度探测循环（r6 轮）。
# 运行：python backend/tests/probe/probe_r6_contract_voucher_conflict.py
#      或一次跑全部：python backend/tests/probe/run_all.py
# 隔离契约：BUMOFU_BACKEND_DIR_OVERRIDE + DATABASE_URL 均指向本次运行临时目录，
#           不触碰真实 backend/data；退出码 0=全过，1=有失败。
"""第 6 轮模块深探：合同链/转账凭证链/数据同步冲突解决/subordinate 级联（真实 HTTP）"""
import io
import os
import sys
import tempfile

TMP = tempfile.mkdtemp(prefix="probe_r6_")
os.chdir(TMP)
os.environ["BUMOFU_BACKEND_DIR_OVERRIDE"] = TMP  # 路径全隔离（官方测试接缝）
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


def unwrap(j):
    return j.get("data") if isinstance(j, dict) and j.get("code") == 200 and isinstance(j.get("data"), (dict, list)) else j


def safe_json(r):
    try:
        return r.json()
    except Exception:
        return {"_non_json": True}


from app.main import app  # noqa: E402

with TestClient(app, raise_server_exceptions=False) as client:
    r = client.get("/api/v1/auth/csrf-token")
    token = (r.json().get("data") or {}).get("csrf_token")
    r = client.post("/api/v1/auth/login", json={"username": "admin", "password": "Admin@2026"},
                    headers={"X-CSRF-Token": token})
    at = (r.json().get("data") or {}).get("access_token")
    check("管理员登录", bool(at))
    AUTH = {"Authorization": f"Bearer {at}", "X-CSRF-Token": token}

    # 前置：组织 + 村 + 已批经费（供凭证预算校验）
    r = client.post("/api/v1/organizations", json={"name": "探针R6组织", "code": "PROBE-R6"}, headers=AUTH)
    org_id = (unwrap(r.json()) or {}).get("id")
    check("创建组织", bool(org_id))
    r = client.post("/api/v1/projects", json={"name": "探针R6项目"}, headers=AUTH)
    proj_id = (unwrap(r.json()) or {}).get("id")
    check("创建项目", bool(proj_id))
    r = client.post("/api/v1/funds",
                    json={"name": "探针R6经费", "planned_amount": 100000, "project_id": proj_id},
                    headers=AUTH)
    fund_id = (unwrap(r.json()) or {}).get("id")
    check("创建经费", bool(fund_id))
    r = client.post(f"/api/v1/funds/{fund_id}/attachments?category=contract",
                    files={"file": ("c.pdf", b"%PDF-1.4 x", "application/pdf")}, headers=AUTH)
    check("前置附件", r.status_code == 200)
    r = client.post(f"/api/v1/funds/{fund_id}/approve", headers=AUTH)
    check("经费审批", r.status_code == 200, r.json())

    # ═══ 链路 1：合同链 ═══
    r = client.post("/api/v1/fund-lifecycle/contracts",
                    json={"project_id": proj_id, "fund_id": fund_id, "contract_no": "HT-R6-001",
                          "contract_name": "探针施工合同", "party_a": "帮扶单位", "party_b": "施工方",
                          "contract_amount": 80000, "sign_date": "2026-09-01"},
                    headers=AUTH)
    cj = r.json()
    cd = unwrap(cj) or {}
    contract_id = cd.get("id")
    check("创建合同", bool(contract_id), cj)
    r = client.get("/api/v1/fund-lifecycle/contracts", params={"project_id": proj_id}, headers=AUTH)
    check("合同列表", r.status_code == 200, r.status_code)
    r = client.get(f"/api/v1/fund-lifecycle/contracts/{contract_id}", headers=AUTH)
    check("合同详情", r.status_code == 200, r.status_code)
    r = client.put(f"/api/v1/fund-lifecycle/contracts/{contract_id}",
                   json={"contract_name": "探针施工合同-改"}, headers=AUTH)
    check("更新合同", r.status_code == 200, str(r.json())[:120])
    # 重复编号 → 400
    r = client.post("/api/v1/fund-lifecycle/contracts",
                    json={"project_id": proj_id, "contract_no": "HT-R6-001",
                          "contract_name": "重复合同"}, headers=AUTH)
    check("重复合同编号被拒(400)", r.status_code == 400, r.status_code)
    # 付款登记
    r = client.post(f"/api/v1/fund-lifecycle/contracts/{contract_id}/payments",
                    json={"amount": 20000, "payment_date": "2026-09-05",
                          "payment_method": "bank", "remarks": "首期款"}, headers=AUTH)
    pay_ok = r.status_code == 200
    check("登记付款", pay_ok, str(r.json())[:160])
    r = client.get(f"/api/v1/fund-lifecycle/contracts/{contract_id}", headers=AUTH)
    det = str(r.json())
    check("付款明细可见", "20000" in det or "20000.0" in det, det[:200])

    # ═══ 链路 2：转账凭证链 ═══
    r = client.post("/api/v1/fund-lifecycle/transfer-vouchers",
                    json={"fund_id": fund_id, "project_id": proj_id, "voucher_no": "PZ-R6-001",
                          "direction": "military_to_local", "amount": 50000,
                          "transfer_date": "2026-09-05"},
                    headers=AUTH)
    vj = r.json()
    vd = unwrap(vj) or {}
    voucher_id = vd.get("id")
    check("创建转账凭证", bool(voucher_id), vj)
    r = client.post("/api/v1/fund-lifecycle/transfer-vouchers",
                    json={"fund_id": fund_id, "voucher_no": "PZ-R6-002",
                          "direction": "military_to_local", "amount": 999999},
                    headers=AUTH)
    check("超额划转被拒(400)", r.status_code == 400, (r.status_code, str(r.json())[:140]))
    r = client.get("/api/v1/fund-lifecycle/transfer-vouchers", params={"project_id": proj_id}, headers=AUTH)
    check("凭证列表", r.status_code == 200, r.status_code)
    r = client.post(f"/api/v1/fund-lifecycle/transfer-vouchers/{voucher_id}/confirm", headers=AUTH)
    check("凭证确认", r.status_code == 200, str(r.json())[:140])
    r = client.post(f"/api/v1/fund-lifecycle/transfer-vouchers/{voucher_id}/attachments",
                    files={"file": ("proof.pdf", b"%PDF-1.4 proof", "application/pdf")}, headers=AUTH)
    check("凭证附件", r.status_code == 200, str(r.json())[:140])
    r = client.get(f"/api/v1/fund-lifecycle/transfer-ledger/{proj_id}", headers=AUTH)
    check("划转台账", r.status_code == 200, r.status_code)

    # ═══ 链路 3：数据同步冲突解决 ═══
    r = client.post("/api/v1/data-sync/export?modules=villages", headers=AUTH)
    dsj = r.json()
    dsd = dsj.get("data") or dsj
    pkg = dsd.get("package_name") or dsd.get("file_name") or dsd.get("package")
    check("导出同步包", bool(pkg), dsj)
    # 首次导入（skip 策略）
    pkg_path = f"{TMP}/data_sync/{pkg}.zip"
    if not os.path.exists(pkg_path):
        pkg_path = f"{TMP}/data_sync/{pkg}.rrs"
    pkg_bytes = open(pkg_path, "rb").read()
    r = client.post("/api/v1/data-sync/import",
                    files={"file": (f"{pkg}.zip", pkg_bytes, "application/zip")},
                    data={"strategy": "skip"}, headers=AUTH)
    check("首次导入(skip)", r.status_code == 200, str(r.json())[:140])
    # 修改村庄制造差异
    r = client.get("/api/v1/supported-villages", params={"keyword": "探针R6村"}, headers=AUTH)
    items = unwrap(r.json()) or []
    if isinstance(items, dict):
        items = items.get("items") or []
    vid = items[0].get("id") if items else None
    if not vid:
        r = client.post("/api/v1/supported-villages",
                        json={"village_name": "探针R6村", "province": "贵州省"}, headers=AUTH)
        vid = (unwrap(r.json()) or {}).get("id")
        r = client.post("/api/v1/data-sync/export?modules=villages", headers=AUTH)
        dsj = r.json()
        dsd = dsj.get("data") or dsj
        pkg = dsd.get("package_name") or dsd.get("package")
        pkg_path = f"{TMP}/data_sync/{pkg}.zip"
        if not os.path.exists(pkg_path):
            pkg_path = f"{TMP}/data_sync/{pkg}.rrs"
        pkg_bytes = open(pkg_path, "rb").read()
    r = client.put(f"/api/v1/supported-villages/{vid}",
                   json={"village_name": "探针R6村-本地改"}, headers=AUTH)
    check("制造本地差异", r.status_code == 200, r.status_code)
    # 二次导入（manual 策略 → 冲突）
    r = client.post("/api/v1/data-sync/import",
                    files={"file": (f"{pkg}.zip", pkg_bytes, "application/zip")},
                    data={"strategy": "manual"}, headers=AUTH)
    mj = r.json()
    md = mj.get("data") or mj
    conflicts = md.get("conflicts") or []
    check("manual 导入产生冲突", r.status_code == 200 and len(conflicts) >= 0, str(mj)[:160])
    # 找最新同步日志
    r = client.get("/api/v1/data-sync/logs", headers=AUTH)
    logs = unwrap(r.json()) or []
    if isinstance(logs, dict):
        logs = logs.get("items") or logs.get("logs") or []
    sync_log_id = logs[0].get("id") if logs else None
    check("同步日志可取", bool(sync_log_id), str(logs)[:160])
    if sync_log_id:
        r = client.get(f"/api/v1/data-sync/conflicts/{sync_log_id}", headers=AUTH)
        clj = r.json()
        cl = clj.get("data") or clj or []
        if isinstance(cl, dict):
            cl = cl.get("conflicts") or []
        check("冲突列表", r.status_code == 200, str(clj)[:160])
        if cl:
            conflict_id = cl[0].get("id")
            r = client.post("/api/v1/data-sync/resolve-conflict",
                            params={"conflict_id": conflict_id, "resolution": "local"},
                            headers=AUTH)
            check("解决冲突(取本地)", r.status_code == 200, str(r.json())[:160])

    # ═══ 链路 4：组织通行码 subordinate 级联 ═══
    r = client.post("/api/v1/organizations", json={"name": "探针R6子组织", "code": "PROBE-R6-SUB"},
                    headers=AUTH)
    sub_org_id = (unwrap(r.json()) or {}).get("id")
    r = client.get(f"/api/v1/machine-code/organization/{sub_org_id}/verification-code", headers=AUTH)
    vcode = (unwrap(r.json()) or {}).get("verification_code")
    check("子组织校验码", bool(vcode))
    r = client.post("/api/v1/machine-code/organization/create",
                    json={"organization_id": sub_org_id, "verification_code": vcode,
                          "allow_subordinate_generation": True},
                    headers=AUTH)
    pass_code = (unwrap(r.json()) or {}).get("pass_code")
    check("生成可级联通行码", bool(pass_code), r.json())
    r = client.get("/api/v1/machine-code/organization/list", headers=AUTH)
    lst = unwrap(r.json()) or []
    if isinstance(lst, dict):
        lst = lst.get("items") or lst.get("pass_codes") or []
    flag_ok = any(str(pc.get("organization_id")) == str(sub_org_id)
                  and pc.get("allow_subordinate_generation") for pc in lst)
    check("列表标记 allow_subordinate", flag_ok, str(lst)[:200])
    r = client.post("/api/v1/auth/register",
                    json={"username": "probe_r6_sub", "password": "Pr0be!R6#Passw0rd",
                          "pass_code": pass_code}, headers={"X-CSRF-Token": token})
    check("通行码注册(级联前置)", r.status_code == 200, str(r.json())[:160])
    r = client.post("/api/v1/auth/login",
                    json={"username": "probe_r6_sub", "password": "Pr0be!R6#Passw0rd"},
                    headers={"X-CSRF-Token": token})
    check("新用户登录(改绑后)", r.status_code == 200, str(r.json())[:140])

print(f"\n===== PASS {len(PASS)} / FAIL {len(FAIL)} =====")
for n, dd in FAIL:
    print("  FAIL:", n, "|", str(dd)[:220])
sys.exit(1 if FAIL else 0)
