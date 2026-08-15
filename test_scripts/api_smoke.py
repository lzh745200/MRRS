# -*- coding: utf-8 -*-
"""帮扶系统 v1.8.1 单机版 API 冒烟+契约+安全测试"""
import json
import sys
import time
import traceback

import httpx

BASE = "http://127.0.0.1:8000/api/v1"
TS = int(time.time())
results = []


def record(name, passed, detail=""):
    results.append({"test": name, "passed": bool(passed), "detail": str(detail)[:500]})
    print(("PASS" if passed else "FAIL"), "|", name, "|", str(detail)[:200])


def envelope_ok(resp):
    try:
        j = resp.json()
        return isinstance(j, dict) and "code" in j and "success" in j
    except Exception:
        return False


client = httpx.Client(base_url=BASE, timeout=60)
tok = None
H = {}


def auth():
    global tok, H
    if tok:
        H = {"Authorization": "Bearer " + tok}
    return H


def try_login(username, password):
    r = client.post("/auth/login", json={"username": username, "password": password})
    return r


# ---------- 0. 健康与版本 ----------
try:
    r = client.get("/health")
    record("01 健康检查返回信封", envelope_ok(r), r.text[:120])
except Exception as e:
    record("01 健康检查返回信封", False, e)

try:
    r = client.get("/system/system/version")
    j = r.json()
    record("02 版本号接口", envelope_ok(r) and r.status_code == 200, str(j)[:200])
except Exception as e:
    record("02 版本号接口", False, e)

# ---------- 1. 登录 ----------
r = try_login("admin", "Admin@12345")
if r.status_code == 200 and envelope_ok(r):
    j = r.json()
    tok = j.get("data", {}).get("access_token") or j.get("data", {}).get("token")
    record("03 admin登录成功+信封", bool(tok), "role=" + str(j.get("data", {}).get("user", {}).get("role")))
    auth()
else:
    record("03 admin登录成功+信封", False, f"status={r.status_code} body={r.text[:200]}")
    # 尝试CSRF令牌后重试
    try:
        csrf = client.get("/auth/csrf-token")
        cj = csrf.json()
        csrf_tok = cj.get("data", {}).get("csrf_token") or cj.get("data", {}).get("token")
        if csrf_tok:
            client.headers["X-CSRF-Token"] = csrf_tok
        r2 = try_login("admin", "Admin@12345")
        if r2.status_code == 200:
            j = r2.json()
            tok = j.get("data", {}).get("access_token")
            auth()
            record("03 admin登录(带CSRF)", bool(tok), r2.text[:150])
    except Exception as e:
        record("03 admin登录(带CSRF)", False, e)

try:
    r = client.get("/auth/me", headers=H)
    j = r.json()
    role = j.get("data", {}).get("role") or j.get("data", {}).get("user", {}).get("role")
    record("04 /auth/me 当前用户", envelope_ok(r) and r.status_code == 200, "role=" + str(role))
except Exception as e:
    record("04 /auth/me 当前用户", False, e)

# ---------- 2. 帮扶村 ----------
vid = None
try:
    r = client.get("/supported-villages", params={"page": 1, "page_size": 5}, headers=H)
    j = r.json()
    items = j.get("data", {}).get("items", [])
    keys = list(items[0].keys()) if items else []
    snake = any("_name" in k or k == "village_name" for k in keys) or "name" in keys
    record("05 帮扶村列表信封+items", envelope_ok(r) and isinstance(items, list),
           f"total={j.get('data', {}).get('total')} first_keys={keys[:8]}")
except Exception as e:
    record("05 帮扶村列表信封+items", False, e)

try:
    vname = f"冒烟测试村<scr>&🎉{TS}"
    payload = {"name": vname, "code": f"SMOKE{TS}", "province": "贵州省", "city": "毕节市",
               "county": "织金县", "town": "珠藏镇", "population": 1234, "support_unit": "某部队"}
    r = client.post("/supported-villages", json=payload, headers=H)
    j = r.json()
    vid = j.get("data", {}).get("id")
    record("06 创建帮扶村(特殊字符)", envelope_ok(r) and r.status_code == 200 and vid, f"id={vid} resp={r.text[:150]}")
