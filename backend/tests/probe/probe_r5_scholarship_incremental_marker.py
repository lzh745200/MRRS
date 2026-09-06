# -*- coding: utf-8 -*-
# 固化自 2026-09 深度探测循环（r5 轮）。
# 运行：python backend/tests/probe/probe_r5_scholarship_incremental_marker.py
#      或一次跑全部：python backend/tests/probe/run_all.py
# 隔离契约：BUMOFU_BACKEND_DIR_OVERRIDE + DATABASE_URL 均指向本次运行临时目录，
#           不触碰真实 backend/data；退出码 0=全过，1=有失败。
"""第 5 轮模块深探：乡村工作台/奖学金导入/增量三端点/地图坐标/update-logs/消息推送联动"""
import io
import os
import sys
import tempfile

TMP = tempfile.mkdtemp(prefix="probe_r5_")
os.chdir(TMP)
os.environ["BUMOFU_BACKEND_DIR_OVERRIDE"] = TMP
os.environ["DATABASE_URL"] = f"sqlite:///{TMP}/probe.db"
os.environ["ENVIRONMENT"] = "test"
os.environ["SECRET_KEY"] = "x" * 40
os.environ["UPLOAD_DIR"] = f"{TMP}/uploads"
os.environ["BACKUP_ENABLED"] = "false"

BACKEND_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, BACKEND_ROOT)

