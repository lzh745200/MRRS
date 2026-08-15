# -*- coding: utf-8 -*-
"""第三轮API冒烟：CSRF修正 + 深度业务流"""
import json, time, io
import httpx

BASE = "http://127.0.0.1:8000/api/v1"
TS = int(time.time())
results = []

def record(name, passed, detail=""):
    results.append({"test": name, "passed": bool(passed), "detail": str(detail)[:400]})
    print(("PASS" if passed else "FAIL"), "|", name, "|", str(detail)[:180])

def envelope_ok(resp):
    try:
        j = resp.json()
        return isinstance(j, dict) and "code" in j and "success" in j
    except Exception:
        return False

c = httpx.Client(base_url=BASE, timeout=90)
# CSRF 令牌
r = c.get("/auth/csrf-token")
csrf_j = r.json()
csrf = (csrf_j.get("data") or {}).get("csrf_token") or (csrf_j.get("data") or {}).get("token")
print("csrf:", bool(csrf), str(csrf)[:20])
c.headers["X-CSRF-Token"] = csrf or ""
r = c.post("/auth/login", json={"username": "admin", "password": "Admin@12345"})
tok = r.json().get("data", {}).get("access_token")
c.headers["Authorization"] = "Bearer " + tok
print("login:", r.status_code, "token:", bool(tok))

# 1. 帮扶村创建
vid = None
try:
    vname = f"冒烟村3<scr>&🎉{TS}"
    r = c.post("/supported-villages", json={"village_name": vname, "code": f"SMK3{TS}",
               "province": "贵州省", "city": "毕节市", "county": "织金县", "population": 999}, headers={})
    j = r.json()
    vid = (j.get("data") or {}).get("id")
    record("R3-01 创建帮扶村", r.status_code in (200, 201) and vid, f"id={vid} status={r.status_code} body={r.text[:120]}")
except Exception as e:
    record("R3-01 创建帮扶村", False, e)

# 2. SQL注入 keyword
try:
    r = c.get("/supported-villages", params={"keyword": "' OR '1'='1", "page": 1, "page_size": 10})
    j = r.json()
    n = len((j.get("data") or {}).get("items", []))
    record("R3-02 SQL注入参数化(keyword)", r.status_code == 200 and n == 0, f"matched={n}")
    r = c.get("/supported-villages", params={"keyword": "冒烟村3", "page": 1, "page_size": 10})
    n2 = len((r.json().get("data") or {}).get("items", []))
    record("R3-03 关键词正常检索", r.status_code == 200 and n2 >= 1, f"matched={n2}")
except Exception as e:
    record("R3-02/03 SQL注入", False, e)

# 3. 年度数据+变更历史+编辑
if vid:
    try:
        r = c.post(f"/supported-villages/{vid}/yearly/2026/income", json={"household_income": 8888.8, "notes": "R3年度"}, headers={})
        r2 = c.put(f"/supported-villages/{vid}", json={"population": 1000}, headers={})
        r3 = c.get(f"/supported-villages/{vid}/change-history", headers={})
        hist = (r3.json().get("data") or [])
        record("R3-04 年度数据+编辑+变更历史", r.status_code == 200 and r2.status_code == 200 and len(hist) >= 1,
               f"hist={len(hist)} update_body={r2.text[:100]}")
    except Exception as e:
        record("R3-04 年度数据+变更历史", False, e)

# 4. 软删除 + include_deleted
if vid:
    try:
        r = c.delete(f"/supported-villages/{vid}", headers={})
        r2 = c.get("/supported-villages", params={"page": 1, "page_size": 200})
        items = (r2.json().get("data") or {}).get("items", [])
        gone = all(i.get("id") != vid for i in items)
        r3 = c.get("/supported-villages", params={"page": 1, "page_size": 200, "include_deleted": True})
        items3 = (r3.json().get("data") or {}).get("items", [])
        back = [i for i in items3 if i.get("id") == vid]
        record("R3-05 软删除+include_deleted", r.status_code == 200 and gone and len(back) == 1,
               f"hidden={gone} visible_deleted={len(back)} approval={r.json().get('data', {}).get('approval_task_id')}")
    except Exception as e:
        record("R3-05 软删除", False, e)