except Exception as e:
    record("06 创建帮扶村(特殊字符)", False, e)

if vid:
    try:
        r = client.get("/supported-villages", params={"name": vname, "page": 1, "page_size": 10}, headers=H)
        items = r.json().get("data", {}).get("items", [])
        found = [i for i in items if i.get("name") == vname]
        record("07 特殊字符村名回读一致", envelope_ok(r) and len(found) == 1, f"found={len(found)}")
    except Exception as e:
        record("07 特殊字符村名回读一致", False, e)

try:
    r = client.get("/supported-villages", params={"name": "' OR '1'='1", "code": "' OR '1'='1", "page": 1, "page_size": 10}, headers=H)
    j = r.json()
    n = len(j.get("data", {}).get("items", []))
    record("08 SQL注入参数化查询", r.status_code == 200 and n == 0, f"status={r.status_code} matched={n}")
except Exception as e:
    record("08 SQL注入参数化查询", False, e)

if vid:
    try:
        r = client.post(f"/supported-villages/{vid}/yearly/2026/income",
                        json={"household_income": 12345.6, "notes": "年度数据冒烟"}, headers=H)
        record("09 年度数据录入income", envelope_ok(r) and r.status_code == 200, r.text[:150])
    except Exception as e:
        record("09 年度数据录入income", False, e)
    try:
        r = client.get(f"/supported-villages/{vid}/yearly/2026", headers=H)
        j = r.json()
        income = j.get("data", {}).get("income")
        record("10 年度数据回读", envelope_ok(r) and income is not None, f"income_keys={list(income.keys())[:6] if isinstance(income, dict) else income}")
    except Exception as e:
        record("10 年度数据回读", False, e)
    try:
        r = client.get(f"/supported-villages/{vid}/change-history", headers=H)
        j = r.json()
        items = j.get("data", {}).get("items", []) if isinstance(j.get("data"), dict) else j.get("data", [])
        record("11 变更历史", envelope_ok(r) and isinstance(items, list) and len(items) > 0, f"entries={len(items)}")
    except Exception as e:
        record("11 变更历史", False, e)

# ---------- 3. 经费 ----------
fid = None
try:
    r = client.post("/funds", json={"name": f"生命周期测试经费{TS}", "planned_amount": 100000, "fund_type": "infrastructure"}, headers=H)
    j = r.json()
    fid = j.get("data", {}).get("id")
    record("12 创建经费", envelope_ok(r) and r.status_code == 200 and fid, f"id={fid} resp={r.text[:150]}")
except Exception as e:
    record("12 创建经费", False, e)

if fid:
    try:
        r = client.get(f"/funds/{fid}", headers=H)
        j = r.json()
        d = j.get("data", {})
        stage = d.get("current_stage") or d.get("currentStage") or d.get("status")
        record("13 经费详情+当前阶段字段", envelope_ok(r) and r.status_code == 200, f"stage={stage} keys={list(d.keys())[:12]}")
    except Exception as e:
        record("13 经费详情+当前阶段字段", False, e)
    for sub, name in [("/approval-flow", "14a 审批流程"), ("/history/status", "14b 状态日志"),
                      ("/history/operations", "14c 操作日志"), ("/history/fields", "14d 修改记录")]:
        try:
            r = client.get(f"/funds/{fid}{sub}", headers=H)
            record("经费四日志: " + name, r.status_code == 200 and envelope_ok(r), f"status={r.status_code}")
        except Exception as e:
            record("经费四日志: " + name, False, e)

# 审批提交+驳回
fid2 = None
try:
    r = client.post("/funds/apply", json={"name": f"审批测试经费{TS}", "planned_amount": 50000, "usage_description": "审批流冒烟"}, headers=H)
    j = r.json()
    fid2 = j.get("data", {}).get("id")
    record("15 经费申请", envelope_ok(r) and fid2, f"id={fid2} status={j.get('data', {}).get('status')}")
