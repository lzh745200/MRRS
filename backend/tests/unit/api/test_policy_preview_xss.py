"""W1-T4 安全回归：政策预览 XSS 转义。

工单 .scratch/w1-security-redline/004
历史缺陷：policy.title/content 未转义即以 text/html 内联渲染（存储型 XSS）。
"""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.core.database import get_db
from app.core.security import get_current_user
from app.main import app


@pytest.fixture(autouse=True)
def _no_camel_to_snake():
    with patch("app.middleware.camel_to_snake._convert_keys",
               side_effect=lambda obj, converter: (obj, False)):
        yield


@pytest.fixture
def client():
    db = MagicMock()
    user = MagicMock()
    user.id = 1
    user.role = "admin"
    user.is_superuser = True
    _original = app.dependency_overrides.copy()
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: user
    yield TestClient(app, raise_server_exceptions=False), db
    app.dependency_overrides = _original


def _policy_with(title="<script>alert(1)</script>", content=None, file_path=None):
    p = MagicMock()
    p.id = 1
    p.title = title
    p.content = content if content is not None else "正文内容"
    p.file_path = file_path
    p.file_type = None
    return p


class TestPreviewXssEscaping:
    def test_title_script_tag_escaped(self, client):
        tc, db = client
        policy = _policy_with()
        db.query.return_value.filter.return_value.first.return_value = policy

        resp = tc.get("/api/v1/policies/1/preview")
        assert resp.status_code == 200
        body = resp.text
        assert "<script>alert(1)</script>" not in body, "未转义的 script 标签直达响应"
        assert "&lt;script&gt;" in body

    def test_content_html_escaped(self, client):
        tc, db = client
        policy = _policy_with(
            title="正常标题",
            content='<img src=x onerror="alert(2)">',
        )
        db.query.return_value.filter.return_value.first.return_value = policy

        resp = tc.get("/api/v1/policies/1/preview")
        assert resp.status_code == 200
        assert '<img src=x onerror' not in resp.text
        assert "&lt;img" in resp.text

    def test_mammoth_branch_title_escaped(self, client):
        """docx 分支：mammoth 转换结果保留，但 title 必须转义。"""
        tc, db = client
        policy = _policy_with(
            title="<b>evil</b>标题",
            content="ignored",
            file_path="C:/tmp/fake.docx",
        )
        policy.file_type = "docx"
        db.query.return_value.filter.return_value.first.return_value = policy

        mammoth_result = MagicMock()
        mammoth_result.value = "<p>转换后的正文</p>"
        fake_mammoth = MagicMock()
        fake_mammoth.convert_to_html.return_value = mammoth_result

        import builtins
        import io as _io
        real_import = builtins.__import__
        real_open = builtins.open

        def fake_import(name, *a, **kw):
            if name == "mammoth":
                return fake_mammoth
            return real_import(name, *a, **kw)

        def fake_open(file, mode="r", *a, **kw):
            if str(file).endswith(".docx") and "b" in mode:
                return _io.BytesIO(b"PK\x03\x04 fake-docx-bytes")
            return real_open(file, mode, *a, **kw)

        with patch("builtins.__import__", side_effect=fake_import), \
             patch("os.path.exists", return_value=True), \
             patch("builtins.open", side_effect=fake_open):
            resp = tc.get("/api/v1/policies/1/preview")

        assert resp.status_code == 200
        assert "<b>evil</b>" not in resp.text
        assert "&lt;b&gt;evil&lt;/b&gt;" in resp.text
        assert "<p>转换后的正文</p>" in resp.text, "mammoth 产物不应被二次转义"

    def test_mammoth_conversion_failure_falls_back_to_download(self, client, tmp_path):
        """覆盖 policy.py:972-974 —— docx 转换抛非-ImportError 异常时回退下载而非 500。"""
        tc, db = client
        docx = tmp_path / "broken.docx"
        docx.write_bytes(b"PK\x03\x04 not-a-real-docx")
        policy = _policy_with(title="t", content="c", file_path=str(docx))
        policy.file_type = "docx"
        db.query.return_value.filter.return_value.first.return_value = policy

        fake_mammoth = MagicMock()
        fake_mammoth.convert_to_html.side_effect = RuntimeError("损坏文档")

        import builtins
        real_import = builtins.__import__

        def fake_import(name, *a, **kw):
            if name == "mammoth":
                return fake_mammoth
            return real_import(name, *a, **kw)

        with patch("builtins.__import__", side_effect=fake_import):
            resp = tc.get("/api/v1/policies/1/preview")

        assert resp.status_code == 200
        # 回退为下载（octet-stream + attachment）
        assert "attachment" in resp.headers.get("content-disposition", "")