# 5. 审批：提交→空原因→带原因驳回→通知；再一笔：提交→通过
fidA = fidB = None
try:
    r = c.post("/funds", json={"name": f"驳回流经费{TS}", "planned_amount": 30000}, headers={})
    fidA = ((r.json().get("data") or {}).get("id"))
    r = c.post("/approval/submit", json={"entity_type": "fund", "entity_id": fidA, "title": f"经费审批{fidA}", "change_data": {}}, headers={})
    taskA = (r.json().get("data") or {}).get("id") or (r.json().get("data") or {}).get("task_id")
    record("R3-06 提交审批", r.status_code in (200, 201) and taskA, f"task={taskA}")
    r = c.post(f"/approval/tasks/{taskA}/reject", json={"reason": ""}, headers={})
    record("R3-07 空驳回原因拦截", r.status_code in (400, 422), f"status={r.status_code} body={r.text[:100]}")
    r = c.post(f"/approval/tasks/{taskA}/reject", json={"reason": "预算超标"}, headers={})
    r2 = c.get(f"/funds/{fidA}", headers={})
    stA = (r2.json().get("data") or {}).get("status")
    r3 = c.get("/messages", params={"page": 1, "page_size": 50})
    txt = json.dumps((r3.json().get("data") or {}).get("items", []), ensure_ascii=False)
    record("R3-08 驳回+状态回退+消息通知", r.status_code == 200 and stA is not None and ("驳回" in txt),
           f"status={stA} notify={'驳回' in txt}")
except Exception as e:
    record("R3-06..08 审批驳回流", False, e)

try:
    r = c.post("/funds", json={"name": f"通过流经费{TS}", "planned_amount": 20000}, headers={})
    fidB = ((r.json().get("data") or {}).get("id"))
    r = c.post("/approval/submit", json={"entity_type": "fund", "entity_id": fidB, "title": f"经费审批{fidB}", "change_data": {}}, headers={})
    taskB = (r.json().get("data") or {}).get("id") or (r.json().get("data") or {}).get("task_id")
    r = c.post(f"/approval/tasks/{taskB}/approve", json={"opinion": "同意拨付"}, headers={})
    r2 = c.get(f"/funds/{fidB}", headers={})
    stB = (r2.json().get("data") or {}).get("status")
    record("R3-09 审批通过+状态更新", r.status_code == 200, f"approve_status={r.status_code} fund_status={stB} body={r.text[:120]}")
except Exception as e:
    record("R3-09 审批通过", False, e)

# 6. 转审
try:
    r = c.get("/users", params={"page": 1, "page_size": 50})
    users = (r.json().get("data") or {}).get("items", [])
    target = next((u for u in users if u.get("username", "").startswith("smokeuser")), None)
    if fidA:
        r = c.post("/approval/submit", json={"entity_type": "fund", "entity_id": fidA, "title": f"转审测试{fidA}", "change_data": {}}, headers={})
        taskC = (r.json().get("data") or {}).get("id")
        if taskC and target:
            r = c.post(f"/approval/tasks/{taskC}/transfer", json={"target_user_id": target.get("id")}, headers={})
            record("R3-10 转审", r.status_code == 200, f"status={r.status_code} body={r.text[:150]}")
        else:
            record("R3-10 转审", False, f"task={taskC} target={bool(target)}")
except Exception as e:
    record("R3-10 转审", False, e)

# 7. 预算预警幂等（amount字段）
try:
    r = c.post("/funds", json={"name": f"预算预警R3-{TS}", "planned_amount": 10000}, headers={})
    fidC = ((r.json().get("data") or {}).get("id"))
    r = c.put(f"/funds/{fidC}", json={"amount": 10000, "approved_amount": 10000, "used_amount": 9200}, headers={})
    time.sleep(0.5)
    c.post("/reminders/scan", headers={})
    time.sleep(0.5)
    def count_bw():
        r = c.get("/reminders", params={"page": 1, "page_size": 300})
        items = (r.json().get("data") or {}).get("items", [])
        return sum(1 for i in items if i.get("type") == "budget_warning" and i.get("entity_id") == fidC)
    c1 = count_bw()
    c.post("/reminders/scan", headers={})
    time.sleep(0.5)
    c2 = count_bw()
    record("R3-11 预算预警92%+幂等", c1 >= 1 and c2 == c1, f"first={c1} second={c2}")
except Exception as e:
    record("R3-11 预算预警幂等", False, e)

# 8. 里程碑
try:
    r = c.post("/projects", json={"name": f"里程碑R3{TS}", "start_date": "2026-02-01", "status": "pending",
                                  "budget": 100, "category": "产业", "location": "贵州", "priority": "low"}, headers={})
    pid = ((r.json().get("data") or {}).get("id"))
    r = c.post(f"/projects/{pid}/milestones", json={"name": "里程碑A", "planned_date": "2026-07-01"}, headers={})
    mid = ((r.json().get("data") or {}).get("id"))
    r2 = c.put(f"/projects/{pid}/milestones/{mid}", json={"status": "completed", "actual_date": "2026-06-01"}, headers={})
    r3 = c.get(f"/projects/{pid}/milestones", headers={})
    data = r3.json().get("data")
    record("R3-12 里程碑创建/完成/列表", r.status_code in (200, 201) and r2.status_code == 200 and isinstance(data, list) and data[0].get("status") == "completed",
           f"list_type={type(data).__name__} status={data[0].get('status') if isinstance(data, list) and data else None}")
