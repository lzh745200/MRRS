# -*- coding: utf-8 -*-
"""R33：单位授权矩阵（org_grants）模型 + 权限包 grants 派生。

覆盖点：
- `OrgGrant` 的列默认值、唯一约束、级别常量序；
- `PermissionPack.grants_dict` 的四条分支（合法矩阵 / 非法 JSON / 非 dict / 空→由
  `menu_keys` 派生），派生规则是"老包一律按 edit"，保证升级不改变存量行为；
- `Organization` 新增的 5 个授权元信息列。
"""

from app.models.org_grant import (
    DEFAULT_GRANT_LEVEL,
    LEVEL_RANK,
    VALID_GRANT_LEVELS,
    OrgGrant,
)
from app.models.organization import Organization
from app.models.permission_pack import PermissionPack


class TestOrgGrantColumns:
    def test_level_defaults_to_none(self):
        col = OrgGrant.__table__.c.level
        assert col.default.arg == DEFAULT_GRANT_LEVEL == "none"
        assert col.server_default.arg == "none"

    def test_organization_and_module_are_required(self):
        assert OrgGrant.__table__.c.organization_id.nullable is False
        assert OrgGrant.__table__.c.module_key.nullable is False

    def test_unique_constraint_declared(self):
        names = {c.name for c in OrgGrant.__table__.constraints if getattr(c, "name", None)}
        assert "uq_org_grant" in names

    def test_columns_indexed(self):
        indexed = {c.name for c in OrgGrant.__table__.c if c.index}
        assert {"organization_id", "module_key"} <= indexed

    def test_repr_includes_org_module_level(self):
        grant = OrgGrant(organization_id=7, module_key="funds", level="view")
        text = repr(grant)
        assert "org=7" in text and "funds" in text and "view" in text

    def test_level_constants_ordering(self):
        assert VALID_GRANT_LEVELS == {"view", "edit", "none"}
        assert LEVEL_RANK["none"] < LEVEL_RANK["view"] < LEVEL_RANK["edit"]


class TestPermissionPackGrantsDict:
    def test_valid_matrix_parsed(self):
        pack = PermissionPack(name="p", grants='{"projects": "edit", "funds": "view"}')
        assert pack.grants_dict == {"projects": "edit", "funds": "view"}

    def test_illegal_levels_are_dropped(self):
        """拼错/非字符串的级别一律丢弃，绝不默认放行。"""
        pack = PermissionPack(
            name="p",
            grants='{"projects": "own", "funds": 1, "ok": "view", "ok2": "none"}',
        )
        assert pack.grants_dict == {"ok": "view", "ok2": "none"}

    def test_invalid_json_falls_back_to_menu_keys(self):
        pack = PermissionPack(name="p", grants="{bad", menu_keys='["projects"]')
        assert pack.grants_dict == {"projects": "edit"}

    def test_non_dict_grants_falls_back_to_menu_keys(self):
        pack = PermissionPack(name="p", grants='["projects"]', menu_keys='["funds"]')
        assert pack.grants_dict == {"funds": "edit"}

    def test_empty_grants_derives_edit_from_menu_keys(self):
        """向后兼容：只有 menu_keys 的老包，其菜单一律按可写生效。"""
        pack = PermissionPack(name="p", menu_keys='["a", "b"]')
        assert pack.grants_dict == {"a": "edit", "b": "edit"}

    def test_no_grants_no_menu_keys_is_empty(self):
        pack = PermissionPack(name="p")
        assert pack.grants_dict == {}

    def test_menu_keys_invalid_json_yields_empty(self):
        pack = PermissionPack(name="p", menu_keys="{bad")
        assert pack.grants_dict == {}


class TestOrganizationGrantColumns:
    NEW_COLUMNS = (
        "grant_version",
        "grant_signature",
        "grant_applied_at",
        "grant_source",
        "inherit_from_parent",
    )

    def test_all_grant_columns_present(self):
        cols = set(Organization.__table__.c.keys())
        for name in self.NEW_COLUMNS:
            assert name in cols, "缺少列 %s" % name

    def test_grant_version_defaults_to_zero(self):
        assert Organization.__table__.c.grant_version.default.arg == 0
        assert Organization.__table__.c.grant_version.server_default.arg == "0"

    def test_inherit_from_parent_defaults_true(self):
        """默认继承上级 —— 下级未显式切断时按组织树合并。"""
        assert Organization.__table__.c.inherit_from_parent.default.arg is True
        assert Organization.__table__.c.inherit_from_parent.server_default.arg == "1"

    def test_signature_and_source_nullable(self):
        assert Organization.__table__.c.grant_signature.nullable is True
        assert Organization.__table__.c.grant_source.nullable is True
