# -*- coding: utf-8 -*-
"""密钥轮换后的自检（P1-S2）。

背景：PII 解密失败是逐字段静默降级（原样回密文），页面表现是「数据变乱码」，
而审计里写的是「轮换成功」。这组用例守住：
  1) PII 往返自检在正常密钥下通过；
  2) 加密/解密被破坏时自检**必须报错**（不是静默通过）；
  3) 轮换端点会真的调用自检，失败时返回 500 且文案可读。
"""
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.core import pii_crypto


class TestPiiSelfCheck:
    def test_roundtrip_passes(self):
        # 自检是纯守卫：正常密钥下必须返回 None 且不抛
        assert pii_crypto.self_check() is None

    def test_missing_marker_raises(self, monkeypatch):
        monkeypatch.setattr(pii_crypto, "encrypt_pii", lambda value: value)
        with pytest.raises(RuntimeError, match="密文标记"):
            pii_crypto.self_check()

    def test_decrypt_mismatch_raises(self, monkeypatch):
        monkeypatch.setattr(pii_crypto, "encrypt_pii", lambda value: pii_crypto.MARKER + "bogus")
        monkeypatch.setattr(pii_crypto, "decrypt_pii", lambda value: "something-else")
        with pytest.raises(RuntimeError, match="往返不一致"):
            pii_crypto.self_check()


@pytest.fixture
def admin_client():
    from app.main import app
    from app.core.security import get_current_active_user

    user = SimpleNamespace(id=1, username="admin", role="super_admin", is_superuser=True)
    app.dependency_overrides[get_current_active_user] = lambda: user
    tc = TestClient(app, raise_server_exceptions=False)
    yield tc
    app.dependency_overrides.pop(get_current_active_user, None)


class TestRotateEndpointSelfCheck:
    def test_rotate_runs_self_check(self, admin_client, monkeypatch):
        calls = []
        monkeypatch.setattr(pii_crypto, "self_check", lambda *a, **kw: calls.append(1))
        resp = admin_client.post("/api/v1/secrets/rotate")
        assert resp.status_code == 200
        assert calls == [1], "轮换必须真的跑一次 PII 往返自检"

    def test_rotate_fails_loudly_when_self_check_fails(self, admin_client, monkeypatch):
        def boom(*a, **kw):
            raise RuntimeError("往返不一致")

        monkeypatch.setattr(pii_crypto, "self_check", boom)
        resp = admin_client.post("/api/v1/secrets/rotate")
        assert resp.status_code == 500
        assert "自检失败" in resp.json()["detail"]