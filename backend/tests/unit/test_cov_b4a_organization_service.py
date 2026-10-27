"""覆盖率攻坚: app/services/organization_service.py 缺口行 289（get_ancestors 路径与 ID 不匹配）."""
import asyncio
from types import SimpleNamespace
from unittest.mock import MagicMock, patch


def _make_service(org):
    from app.services.organization_service import OrganizationService

    svc = OrganizationService(db=MagicMock())
    svc.get_organization = lambda org_id: org
    return svc


class TestGetAncestorsPathMismatch:
    def test_path_tail_not_matching_org_id_returns_empty(self):
        """path 末段不等于 org_id 时返回空列表（第 289 行）."""
        org = SimpleNamespace(id=5, path="/1/2/")
        svc = _make_service(org)
        assert svc.get_ancestors(5) == []

    def test_empty_path_returns_empty(self):
        """path 为空串解析不出 ID 时同样返回空列表（第 289 行）."""
        org = SimpleNamespace(id=7, path="")
        svc = _make_service(org)
        assert svc.get_ancestors(7) == []


class TestGetAncestorsNullPath:
    """path 为 NULL 的历史组织不得把异常升级成 500（数据上报等链路会调到这里）."""

    def test_null_path_returns_empty(self):
        org = SimpleNamespace(id=9, path=None)
        svc = _make_service(org)
        assert svc.get_ancestors(9) == []

    def test_non_numeric_path_segment_returns_empty(self):
        """父级 path 为 NULL 时曾拼出 "None12/"，int() 会抛 ValueError."""
        org = SimpleNamespace(id=12, path="/1/None12/")
        svc = _make_service(org)
        assert svc.get_ancestors(12) == []

    def test_valid_path_still_resolves_ancestors(self):
        """回归保护：合法 path 仍能正常解析出祖先."""
        db = MagicMock()
        ancestor = SimpleNamespace(id=1, level=1)
        db.query.return_value.filter.return_value.order_by.return_value.all.return_value = [ancestor]
        from app.services.organization_service import OrganizationService

        svc = OrganizationService(db=db)
        svc.get_organization = lambda org_id: SimpleNamespace(id=2, path="/1/2/")
        assert svc.get_ancestors(2) == [ancestor]


class TestCreateOrganizationNullParentPath:
    """父级 path 为 NULL 时，子组织 path 不得拼成 "None{id}/".

    2026-10-27：编码改为以传入的行政区划代码为准（不再是随机 ORG-XXXX），
    故父级用真实代码 522700（黔南州），子级 522701（都匀市）。
    """

    def test_parent_path_none_uses_parent_id_segment(self):
        from app.services.organization_service import OrganizationService

        db = MagicMock()
        parent = SimpleNamespace(id=1, code="522700", level="2", path=None)
        # 第一次查询取父级，第二次查编码是否重复（无冲突）
        db.query.return_value.filter.return_value.first.side_effect = [parent, None]
        db.query.return_value.filter.return_value.scalar.return_value = 0

        created = {}

        def _add(obj):
            created["org"] = obj

        def _flush():
            created["org"].id = 42

        db.add.side_effect = _add
        db.flush.side_effect = _flush

        svc = OrganizationService(db=db)
        data = SimpleNamespace(
            parent_id=1, code="522701", name="Child", is_active=True,
            description=None, contact_person=None, contact_phone=None, address=None,
        )
        org = asyncio.run(svc.create_organization(data, created_by=1))
        assert org.path == "/1/42/", "父级 path 为 NULL 时应回退为父 ID 单段路径"
        assert org.code == "522701", "编码必须取传入的行政区划代码"
        assert str(org.level) == "3", "都匀市应为县市级（level 3）"
