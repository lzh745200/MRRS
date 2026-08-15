# -*- coding: utf-8 -*-
"""诊断下半部分：驳回opinion/转审transfer_to_id/提醒结构/里程碑/413/受助学生"""
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
db = sqlite3.connect(r"data/smoke_test.db")

# messages 表结构
print("messages cols:", [x[1] for x in db.execute("PRAGMA table_info(messages)").fetchall()])
rows = db.execute("SELECT id, title, content, user_id FROM messages ORDER BY id DESC LIMIT 5").fetchall()
print("recent messages:", rows)

# B'. 驳回用 opinion
r = c.post("/funds", json={"name": f"驳回诊断B{TS}", "planned_amount": 30000})
fid = (r.json().get("data") or {}).get("id")
r = c.post("/approval/submit", json={"entity_type": "fund", "entity_id": fid, "title": f"B{fid}", "change_data": {}})
task = (r.json().get("data") or {}).get("task_id")
r = c.post(f"/approval/tasks/{task}/reject", json={"opinion": "预算超标，请修改"})
print("B' reject(opinion):", r.status_code, r.text[:250])
r = c.get(f"/funds/{fid}")
print("B' fund status after reject:", r.json().get("data", {}).get("status"))
r = c.get(f"/approval/tasks/{task}")
print("B' task after reject:", r.status_code, r.text[:250])

# C'. 转审 transfer_to_id
r = c.post("/approval/submit", json={"entity_type": "fund", "entity_id": fid, "title": f"C{fid}", "change_data": {}})
task2 = (r.json().get("data") or {}).get("task_id")
r = c.post(f"/approval/tasks/{task2}/transfer", json={"transfer_to_id": 2})
print("C' transfer:", r.status_code, r.text[:250])

# D'. 提醒扫描 + /reminders 原始
r = c.post("/funds", json={"name": f"预警诊断D{TS}", "planned_amount": 10000})
fid2 = (r.json().get("data") or {}).get("id")
r = c.put(f"/funds/{fid2}", json={"amount": 10000, "approved_amount": 10000, "used_amount": 9200})
r = c.post("/reminders/scan")
print("D' scan1:", r.status_code, r.text[:150])
r = c.post("/reminders/scan")
print("D' scan2:", r.status_code, r.text[:150])
r = c.get("/reminders", params={"page": 1, "page_size": 300})
j = r.json()
items = (j.get("data") or {}).get("items", [])
print("D' reminders count:", len(items), "keys:", list(items[0].keys()) if items else None)
bw = [i for i in items if "budget" in json.dumps(i, ensure_ascii=False) and str(fid2) in json.dumps(i, ensure_ascii=False)]
print("D' budget entries for fid2:", len(bw), bw[:2])

# E'. 里程碑
r = c.post("/projects", json={"name": f"里程碑诊断E{TS}", "start_date": "2026-02-01", "status": "pending", "budget": 100, "category": "产业", "location": "贵州", "priority": "low"})
pid = (r.json().get("data") or {}).get("id")
r = c.post(f"/projects/{pid}/milestones", json={"name": "M1", "planned_date": "2026-07-01"})
mid = (r.json().get("data") or {}).get("id")
r = c.put(f"/projects/{pid}/milestones/{mid}", json={"status": "completed"})
print("E' milestone update:", r.status_code, r.text[:150])
r = c.get(f"/projects/{pid}/milestones")
print("E' milestones raw:", r.text[:300])
# 项目进度是否自动更新
r = c.get(f"/projects/{pid}")
print("E' project after milestone done:", r.json().get("data", {}).get("progress"), "| keys:", [k for k in (r.json().get("data") or {}).keys() if 'prog' in k])

# F'. 大文件
for size_mb in (11, 21):
    big = b"\x89PNG\r\n\x1a\n" + b"\x00" * (size_mb * 1024 * 1024)
    r = c.post("/files/upload", files={"file": (f"big{size_mb}.png", big, "image/png")})
    print(f"F' upload {size_mb}MB:", r.status_code, r.text[:100])

# G'. 受助学生（年份int列）
r = c.get("/schools", params={"page": 1, "page_size": 1})
sid = ((r.json().get("data") or {}).get("items") or [{}])[0].get("id")
from openpyxl import Workbook
wb = Workbook(); ws = wb.active
ws.append(["学生姓名", "年级", "年份", "资助金额"])
ws.append([f"张三{TS}", "三年级", 2026, 500])
ws.append([f"李四{TS}", "三年级", 2026, 800])
buf = io.BytesIO(); wb.save(buf); buf.seek(0)
r = c.post(f"/schools/{sid}/scholarship-students/import", files={"file": ("stu3.xlsx", buf.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")})
print("G' import:", r.status_code, r.text[:250])
r = c.get(f"/schools/{sid}/scholarship-students", params={"page": 1, "page_size": 300})
stu = (r.json().get("data") or {}).get("items", [])
mine = [s for s in stu if str(s.get("student_name", "")).startswith("张") or str(s.get("student_name", "")).startswith("李")]
print("G' students:", len(mine), "sum:", sum(float(s.get("amount") or 0) for s in mine))
