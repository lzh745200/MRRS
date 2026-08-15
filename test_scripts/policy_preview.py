# -*- coding: utf-8 -*-
"""政策文件上传+预览验证"""
import httpx
BASE = "http://127.0.0.1:8000/api/v1"
c = httpx.Client(base_url=BASE, timeout=60)
r = c.get("/auth/csrf-token")
csrf = (r.json().get("data") or {}).get("csrf_token")
c.headers["X-CSRF-Token"] = csrf or ""
r = c.post("/auth/login", json={"username": "admin", "password": "Admin@12345"})
c.headers["Authorization"] = "Bearer " + r.json()["data"]["access_token"]
TS = 1
r = c.post("/policies", json={"title": f"PDF政策测试", "content": "预览测试", "category": "产业", "status": "active"})
pid = (r.json().get("data") or {}).get("id")
print("create policy:", r.status_code, pid)
# 构造最小PDF
pdf = b"%PDF-1.4\n1 0 obj<</Type/Catalog>>endobj\ntrailer<</Root 1 0 R>>\n%%EOF"
r = c.post(f"/policies/{pid}/upload", files={"file": ("doc.pdf", pdf, "application/pdf")})
print("policy upload pdf:", r.status_code, r.text[:200])
r = c.get(f"/policies/{pid}/preview")
print("policy preview:", r.status_code, r.headers.get("content-type"), r.text[:80] if "text" in str(r.headers.get("content-type", "")) else f"bytes={len(r.content)}")
# word 上传
docx = b"PK\x03\x04 fake docx content"
r = c.post(f"/policies/{pid}/upload", files={"file": ("doc.docx", docx, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")})
print("policy upload docx:", r.status_code, r.text[:200])
r = c.get(f"/policies/{pid}/preview")
print("policy preview after docx:", r.status_code, str(r.headers.get("content-type"))[:60], f"bytes={len(r.content)}")
