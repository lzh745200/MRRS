"""
Tests for validation.py — data validation rules API, CRUD + validate endpoint.
Covers list_rules, create_rule, update_rule, delete_rule, validate_data, _check_rule.
"""
import json
from unittest.mock import MagicMock, patch
import pytest

BASE = "/api/v1/validation"


# ── list_rules ───────────────────────────────────────────────────────

class TestListRules:
    def test_requires_auth(self, client):
        resp = client.get(f"{BASE}/rules")
        assert resp.status_code == 401

    def test_all_rules(self, client_with_mocked_auth):
        resp = client_with_mocked_auth.get(f"{BASE}/rules")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_filter_by_module(self, client_with_mocked_auth):
        resp = client_with_mocked_auth.get(f"{BASE}/rules?module=test")
        assert resp.status_code == 200

    def test_filter_by_active(self, client_with_mocked_auth):
        resp = client_with_mocked_auth.get(f"{BASE}/rules?is_active=true")
        assert resp.status_code == 200

    def test_filter_by_inactive(self, client_with_mocked_auth):
        resp = client_with_mocked_auth.get(f"{BASE}/rules?is_active=false")
        assert resp.status_code == 200


# ── create_rule ──────────────────────────────────────────────────────

class TestCreateRule:
    def test_requires_auth(self, client):
        resp = client.post(f"{BASE}/rules", json={"module": "t", "field": "f", "rule_type": "required"})
        assert resp.status_code == 401

    def test_create_success(self, client_with_mocked_auth):
        resp = client_with_mocked_auth.post(
            f"{BASE}/rules",
            json={"module": "villages", "field": "name", "rule_type": "required", "error_message": "名称必填"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["module"] == "villages"

    def test_create_invalid_json_params(self, client_with_mocked_auth):
        resp = client_with_mocked_auth.post(
            f"{BASE}/rules",
            json={"module": "t", "field": "f", "rule_type": "regex", "params": "not-json"},
        )
        assert resp.status_code == 400
        assert "JSON" in resp.text or "json" in resp.text.lower()

    def test_create_with_valid_params(self, client_with_mocked_auth):
        resp = client_with_mocked_auth.post(
            f"{BASE}/rules",
            json={"module": "t", "field": "f", "rule_type": "max_length",
                  "params": json.dumps({"max": 100}), "priority": 50},
        )
        assert resp.status_code == 200

    def test_create_all_fields(self, client_with_mocked_auth):
        resp = client_with_mocked_auth.post(
            f"{BASE}/rules",
            json={"module": "m", "field": "f", "rule_type": "range",
                  "params": json.dumps({"min": 0, "max": 100}),
                  "error_message": "范围错误", "description": "test", "is_active": True, "priority": 10},
        )
        assert resp.status_code == 200


# ── update_rule ──────────────────────────────────────────────────────

class TestUpdateRule:
    def test_update_not_found(self, client_with_mocked_auth):
        resp = client_with_mocked_auth.put(f"{BASE}/rules/99999", json={"field": "x"})
        assert resp.status_code == 404

    def test_update_success(self, client_with_mocked_auth):
        create_resp = client_with_mocked_auth.post(
            f"{BASE}/rules", json={"module": "t", "field": "f", "rule_type": "required"},
        )
        rule_id = create_resp.json()["id"]
        resp = client_with_mocked_auth.put(
            f"{BASE}/rules/{rule_id}",
            json={"field": "new_field", "error_message": "new error"},
        )
        assert resp.status_code == 200
        assert resp.json()["field"] == "new_field"

    def test_update_invalid_params(self, client_with_mocked_auth):
        create_resp = client_with_mocked_auth.post(
            f"{BASE}/rules", json={"module": "t", "field": "f", "rule_type": "required"},
        )
        rule_id = create_resp.json()["id"]
        resp = client_with_mocked_auth.put(
            f"{BASE}/rules/{rule_id}", json={"params": "bad-json"},
        )
        assert resp.status_code == 400

    def test_update_deactivate(self, client_with_mocked_auth):
        create_resp = client_with_mocked_auth.post(
            f"{BASE}/rules", json={"module": "t", "field": "f", "rule_type": "required"},
        )
        rule_id = create_resp.json()["id"]
        resp = client_with_mocked_auth.put(
            f"{BASE}/rules/{rule_id}", json={"is_active": False},
        )
        assert resp.status_code == 200
        assert resp.json()["is_active"] is False


# ── delete_rule ──────────────────────────────────────────────────────

class TestDeleteRule:
    def test_delete_not_found(self, client_with_mocked_auth):
        resp = client_with_mocked_auth.delete(f"{BASE}/rules/99999")
        assert resp.status_code == 404

    def test_delete_success(self, client_with_mocked_auth):
        create_resp = client_with_mocked_auth.post(
            f"{BASE}/rules", json={"module": "t", "field": "f", "rule_type": "required"},
        )
        rule_id = create_resp.json()["id"]
        resp = client_with_mocked_auth.delete(f"{BASE}/rules/{rule_id}")
        assert resp.status_code == 200
        assert resp.json()["message"] == "规则已删除"


# ── validate_data ────────────────────────────────────────────────────

class TestValidateData:
    def test_validate_no_rules(self, client_with_mocked_auth):
        resp = client_with_mocked_auth.post(
            f"{BASE}/validate?module=empty_module",
            json={"name": "test"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["valid"] is True
        assert data["errors"] == []

    def test_validate_with_active_rules(self, client_with_mocked_auth):
        client_with_mocked_auth.post(
            f"{BASE}/rules",
            json={"module": "profile", "field": "name", "rule_type": "required", "is_active": True},
        )
        resp = client_with_mocked_auth.post(
            f"{BASE}/validate?module=profile",
            json={"name": "John"},
        )
        assert resp.status_code == 200
        assert resp.json()["valid"] is True

    def test_validate_fails_required(self, client_with_mocked_auth):
        client_with_mocked_auth.post(
            f"{BASE}/rules",
            json={"module": "profile", "field": "email", "rule_type": "required", "is_active": True},
        )
        resp = client_with_mocked_auth.post(
            f"{BASE}/validate?module=profile",
            json={"name": "John"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["valid"] is False
        assert any(e["field"] == "email" for e in data["errors"])

    def test_validate_multiple_rules(self, client_with_mocked_auth):
        for f in ["a", "b"]:
            client_with_mocked_auth.post(
                f"{BASE}/rules",
                json={"module": "multi", "field": f, "rule_type": "required", "is_active": True},
            )
        resp = client_with_mocked_auth.post(
            f"{BASE}/validate?module=multi",
            json={"a": "ok"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["valid"] is False
        field_names = [e["field"] for e in data["errors"]]
        assert "b" in field_names

    def test_validate_fails_regex(self, client_with_mocked_auth):
        client_with_mocked_auth.post(
            f"{BASE}/rules",
            json={"module": "fmt", "field": "phone", "rule_type": "regex",
                  "params": json.dumps({"pattern": "^1[3-9]\\d{9}$"}), "is_active": True},
        )
        resp = client_with_mocked_auth.post(
            f"{BASE}/validate?module=fmt",
            json={"phone": "123"},
        )
        assert resp.status_code == 200
        assert resp.json()["valid"] is False

    def test_validate_field_label_in_error(self, client_with_mocked_auth):
        client_with_mocked_auth.post(
            f"{BASE}/rules",
            json={"module": "villages", "field": "village_name", "rule_type": "required",
                  "error_message": "数据校验失败", "is_active": True},
        )
        resp = client_with_mocked_auth.post(
            f"{BASE}/validate?module=villages",
            json={},
        )
        data = resp.json()
        assert data["valid"] is False
        error = data["errors"][0]
        assert error["field_label"] == "帮扶村名称"


# ── _check_rule internals ────────────────────────────────────────────

def _make_rule(rule_type, params=None):
    r = MagicMock()
    r.rule_type = rule_type
    r.params = json.dumps(params) if params else None
    return r

class TestCheckRule:
    def test_required_none(self):
        from app.api.v1.validation import _check_rule
        assert _check_rule(_make_rule("required"), None, {}, {}) is True

    def test_required_empty_string(self):
        from app.api.v1.validation import _check_rule
        assert _check_rule(_make_rule("required"), "", {}, {}) is True

    def test_required_value_present(self):
        from app.api.v1.validation import _check_rule
        assert _check_rule(_make_rule("required"), "x", {}, {}) is False

    def test_positive_valid(self):
        from app.api.v1.validation import _check_rule
        assert _check_rule(_make_rule("positive"), 5, {}, {}) is False

    def test_positive_zero(self):
        from app.api.v1.validation import _check_rule
        assert _check_rule(_make_rule("positive"), 0, {}, {}) is True

    def test_positive_negative(self):
        from app.api.v1.validation import _check_rule
        assert _check_rule(_make_rule("positive"), -1, {}, {}) is True

    def test_positive_bad_value(self):
        from app.api.v1.validation import _check_rule
        assert _check_rule(_make_rule("positive"), "abc", {}, {}) is True

    def test_non_negative_valid(self):
        from app.api.v1.validation import _check_rule
        assert _check_rule(_make_rule("non_negative"), 0, {}, {}) is False

    def test_non_negative_negative(self):
        from app.api.v1.validation import _check_rule
        assert _check_rule(_make_rule("non_negative"), -1, {}, {}) is True

    def test_non_negative_bad(self):
        from app.api.v1.validation import _check_rule
        assert _check_rule(_make_rule("non_negative"), "abc", {}, {}) is True

    def test_max_length_exceeded(self):
        from app.api.v1.validation import _check_rule
        r = _make_rule("max_length", {"max": 3})
        assert _check_rule(r, "abcd", {"max": 3}, {}) is True

    def test_max_length_ok(self):
        from app.api.v1.validation import _check_rule
        assert _check_rule(_make_rule("max_length", {"max": 5}), "abcd", {}, {}) is False

    def test_min_length_below(self):
        from app.api.v1.validation import _check_rule
        r = _make_rule("min_length", {"min": 3})
        assert _check_rule(r, "ab", {"min": 3}, {}) is True

    def test_min_length_ok(self):
        from app.api.v1.validation import _check_rule
        assert _check_rule(_make_rule("min_length", {"min": 2}), "ab", {}, {}) is False

    def test_range_below_min(self):
        from app.api.v1.validation import _check_rule
        r = _make_rule("range", {"min": 1, "max": 10})
        assert _check_rule(r, 0, {"min": 1, "max": 10}, {}) is True

    def test_range_above_max(self):
        from app.api.v1.validation import _check_rule
        r = _make_rule("range", {"min": 1, "max": 10})
        assert _check_rule(r, 11, {"min": 1, "max": 10}, {}) is True

    def test_range_valid(self):
        from app.api.v1.validation import _check_rule
        assert _check_rule(_make_rule("range", {"min": 1, "max": 10}), 5, {}, {}) is False

    def test_range_bad_value(self):
        from app.api.v1.validation import _check_rule
        assert _check_rule(_make_rule("range", {"min": 1}), "abc", {}, {}) is True

    def test_regex_match(self):
        from app.api.v1.validation import _check_rule
        assert _check_rule(_make_rule("regex", {"pattern": "^\\d+$"}), "123", {}, {}) is False

    def test_regex_no_match(self):
        from app.api.v1.validation import _check_rule
        r = _make_rule("regex", {"pattern": "^\\d+$"})
        assert _check_rule(r, "abc", {"pattern": "^\\d+$"}, {}) is True

    def test_date_format_valid(self):
        from app.api.v1.validation import _check_rule
        assert _check_rule(_make_rule("date_format", {"format": "%Y-%m-%d"}), "2024-01-01", {}, {}) is False

    def test_date_format_invalid(self):
        from app.api.v1.validation import _check_rule
        assert _check_rule(_make_rule("date_format", {"format": "%Y-%m-%d"}), "not-a-date", {}, {}) is True

    def test_file_type_allowed(self):
        from app.api.v1.validation import _check_rule
        r = _make_rule("file_type", {"allowed": ["pdf", "docx"]})
        assert _check_rule(r, "file.pdf", {"allowed": ["pdf", "docx"]}, {}) is False

    def test_file_type_denied(self):
        from app.api.v1.validation import _check_rule
        assert _check_rule(_make_rule("file_type", {"allowed": ["pdf"]}), "file.exe", {}, {}) is True

    def test_enum_values_valid(self):
        from app.api.v1.validation import _check_rule
        r = _make_rule("enum_values", {"values": ["a", "b"]})
        assert _check_rule(r, "a", {"values": ["a", "b"]}, {}) is False

    def test_enum_values_invalid(self):
        from app.api.v1.validation import _check_rule
        assert _check_rule(_make_rule("enum_values", {"values": ["a", "b"]}), "c", {}, {}) is True

    def test_cross_field_less_equal_ok(self):
        from app.api.v1.validation import _check_rule
        r = _make_rule("cross_field", {"operator": "<=", "other_field": "max"})
        assert _check_rule(r, 5, {"operator": "<=", "other_field": "max"}, {"max": 5}) is False

    def test_cross_field_less_equal_fail(self):
        from app.api.v1.validation import _check_rule
        r = _make_rule("cross_field", {"operator": "<=", "other_field": "max"})
        assert _check_rule(r, 15, {"operator": "<=", "other_field": "max"}, {"max": 10}) is True

    def test_cross_field_greater_equal_ok(self):
        from app.api.v1.validation import _check_rule
        r = _make_rule("cross_field", {"operator": ">=", "other_field": "min"})
        assert _check_rule(r, 5, {"operator": ">=", "other_field": "min"}, {"min": 5}) is False

    def test_cross_field_greater_equal_fail(self):
        from app.api.v1.validation import _check_rule
        r = _make_rule("cross_field", {"operator": ">=", "other_field": "min"})
        assert _check_rule(r, 5, {"operator": ">=", "other_field": "min"}, {"min": 10}) is True

    def test_cross_field_less_ok(self):
        from app.api.v1.validation import _check_rule
        r = _make_rule("cross_field", {"operator": "<", "other_field": "max"})
        assert _check_rule(r, 4, {"operator": "<", "other_field": "max"}, {"max": 5}) is False

    def test_cross_field_less_fail(self):
        from app.api.v1.validation import _check_rule
        r = _make_rule("cross_field", {"operator": "<", "other_field": "max"})
        assert _check_rule(r, 5, {"operator": "<", "other_field": "max"}, {"max": 4}) is True

    def test_cross_field_greater_ok(self):
        from app.api.v1.validation import _check_rule
        r = _make_rule("cross_field", {"operator": ">", "other_field": "min"})
        assert _check_rule(r, 6, {"operator": ">", "other_field": "min"}, {"min": 5}) is False

    def test_cross_field_greater_fail(self):
        from app.api.v1.validation import _check_rule
        r = _make_rule("cross_field", {"operator": ">", "other_field": "min"})
        assert _check_rule(r, 4, {"operator": ">", "other_field": "min"}, {"min": 5}) is True

    def test_cross_field_equal_ok(self):
        from app.api.v1.validation import _check_rule
        r = _make_rule("cross_field", {"operator": "==", "other_field": "confirm"})
        assert _check_rule(r, 5, {"operator": "==", "other_field": "confirm"}, {"confirm": 5}) is False

    def test_cross_field_equal_fail(self):
        from app.api.v1.validation import _check_rule
        r = _make_rule("cross_field", {"operator": "==", "other_field": "confirm"})
        assert _check_rule(r, 4, {"operator": "==", "other_field": "confirm"}, {"confirm": 5}) is True

    def test_cross_field_bad_value(self):
        from app.api.v1.validation import _check_rule
        r = _make_rule("cross_field", {"operator": "<=", "other_field": "max"})
        assert _check_rule(r, "abc", {"operator": "<=", "other_field": "max"}, {"max": 5}) is True

    def test_cross_field_missing_other_field(self):
        from app.api.v1.validation import _check_rule
        r = _make_rule("cross_field", {"operator": "<=", "other_field": "missing"})
        assert _check_rule(r, 5, {"operator": "<=", "other_field": "missing"}, {}) is False

    def test_unknown_rule_type(self):
        from app.api.v1.validation import _check_rule
        r = _make_rule("unknown_type")
        r.rule_type = None
        assert _check_rule(r, "val", {}, {}) is False

    def test_none_value_skips_non_required(self):
        from app.api.v1.validation import _check_rule
        assert _check_rule(_make_rule("positive"), None, {}, {}) is False


# ── query-check / fields（小白友好条件查询校验） ──────────────────────

class TestQueryCheck:
    def test_fields_endpoint(self, client_with_mocked_auth):
        resp = client_with_mocked_auth.get(f"{BASE}/fields?module=village")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["module"] == "village"
        assert any(f["key"] == "village_name" for f in data["fields"])

    def test_fields_unsupported_module(self, client_with_mocked_auth):
        resp = client_with_mocked_auth.get(f"{BASE}/fields?module=unknown")
        assert resp.status_code == 400

    def test_query_check_success(self, client_with_mocked_auth):
        resp = client_with_mocked_auth.post(
            f"{BASE}/query-check",
            json={
                "module": "village",
                "logic": "and",
                "conditions": [
                    {"field": "county", "operator": "eq", "value": "赫章县"},
                    {"field": "village_name", "operator": "not_empty", "value": None},
                ],
            },
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert "total" in data and "matched" in data and "results" in data
        assert data["condition_count"] == 2

    def test_query_check_invalid_field(self, client_with_mocked_auth):
        resp = client_with_mocked_auth.post(
            f"{BASE}/query-check",
            json={
                "module": "village",
                "logic": "and",
                "conditions": [{"field": "no_such_column", "operator": "eq", "value": "x"}],
            },
        )
        assert resp.status_code == 400

    def test_query_check_invalid_module(self, client_with_mocked_auth):
        resp = client_with_mocked_auth.post(
            f"{BASE}/query-check",
            json={"module": "bad", "logic": "and", "conditions": [{"field": "x", "operator": "eq", "value": "1"}]},
        )
        assert resp.status_code == 400

    def test_query_check_invalid_logic(self, client_with_mocked_auth):
        resp = client_with_mocked_auth.post(
            f"{BASE}/query-check",
            json={"module": "village", "logic": "xor", "conditions": [{"field": "county", "operator": "eq", "value": "x"}]},
        )
        assert resp.status_code == 400
