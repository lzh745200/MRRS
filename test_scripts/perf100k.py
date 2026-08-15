# -*- coding: utf-8 -*-
"""10万条数据性能测试（冒烟DB）"""
import sqlite3, time, json
import httpx

db = sqlite3.connect(r'data/smoke_test.db')
t0 = time.time()
# 批量插入 10 万条帮扶村
db.execute("BEGIN")
for i in range(100000):
    db.execute("INSERT INTO supported_villages (village_name, sequence_no, province, city, county, is_active, organization_id, created_at) VALUES (?,?,?,?,?,1,1,datetime('now'))",
               (f"压测村{i}", f"PERF-{i:06d}", "贵州省", "毕节市", "织金县"))
db.execute("COMMIT")
print(f"insert 100k rows: {time.time()-t0:.1f}s")
db.close()

c = httpx.Client(base_url="http://127.0.0.1:8000/api/v1", timeout=120)
r = c.get("/auth/csrf-token")
csrf = (r.json().get("data") or {}).get("csrf_token")
c.headers["X-CSRF-Token"] = csrf or ""
r = c.post("/auth/login", json={"username": "admin", "password": "Admin@12345"})
c.headers["Authorization"] = "Bearer " + r.json()["data"]["access_token"]

def timed(label, fn):
    t = time.time()
    resp = fn()
    dt = (time.time() - t) * 1000
    print(f"{label}: status={resp.status_code} {dt:.0f}ms")
    return resp

timed("列表 page1 page_size=200", lambda: c.get("/supported-villages", params={"page": 1, "page_size": 200}))
timed("列表 page500", lambda: c.get("/supported-villages", params={"page": 500, "page_size": 200}))
timed("关键词筛选 压测村9999", lambda: c.get("/supported-villages", params={"keyword": "压测村9999", "page": 1, "page_size": 20}))
timed("组合筛选 county", lambda: c.get("/supported-villages", params={"county": "织金县", "page": 1, "page_size": 20}))
r = timed("统计 total 读取", lambda: c.get("/supported-villages", params={"page": 1, "page_size": 1}))
print("total:", (r.json().get("data") or {}).get("total"))
