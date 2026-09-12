"""覆盖 app.middleware.csrf_middleware 缺口：本机内部备份通道豁免（E1 ASGI 版）。"""
from unittest.mock import MagicMock

from app.core.config import settings
from app.middleware.csrf_middleware import CSRFMiddleware


def _scope(path="/api/v1/system/users", internal_backup=None):
    headers = [(b"host", b"127.0.0.1:8000")]
    if internal_backup:
        headers.append((b"x-internal-backup", internal_backup.encode()))
    return {
        "type": "http", "method": "POST", "path": path, "headers": headers,
        "client": ("127.0.0.1", 50000), "query_string": b"",
        "scheme": "http", "server": ("127.0.0.1", 8000),
    }


async def _drive(mw, scope):
    called = [False]
    captured = {"status": None}

    async def downstream(s, receive, send):
        called[0] = True

    async def receive():
        return {"type": "http.request"}

    async def send(message):
        if message["type"] == "http.response.start":
            captured["status"] = message["status"]

    mw.app = downstream
    await mw(scope, receive, send)
    return called[0], captured["status"]


class TestInternalBackupBypass:
    async def test_internal_backup_key_bypasses_csrf(self, monkeypatch):
        monkeypatch.setattr(settings, "CSRF_ENABLED", True)
        monkeypatch.setenv("INTERNAL_BACKUP_KEY", "backup-secret")

        mw = CSRFMiddleware(app=MagicMock())
        called, status = await _drive(mw, _scope(internal_backup="backup-secret"))

        assert called is True
        assert status is None  # 未产出 403 响应，直接透传下游

    async def test_wrong_internal_key_falls_through_to_403(self, monkeypatch):
        # 对照组：内部密钥不匹配 → 继续 CSRF 校验，缺少 token 返回 403
        monkeypatch.setattr(settings, "CSRF_ENABLED", True)
        monkeypatch.setenv("INTERNAL_BACKUP_KEY", "backup-secret")

        mw = CSRFMiddleware(app=MagicMock())
        called, status = await _drive(mw, _scope())

        assert called is False
        assert status == 403
