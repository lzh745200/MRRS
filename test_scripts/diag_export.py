import httpx, sqlite3
BASE = "http://127.0.0.1:8001/api/v1"
c = httpx.Client(base_url=BASE, timeout=60)
r = c.get("/auth/csrf-token")
csrf = (r.json().get("data") or {}).get("csrf_token")
c.headers["X-CSRF-Token"] = csrf or ""
r = c.post("/auth/login", json={"username": "subuser1", "password": "Sub@123456"})
tok = r.json()["data"]["access_token"]
H = {"Authorization": "Bearer " + tok}
r = c.post("/data-packages/one-click-report", json={"remarks": "诊断"}, headers=H)
print("report:", r.status_code, r.headers.get("X-Package-Id"), r.headers.get("X-Record-Count"))
db = sqlite3.connect(r"data/permflow_test.db")
rows = db.execute("SELECT id, org_id, status, type, created_by FROM data_packages").fetchall()
print("packages now:", rows)
# 看上传目录文件
import os
ud = db.execute("SELECT value FROM app_config WHERE key LIKE '%upload%'").fetchall()
print("config upload:", ud[:3])
print("uploads dir:", os.listdir("data/uploads")[:5] if os.path.isdir("data/uploads") else "no dir")
