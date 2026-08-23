"""补齐 app.services.permission_package_service 覆盖率缺口。

目标行：
- 145：export_package 收集启用组织（organizations_data.append）
- 411-453：_import_organizations 全分支（无 name 跳过 / 按 code 匹配更新 /
  按 name 匹配更新 / 无 code 更新 / 新建组织）
- 573-579：_import_user_legacy 组织关联恢复（按 ID 命中恢复 / 未命中置空）

db 使用 MagicMock 链式 mock；导出 ZIP 写入 tmp_path 真实校验内容。
"""

import json
import zipfile
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.services.permission_package_service import PermissionPackageService


class TestExportPackageOrganizations:
    def test_export_includes_active_organizations(self, tmp_path):
        db = MagicMock()
        q = db.query.return_value
        q.filter.return_value = q
        q.order_by.return_value.all.return_value = []  # RbacRole 列表为空
        org = SimpleNamespace(id=7, name="帮扶办", code="BF001", is_active=True)
        # all() 调用顺序（T08 起）：User(id,name) / RbacRole(id,name) /
        # Organization(id,code) 映射查询 ×3 → UserRole → UserPermission →
        # User(启用) → Organization(启用)
        q.all.side_effect = [[], [], [], [], [], [], [org]]

        with patch("app.utils.paths.get_uploads_path", return_value=tmp_path):
            svc = PermissionPackageService(db)
            result = svc.export_package(description="覆盖测试导出")

        assert result["success"] is True
        assert result["user_count"] == 0
        assert result["role_count"] == 0
        assert "1 个组织" in result["message"]

        with zipfile.ZipFile(result["file_path"], "r") as zf:
            orgs = json.loads(zf.read("data/organizations.json").decode("utf-8"))
        assert orgs == [{
            "id": 7,
            "name": "帮扶办",
            "code": "BF001",
            "org_type": None,
            "level": None,
            "parent_id": None,
            "is_active": True,
            "sort_order": 0,
        }]


class TestImportOrganizations:
    @staticmethod
    def _existing_org(**kw):
        base = {"code": None, "org_type": "乡镇", "level": 1, "is_active": True, "sort_order": 1}
        base.update(kw)
        return SimpleNamespace(**base)

    def test_all_branches(self):
        db = MagicMock()
        q = db.query.return_value
        q.filter.return_value = q
        by_code = self._existing_org()
        by_name = self._existing_org()
        no_code = self._existing_org()
        # first() 顺序：B(code 命中) → C(code 未中) → C(name 命中)
        #              → D(name 命中) → E(code 未中) → E(name 未中)
        q.first.side_effect = [by_code, None, by_name, no_code, None, None]

        svc = PermissionPackageService(db)
        stats = svc._init_import_stats()
        stats, errors = svc._import_organizations(
            [
                {"code": "C0"},                                # 无 name → 跳过
                {"name": "B", "code": "CB", "sort_order": 5},  # 按 code 匹配 → 更新
                {"name": "C", "code": "CC"},                   # 按 name 匹配 → 更新
                {"name": "D"},                                 # 无 code → 按 name 匹配 → 更新
                {"name": "E", "code": "CE", "org_type": "县"},  # 均未命中 → 新建
            ],
            stats,
            [],
        )

        assert errors == []
        assert stats["organizations_updated"] == 3
        assert stats["organizations_created"] == 1
        assert by_code.code == "CB"
        assert by_code.sort_order == 5
        assert by_name.code == "CC"
        assert no_code.code is None  # 无 code 时不回写 code 字段
        db.add.assert_called_once()
        new_org = db.add.call_args.args[0]
        assert new_org.name == "E"
        assert new_org.code == "CE"
        assert new_org.org_type == "县"
        db.flush.assert_called_once()


class TestImportUserLegacyOrgRestore:
    def test_org_found_restores_and_missing_org_clears(self):
        db = MagicMock()
        q = db.query.return_value
        q.filter.return_value = q
        user_hit = SimpleNamespace(
            username="u1", role="operator", permissions="", data_scope="org", organization_id=None,
        )
        user_miss = SimpleNamespace(
            username="u2", role="operator", permissions="", data_scope="org", organization_id=5,
        )
        org = SimpleNamespace(id=10)
        # first() 顺序：User(u1) → Organization(10) → User(u2) → Organization(99)
        q.first.side_effect = [user_hit, org, user_miss, None]

        svc = PermissionPackageService(db)
        stats = svc._init_import_stats()
        stats, errors = svc._import_user_legacy(
            [
                {"username": "u1", "organization_id": 10},
                {"username": "u2", "organization_id": 99},
            ],
            stats,
            [],
        )

        assert errors == []
        assert stats["user_legacy_updated"] == 2
        assert user_hit.organization_id == 10  # 组织 ID 命中 → 恢复关联
        assert user_miss.organization_id is None  # 组织 ID 未命中 → 置空
