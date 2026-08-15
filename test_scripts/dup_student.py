# 受助学生重复导入观察
import httpx, io, time
from openpyxl import Workbook
BASE = "http://127.0.0.1:8000/api/v1"
c = httpx.Client(base_url=BASE, timeout=90)
r = c.get("/auth/csrf-token")
csrf = (r.json().get("data") or {}).get("csrf_token")
c.headers["X-CSRF-Token"] = csrf or ""
r = c.post("/auth/login", json={"username": "admin", "password": "Admin@12345"})
c.headers["Authorization"] = "Bearer " + r.json()["data"]["access_token"]
r = c.get("/schools", params={"page": 1, "page_size": 1})
sid = ((r.json().get("data") or {}).get("items") or [{}])[0].get("id")
TS = int(time.time())
wb = Workbook(); ws = wb.active
ws.append(["学生姓名", "年级", "年份", "资助金额"])
ws.append([f"重复学生{TS}", "四年级", 2026, 600])
buf = io.BytesIO(); wb.save(buf); buf.seek(0)
files = {"file": ("dup.xlsx", buf.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
r1 = c.post(f"/schools/{sid}/scholarship-students/import", files=files)
buf.seek(0)
r2 = c.post(f"/schools/{sid}/scholarship-students/import", files=files)
print("import1:", r1.status_code, r1.text[:200])
print("import2:", r2.status_code, r2.text[:200])
r = c.get(f"/schools/{sid}/scholarship-students", params={"page": 1, "page_size": 500})
items = (r.json().get("data") or {}).get("items", [])
n = sum(1 for s in items if s.get("student_name") == f"重复学生{TS}")
print("同名记录数:", n)
