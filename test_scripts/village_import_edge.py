# 帮扶村导入边界：空村名/特殊字符
import httpx, io, time
from openpyxl import Workbook
BASE = "http://127.0.0.1:8000/api/v1"
c = httpx.Client(base_url=BASE, timeout=90)
r = c.get("/auth/csrf-token")
csrf = (r.json().get("data") or {}).get("csrf_token")
c.headers["X-CSRF-Token"] = csrf or ""
r = c.post("/auth/login", json={"username": "admin", "password": "Admin@12345"})
c.headers["Authorization"] = "Bearer " + r.json()["data"]["access_token"]
TS = int(time.time())
wb = Workbook(); ws = wb.active
ws.append(["村名", "编码", "省", "市", "县"])
ws.append([f"特殊字符村<scr>&🎉{TS}", f"SPC{TS}", "贵州省", "毕节市", "织金县"])   # 合法+特殊字符
ws.append([None, f"NONAME{TS}", "贵州省", "毕节市", "织金县"])                      # 空村名
buf = io.BytesIO(); wb.save(buf); buf.seek(0)
r = c.post("/supported-villages/import", files={"file": (f"edge{TS}.xlsx", buf.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")})
print("import status:", r.status_code)
print(r.text[:600])
r = c.get("/supported-villages", params={"keyword": f"特殊字符村<scr>&🎉{TS}", "page": 1, "page_size": 5})
items = (r.json().get("data") or {}).get("items", [])
print("特殊字符村检索:", len(items), items[0].get("village_name") if items else None)