except Exception as e:
    record("15 经费申请", False, e)

task_id = None
if fid2:
    try:
        r = client.post("/approval/submit", json={"entity_type": "fund", "entity_id": fid2, "title": f"经费审批{fid2}"}, headers=H)
        j = r.json()
        task_id = j.get("data", {}).get("id") or j.get("data", {}).get("task_id")
        record("16 提交审批", envelope_ok(r) and task_id, f"task_id={task_id} resp={r.text[:150]}")
    except Exception as e:
        record("16 提交审批", False, e)
    if task_id:
        try:
            r = client.get("/approval/tasks/pending", headers=H)
            j = r.json()
            items = j.get("data", {}).get("items", []) if isinstance(j.get("data"), dict) else j.get("data", [])
            has = any(str(i.get("id")) == str(task_id) for i in items)
            record("17 待审批列表包含任务", envelope_ok(r) and has, f"pending={len(items)}")
        except Exception as e:
            record("17 待审批列表包含任务", False, e)
        try:
            r = client.post(f"/approval/tasks/{task_id}/reject", json={"reason": ""}, headers=H)
            record("18 驳回空原因被拦截", r.status_code in (400, 422), f"status={r.status_code} body={r.text[:150]}")
        except Exception as e:
            record("18 驳回空原因被拦截", False, e)
        try:
            r = client.post(f"/approval/tasks/{task_id}/reject", json={"reason": "预算不合理，请修改"}, headers=H)
            record("19 驳回(带原因)", envelope_ok(r) and r.status_code == 200, r.text[:150])
        except Exception as e:
            record("19 驳回(带原因)", False, e)
        try:
            r = client.get("/messages", params={"page": 1, "page_size": 20}, headers=H)
            j = r.json()
            items = j.get("data", {}).get("items", []) if isinstance(j.get("data"), dict) else j.get("data", [])
            txt = json.dumps(items, ensure_ascii=False)
            record("20 驳回通知消息", envelope_ok(r) and "驳回" in txt or "预算" in txt, f"msgs={len(items)}")
        except Exception as e:
            record("20 驳回通知消息", False, e)

# ---------- 4. 预算预警幂等 ----------
fid3 = None
try:
    r = client.post("/funds", json={"name": f"预算预警测试{TS}", "planned_amount": 10000}, headers=H)
    fid3 = r.json().get("data", {}).get("id")
    r2 = client.put(f"/funds/{fid3}", json={"approved_amount": 10000, "used_amount": 9200}, headers=H)
    record("21 预算92%数据准备", r2.status_code == 200, r2.text[:150])
except Exception as e:
    record("21 预算92%数据准备", False, e)

if fid3:
    def count_bw():
        try:
            r = client.get("/reminders", params={"page": 1, "page_size": 100}, headers=H)
            items = r.json().get("data", {}).get("items", [])
            return sum(1 for i in items if i.get("type") == "budget_warning" and i.get("entity_id") == fid3)
        except Exception:
            return -1
    try:
        r1 = client.post("/reminders/scan", headers=H)
        c1 = count_bw()
        time.sleep(1)
        r2 = client.post("/reminders/scan", headers=H)
        c2 = count_bw()
        record("22 预算预警扫描幂等", r1.status_code == 200 and c1 >= 1 and c2 == c1, f"scan1={c1} scan2={c2}")
    except Exception as e:
        record("22 预算预警扫描幂等", False, e)

# ---------- 5. 项目 ----------
pid = None
try:
    r = client.post("/projects", json={"name": f"测试项目{TS}", "start_date": "2026-01-01", "status": "pending",
                                       "budget": 500, "category": "产业", "location": "贵州省毕节市织金县",
                                       "priority": "medium", "progress": 30}, headers=H)
    j = r.json()
    pid = j.get("data", {}).get("id")
    prog = j.get("data", {}).get("progress")
    record("23 创建项目(进度字段)", envelope_ok(r) and pid, f"id={pid} progress={prog} resp={r.text[:150]}")