except Exception as e:
    record("R3-12 里程碑", False, e)

# 9. 413 大文件 png
try:
    big = b"\x89PNG\r\n\x1a\n" + b"\x00" * (11 * 1024 * 1024)
    r = c.post("/files/upload", files={"file": ("big.png", big, "image/png")}, headers={})
    record("R3-13 11MB文件413", r.status_code == 413, f"status={r.status_code} body={r.text[:120]}")
except Exception as e:
    record("R3-13 413", False, e)

# 10. 转账凭证
try:
    r = c.post("/fund-lifecycle/transfer-vouchers", json={"voucher_no": f"V3{TS}", "direction": "military_to_local",
               "amount": 5000, "transfer_date": "2026-08-15", "project_id": 1}, headers={})
    record("R3-14 转账凭证创建", r.status_code in (200, 201), f"status={r.status_code} body={r.text[:150]}")
except Exception as e:
    record("R3-14 转账凭证", False, e)

# 11. 工作日志
try:
    r = c.post("/work-logs", json={"content": f"R3工作日志{TS}", "log_date": "2026-08-15"}, headers={})
    record("R3-15 工作日志创建", r.status_code in (200, 201), f"status={r.status_code} body={r.text[:120]}")
except Exception as e:
    record("R3-15 工作日志", False, e)

# 12. Excel导入（平铺自制文件：1行合法+1行坏）
try:
    from openpyxl import Workbook
    wb = Workbook()
    ws = wb.active
    ws.append(["村名", "编码", "省", "市", "县"])
    ws.append([f"导入村{TS}", f"IMPOK{TS}", "贵州省", "毕节市", "织金县"])
    ws.append(["x" * 300, f"IMPBAD{TS}", "贵州省", "毕节市", "织金县"])
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    r = c.post("/supported-villages/import", files={"file": (f"imp{TS}.xlsx", buf.getvalue(),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}, headers={})
    record("R3-16 Excel导入(1合法+1坏行)", r.status_code == 200, f"status={r.status_code} body={r.text[:500]}")
except Exception as e:
    record("R3-16 Excel导入", False, e)

# 13. 受助学生导入+汇总+重复
try:
    r = c.get("/schools", params={"page": 1, "page_size": 1})
    sid = ((r.json().get("data") or {}).get("items") or [{}])[0].get("id")
    from openpyxl import Workbook
    wb = Workbook()
    ws = wb.active
    ws.append(["学生姓名", "年级", "班级", "资助金额"])
    ws.append([f"张三{TS}", "三年级", "1班", 500])
    ws.append([f"李四{TS}", "三年级", "2班", 800])
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    r = c.post(f"/schools/{sid}/scholarship-students/import", files={"file": ("stu.xlsx", buf.getvalue(),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}, headers={})
    r2 = c.get(f"/schools/{sid}/scholarship-students", params={"page": 1, "page_size": 100})
    stu = (r2.json().get("data") or {}).get("items", [])
    mine = [s for s in stu if str(s.get("student_name", "")).startswith("张") or str(s.get("student_name", "")).startswith("李")]
    total = sum(float(s.get("amount") or 0) for s in mine)
    record("R3-17 受助学生导入+金额汇总", r.status_code in (200, 201) and len(mine) >= 2 and abs(total - 1300) < 0.01,
           f"import_status={r.status_code} mine={len(mine)} sum={total} body={r.text[:200]}")
    # 重复导入同名学生
    r3 = c.post(f"/schools/{sid}/scholarship-students/import", files={"file": ("stu.xlsx", buf.getvalue(),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}, headers={})
    r4 = c.get(f"/schools/{sid}/scholarship-students", params={"page": 1, "page_size": 200})
    stu4 = (r4.json().get("data") or {}).get("items", [])
    n = sum(1 for s in stu4 if s.get("student_name") == f"张三{TS}")
    record("R3-18 重复学生处理观察", r3.status_code in (200, 201), f"repeat_status={r3.status_code} 张三出现次数={n} body={r3.text[:200]}")
except Exception as e:
    record("R3-17/18 受助学生", False, e)

summary = {"total": len(results), "passed": sum(1 for x in results if x["passed"]),
           "failed": sum(1 for x in results if not x["passed"]), "results": results}
print("===SUMMARY===")
print(json.dumps(summary, ensure_ascii=False))
