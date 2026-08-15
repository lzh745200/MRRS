# 真实docx预览测试
import httpx, io, zipfile
BASE = "http://127.0.0.1:8000/api/v1"
c = httpx.Client(base_url=BASE, timeout=60)
r = c.get("/auth/csrf-token")
csrf = (r.json().get("data") or {}).get("csrf_token")
c.headers["X-CSRF-Token"] = csrf or ""
r = c.post("/auth/login", json={"username": "admin", "password": "Admin@12345"})
c.headers["Authorization"] = "Bearer " + r.json()["data"]["access_token"]
r = c.post("/policies", json={"title": "真实DOCX政策", "content": "内容", "category": "产业"})
pid = (r.json().get("data") or {}).get("id")
# 构造最小合法 docx（zip 结构）
buf = io.BytesIO()
with zipfile.ZipFile(buf, 'w') as z:
    z.writestr('[Content_Types].xml', '<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/></Types>')
    z.writestr('_rels/.rels', '<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>')
    z.writestr('word/document.xml', '<?xml version="1.0"?><w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>帮扶政策正文</w:t></w:r></w:p></w:body></w:document>')
data = buf.getvalue()
r = c.post(f"/policies/{pid}/upload", files={"file": ("real.docx", data, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")})
print("upload real docx:", r.status_code)
r = c.get(f"/policies/{pid}/preview")
print("preview real docx:", r.status_code, str(r.headers.get("content-type"))[:60])
if r.status_code == 200:
    print("preview html head:", r.text[:200])
