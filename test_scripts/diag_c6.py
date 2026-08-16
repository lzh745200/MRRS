import httpx, json
BASE = "http://127.0.0.1:8001/api/v1"
c = httpx.Client(base_url=BASE, timeout=60)
r = c.get("/auth/csrf-token")
csrf = (r.json().get("data") or {}).get("csrf_token")
c.headers["X-CSRF-Token"] = csrf or ""
r = c.post("/auth/login", json={"username": "subuser2", "password": "Sub@123456"})
tok = r.json()["data"]["access_token"]
SH = {"Authorization": "Bearer " + tok}
# 找一个属于org2的包
r = c.post("/data-packages/one-click-report", json={"remarks": "C6诊断"}, headers=SH)
pid = r.headers.get("X-Package-Id")
print("pkg:", pid)
r = c.post("/data-reports", json={"title": "乙单位上报诊断", "report_type": "monthly", "package_id": int(pid), "target_org_id": 1}, headers=SH)
print("create:", r.status_code, r.text[:400])
