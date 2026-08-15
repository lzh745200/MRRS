# -*- coding: utf-8 -*-
"""诊断脚本：413/导入超长/驳回回退/预算预警/里程碑格式"""
import json, time, io
import httpx
import sqlite3

BASE = "http://127.0.0.1:8000/api/v1"
c = httpx.Client(base_url=BASE, timeout=90)
r = c.get("/auth/csrf-token")
csrf = (r.json().get("data") or {}).get("csrf_token")
c.headers["X-CSRF-Token"] = csrf or ""
r = c.post("/auth/login", json={"username": "admin", "password": "Admin@12345"})
c.headers["Authorization"] = "Bearer " + r.json()["data"]["access_token"]
TS = int(time.time())

# A. 超长村名入库检查
db = sqlite3.connect(r"data/smoke_test.db")
row = db.execute("SELECT village_name, length(village_name) FROM supported_villages WHERE village_name LIKE 'x%' ORDER BY id DESC LIMIT 1").fetchone()
print("A. 超长村名入库: name_len =", row)

# B. 驳回流详细
r = c.post("/funds", json={"name": f"驳回诊断{TS}", "planned_amount": 30000})
fid = (r.json().get("data") or {}).get("id")
print("B0. fund create:", r.status_code, r.text[:100])
r = c.post("/approval/submit", json={"entity_type": "fund", "entity_id": fid, "title": f"诊断{fid}", "change_data": {}})
print("B1. submit:", r.status_code, r.text[:200])
task = (r.json().get("data") or {}).get("id") or (r.json().get("data") or {}).get("task_id")
r = c.post(f"/approval/tasks/{task}/reject", json={"reason": "测试驳回"})
print("B2. reject:", r.status_code, r.text[:250])
r = c.get(f"/funds/{fid}")
print("B3. fund after reject:", r.json().get("data", {}).get("status"))
r = c.get("/messages", params={"page": 1, "page_size": 50})
items = (r.json().get("data") or {}).get("items", [])
print("B4. messages total:", len(items), [ (m.get('type'), m.get('title')) for m in items[:6] ])
print("B5. 含驳回的message:", [ (m.get('type'), m.get('title'), m.get('content')) for m in items if '驳回' in json.dumps(m, ensure_ascii=False) ][:3])

# C. 转审
r = c.get("/users", params={"page": 1, "page_size": 50})
users = (r.json().get("data") or {}).get("items", [])
target = next((u for u in users if u.get("username", "").startswith("smokeuser")), None)
print("C0. target user:", target)
r = c.post("/approval/submit", json={"entity_type": "fund", "entity_id": fid, "title": f"转审诊断{fid}", "change_data": {}})
print("C1. submit:", r.status_code, r.text[:200])
task2 = (r.json().get("data") or {}).get("id") or (r.json().get("data") or {}).get("task_id")
if target and task2:
    r = c.post(f"/approval/tasks/{task2}/transfer", json={"target_user_id": target.get("id")})
    print("C2. transfer:", r.status_code, r.text[:250])

# D. 预算预警：消息表直查
r = c.post("/funds", json={"name": f"预警诊断{TS}", "planned_amount": 10000})
fid2 = (r.json().get("data") or {}).get("id")
r = c.put(f"/funds/{fid2}", json={"amount": 10000, "approved_amount": 10000, "used_amount": 9200})
print("D0. fund put:", r.status_code, r.text[:100])
r = c.post("/reminders/scan")
print("D1. scan:", r.status_code, r.text[:150])
rows = db.execute("SELECT id, type, entity_id, title, content FROM messages WHERE type='budget_warning' AND entity_id=? ORDER BY id DESC LIMIT 5", (fid2,)).fetchall()
print("D2. budget_warning messages for fid2:", rows)
r = c.get("/reminders", params={"page": 1, "page_size": 300})
items = (r.json().get("data") or {}).get("items", [])
bw = [i for i in items if i.get("type") == "budget_warning"]
print("D3. /reminders budget_warning items:", len(bw), bw[:2])
print("D4. /reminders item keys sample:", list(items[0].keys()) if items else None)

# E. 里程碑原始响应
r = c.post("/projects", json={"name": f"里程碑诊断{TS}", "start_date": "2026-02-01", "status": "pending", "budget": 100, "category": "产业", "location": "贵州", "priority": "low"})
pid = (r.json().get("data") or {}).get("id")
r = c.post(f"/projects/{pid}/milestones", json={"name": "M1", "planned_date": "2026-07-01"})
mid = (r.json().get("data") or {}).get("id")
print("E0. milestone create:", r.status_code, r.text[:150])
r = c.put(f"/projects/{pid}/milestones/{mid}", json={"status": "completed"})
print("E1. milestone update:", r.status_code, r.text[:150])
r = c.get(f"/projects/{pid}/milestones")
print("E2. milestones GET raw:", r.text[:200])
print("E3. milestones GET type:", type(r.json()).__name__)

# F. 大文件上传：不同大小
for size_mb in (11, 21):
    big = b"\x89PNG\r\n\x1a\n" + b"\x00" * (size_mb * 1024 * 1024)
    r = c.post("/files/upload", files={"file": (f"big{size_mb}.png", big, "image/png")})
    print(f"F. upload {size_mb}MB:", r.status_code, r.text[:120])

# G. 受助学生导入正确列
r = c.get("/schools", params={"page": 1, "page_size": 1})
sid = ((r.json().get("data") or {}).get("items") or [{}])[0].get("id")
from openpyxl import Workbook
wb = Workbook(); ws = wb.active
ws.append(["学生姓名", "年级", "年份", "资助金额"])
ws.append([f"张三{TS}", "三年级", 2026, 500])
ws.append([f"李四{TS}", "三年级", 2026, 800])
buf = io.BytesIO(); wb.save(buf); buf.seek(0)
r = c.post(f"/schools/{sid}/scholarship-students/import", files={"file": ("stu2.xlsx", buf.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")})
print("G. scholarship import v2:", r.status_code, r.text[:250])
r = c.get(f"/schools/{sid}/scholarship-students", params={"page": 1, "page_size": 200})
stu = (r.json().get("data") or {}).get("items", [])
mine = [s for s in stu if str(s.get("student_name","")).startswith("张") or str(s.get("student_name","")).startswith("李")]
print("G2. students:", len(mine), "sum:", sum(float(s.get("amount") or 0) for s in mine))
