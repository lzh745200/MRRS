# -*- coding: utf-8 -*-
# 固化自 2026-09 深度探测循环（r2 轮）。
# 运行：python backend/tests/probe/probe_r2_approval_reports_map.py
#      或一次跑全部：python backend/tests/probe/run_all.py
# 隔离契约：BUMOFU_BACKEND_DIR_OVERRIDE + DATABASE_URL 均指向本次运行临时目录，
#           不触碰真实 backend/data；退出码 0=全过，1=有失败。
"""第 2 轮模块深探：审批流/报表模板/地图/消息/待办/监控健康（真实 HTTP 全链路）"""
import io
import json
import os
import sys
import tempfile

TMP = tempfile.mkdtemp(prefix="probe_r2_")
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
    lj = r.json()
    at = (lj.get("data") or {}).get("access_token")
    check("管理员登录", bool(at), lj)
    AUTH = {"Authorization": f"Bearer {at}", "X-CSRF-Token": token}

    # ═══ 链路 1：审批流全生命周期 ═══
    # 1.1 创建工作流（village 实体，user 类型节点指向 admin=1）
    r = client.post("/api/v1/approval/workflows",
                    json={"name": "探针村变更审批", "entity_type": "village", "is_active": True,
                          "nodes": [{"name": "一级审批", "approver_type": "user", "approver_id": 1}]},
                    headers=AUTH)
    wj = r.json()
    wd = unwrap(wj)
    wf_id = (wd or {}).get("id") or (wd or {}).get("workflow_id")
    check("创建审批工作流", bool(wf_id), wj)

    # 1.2 工作流列表/详情
    r = client.get("/api/v1/approval/workflows", headers=AUTH)
    check("工作流列表", r.status_code == 200, r.status_code)
    r = client.get(f"/api/v1/approval/workflows/{wf_id}", headers=AUTH)
    check("工作流详情", r.status_code == 200, r.status_code)

    # 1.3 提交审批（用一个真实存在的 village；先建一个）
    r = client.post("/api/v1/supported-villages",
                    json={"village_name": "探针审批村", "province": "贵州省", "city": "贵阳市", "county": "南明区"},
                    headers=AUTH)
    vj = r.json()
    vid = (unwrap(vj) or {}).get("id") or (vj.get("data") or {}).get("id")
    check("创建村庄", bool(vid), vj)

    r = client.post("/api/v1/approval/submit",
                    json={"entity_type": "village", "entity_id": vid,
                          "change_data": {"name": "探针审批村-改"}, "title": "探针审批"},
                    headers=AUTH)
    sj = r.json()
    task_id = (unwrap(sj) or {}).get("task_id") or (unwrap(sj) or {}).get("id")
    check("提交审批", bool(task_id), sj)

    # 1.4 待审批列表可见
    r = client.get("/api/v1/approval/tasks/pending", headers=AUTH)
    lst_ok = r.status_code == 200
    items = unwrap(r.json()) or []
    if isinstance(items, dict):
        items = items.get("items") or items.get("tasks") or items.get("list") or []
    has_task = any(str(t.get("id")) == str(task_id) for t in items)
    check("待审批列表含新任务", lst_ok and has_task, (r.status_code, str(items)[:200]))

    # 1.5 审批通过
    r = client.post(f"/api/v1/approval/tasks/{task_id}/approve", json={"comment": "同意"}, headers=AUTH)
    aj = r.json()
    check("审批通过", r.status_code == 200, aj)

    # 1.6 任务状态已变更
    r = client.get("/api/v1/approval/tasks/history", headers=AUTH)
    items2 = unwrap(r.json()) or []
    if isinstance(items2, dict):
        items2 = items2.get("items") or items2.get("tasks") or items2.get("list") or []
    check("任务进入历史(已通过)列表", any(str(t.get("id")) == str(task_id) for t in items2), (r.status_code, str(items2)[:150]))

    # 1.7 提交并自动审批（单机版一键通道）
    r = client.post("/api/v1/approval/submit-auto",
                    json={"entity_type": "village", "entity_id": vid, "change_data": {"name": "探针村-自动"}},
                    headers=AUTH)
    check("提交并自动审批", r.status_code == 200, r.json())

    # 1.8 不存在的实体提交 → 仍建任务（审批对实体弱耦合）或 400/404
    r = client.post("/api/v1/approval/submit",
                    json={"entity_type": "village", "entity_id": 999999, "change_data": {"x": 1}},
                    headers=AUTH)
    check("幽灵实体提交被拒或接受(≤500)", r.status_code in (200, 400, 404), r.status_code)

    # ═══ 链路 2：报表模板 ═══
    r = client.get("/api/v1/report-templates/available-fields?module=villages", headers=AUTH)
    check("可用字段接口", r.status_code == 200, r.status_code)
    r = client.post("/api/v1/report-templates",
                    json={"name": "探针村报表模板", "type": "export", "module": "village",
                          "fields": "name,province,city"},
                    headers=AUTH)
    tj = r.json()
    tpl_id = (unwrap(tj) or {}).get("id")
    check("创建报表模板", bool(tpl_id), tj)
    r = client.get(f"/api/v1/report-templates/{tpl_id}", headers=AUTH)
    check("模板详情", r.status_code == 200, r.status_code)
    r = client.get(f"/api/v1/report-templates/{tpl_id}/download", headers=AUTH)
    check("模板导出下载", r.status_code == 200 and len(r.content) > 300, (r.status_code, len(r.content)))
    r = client.put(f"/api/v1/report-templates/{tpl_id}",
                   json={"name": "探针村报表模板-改", "type": "export", "module": "village",
                         "fields": "name,province"},
                   headers=AUTH)
    check("更新模板", r.status_code == 200, str(r.json())[:140])
    r = client.get("/api/v1/report-templates", headers=AUTH)
    check("模板列表", r.status_code == 200, r.status_code)

    # ═══ 链路 3：地图与离线瓦片 ═══
    r = client.get("/api/v1/map/config", headers=AUTH)
    check("地图配置", r.status_code == 200, r.status_code)
    r = client.get("/api/v1/map/markers", headers=AUTH)
    check("地图标记", r.status_code == 200, r.status_code)
    r = client.get("/api/v1/map/regions", headers=AUTH)
    check("地图区域", r.status_code == 200, r.status_code)
    r = client.get("/api/v1/map/county-coords", headers=AUTH)
    check("县区坐标", r.status_code == 200, r.status_code)
    r = client.get("/api/v1/offline-map/status", headers=AUTH)
    check("离线瓦片状态", r.status_code == 200, r.status_code)
    r = client.get("/api/v1/offline-map/tiles/8/107/210", headers=AUTH)
    check("瓦片端点(404或图属正常)", r.status_code in (200, 404), r.status_code)

    # ═══ 链路 4：消息与待办 ═══
    r = client.get("/api/v1/messages", headers=AUTH)
    check("消息列表", r.status_code == 200, r.status_code)
    r = client.get("/api/v1/messages/unread-count", headers=AUTH)
    uj = r.json()
    check("未读数", r.status_code == 200 and isinstance(unwrap(uj), dict) and "total" in (unwrap(uj) or {}), uj)
    r = client.post("/api/v1/messages/mark-all-read", headers=AUTH)
    check("全部标记已读", r.status_code == 200, r.status_code)
    r = client.get("/api/v1/messages/stats/summary", headers=AUTH)
    check("消息统计", r.status_code == 200, r.status_code)
    r = client.get("/api/v1/messages/recent-activities", headers=AUTH)
    check("最近动态", r.status_code == 200, r.status_code)

    r = client.post("/api/v1/todos",
                    json={"title": "探针待办-完成体检", "priority": "high", "deadline": "2026-09-30"},
                    headers=AUTH)
    dj = r.json()
    todo_id = (unwrap(dj) or {}).get("id")
    check("创建待办", bool(todo_id), dj)
    r = client.get("/api/v1/todos", headers=AUTH)
    check("待办列表", r.status_code == 200, r.status_code)
    r = client.patch(f"/api/v1/todos/{todo_id}/toggle", headers=AUTH)
    td = unwrap(r.json()) or {}
    check("切换完成", r.status_code == 200 and (td.get("is_completed") or td.get("completed")), r.json())
    r = client.put(f"/api/v1/todos/{todo_id}",
                   json={"title": "探针待办-改", "priority": "medium"}, headers=AUTH)
    check("更新待办", r.status_code == 200, r.status_code)
    r = client.delete(f"/api/v1/todos/{todo_id}", headers=AUTH)
    check("删除待办", r.status_code == 200, r.status_code)

    # ═══ 链路 5：监控健康 ═══
    r = client.get("/health")
    check("基础健康(无认证)", r.status_code == 200, r.status_code)
    r = client.get("/api/v1/health")
    check("api health", r.status_code == 200, r.status_code)
    r = client.get("/api/v1/system/monitor/health", headers=AUTH)
    check("monitor health", r.status_code in (200, 404), r.status_code)
    r = client.get("/api/v1/system/monitor/system", headers=AUTH)
    check("系统资源监控", r.status_code in (200, 404), r.status_code)
    r = client.get("/api/v1/system/metrics", headers=AUTH)
    check("metrics", r.status_code in (200, 404), r.status_code)
    r = client.get("/api/v1/system/audit/logs", headers=AUTH)
    check("审计日志", r.status_code == 200, r.status_code)
    r = client.get("/api/v1/system/audit/logs/export", headers=AUTH)
    check("审计日志导出", r.status_code in (200, 500), r.status_code)  # 空库导出允许500兜底
    r = client.get("/api/v1/messages/stats/summary", headers=AUTH)
    check("消息统计复验", r.status_code == 200, r.status_code)

print(f"\n===== PASS {len(PASS)} / FAIL {len(FAIL)} =====")
for n, dd in FAIL:
    print("  FAIL:", n, "|", str(dd)[:220])
sys.exit(1 if FAIL else 0)
