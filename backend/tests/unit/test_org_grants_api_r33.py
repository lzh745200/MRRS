# -*- coding: utf-8 -*-
"""R33：单位授权矩阵 API（org_grants）。

覆盖点：
- `_require_admin_and_reach` 的三种结果（非管理员 403 / 单位不存在 404 / 通过）；
- 导入：空文件、超大文件、包不合法（400）、成功（落库 + 返回版本与模块数）；
- 导出：单位缺 code（400）、成功（返回 JSON 下载，版本号 +1）；
- 查询：返回矩阵与元信息（含 applied_at 有值/无值两条分支）；
- 设置：非法级别 400、成功（**替换**语义 + 版本递增 + source=local）。
"""

import json
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
from app.services.grant_package_service import build_package

ADMIN = SimpleNamespace(id=1, username="admin", role="admin", is_superuser=True)
VIEWER = SimpleNamespace(id=2, username="u", role="viewer", is_superuser=False)


@pytest.fixture
def db(monkeypatch):
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine, tables=[Organization.__table__, OrgGrant.__table__])
    session = sessionmaker(bind=engine)()
    egs.clear_cache()
    monkeypatch.setattr(api, "assert_org_reachable", lambda *a, **kw: None)
    monkeypatch.setattr(api, "settings", SimpleNamespace(
        GRANT_PUBKEY="", GRANT_ALLOW_UNSIGNED=True, GRANT_SIGNING_KEY="",
    ))
    monkeypatch.setattr(api, "write_work_log", lambda *a, **kw: None)
    try:
        yield session
    finally:
        session.close()
        engine.dispose()
        egs.clear_cache()


def _org(db, code="C001", name="某某县", version=0):
    org = Organization(name=name, code=code, grant_version=version)
    db.add(org)
    db.commit()
    db.refresh(org)
    return org


def _upload(content: bytes):
    """模拟 UploadFile：支持分块 read（`read_upload_with_limit` 按 chunk 读取）。"""

    class _F:
        def __init__(self):
            self._pos = 0

        async def read(self, size: int = -1):
            if size is None or size < 0:
                data = content[self._pos:]
            else:
                data = content[self._pos:self._pos + size]
            self._pos += len(data)
            return data

    return _F()


class TestRequireAdminAndReach:
    def test_non_admin_denied(self, db):
        org = _org(db)
        with pytest.raises(HTTPException) as exc:
            api._require_admin_and_reach(db, VIEWER, org.id, "x")
        assert exc.value.status_code == 403

    def test_org_missing(self, db):
        with pytest.raises(HTTPException) as exc:
            api._require_admin_and_reach(db, ADMIN, 99999, "x")
        assert exc.value.status_code == 404

    def test_ok(self, db):
        org = _org(db)
        assert api._require_admin_and_reach(db, ADMIN, org.id, "x").id == org.id


class TestLocalOrgCode:
    def test_returns_value(self, db, monkeypatch):
        monkeypatch.setattr(api, "SystemConfigService",
                            lambda _db: SimpleNamespace(get=lambda _k: " C001 "))
        assert api._local_org_code(db) == "C001"

    def test_returns_empty_when_unset(self, db, monkeypatch):
        monkeypatch.setattr(api, "SystemConfigService",
                            lambda _db: SimpleNamespace(get=lambda _k: None))
        assert api._local_org_code(db) == ""


class TestImport:
    async def test_empty_file(self, db):
        with pytest.raises(HTTPException) as exc:
            await api.import_grant_package(_upload(b""), db=db, current_user=ADMIN)
        assert exc.value.status_code == 400

    async def test_oversize_file(self, db, monkeypatch):
        monkeypatch.setattr(api, "_MAX_PACKAGE_BYTES", 4)
        with pytest.raises(HTTPException) as exc:
            await api.import_grant_package(_upload(b"12345"), db=db, current_user=ADMIN)
        assert "1MB" in exc.value.detail or exc.value.status_code == 400

    async def test_invalid_package(self, db):
        with pytest.raises(HTTPException) as exc:
            await api.import_grant_package(_upload(b"{bad json"), db=db, current_user=ADMIN)
        assert exc.value.status_code == 400

    async def test_success(self, db, monkeypatch):
        org = _org(db)
        monkeypatch.setattr(api, "SystemConfigService",
                            lambda _db: SimpleNamespace(get=lambda _k: "C001"))
        pkg = build_package(org_code="C001", grants={"projects": "edit"}, version=1)
        resp = await api.import_grant_package(
            _upload(json.dumps(pkg).encode()), db=db, current_user=ADMIN
        )
        assert resp["data"]["version"] == 1
        assert resp["data"]["modules"] == 1
        db.refresh(org)
        assert org.grant_version == 1
        assert org.grant_source == "import"

    async def test_non_admin_denied(self, db):
        with pytest.raises(HTTPException) as exc:
            await api.import_grant_package(_upload(b"{}"), db=db, current_user=VIEWER)
        assert exc.value.status_code == 403


