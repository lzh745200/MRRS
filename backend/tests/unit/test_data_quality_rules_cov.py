"""data_quality API 覆盖率补充：validate_rules 全分支 + validate_data 分支（CI --cov-fail-under 门禁）"""
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def _authed_super_admin():
    """本文件聚焦规则引擎分支覆盖；认证/隔离行为由
    tests/unit/api/test_data_quality_auth_scope.py 覆盖。"""
    from app.api.v1.deps import get_current_active_user
    from app.main import app

    _user = Mock(id=1, username="admin", role="super_admin", is_superuser=True,
                 is_active=True, permissions_list=["*"], organization_id=1)
    original = app.dependency_overrides.get(get_current_active_user)
    app.dependency_overrides[get_current_active_user] = lambda: _user
    yield
    if original:
        app.dependency_overrides[get_current_active_user] = original
    else:
        app.dependency_overrides.pop(get_current_active_user, None)


class TestValidateRules:
    """自定义规则校验端点（/data-quality/validate-rules）全分支覆盖"""

    def _call(self, client, entity_type="village", rules=None):
        payload = {
            "entity_type": entity_type,
            "rules": rules or [{"field": "name", "operator": "eq", "value": "x"}],
        }
        return client.post("/api/v1/data-quality/validate-rules", json=payload)

    def test_unsupported_entity_type_400(self, client):
        resp = self._call(client, entity_type="unknown")
        assert resp.status_code == 400
        assert "不支持的模块" in resp.json()["detail"]

    def test_empty_records(self, client):
        resp = self._call(client, entity_type="school", rules=[{"field": "name", "operator": "eq", "value": "x"}])
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["total"] == 0
        assert data["matched_count"] == 0
        assert data["failed_count"] == 0

    def test_operators_all_branches(self, client):
        """eq/ne/contains/gt/lt/not_empty/is_empty/未知 operator 全分支"""
        from app.models.supported_village import SupportedVillage

        from app.core.database import get_db as _get_db
        db = next(client.app.dependency_overrides[_get_db]())
        db.add(SupportedVillage(village_name="示范村", province="贵州", transition_fund_military_total=1200))
        db.commit()

        cases = [
            # (field, operator, value, 期望 matched 数)
            ("village_name", "eq", "示范村", 1),
            ("village_name", "ne", "不存在", 1),
            ("village_name", "contains", "示范", 1),
            ("transition_fund_military_total", "gt", 1000, 1),  # 1200 > 1000
            ("transition_fund_military_total", "gt", "abc", 0),  # float 转换失败 → False
            ("transition_fund_military_total", "lt", 2000, 1),
            ("transition_fund_military_total", "lt", "abc", 0),
            ("village_name", "not_empty", None, 1),
            ("village_name", "is_empty", None, 0),
            ("village_name", "unknown_op", None, 0),  # 未知 operator → False
        ]
        for field, op, value, expected in cases:
            resp = self._call(
                client, entity_type="village",
                rules=[{"field": field, "operator": op, "value": value}],
            )
            assert resp.status_code == 200, f"op={op} 失败: {resp.text}"
            data = resp.json()["data"]
            assert data["matched_count"] == expected, f"op={op} expected {expected} got {data['matched_count']}"
            # 断言信封语义：code/success/message 顶层，data 内含统计
            assert resp.json()["success"] is True
            assert "校验完成" in resp.json()["message"]

    def test_logic_and_or(self, client):
        """logic=and/or 组合分支（复用 conftest client：CSRF 已禁用）"""
        from app.models.supported_village import SupportedVillage

        from app.core.database import get_db as _get_db
        db = next(client.app.dependency_overrides[_get_db]())
        db.add(SupportedVillage(village_name="甲村", transition_fund_military_total=500))
        db.add(SupportedVillage(village_name="乙村", transition_fund_military_total=3000))
        db.commit()
        try:
            # and 逻辑：population > 100 AND name contains 乙 → 只匹配乙村
            resp = client.post("/api/v1/data-quality/validate-rules", json={
                "entity_type": "village",
                "rules": [
                    {"field": "transition_fund_military_total", "operator": "gt", "value": 1000},
                    {"field": "village_name", "operator": "contains", "value": "乙", "logic": "and"},
                ],
            })
            assert resp.status_code == 200, resp.text
            assert resp.json()["data"]["matched_count"] == 1, f"and逻辑失败: {resp.text}"

            # or 逻辑：population < 100 OR name contains 乙 → 两村都匹配
            resp = client.post("/api/v1/data-quality/validate-rules", json={
                "entity_type": "village",
                "rules": [
                    {"field": "transition_fund_military_total", "operator": "lt", "value": 100},
                    {"field": "village_name", "operator": "contains", "value": "乙", "logic": "or"},
                ],
            })
            assert resp.status_code == 200, resp.text
            assert resp.json()["data"]["matched_count"] == 1, f"or逻辑失败: {resp.text}"  # 乙村

            # contains 单独验证（诊断）
            resp = client.post("/api/v1/data-quality/validate-rules", json={
                "entity_type": "village",
                "rules": [{"field": "village_name", "operator": "contains", "value": "乙"}],
            })
            assert resp.status_code == 200, resp.text
            assert resp.json()["data"]["matched_count"] == 1, f"contains单规则失败: {resp.text}"
        finally:
            db.query(SupportedVillage).delete()
            db.commit()

    def test_failed_records_payload(self, client):
        """failed 列表包含不满足记录（含 record_id/label/matched）"""
        from app.models.supported_village import SupportedVillage

        from app.core.database import get_db as _get_db
        db = next(client.app.dependency_overrides[_get_db]())
        db.add(SupportedVillage(village_name="不匹配村"))
        db.commit()
        resp = self._call(client, entity_type="village",
                          rules=[{"field": "village_name", "operator": "eq", "value": "不存在"}])
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["failed_count"] == 1
        assert data["failed"][0]["matched"] is False
        assert data["failed"][0]["label"] == "不匹配村"
        assert data["failed"][0]["record_id"] is not None


