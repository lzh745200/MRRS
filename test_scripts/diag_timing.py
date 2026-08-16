import httpx, time
BASE = "http://127.0.0.1:8001/api/v1"
c = httpx.Client(base_url=BASE, timeout=60)
r = c.get("/auth/csrf-token")
csrf = (r.json().get("data") or {}).get("csrf_token")
c.headers["X-CSRF-Token"] = csrf or ""
r = c.post("/auth/login", json={"username": "subuser1", "password": "Sub@123456"})
tok = r.json()["data"]["access_token"]
SH = {"Authorization": "Bearer " + tok}
for i in range(3):
    r = c.post("/data-packages/one-click-report", json={"remarks": f"时序诊断{i}"}, headers=SH)
    pid = r.headers.get("X-Package-Id")
    r2 = c.get("/data-packages", params={"page": 1, "page_size": 50}, headers=SH)
    total = (r2.json().get("data") or {}).get("total") if isinstance(r2.json().get("data"), dict) else r2.json().get("total")
    items = (r2.json().get("data") or {}).get("items", []) if isinstance(r2.json().get("data"), dict) else []
    has = any(str(i.get("id")) == str(pid) for i in items)
    print(f"round{i}: pkg={pid} list_total={total} has_new={has}")
    time.sleep(1)