except Exception as e:
    record("23 创建项目(进度字段)", False, e)

if pid:
    try:
        r = client.get(f"/projects/{pid}", headers=H)
        j = r.json()
        prog = j.get("data", {}).get("progress")
        record("24 项目详情无迭代错误+进度保留", r.status_code == 200 and prog is not None, f"progress={prog}")
    except Exception as e:
        record("24 项目详情无迭代错误+进度保留", False, e)
    try:
        r = client.post(f"/projects/{pid}/milestones", json={"name": "里程碑一", "planned_date": "2026-06-30", "sort_order": 1}, headers=H)
        mid = r.json().get("data", {}).get("id")
        r2 = client.put(f"/projects/{pid}/milestones/{mid}", json={"status": "completed", "actual_date": "2026-05-01"}, headers=H)
        r3 = client.get(f"/projects/{pid}/milestones", headers=H)
        items = r3.json().get("data", {}).get("items", []) if isinstance(r3.json().get("data"), dict) else r3.json().get("data", [])
        st = items[0].get("status") if items else None
        record("25 里程碑完成", r.status_code == 200 and r2.status_code == 200 and st == "completed", f"milestone_status={st}")
    except Exception as e:
        record("25 里程碑完成", False, e)

# ---------- 6. 学校 ----------
try:
    r = client.post("/schools", json={"name": f"测试小学{TS}", "code": f"S{TS}", "school_type": "primary",
                                      "school_level": "township", "province": "贵州省", "city": "毕节市",
                                      "district": "织金县"}, headers=H)
    j = r.json()
    sid = j.get("data", {}).get("id")
    d = j.get("data", {}).get("district")
    record("26 创建学校(贵州区划)", envelope_ok(r) and sid and d == "织金县", f"id={sid} district={d} resp={r.text[:150]}")
except Exception as e:
    record("26 创建学校(贵州区划)", False, e)

# ---------- 7. 政策 ----------
try:
    r = client.post("/policies", json={"title": f"测试政策{TS}", "content": "产业帮扶政策内容", "category": "产业", "status": "active"}, headers=H)
    j = r.json()
    polid = j.get("data", {}).get("id")
    record("27 创建政策", envelope_ok(r) and polid, f"id={polid}")
except Exception as e:
    record("27 创建政策", False, e)
try:
    r = client.get("/policies", params={"page": 1, "page_size": 5}, headers=H)
    record("28 政策列表信封", envelope_ok(r), r.text[:120])
except Exception as e:
    record("28 政策列表信封", False, e)
try:
    r = client.request("POST", "/policies/1/submit-approval", json={}, headers=H)
    record("29 政策无submit-approval端点", r.status_code in (404, 405), f"status={r.status_code}")
except Exception as e:
    record("29 政策无submit-approval端点", False, e)

# ---------- 8. 文件上传/413 ----------
try:
    png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
    r = client.post("/files/upload", files={"file": ("t.png", png, "image/png")}, headers=H)
    record("30 文件上传信封", envelope_ok(r), f"status={r.status_code} body={r.text[:150]}")
except Exception as e:
    record("30 文件上传信封", False, e)

try:
    big = b"x" * (11 * 1024 * 1024)
    r = client.post("/files/upload", files={"file": ("big.bin", big, "application/octet-stream")}, headers=H)
    record("31 超10MB文件被413拦截", r.status_code == 413, f"status={r.status_code} body={r.text[:150]}")
except Exception as e:
    record("31 超10MB文件被413拦截", False, e)

# ---------- 9. 错误处理 ----------
try:
    r = client.get("/supported-villages/99999999", headers=H)
    rid = r.headers.get("x-request-id") or r.headers.get("X-Request-ID")
    record("32 404+request_id", r.status_code == 404 and bool(rid), f"status={r.status_code} rid={rid}")
except Exception as e:
    record("32 404+request_id", False, e)
try:
    r = client.get("/funds")
    record("33 未授权访问401/403", r.status_code in (401, 403), f"status={r.status_code}")
except Exception as e:
    record("33 未授权访问401/403", False, e)

