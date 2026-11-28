"""角色/数据范围单一事实源回归（2026-11-28 RBAC 精简）。"""

from app.api.v1.auth.users import DATA_SCOPE_OPTIONS, ROLE_OPTIONS
from app.core.constants import (
    ACCOUNT_PACKAGE_DATA_SCOPES,
    ACCOUNT_PACKAGE_ROLES,
    ALL_ROLES,
    DATA_SCOPES,
    ROLE_ADMIN,
    ROLE_LABELS,
    ROLE_SUPER_ADMIN,
    ROLE_USER,
    ROLE_VIEWER,
    normalize_role,
)


def test_exactly_four_system_roles():
    assert ALL_ROLES == [ROLE_SUPER_ADMIN, ROLE_ADMIN, ROLE_USER, ROLE_VIEWER]
    assert set(ROLE_LABELS) == {ROLE_SUPER_ADMIN, ROLE_ADMIN, ROLE_USER, ROLE_VIEWER}
    assert ROLE_LABELS[ROLE_SUPER_ADMIN] == "超级管理员"
    assert ROLE_LABELS[ROLE_ADMIN] == "系统管理员"
    assert ROLE_LABELS[ROLE_USER] == "普通用户"
    assert ROLE_LABELS[ROLE_VIEWER] == "访客"


def test_role_options_are_derived_from_constants():
    assert [item["value"] for item in ROLE_OPTIONS] == ALL_ROLES
    for item in ROLE_OPTIONS:
        assert item["label"] == ROLE_LABELS[item["value"]]
        assert item["description"]


def test_data_scope_options_are_four_and_ordered():
    assert DATA_SCOPES == ("all", "org_children", "org", "self")
    assert [item["value"] for item in DATA_SCOPE_OPTIONS] == list(DATA_SCOPES)


def test_account_package_roles_exclude_super_admin():
    assert ROLE_SUPER_ADMIN not in ACCOUNT_PACKAGE_ROLES
    assert set(ACCOUNT_PACKAGE_ROLES) == {ROLE_ADMIN, ROLE_USER, ROLE_VIEWER}
    assert "all" not in ACCOUNT_PACKAGE_DATA_SCOPES
    assert set(ACCOUNT_PACKAGE_DATA_SCOPES) <= set(DATA_SCOPES)


def test_legacy_roles_normalize_to_four_values():
    assert normalize_role("approval_leader") == ROLE_ADMIN
    assert normalize_role("manager") == ROLE_ADMIN
    assert normalize_role("operator") == ROLE_USER
    assert normalize_role(None) == ROLE_USER
    assert normalize_role("") == ROLE_USER
    # 未知值原样返回，由调用方校验拒绝，不静默提权
    assert normalize_role("mystery") == "mystery"
