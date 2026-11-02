# -*- coding: utf-8 -*-
"""R48：组织策略树配置 + 按单位有效矩阵批量导出。

覆盖点：
- `get_grant_matrix_for_org` 与 `get_grant_matrix` 同口径（继承、深者优先、来源）；
- `GET /org-grants/tree`：子树嵌套、显式矩阵、越权 403；
- `GET /org-grants/{id}` 返回 effective/sources；
- `POST /org-grants/{id}/export-branch`：zip 内含每个单位一个 v1 包、版本落库、
  空有效矩阵跳过并写入 manifest.skipped、包可被现有 apply_package 导入；
- 缺 code 的单位使整批 400 且不消耗版本号。
"""

import io
import json
import zipfile
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.v1 import org_grants as api
from app.models.base import Base
from app.models.org_grant import OrgGrant
from app.models.organization import Organization
from app.services import effective_grant_service as egs
from app.services.grant_package_service import apply_package

ADMIN = SimpleNamespace(id=1, username="admin", role="admin", is_superuser=True)
VIEWER = SimpleNamespace(id=2, username="u", role="viewer", is_superuser=False)


def _make_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(
        engine, tables=[Organization.__table__, OrgGrant.__table__]
    )
    return engine, sessionmaker(bind=engine)()


@pytest.fixture
def db(monkeypatch):
    engine, session = _make_db()
    egs.clear_cache()
    monkeypatch.setattr(api, "assert_org_reachable", lambda *a, **kw: None)
    monkeypatch.setattr(
        api,
        "settings",
        SimpleNamespace(
            GRANT_PUBKEY="", GRANT_ALLOW_UNSIGNED=True, GRANT_SIGNING_KEY=""
        ),
    )
    monkeypatch.setattr(api, "write_work_log", lambda *a, **kw: None)
    try:
        yield session
    finally:
        session.close()
        engine.dispose()
        egs.clear_cache()


def _org(db, code, name=None, parent=None, version=0):
    org = Organization(
        name=name or code,
        code=code,
        parent_id=parent.id if parent is not None else None,
        grant_version=version,
    )
    db.add(org)
    db.commit()
    db.refresh(org)
    return org


def _grant(db, org, key, level):
    db.add(OrgGrant(organization_id=org.id, module_key=key, level=level))
    db.commit()


@pytest.fixture
def tree(db):
    """省 522700 → 市 522701 → 县 522702；另有一个兄弟省 520000。"""
    root = _org(db, "522700", "黔南州")
    city = _org(db, "522701", "都匀市", parent=root)
    county = _org(db, "522702", "福泉市", parent=city)
    sibling = _org(db, "520000", "贵州省")
    _grant(db, root, "projects", "edit")
    _grant(db, city, "projects", "view")
    _grant(db, county, "funds", "view")
    return SimpleNamespace(root=root, city=city, county=county, sibling=sibling)


class TestGrantMatrixForOrg:
    def test_inherits_and_reports_source(self, db, tree):
        # 县自己显式 funds=view；projects 继承市局的 view（而非省厅的 edit）
        matrix = egs.get_grant_matrix_for_org(db, tree.county)
        assert matrix.active is True
        assert matrix.levels == {"projects": "view", "funds": "view"}
        assert matrix.sources["projects"] == "522701"
        assert matrix.sources["funds"] == "522702"

    def test_matches_user_entry(self, db, tree):
        matrix = egs.get_grant_matrix_for_org(db, tree.county)
        user = SimpleNamespace(id=9, role="user", organization_id=tree.county.id)
        assert egs.get_grant_matrix(db, user).levels == matrix.levels
        assert egs.get_grant_matrix(db, user).sources == matrix.sources

    def test_inactive_when_nothing_declared(self, db):
        alone = _org(db, "510000", "四川省")
        assert egs.get_grant_matrix_for_org(db, alone).active is False


class TestTreeEndpoint:
    def test_nested_subtree_with_explicit_grants(self, db, tree):
        resp = api.get_org_grant_tree(root_id=tree.root.id, db=db, current_user=ADMIN)
        data = resp["data"]
        assert data["root_id"] == tree.root.id
        node = data["node"]
        assert node["code"] == "522700"
        assert node["grants"] == {"projects": "edit"}
        assert [c["code"] for c in node["children"]] == ["522701"]
        assert [c["code"] for c in node["children"][0]["children"]] == ["522702"]
        # 兄弟省不在子树内
        assert "520000" not in json.dumps(data, ensure_ascii=False)

    def test_non_admin_denied(self, db, tree):
        with pytest.raises(HTTPException) as exc:
            api.get_org_grant_tree(root_id=tree.root.id, db=db, current_user=VIEWER)
        assert exc.value.status_code == 403

    def test_defaults_to_top_root_for_superuser_without_org(self, db, tree):
        """首次初始化的超管不绑定单位：应自动回落到组织树最顶层，而不是 400。"""
        resp = api.get_org_grant_tree(root_id=None, db=db, current_user=ADMIN)
        assert resp["data"]["root_id"] == tree.root.id

    def test_without_org_and_not_superuser_400(self, db, tree):
        with pytest.raises(HTTPException) as exc:
            api.get_org_grant_tree(root_id=None, db=db, current_user=VIEWER)
        assert exc.value.status_code == 400
        assert "未绑定单位" in exc.value.detail

    def test_superuser_without_org_and_empty_tree_400(self, db):
        """组织树为空时超管回落也无根可用，仍应 400 而不是崩。"""
        with pytest.raises(HTTPException) as exc:
            api.get_org_grant_tree(root_id=None, db=db, current_user=ADMIN)
        assert exc.value.status_code == 400
        assert "未绑定单位" in exc.value.detail