# ---------- 10. 数据库完整性 ----------
try:
    r = client.post("/system-health/integrity-check", headers=H)
    j = r.json()
    ok = j.get("data", {}).get("ok") or j.get("data", {}).get("integrity_ok")
    record("34 SQLite integrity_check", r.status_code == 200, str(j)[:250])
except Exception as e:
    record("34 SQLite integrity_check", False, e)
try:
    r = client.post("/system-health/wal-checkpoint", headers=H)
    record("35 WAL检查点", r.status_code == 200, r.text[:150])
except Exception as e:
    record("35 WAL检查点", False, e)

# ---------- 11. 审计日志 ----------
try:
    r = client.get("/system/audit/logs", params={"page": 1, "page_size": 5}, headers=H)
    j = r.json()
    n = j.get("data", {}).get("total", 0)
    record("36 审计日志有记录", envelope_ok(r) and n > 0, f"total={n}")
except Exception as e:
    record("36 审计日志有记录", False, e)

# ---------- 12. 角色权限（user 可全操作经费 / viewer 只读） ----------
def mk_user(role, uname):
    r = client.post("/users", json={"username": uname, "password": "Smoke@123456", "full_name": uname,
                                    "role": role}, headers=H)
    if r.status_code not in (200, 201):
        print("   create user raw:", r.status_code, r.text[:300])
    return r

def login_as(uname):
    r = client.post("/auth/login", json={"username": uname, "password": "Smoke@123456"})
    t = None
    if r.status_code == 200:
        t = r.json().get("data", {}).get("access_token")
    return t

try:
    u = f"smokeuser{TS}"
    r = mk_user("user", u)
    j = r.json()
    uid = j.get("data", {}).get("id")
    record("37 创建user角色账号", r.status_code in (200, 201) and uid, r.text[:150])
    t = login_as(u)
    if t:
        r2 = client.post("/funds", json={"name": f"user角色经费{TS}", "planned_amount": 1000}, headers={"Authorization": "Bearer " + t})
        record("38 user角色经费全操作放行", r2.status_code == 200 and envelope_ok(r2), f"status={r2.status_code} body={r2.text[:120]}")
    else:
        record("38 user角色经费全操作放行", False, "login failed")
except Exception as e:
    record("37/38 user角色", False, e)

try:
    v = f"smokeviewer{TS}"
    r = mk_user("viewer", v)
    t = login_as(v)
    if t:
        r2 = client.post("/funds", json={"name": f"viewer越权{TS}"}, headers={"Authorization": "Bearer " + t})
        record("39 viewer角色写操作被拒", r2.status_code in (401, 403), f"status={r2.status_code}")
    else:
        record("39 viewer角色写操作被拒", False, "login failed")
except Exception as e:
    record("39 viewer角色写操作被拒", False, e)

# ---------- 13. 备份 ----------
try:
    r = client.post("/system/backup", json={"name": f"smoke-backup-{TS}"}, headers=H)
    record("40 手动备份", r.status_code == 200 and envelope_ok(r), r.text[:200])
except Exception as e:
    record("40 手动备份", False, e)
try:
    r = client.get("/system/backup", headers=H)
    j = r.json()
    items = j.get("data", {}).get("items", []) if isinstance(j.get("data"), dict) else j.get("data", [])
    record("41 备份列表信封", envelope_ok(r), f"backups={len(items)}")
except Exception as e:
    record("41 备份列表信封", False, e)

# ---------- 14. 登录限流（最后执行） ----------
try:
    statuses = []
    for i in range(6):
        rr = client.post("/auth/login", json={"username": "admin", "password": "wrong-pass-xxx"})
        statuses.append(rr.status_code)
    record("42 登录限流429", 429 in statuses, f"statuses={statuses}")
except Exception as e:
    record("42 登录限流429", False, e)

summary = {"total": len(results), "passed": sum(1 for x in results if x["passed"]),
           "failed": sum(1 for x in results if not x["passed"]), "results": results}
print("===SUMMARY===")
print(json.dumps(summary, ensure_ascii=False))
