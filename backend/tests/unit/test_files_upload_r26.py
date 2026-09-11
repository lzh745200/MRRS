"""R26 回归锁定：`/files/upload` 的 category 双形态 + 分块落盘 + 零残留。

R26 探针（真实 HTTP）发现两处：
1. `category` 只认**查询参数**。元素上传组件（el-upload 的 `data`/`:data`）天然走
   multipart 表单字段，于是"调用方传了 category 却静默落到 generic/"——与 R14
   经费附件 `category` 走 FormData 而后端只认 Query 是同一类坑。修复：查询参数与
   表单字段都接受（对外线名都是 `category`）。
2. `await file.read()` 一次性把整个文件读进内存，50MB 上限在**读完之后**才判 ——
   超大文件会先把内存吃满再被拒（OOM）。修复：8MB 分块流式落盘 + 滚动大小校验，
   超限/嗅探失败即删残片（对齐 backup upload-restore 既有约定）。
"""

import io
import os

import pytest

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 128


@pytest.fixture
def upload_dir(tmp_path, monkeypatch):
    """把 UPLOAD_DIR 指到临时目录，断言落盘位置与残留。"""
    from app.core.config import settings

    target = tmp_path / "uploads"
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(target))
    target.mkdir(parents=True, exist_ok=True)
    return target


class TestCategoryBothForms:
    def test_query_param(self, client_with_mocked_auth, upload_dir):
        resp = client_with_mocked_auth.post(
            "/api/v1/files/upload?category=policies",
            files={"file": ("a.txt", b"hello", "text/plain")},
        )
        assert resp.status_code == 200
        assert "/uploads/generic/policies/" in resp.json()["data"]["url"]

    def test_form_field(self, client_with_mocked_auth, upload_dir):
        """el-upload 的 data/:data 走表单字段 —— 必须同样生效。"""
        resp = client_with_mocked_auth.post(
            "/api/v1/files/upload",
            files={"file": ("a.txt", b"hello", "text/plain")},
            data={"category": "schools"},
        )
        assert resp.status_code == 200
        assert "/uploads/generic/schools/" in resp.json()["data"]["url"]

    def test_form_field_traversal_neutralized(self, client_with_mocked_auth, upload_dir):
        resp = client_with_mocked_auth.post(
            "/api/v1/files/upload",
            files={"file": ("a.txt", b"hello", "text/plain")},
            data={"category": "../../evil"},
        )
        assert resp.status_code == 200
        url = resp.json()["data"]["url"]
        assert ".." not in url
        assert url.startswith("/uploads/generic/")
        assert not (upload_dir.parent / "evil").exists()

    def test_no_category_uses_generic(self, client_with_mocked_auth, upload_dir):
        resp = client_with_mocked_auth.post(
            "/api/v1/files/upload",
            files={"file": ("a.txt", b"hello", "text/plain")},
        )
        assert resp.status_code == 200
        url = resp.json()["data"]["url"]
        assert "/uploads/generic/" in url and "/generic/policies/" not in url


class TestStreamedUpload:
    def test_file_written_and_size_reported(self, client_with_mocked_auth, upload_dir):
        resp = client_with_mocked_auth.post(
            "/api/v1/files/upload",
            files={"file": ("scan.png", PNG, "image/png")},
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["file_size"] == len(PNG)
        rel = data["url"].replace("/uploads/", "")
        written = upload_dir / rel.replace("/", os.sep)
        assert written.is_file() and written.stat().st_size == len(PNG)

    def test_oversize_rejected_without_residue(self, client_with_mocked_auth, upload_dir, monkeypatch):
        from app.core.config import settings

        monkeypatch.setattr(settings, "MAX_FILE_SIZE", 32)
        resp = client_with_mocked_auth.post(
            "/api/v1/files/upload",
            files={"file": ("big.txt", b"x" * 4096, "text/plain")},
        )
        assert resp.status_code == 413
        assert "超过限制" in resp.json()["detail"]
        leftovers = [p for p in upload_dir.rglob("*") if p.is_file()]
        assert leftovers == [], f"拒绝路径必须零磁盘残留，实际 {leftovers}"

    def test_magic_mismatch_rejected_without_residue(self, client_with_mocked_auth, upload_dir):
        resp = client_with_mocked_auth.post(
            "/api/v1/files/upload",
            files={"file": ("fake.png", b"definitely not a png" * 8, "image/png")},
        )
        assert resp.status_code == 400
        assert "不匹配" in resp.json()["detail"]
        leftovers = [p for p in upload_dir.rglob("*") if p.is_file()]
        assert leftovers == [], f"嗅探失败必须零磁盘残留，实际 {leftovers}"

    def test_disallowed_extension_rejected_before_write(self, client_with_mocked_auth, upload_dir):
        resp = client_with_mocked_auth.post(
            "/api/v1/files/upload",
            files={"file": ("evil.exe", b"MZ" + b"\x00" * 32, "application/octet-stream")},
        )
        assert resp.status_code == 400
        assert not list(upload_dir.rglob("*")), "扩展名不合规不应产生任何文件"

    def test_multichunk_file_still_correct(self, client_with_mocked_auth, upload_dir, monkeypatch):
        """跨分块写入的内容必须完整（分块边界不丢字节）。"""
        import app.api.v1.files as files_mod

        monkeypatch.setattr(files_mod, "_UPLOAD_CHUNK_SIZE", 8)
        payload = b"0123456789" * 5
        resp = client_with_mocked_auth.post(
            "/api/v1/files/upload",
            files={"file": ("multi.txt", io.BytesIO(payload), "text/plain")},
        )
        assert resp.status_code == 200
        rel = resp.json()["data"]["url"].replace("/uploads/", "")
        assert (upload_dir / rel.replace("/", os.sep)).read_bytes() == payload