class TestTreeEdgeCases:
    def test_tree_404_when_subtree_empty(self, db, tree, monkeypatch):
        """根单位存在但子树解析为空（异常数据）时返回 404，而不是空树。"""
        monkeypatch.setattr(api, "subtree_orgs", lambda *a, **kw: [])
        with pytest.raises(HTTPException) as exc:
            api.get_org_grant_tree(root_id=tree.root.id, db=db, current_user=ADMIN)
        assert exc.value.status_code == 404

    def test_export_branch_404_when_subtree_empty(self, db, tree, monkeypatch):
        monkeypatch.setattr(api, "subtree_orgs", lambda *a, **kw: [])
        with pytest.raises(HTTPException) as exc:
            api.export_grant_branch(tree.root.id, db=db, current_user=ADMIN)
        assert exc.value.status_code == 404

    def test_export_branch_package_error_400(self, db, tree, monkeypatch):
        """单个单位建包失败（编码/字段非法）时整批 400，且不落版本号。"""
        from app.services.grant_package_service import GrantPackageError

        def boom(**kwargs):
            raise GrantPackageError("bad package")

        monkeypatch.setattr(api, "build_package", boom)
        with pytest.raises(HTTPException) as exc:
            api.export_grant_branch(tree.root.id, db=db, current_user=ADMIN)
        assert exc.value.status_code == 400
        assert "bad package" in exc.value.detail
        for org in (tree.root, tree.city, tree.county):
            db.refresh(org)
            assert org.grant_version == 0


class TestGetIncludesEffective:
    def test_effective_and_sources(self, db, tree):
        data = api.get_org_grants(tree.county.id, db=db, current_user=ADMIN)["data"]
        assert data["grants"] == {"funds": "view"}
        assert data["effective"] == {"projects": "view", "funds": "view"}
        assert data["sources"]["projects"] == "522701"


class TestExportBranch:
    def test_zip_contains_one_package_per_org(self, db, tree):
        resp = api.export_grant_branch(tree.root.id, db=db, current_user=ADMIN)
        assert resp.media_type == "application/zip"
        zf = zipfile.ZipFile(io.BytesIO(resp.body))
        names = set(zf.namelist())
        assert "manifest.json" in names
        assert {"grant-522700-v1.json", "grant-522701-v1.json", "grant-522702-v1.json"} <= names
        manifest = json.loads(zf.read("manifest.json").decode("utf-8"))
        assert manifest["format"] == "r33-grant-batch"
        assert manifest["root_org_code"] == "522700"
        assert len(manifest["packages"]) == 3
        assert manifest["skipped"] == []

        city = json.loads(zf.read("grant-522701-v1.json").decode("utf-8"))
        assert city["org_code"] == "522701"
        assert city["grants"] == {"projects": "view"}
        county = json.loads(zf.read("grant-522702-v1.json").decode("utf-8"))
        assert county["grants"] == {"projects": "view", "funds": "view"}

        # 版本必须落库，否则连续导出会重复版本号
        for org in (tree.root, tree.city, tree.county):
            db.refresh(org)
            assert org.grant_version == 1

    def test_packages_are_importable_by_existing_apply(self, db, tree):
        resp = api.export_grant_branch(tree.root.id, db=db, current_user=ADMIN)
        zf = zipfile.ZipFile(io.BytesIO(resp.body))
        engine, lower = _make_db()
        try:
            lower_root = Organization(name="黔南州", code="522700", grant_version=0)
            lower.add(lower_root)
            lower.commit()
            lower_city = Organization(
                name="都匀市", code="522701", parent_id=lower_root.id, grant_version=0
            )
            lower.add(lower_city)
            lower.commit()
            lower_county = Organization(
                name="福泉市", code="522702", parent_id=lower_city.id, grant_version=0
            )
            lower.add(lower_county)
            lower.commit()
            for name in zf.namelist():
                if name == "manifest.json":
                    continue
                result = apply_package(lower, zf.read(name), allow_unsigned=True)
                assert result["version"] == 1

            county_org = lower.query(Organization).filter(Organization.code == "522702").one()
            matrix = egs.get_grant_matrix_for_org(lower, county_org)
            assert matrix.levels == {"projects": "view", "funds": "view"}
        finally:
            lower.close()
            engine.dispose()
            egs.clear_cache()

    def test_empty_matrix_is_skipped(self, db):
        root = _org(db, "530000", "云南省")
        _org(db, "530100", "昆明市", parent=root)
        resp = api.export_grant_branch(root.id, db=db, current_user=ADMIN)
        zf = zipfile.ZipFile(io.BytesIO(resp.body))
        assert zf.namelist() == ["manifest.json"]
        manifest = json.loads(zf.read("manifest.json").decode("utf-8"))
        assert {s["org_code"] for s in manifest["skipped"]} == {"530000", "530100"}
        assert manifest["packages"] == []
        db.refresh(root)
        assert root.grant_version == 0

    def test_missing_code_aborts_without_bumping(self, db, tree):
        bad = Organization(name="无编码单位", code=None, parent_id=tree.city.id)
        db.add(bad)
        db.commit()
        with pytest.raises(HTTPException) as exc:
            api.export_grant_branch(tree.root.id, db=db, current_user=ADMIN)
        assert exc.value.status_code == 400
        assert "单位编号" in exc.value.detail
        for org in (tree.root, tree.city, tree.county):
            db.refresh(org)
            assert org.grant_version == 0

    def test_non_admin_denied(self, db, tree):
        with pytest.raises(HTTPException) as exc:
            api.export_grant_branch(tree.root.id, db=db, current_user=VIEWER)
        assert exc.value.status_code == 403
