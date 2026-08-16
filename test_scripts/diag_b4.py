import httpx, json, sqlite3
db = sqlite3.connect(r"data/permflow_test.db")
print("packages:", db.execute("SELECT id, org_id, status, type, created_by, record_count FROM data_packages").fetchall())
print("user2 org:", db.execute("SELECT id, username, organization_id, data_scope FROM users").fetchall())
BASE = "http://127.0.0.1:8001/api/v1"
c = httpx.Client(base_url=BASE, timeout=60)
r = c.get("/auth/csrf-token")
csrf = (r.json().get("data") or {}).get("csrf_token")
c.headers["X-CSRF-Token"] = csrf or ""
r = c.post("/auth/login", json={"username": "subuser1", "password": "Sub@123456"})
tok = r.json()["data"]["access_token"]
SH = {"Authorization": "Bearer " + tok}
r = c.get("/data-packages", params={"page": 1, "page_size": 50}, headers=SH)
print("subuser list now:", r.status_code, r.text[:400])