class TestExport:
    def test_missing_org_code(self, db):
        org = _org(db, code=None)
        with pytest.raises(HTTPException) as exc:
            api.export_grant_package(org.id, db=db, current_user=ADMIN)
        assert "单位编号" in exc.value.detail

    def test_success_unsigned(self, db):
        org = _org(db, version=2)
        db.add(OrgGrant(organization_id=org.id, module_key="projects", level="view"))
        db.commit()
        resp = api.export_grant_package(org.id, db=db, current_user=ADMIN)
        payload = json.loads(resp.body.decode("utf-8"))
        assert payload["org_code"] == "C001"
        assert payload["version"] == 3  # 当前 2 → 导出 3
        assert payload["grants"] == {"projects": "view"}
        assert "signature" not in payload
        assert "grant-C001-v3.json" in resp.headers["content-disposition"]

    def test_invalid_grant_level_in_db_breaks_export(self, db):
        """库里存在非法级别时导出应报 400，而不是产出坏包。"""
        org = _org(db)
        db.add(OrgGrant(organization_id=org.id, module_key="projects", level="own"))
        db.commit()
        with pytest.raises(HTTPException) as exc:
            api.export_grant_package(org.id, db=db, current_user=ADMIN)
        assert exc.value.status_code == 400


class TestGet:
    def test_returns_matrix_and_meta(self, db):
        org = _org(db, version=4)
        db.add(OrgGrant(organization_id=org.id, module_key="funds", level="edit"))
        db.commit()
        data = api.get_org_grants(org.id, db=db, current_user=ADMIN)["data"]
        assert data["grant_version"] == 4
        assert data["grants"] == {"funds": "edit"}
        assert data["grant_applied_at"] is None
        assert data["signed"] is False

    def test_applied_at_serialized(self, db):
        from datetime import datetime, timezone

        org = _org(db)
        org.grant_applied_at = datetime(2026, 10, 19, tzinfo=timezone.utc)
        org.grant_signature = "ab" * 64
        db.commit()
        data = api.get_org_grants(org.id, db=db, current_user=ADMIN)["data"]
        assert data["grant_applied_at"].startswith("2026-10-19")
        assert data["signed"] is True


class TestSet:
    def test_invalid_level(self, db):
        org = _org(db)
        body = api.GrantSetRequest(grants={"projects": "own"})
        with pytest.raises(HTTPException) as exc:
            api.set_org_grants(org.id, body, db=db, current_user=ADMIN)
        assert exc.value.status_code == 400

    def test_empty_module_key(self, db):
        org = _org(db)
        body = api.GrantSetRequest(grants={"": "edit"})
        with pytest.raises(HTTPException) as exc:
            api.set_org_grants(org.id, body, db=db, current_user=ADMIN)
        assert exc.value.status_code == 400

    def test_replaces_and_bumps_version(self, db):
        org = _org(db, version=1)
        db.add(OrgGrant(organization_id=org.id, module_key="old", level="edit"))
        db.commit()

        body = api.GrantSetRequest(grants={"projects": "view"})
        data = api.set_org_grants(org.id, body, db=db, current_user=ADMIN)["data"]
        assert data["grant_version"] == 2
        assert data["modules"] == 1

        rows = db.query(OrgGrant).filter(OrgGrant.organization_id == org.id).all()
        assert [(r.module_key, r.level) for r in rows] == [("projects", "view")]
        db.refresh(org)
        assert org.grant_source == "local"