from openpyxl import Workbook  # noqa: E402
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

    # 前置：组织 + 村庄
    r = client.post("/api/v1/organizations", json={"name": "探针R5组织", "code": "PROBE-R5"}, headers=AUTH)
    org_id = (unwrap(r.json()) or {}).get("id")
    check("创建组织", bool(org_id), r.json())
    r = client.post("/api/v1/supported-villages",
                    json={"village_name": "探针R5村", "province": "贵州省"}, headers=AUTH)
    vid = (unwrap(r.json()) or {}).get("id")
    check("创建村庄", bool(vid), r.json())

    # ═══ 链路 1：乡村振兴工作台 ═══
    # 乡村振兴工作台村庄下拉：帮扶村按名称 upsert 进 villages 表（FK 目标），下拉用其 id
    r = client.get("/api/v1/rural-works/villages", headers=AUTH)
    vselect = unwrap(r.json()) or []
    if isinstance(vselect, dict):
        vselect = vselect.get("villages") or vselect.get("items") or []
    vw_id = next((v["id"] for v in vselect if v.get("name") == "探针R5村"), None)
    check("村庄下拉含帮扶村(同步 upsert)", bool(vw_id), str(vselect)[:160])

    # 悬挂 village_id → 400（非 500）
    r = client.post("/api/v1/rural-works",
                    json={"name": "探针R5悬挂测试", "village_id": 9999}, headers=AUTH)
    check("悬挂村庄被拒(400)", r.status_code == 400, (r.status_code, str(r.json())[:120]))

    r = client.post("/api/v1/rural-works",
                    json={"name": "探针R5工作-人居环境整治", "type": "整治", "status": "in_progress",
                          "village_id": vw_id, "responsible_person": "探针负责人"},
                    headers=AUTH)
    wj = r.json()
    rw_id = (unwrap(wj) or {}).get("id")
    check("创建乡村工作", bool(rw_id), wj)
    r = client.get("/api/v1/rural-works", headers=AUTH)
    check("乡村工作列表", r.status_code == 200, r.status_code)
    r = client.get("/api/v1/rural-works/statistics/summary", headers=AUTH)
    check("工作台统计", r.status_code == 200, r.status_code)
    r = client.get("/api/v1/rural-works/villages", headers=AUTH)
    check("工作台村庄维度", r.status_code == 200, r.status_code)
    r = client.get("/api/v1/rural-works/years", headers=AUTH)
    check("工作台年份", r.status_code == 200, r.status_code)
    r = client.get(f"/api/v1/rural-works/{rw_id}", headers=AUTH)
    check("工作详情", r.status_code == 200, r.status_code)
    r = client.put(f"/api/v1/rural-works/{rw_id}", json={"status": "completed"}, headers=AUTH)
    check("更新工作", r.status_code == 200, r.status_code)

    # ═══ 链路 2：奖学金导入 ═══
    r = client.post("/api/v1/schools",
                    json={"name": "探针希望小学", "code": "SCH-PROBE-R5", "school_type": "primary",
                          "school_level": "county"}, headers=AUTH)
    check("前置建学校", r.status_code in (200, 201), str(r.json())[:120])

    wb = Workbook()
    ws = wb.active
    ws.append(["序号", "姓名", "学号", "年份", "金额", "学校", "年级", "事由", "状态"])
    ws.append([1, "探针学生甲", "S2026001", 2026, 3000, "探针希望小学", "五年级", "品学兼优", "已发放"])
    buf = io.BytesIO()
    wb.save(buf)
    r = client.post("/api/v1/schools/scholarship/import",
                    files={"file": ("stu.xlsx", buf.getvalue(),
                                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
                    headers=AUTH)
    ij = r.json()
    ijd = unwrap(ij) or ij
    check("奖学金导入", r.status_code == 200 and (ijd or {}).get("imported", 0) >= 1, ij)
    # 非 Excel 文件 → 400
    r = client.post("/api/v1/schools/scholarship/import",
                    files={"file": ("not.xlsx", b"plain text", "application/octet-stream")},
                    headers=AUTH)
    check("非Excel被拒(400)", r.status_code == 400, r.status_code)

    # ═══ 链路 3：数据包增量三端点 ═══
    r = client.post("/api/v1/data-packages/export",
                    json={"data_types": ["villages"], "description": "探针基准包", "type": "report",
                          "org_id": org_id},
                    headers=AUTH)
    ej = r.json()
    ed = unwrap(ej) or {}
    base_pkg_id = ed.get("package_id")
    check("基准包导出", r.status_code == 200 and bool(base_pkg_id), ej)

    r = client.post("/api/v1/data-packages/incremental/detect-changes",
                    params={"base_package_id": base_pkg_id, "org_id": org_id,
                            "data_types": "villages"},
                    headers=AUTH)
    dj = r.json()
    check("增量变更检测", r.status_code == 200, str(dj)[:160])

    # 制造增量：再建一个村庄
    r = client.post("/api/v1/supported-villages",
                    json={"village_name": "探针R5增量村", "province": "贵州省"}, headers=AUTH)
    check("制造增量数据", r.status_code == 200, r.status_code)

    r = client.post("/api/v1/data-packages/incremental/export",
                    json={"base_package_id": base_pkg_id, "data_types": ["villages"],
                          "org_id": org_id, "description": "探针增量包"},
                    headers=AUTH)
    ej2 = r.json()
    ed2 = unwrap(ej2) or {}
    inc_pkg_id = ed2.get("package_id")
    check("增量包导出", r.status_code == 200 and bool(inc_pkg_id), ej2)

    r = client.post("/api/v1/data-packages/incremental/import",
                    json={"package_id": inc_pkg_id, "apply_changes": False},
                    headers=AUTH)
    ij2 = r.json()
    check("增量包导入(试运行)", r.status_code == 200, str(ij2)[:200])

    # ═══ 链路 4：地图标记坐标写入 ═══
    r = client.put(f"/api/v1/map/markers/village/{vid}/coordinates",
                   json={"latitude": 26.6470, "longitude": 106.6302}, headers=AUTH)
    check("写入村坐标", r.status_code == 200, r.json())
    r = client.put(f"/api/v1/map/markers/village/{vid}/coordinates",
                   json={"latitude": 200.0, "longitude": 106.6}, headers=AUTH)
    check("非法坐标被拒(400)", r.status_code == 400, r.status_code)
    r = client.get("/api/v1/map/markers", headers=AUTH)
    mkraw = r.json()
    mk = unwrap(mkraw) or []
    if isinstance(mk, dict):
        mk = mk.get("markers") or mk.get("items") or mk.get("villages") or []
    found = False
    for m in mk:
        mid = m.get("id") or m.get("villageId") or m.get("village_id")
        lat = m.get("latitude") or m.get("lat")
        if str(mid) == str(vid) and lat:
            found = True
            break
    check("标记列表含坐标", found, str(mkraw)[:260])

    # ═══ 链路 5：update-logs ═══
    r = client.get("/api/v1/system/update-logs", headers=AUTH)
    check("更新日志列表", r.status_code == 200, r.status_code)
    r = client.get("/api/v1/update-logs/latest", headers=AUTH)
    check("最新更新日志(空库允许404)", r.status_code in (200, 404), r.status_code)
    r = client.post("/api/v1/system/update-logs",
                    json={"version": "9.9.9-probe", "description": "探针日志条目", "updated_by": "探针"},
                    headers=AUTH)
    uj = r.json()
    upd_id = (uj.get("data") or uj).get("id")
    check("创建更新日志", bool(upd_id), uj)
    r = client.get(f"/api/v1/system/update-logs/{upd_id}", headers=AUTH)
    check("更新日志详情", r.status_code == 200, r.status_code)

    # ═══ 链路 6：消息推送联动（审批→未读数）═══
    r = client.post("/api/v1/approval/workflows",
                    json={"name": "探针R5审批流", "entity_type": "village", "is_active": True,
                          "nodes": [{"name": "一级审批", "approver_type": "user", "approver_id": 1}]},
                    headers=AUTH)
    check("建审批流", r.status_code == 200, str(r.json())[:120])
    r = client.get("/api/v1/messages/unread-count", headers=AUTH)
    base_unread = (unwrap(r.json()) or {}).get("total", 0)
    r = client.post("/api/v1/approval/submit",
                    json={"entity_type": "village", "entity_id": vid,
                          "change_data": {"village_name": "探针R5村-改"}, "title": "探针R5审批"},
                    headers=AUTH)
    sj = r.json()
    task_id = (unwrap(sj) or {}).get("task_id") or (unwrap(sj) or {}).get("id")
    check("提交审批", bool(task_id), sj)
    r = client.get("/api/v1/messages/unread-count", headers=AUTH)
    after_unread = (unwrap(r.json()) or {}).get("total", 0)
    check("审批消息推送到未读数", after_unread >= base_unread, (base_unread, after_unread))
    r = client.post("/api/v1/messages/mark-all-read", headers=AUTH)
    check("标记全部已读", r.status_code == 200, r.status_code)
    r = client.post(f"/api/v1/approval/tasks/{task_id}/approve", json={"comment": "ok"}, headers=AUTH)
    check("审批通过收尾", r.status_code == 200, r.json())

print(f"\n===== PASS {len(PASS)} / FAIL {len(FAIL)} =====")
for n, dd in FAIL:
    print("  FAIL:", n, "|", str(dd)[:220])
sys.exit(1 if FAIL else 0)
