"""金额 4 位小数端到端回归（Phase G 补强）。

验证链路：API 创建（quantize_money）→ SQLite 存储 → API 读回。
"""
from decimal import Decimal

import pytest


def _make_admin():
    u = type("U", (), {})()
    u.id = 1
    u.username = "admin1"
    u.role = "admin"
    u.is_superuser = True
    u.is_active = True
    u.organization_id = 1
    u.permissions_list = ["*"]
    return u


class TestMoneyRoundTrip:
    def test_project_budget_4_decimals_roundtrip(self, client):
        """创建项目 budget=1.23456 → 存储量化为 1.2346 → 详情读回一致。"""
        from app.core.security import get_current_user

        admin = _make_admin()
        original = client.app.dependency_overrides.copy()
        client.app.dependency_overrides[get_current_user] = lambda: admin
        try:
            resp = client.post("/api/v1/projects", json={
                "name": "精度回归项目",
                "type": "infrastructure",
                "budget": 1.23456,
            })
            assert resp.status_code in (200, 201), resp.text[:200]
            data = resp.json().get("data") or {}
            pid = data.get("id")

            detail = client.get(f"/api/v1/projects/{pid}")
            assert detail.status_code == 200
            body = detail.json().get("data") or {}
            stored = float(body.get("budget") or 0)
            assert abs(stored - 1.2346) < 1e-9, f"期望 1.2346，实际 {stored}"
        finally:
            client.app.dependency_overrides = original

    def test_fund_amount_4_decimals_roundtrip(self, client):
        """经费 amount=2.00025 → HALF_UP 进位为 2.0003。"""
        from app.core.security import get_current_user

        admin = _make_admin()
        original = client.app.dependency_overrides.copy()
        client.app.dependency_overrides[get_current_user] = lambda: admin
        try:
            resp = client.post("/api/v1/funds", json={
                "name": "精度回归经费",
                "amount": 2.00025,
                "status": "pending",
            })
            if resp.status_code in (403, 401):
                pytest.skip(f"权限环境不可用: {resp.status_code}")
            assert resp.status_code in (200, 201), resp.text[:200]
            fid = (resp.json().get("data") or {}).get("id")

            detail = client.get(f"/api/v1/funds/{fid}")
            assert detail.status_code == 200
            body = detail.json().get("data") or {}
            stored = float(body.get("amount") or 0)
            assert abs(stored - 2.0003) < 1e-9, f"期望 2.0003，实际 {stored}"
        finally:
            client.app.dependency_overrides = original

    def test_decimal_quantize_half_up_semantics(self):
        """写入层 ROUND_HALF_UP 语义锁定（非银行家舍入）。"""
        from app.utils.helpers import quantize_money

        # 0.5 界 → 远离零
        assert quantize_money(Decimal("0.00005")) == Decimal("0.0001")
        assert quantize_money(Decimal("-0.00005")) == Decimal("-0.0001")
        # 3 位小数输入不变（仅补齐位数）
        assert quantize_money(Decimal("1.234")) == Decimal("1.2340")
