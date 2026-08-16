import httpx, time
BASE = "http://127.0.0.1:8001/api/v1"
c = httpx.Client(base_url=BASE, timeout=60)
r = c.get("/auth/csrf-token")
csrf = (r.json().get("data") or {}).get("csrf_token")
c.headers["X-CSRF-Token"] = csrf or ""
r = c.post("/auth/login", json={"username": "subuser1", "password": "Sub@123456"})
tok = r.json()["data"]["access_token"]
SH = {"Authorization": "Bearer " + tok}
r = c.post("/data-packages/one-click-report", json={"remarks": "明细诊断"}, headers=SH)
pid = r.headers.get("X-Package-Id")
r2 = c.get("/data-packages", params={"page": 1, "page_size": 50}, headers=SH)
j = r2.json()
data = j.get("data") if isinstance(j.get("data"), dict) else j
items = data.get("items") or []
print("total:", data.get("total"), "items ids:", [(i.get("id"), i.get("org_id"), i.get("status")) for i in items], "new pid:", pid)
