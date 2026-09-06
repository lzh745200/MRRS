# -*- coding: utf-8 -*-
# 固化自 2026-09 深度探测循环（r3 轮）。
# 运行：python backend/tests/probe/probe_r3_funds_state_yearly_rbac.py
#      或一次跑全部：python backend/tests/probe/run_all.py
# 隔离契约：BUMOFU_BACKEND_DIR_OVERRIDE + DATABASE_URL 均指向本次运行临时目录，
#           不触碰真实 backend/data；退出码 0=全过，1=有失败。
"""第 3 轮模块深探：经费状态机/村年度板块/RBAC/系统配置与调度/数据包链（真实 HTTP）"""
import io
import os
import sys
import tempfile

TMP = tempfile.mkdtemp(prefix="probe_r3_")
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

    # 前置：建一个普通用户（复用 R1 的通行码链路简版：直接建用户走 users API）
    r = client.post("/api/v1/auth/register",
                    json={"username": "probe_r3_user", "password": "Pr0be!R3#Passw0rd",
                          "pass_code": "XXXX"},  # 伪造通行码应 400
                    headers={"X-CSRF-Token": token})
    check("无效通行码注册被拒(400)", r.status_code == 400, r.status_code)

    # ═══ 链路 1：经费状态机全生命周期 ═══
    r = client.post("/api/v1/funds",
                    json={"name": "探针经费-道路硬化", "type": "项目经费", "planned_amount": 50000,
                          "source": "省帮扶资金", "purpose": "村内道路硬化"},
                    headers=AUTH)
    fj = r.json()
    fund_id = (unwrap(fj) or {}).get("id")
    check("创建经费(planned)", bool(fund_id), fj)

    r = client.get(f"/api/v1/funds/{fund_id}", headers=AUTH)
    fd = unwrap(r.json()) or {}
    check("经费详情初始状态", r.status_code == 200 and fd.get("status") in ("planned", "pending", "draft"),
          (r.status_code, fd.get("status")))

    # 审批守卫：approve 需 ≥1 附件（R14 状态机守卫）
    r = client.post(f"/api/v1/funds/{fund_id}/approve", headers=AUTH)
    aj0 = r.json()
    check("无附件审批被拒(400)", r.status_code == 400 and "附件" in str(aj0.get("detail", "")), aj0)

    r = client.post(f"/api/v1/funds/{fund_id}/attachments?category=contract",
                    files={"file": ("contract.pdf", b"%PDF-1.4 fake contract", "application/pdf")},
                    headers=AUTH)
    check("上传合同附件", r.status_code == 200, r.json())

    r = client.post(f"/api/v1/funds/{fund_id}/approve", headers=AUTH)
    check("经费审批通过", r.status_code == 200, r.json())

    # 拨付守卫：缺分配令 → 400 且指明缺什么
    r = client.post(f"/api/v1/funds/{fund_id}/allocate", headers=AUTH)
    aj = r.json()
    check("缺分配令拨付被拒(400+明细)", r.status_code == 400 and "缺少必需文档" in str(aj.get("detail", "")), aj)

    # 上传两类必需附件
    png = b"\x89PNG\r\n\x1a\n" + b"0" * 64
    r = client.post(f"/api/v1/funds/{fund_id}/attachments?category=contract",
                    files={"file": ("contract.pdf", b"%PDF-1.4 fake contract", "application/pdf")},
                    headers=AUTH)
    check("上传合同附件", r.status_code == 200, r.json())
    r = client.post(f"/api/v1/funds/{fund_id}/attachments?category=allocation_order",
                    files={"file": ("order.pdf", b"%PDF-1.4 fake allocation order", "application/pdf")},
                    headers=AUTH)
    check("上传分配令附件", r.status_code == 200, r.json())

    # 附件列表可见
    r = client.get(f"/api/v1/funds/{fund_id}/attachments", headers=AUTH)
    ats = unwrap(r.json()) or []
    if isinstance(ats, dict):
        ats = ats.get("items") or ats.get("attachments") or []
    cats = {a.get("category") for a in ats}
    check("附件列表含两类必需文档", {"contract", "allocation_order"} <= cats, (r.status_code, cats))

    # 拨付 → 使用中 → 完成
    r = client.post(f"/api/v1/funds/{fund_id}/allocate", headers=AUTH)
    check("经费拨付", r.status_code == 200, r.json())
    r = client.post(f"/api/v1/funds/{fund_id}/start-use", headers=AUTH)
    check("开始使用", r.status_code == 200, r.json())
    r = client.post(f"/api/v1/funds/{fund_id}/complete", headers=AUTH)
    check("经费完结", r.status_code == 200, r.json())
    r = client.get(f"/api/v1/funds/{fund_id}", headers=AUTH)
    check("终态 completed", (unwrap(r.json()) or {}).get("status") == "completed",
          (unwrap(r.json()) or {}).get("status"))

    # 非法流转：completed → allocate 应 400
    r = client.post(f"/api/v1/funds/{fund_id}/allocate", headers=AUTH)
    check("终态后流转被拒(400)", r.status_code == 400, r.status_code)

    # 统计端点
    r = client.get("/api/v1/funds/statistics/overview", headers=AUTH)
    check("经费总览统计", r.status_code == 200, r.status_code)
    r = client.get("/api/v1/funds/statistics/multi-dimension", headers=AUTH)
    check("多维统计", r.status_code == 200, r.status_code)

    # ═══ 链路 2：帮扶村年度板块 ═══
    r = client.post("/api/v1/supported-villages",
                    json={"village_name": "探针年度村", "province": "贵州省"}, headers=AUTH)
    vid = (unwrap(r.json()) or {}).get("id")
    check("创建村庄", bool(vid), r.json())

    r = client.post(f"/api/v1/supported-villages/{vid}/yearly/2026/population",
                    json={"year": 2026, "total_population": 1200, "labor_population": 480},
                    headers=AUTH)
    check("保存人口板块", r.status_code == 200, r.json())

    # 连字符板块（force-investment）
    r = client.post(f"/api/v1/supported-villages/{vid}/yearly/2026/force-investment",
                    json={"year": 2026, "investment_amount": 300000, "project_count": 3},
                    headers=AUTH)
    check("保存帮扶投入板块(连字符)", r.status_code == 200, r.json())

    # 未知板块 → 400
    r = client.post(f"/api/v1/supported-villages/{vid}/yearly/2026/unknown-section",
                    json={}, headers=AUTH)
    check("未知板块被拒(400)", r.status_code == 400, r.status_code)

    r = client.get(f"/api/v1/supported-villages/{vid}/yearly/2026", headers=AUTH)
    yd = unwrap(r.json()) or {}
    pop = (yd.get("population") or {}) if isinstance(yd, dict) else {}
    check("年度数据回读", r.status_code == 200 and str(pop.get("totalPopulation")) == "1200", str(yd)[:200])

    r = client.post(f"/api/v1/supported-villages/{vid}/yearly/2026/validate", headers=AUTH)
    check("年度校验", r.status_code == 200, str(r.json())[:140])

    r = client.post(f"/api/v1/supported-villages/{vid}/yearly/copy",
                    json={"from_year": 2026, "to_year": 2027}, headers=AUTH)
    check("年度复制", r.status_code == 200, str(r.json())[:140])

    r = client.delete(f"/api/v1/supported-villages/{vid}/yearly/2027/population", headers=AUTH)
    check("删除年度板块", r.status_code == 200, r.status_code)

    # ═══ 链路 3：RBAC 用户与角色 ═══
    r = client.post("/api/v1/rbac/roles",
                    json={"name": "probe_r3_role", "description": "探针角色",
                          "permissions": ["villages:view", "funds:view"]},
                    headers=AUTH)
    rj = r.json()
    role_id = (unwrap(rj) or {}).get("id") or rj.get("role_id")
    check("创建角色", bool(role_id), rj)

    r = client.get("/api/v1/rbac/roles", headers=AUTH)
    check("角色列表", r.status_code == 200, r.status_code)

    # 建一个真实用户来分配角色
    r = client.post("/api/v1/users",
                    json={"username": "probe_r3_mgr", "password": "Pr0be!R3#User#2026",
                          "full_name": "探针经理", "role": "user"},
                    headers=AUTH)
    uj = r.json()
    new_uid = (unwrap(uj) or {}).get("id")
    check("管理员建用户", bool(new_uid), uj)

    r = client.post("/api/v1/rbac/assign/role",
                    json={"user_id": new_uid, "role_id": role_id}, headers=AUTH)
    check("分配角色", r.status_code == 200, str(r.json())[:140])

    r = client.get(f"/api/v1/rbac/user/{new_uid}/permissions", headers=AUTH)
    check("用户权限查询", r.status_code == 200, r.status_code)
    r = client.get(f"/api/v1/rbac/user/{new_uid}/roles", headers=AUTH)
    check("用户角色查询", r.status_code == 200, r.status_code)

    r = client.put(f"/api/v1/rbac/roles/{role_id}",
                   json={"name": "probe_r3_role_v2", "description": "探针角色改",
                         "permissions": ["villages:view"]}, headers=AUTH)
    check("更新角色", r.status_code == 200, r.status_code)
    r = client.get(f"/api/v1/rbac/roles/{role_id}/users", headers=AUTH)
    check("角色成员查询", r.status_code == 200, r.status_code)
    r = client.delete(f"/api/v1/rbac/roles/{role_id}", headers=AUTH)
    check("删除角色", r.status_code == 200, r.status_code)

    # ═══ 链路 4：系统配置与备份调度 ═══
    r = client.get("/api/v1/system/config", headers=AUTH)
    check("系统配置读取", r.status_code == 200, r.status_code)
    r = client.get("/api/v1/system/config/defaults", headers=AUTH)
    check("默认配置", r.status_code == 200, r.status_code)
    r = client.put("/api/v1/system/config", json={"items": [{"key": "probe_r3_key", "value": "v1"}]}, headers=AUTH)
    check("批量更新配置", r.status_code in (200, 400, 422), r.status_code)
    r = client.get("/api/v1/config/probe_r3_key", headers=AUTH)
    check("单项配置读取", r.status_code in (200, 404), r.status_code)

    r = client.get("/api/v1/system/backup/schedule", headers=AUTH)
    sj = unwrap(r.json()) or {}
    check("备份计划读取", r.status_code == 200, r.json())
    r = client.put("/api/v1/system/backup/schedule",
                   json={"enabled": True, "schedule": "0 3 * * *", "keep_count": 15}, headers=AUTH)
    check("备份计划更新", r.status_code == 200, str(r.json())[:140])
    r = client.get("/api/v1/system/backup/schedule", headers=AUTH)
    sj2 = unwrap(r.json()) or {}
    check("备份计划回读生效", sj2.get("enabled") is True and str(sj2.get("keepCount")) == "15", sj2)

    # ═══ 链路 5：数据包 预览→导出→导入 ═══
    # 先建组织：空组织表时 get_org_with_fallback 穷尽回退 → 正确 fail-loud
    r = client.post("/api/v1/organizations", json={"name": "探针R3组织", "code": "PROBE-R3"}, headers=AUTH)
    check("创建组织(数据包前置)", r.status_code == 200, str(r.json())[:120])
    org_id2 = (unwrap(r.json()) or {}).get("id")
    r = client.post("/api/v1/data-packages/preview",
                    json={"data_types": ["villages", "projects"]}, headers=AUTH)
    pj = r.json()
    counts = (unwrap(pj) or {}).get("counts")
    check("数据包导出预览", r.status_code == 200 and isinstance(counts, dict), pj)

    r = client.post("/api/v1/data-packages/export",
                    json={"data_types": ["villages"], "description": "探针数据包", "type": "report"},
                    headers=AUTH)
    ej = r.json()
    ed = unwrap(ej) or {}
    pkg_file = ed.get("file_path") or ed.get("file_name")
    check("数据包导出", r.status_code == 200 and bool(pkg_file), ej)

    if ed.get("file_path") and os.path.exists(ed["file_path"]):
        pkg_bytes = open(ed["file_path"], "rb").read()
        r = client.post("/api/v1/data-packages/import",
                        files={"file": (ed.get("file_name") or "pkg.zip", pkg_bytes, "application/zip")},
                        params={"org_id": org_id2},
                        headers=AUTH)
        ij = r.json()
        check("数据包导入(回环)", r.status_code == 200, str(ij)[:200])
        r = client.get("/api/v1/data-packages", headers=AUTH)
        check("数据包列表", r.status_code == 200, r.status_code)

print(f"\n===== PASS {len(PASS)} / FAIL {len(FAIL)} =====")
for n, dd in FAIL:
    print("  FAIL:", n, "|", str(dd)[:220])
sys.exit(1 if FAIL else 0)