class TestValidateDataBranches:
    """validate_data 错误消息三种格式分支：dict / "field: message" / 纯消息"""

    def test_error_dict_and_plain_message(self, client):
        from unittest.mock import Mock
        from app.api.v1.deps import get_current_active_user
        from app.main import app

        _user = Mock(id=1, username="admin", role="admin", is_superuser=True, is_active=True,
                     permissions_list=["*"], organization_id=1)
        original_override = app.dependency_overrides.get(get_current_active_user)
        app.dependency_overrides[get_current_active_user] = lambda: _user
        try:
            self._run_validate_cases(client)
        finally:
            if original_override:
                app.dependency_overrides[get_current_active_user] = original_override
            else:
                app.dependency_overrides.pop(get_current_active_user, None)

    def _run_validate_cases(self, client):
        from app.services.validation_engine_service import ValidationEngine

        original = ValidationEngine.validate_with_db_rules
        ValidationEngine.validate_with_db_rules = Mock(side_effect=[
            [{"field": "name", "message": "dict 错误", "severity": "error"}],
            ["纯消息无冒号"],
            ["field_a: 带冒号消息"],
        ])
        try:
            import json

            # dict 格式
            resp = client.post("/api/v1/data-quality/validate", json={
                "entity_type": "village", "data": {"name": ""},
            })
            assert resp.status_code == 200
            assert resp.json()["data"]["issues"][0]["field"] == "name"

            # 纯消息（无冒号）→ field 回退 request.field_name
            resp = client.post("/api/v1/data-quality/validate", json={
                "entity_type": "village", "data": {"name": ""}, "field_name": "兜底字段",
            })
            assert resp.status_code == 200
            assert resp.json()["data"]["issues"][0]["field"] == "兜底字段"
            assert resp.json()["data"]["valid"] is False

            # "field: message" 格式
            resp = client.post("/api/v1/data-quality/validate", json={
                "entity_type": "village", "data": {"name": ""},
            })
            assert resp.status_code == 200
            assert resp.json()["data"]["issues"][0]["field"] == "field_a"
        finally:
            ValidationEngine.validate_with_db_rules = original

