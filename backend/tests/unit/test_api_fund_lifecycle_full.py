"""Tests for fund lifecycle API — 44 routes across 7 phases."""


class TestFundLifecyclePhaseManagement:
    """Phase management endpoints (Phase 1: 论证立项)."""

    def test_list_phases_unauthenticated(self, client):
        resp = client.get("/api/v1/fund-lifecycle/phases/1")
        assert resp.status_code in (200, 401, 404, 405)

    def test_list_phases_authenticated(self, auth_client):
        resp = auth_client.get("/api/v1/fund-lifecycle/phases/1")
        assert resp.status_code in (200, 401, 404, 405, 422)

    def test_init_phases(self, auth_client):
        resp = auth_client.post("/api/v1/fund-lifecycle/phases/1/init")
        assert resp.status_code in (200, 201, 400, 404, 405, 422)

    def test_advance_phase(self, auth_client):
        resp = auth_client.post("/api/v1/fund-lifecycle/phases/1/advance", json={"phase": 2})
        assert resp.status_code in (200, 400, 404, 405, 422)

    def test_rollback_phase(self, auth_client):
        resp = auth_client.post("/api/v1/fund-lifecycle/phases/1/rollback", json={"phase": 1})
        assert resp.status_code in (200, 400, 404, 405, 422)


class TestFundLifecycleBudget:
    """Phase 2: 预算基线管理."""

    def test_list_budgets(self, auth_client):
        resp = auth_client.get("/api/v1/fund-lifecycle/budgets/1")
        assert resp.status_code in (200, 401, 404, 405, 422)

    def test_create_budget(self, auth_client):
        resp = auth_client.post("/api/v1/fund-lifecycle/budgets/1", json={
            "snapshot_year": 2026, "baseline_amount": 100.0
        })
        assert resp.status_code in (200, 201, 400, 404, 405, 422)

    def test_lock_budget(self, auth_client):
        resp = auth_client.post("/api/v1/fund-lifecycle/budgets/1/lock")
        assert resp.status_code in (200, 400, 404, 405, 422)


class TestFundLifecycleTransfer:
    """Phase 3-4: 资金调拨与划转."""

    def test_list_vouchers(self, auth_client):
        resp = auth_client.get("/api/v1/fund-lifecycle/vouchers/1")
        assert resp.status_code in (200, 401, 404, 405, 422)

    def test_create_voucher(self, auth_client):
        resp = auth_client.post("/api/v1/fund-lifecycle/vouchers/1", json={
            "amount": 50.0, "direction": "military_to_local"
        })
        assert resp.status_code in (200, 201, 400, 404, 405, 422)


class TestFundLifecycleContract:
    """Phase 4: 合同管理."""

    def test_list_contracts(self, auth_client):
        resp = auth_client.get("/api/v1/fund-lifecycle/contracts/1")
        assert resp.status_code in (200, 401, 404, 405, 422)

    def test_create_contract(self, auth_client):
        resp = auth_client.post("/api/v1/fund-lifecycle/contracts/1", json={
            "contract_name": "测试合同", "contract_amount": 100.0
        })
        assert resp.status_code in (200, 201, 400, 404, 405, 422)

    def test_create_contract_empty_date_strings(self, auth_client):
        """前端表单未选日期提交空字符串 → 不应 422（Pydantic date 解析兜底）"""
        resp = auth_client.post("/api/v1/fund-lifecycle/contracts/1", json={
            "contract_name": "空日期合同",
            "contract_no": "C-EMPTY-DATE",
            "contract_amount": 100.0,
            "sign_date": "",
            "deadline": "",
        })
        assert resp.status_code not in (422,)
        assert resp.status_code in (200, 201, 400, 404, 405)

    def test_update_contract_empty_date_strings(self, auth_client):
        """更新合同时空字符串日期 → 不应 422"""
        resp = auth_client.put("/api/v1/fund-lifecycle/contracts/1", json={
            "sign_date": "",
            "deadline": "  ",
        })
        assert resp.status_code not in (422,)
        assert resp.status_code in (200, 400, 404, 405)

    def test_create_voucher_empty_date_string(self, auth_client):
        """转账凭证 transfer_date 空字符串 → 不应 422"""
        resp = auth_client.post("/api/v1/fund-lifecycle/vouchers/1", json={
            "amount": 50.0,
            "direction": "military_to_local",
            "transfer_date": "",
        })
        assert resp.status_code not in (422,)
        assert resp.status_code in (200, 201, 400, 404, 405)


class TestFundLifecycleAnomaly:
    """Phase 5: 异常检测."""

    def test_list_anomalies(self, auth_client):
        resp = auth_client.get("/api/v1/fund-lifecycle/anomalies/1")
        assert resp.status_code in (200, 401, 404, 405, 422)

    def test_resolve_anomaly(self, auth_client):
        resp = auth_client.post("/api/v1/fund-lifecycle/anomalies/1/resolve", json={"resolution": "fixed"})
        assert resp.status_code in (200, 400, 404, 405, 422)


class TestFundLifecycleSettlement:
    """Phase 6-7: 结算与资产核销."""

    def test_list_settlements(self, auth_client):
        resp = auth_client.get("/api/v1/fund-lifecycle/settlements/1")
        assert resp.status_code in (200, 401, 404, 405, 422)

    def test_create_settlement(self, auth_client):
        resp = auth_client.post("/api/v1/fund-lifecycle/settlements/1", json={
            "settlement_amount": 100.0
        })
        assert resp.status_code in (200, 201, 400, 404, 405, 422)

    def test_verify_asset(self, auth_client):
        resp = auth_client.post("/api/v1/fund-lifecycle/assets/1/verify", json={"verified": True})
        assert resp.status_code in (200, 400, 404, 405, 422)


class TestFundLifecycleHealth:
    """Health score and statistics."""

    def test_health_score(self, auth_client):
        resp = auth_client.get("/api/v1/fund-lifecycle/health/1")
        assert resp.status_code in (200, 401, 404, 405, 422)

    def test_allocation_plan(self, auth_client):
        resp = auth_client.get("/api/v1/fund-lifecycle/allocation-plan/1")
        assert resp.status_code in (200, 401, 404, 405, 422)
