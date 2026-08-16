import httpx, json
BASE = "http://127.0.0.1:8001/api/v1"
c = httpx.Client(base_url=BASE, timeout=60)
r = c.get("/auth/csrf-token")
csrf = (r.json().get("data") or {}).get("csrf_token")
c.headers["X-CSRF-Token"] = csrf or ""
def login(u, p):
    r = c.post("/auth/login", json={"username": u, "password": p})
    return r.json()["data"]["access_token"]
SUB = login("subuser1", "Sub@123456")
ADMIN = login("admin", "Admin@12345")
SH = {"Authorization": "Bearer " + SUB}
AH = {"Authorization": "Bearer " + ADMIN}
r = c.get("/data-packages", params={"page": 1, "page_size": 50}, headers=SH)
print("subuser list:", r.status_code, r.text[:300])
r = c.get("/data-packages", params={"page": 1, "page_size": 50}, headers=AH)
print("admin list:", r.status_code, r.text[:300])
r = c.get("/menus/accessible", headers=AH)
print("admin menus/accessible:", r.status_code, r.text[:400])
r = c.get("/menus/accessible", headers=SH)
print("subuser menus/accessible:", r.status_code, r.text[:400])
