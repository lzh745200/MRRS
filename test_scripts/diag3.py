# -*- coding: utf-8 -*-
"""最终诊断：51MB/里程碑进度/双账号驳回通知"""
import json, time
import httpx

BASE = "http://127.0.0.1:8000/api/v1"
c = httpx.Client(base_url=BASE, timeout=180)
r = c.get("/auth/csrf-token")
csrf = (r.json().get("data") or {}).get("csrf_token")
c.headers["X-CSRF-Token"] = csrf or ""
r = c.post("/auth/login", json={"username": "admin", "password": "Admin@12345"})
c.headers["Authorization"] = "Bearer " + r.json()["data"]["access_token"]
TS = int(time.time())

# 1. 51MB png
big = b"\x89PNG\r\n\x1a\n" + b"\x00" * (51 * 1024 * 1024)
r = c.post("/files/upload", files={"file": ("big51.png", big, "image/png")})
print("1. 51MB upload:", r.status_code, r.text[:120])

# 2. 里程碑 → 项目进度
r = c.post("/projects", json={"name": f"进度项目{TS}", "start_date": "2026-02-01", "status": "pending", "budget": 100, "category": "产业", "location": "贵州", "priority": "low"})
pid = (r.json().get("data") or {}).get("id")
r = c.post(f"/projects/{pid}/milestones", json={"name": "M1", "planned_date": "2026-07-01"})
print("2a. milestone create raw:", r.status_code, r.text[:200])
mid = (r.json().get("data") or {}).get("id") if isinstance(r.json(), dict) else None
if mid is None and isinstance(r.json(), dict):
    mid = r.json().get("id")
if mid is None and isinstance(r.json(), list) and r.json():
    mid = r.json()[0].get("id")
r = c.post(f"/projects/{pid}/milestones", json={"name": "M2", "planned_date": "2026-09-01"})
print("2b. m2:", r.status_code, r.text[:120])
r = c.put(f"/projects/{pid}/milestones/{mid}", json={"status": "completed", "actual_date": "2026-06-01"})
print("2c. complete M1:", r.status_code, r.text[:150])
r = c.get(f"/projects/{pid}")
print("2d. project progress after 1/2 done:", r.json().get("data", {}).get("progress"))

# 3. 双账号驳回通知
user = f"smokeuser{TS}"
r = c.post("/users", json={"username": user, "password": "Smoke@123456", "full_name": user, "role": "user", "organization_id": 1})
uid = ((r.json().get("data") or {})).get("id")
print("3a. create user:", r.status_code, r.text[:120])
# user 登录
r = c.post("/auth/login", json={"username": user, "password": "Smoke@123456"})
utok = r.json().get("data", {}).get("access_token")
print("3b. user login:", r.status_code, bool(utok))
UH = {"Authorization": "Bearer " + utok, "X-CSRF-Token": csrf or ""}
r = c.post("/funds", json={"name": f"双账号经费{TS}", "planned_amount": 5000}, headers=UH)
fid = ((r.json().get("data") or {})).get("id")
print("3c. user create fund:", r.status_code, bool(fid))
r = c.post("/approval/submit", json={"entity_type": "fund", "entity_id": fid, "title": f"双账号审批{fid}", "change_data": {}}, headers=UH)
task = ((r.json().get("data") or {})).get("task_id")
print("3d. user submit:", r.status_code, "task:", task)
# admin 驳回
r = c.post(f"/approval/tasks/{task}/reject", json={"opinion": "材料不全，请补充预算明细"}, headers={})
print("3e. admin reject:", r.status_code, r.text[:150])
# user 查消息
r = c.get("/messages-extended/list", params={"page": 1, "page_size": 30}, headers=UH)
print("3f. user messages-extended:", r.status_code, r.text[:400])
r = c.get("/messages", params={"page": 1, "page_size": 30}, headers=UH)
print("3g. user /messages:", r.status_code, r.text[:300])
