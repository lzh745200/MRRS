"""w17-007 一村/一校一档 PDF 端点测试（真实 SQLite 内存库）。

覆盖：
- GET /supported-villages/{id}/dossier.pdf：成功 200（PDF + 附件名）、不存在 404、
  数据域越权 404、生成失败 500 泛化文案（不泄露内部异常）、生成写审计；
- GET /schools/{id}/dossier.pdf：同上。
"""

from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import get_db
from app.core.security import get_current_user
from app.main import app
from app.models import Base
from app.models.school import School
from app.models.supported_village import SupportedVillage

PDF_MAGIC = b"%PDF-"


def _admin():
    return SimpleNamespace(
        id=1,
        username="admin",
        role="admin",
        is_superuser=True,
        organization_id=7,
        full_name="Admin",
        is_active=True,
        permissions_list=["*"],
    )


def _outside_user():
    return SimpleNamespace(
        id=5,
        username="outside",
        role="user",
        is_superuser=False,
        organization_id=9,
        full_name="外人",
        is_active=True,
    )


@pytest.fixture()
def dossier_client():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = TestingSessionLocal()
    holder = {"user": _admin()}

    def override_get_db():
        yield db

    async def mock_user():
        return holder["user"]

    original = app.dependency_overrides.copy()
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = mock_user
    try:
        yield TestClient(app, raise_server_exceptions=False), db, holder
    finally:
        app.dependency_overrides = original
        db.close()


def _seed_village(db, name="甲村", org_id=2, created_by=2, is_active=True):
    village = SupportedVillage(
        village_name=name, organization_id=org_id, created_by=created_by, is_active=is_active
    )
    db.add(village)
    db.commit()
    db.refresh(village)
    return village


def _seed_school(db, name="希望小学", org_id=2, created_by=2, is_active=True):
    school = School(
        name=name, code=f"SCH-{name}", organization_id=org_id, created_by=created_by,
        is_active=is_active,
    )
    db.add(school)
    db.commit()
    db.refresh(school)
    return school


class TestVillageDossierEndpoint:
    def test_not_found_404(self, dossier_client):
        client, _db, _holder = dossier_client
        resp = client.get("/api/v1/supported-villages/9999/dossier.pdf")
        assert resp.status_code == 404
        assert resp.json()["detail"] == "帮扶村不存在"

    def test_out_of_scope_404(self, dossier_client):
        client, db, holder = dossier_client
        village = _seed_village(db)
        holder["user"] = _outside_user()
        resp = client.get(f"/api/v1/supported-villages/{village.id}/dossier.pdf")
        assert resp.status_code == 404
        assert resp.json()["detail"] == "帮扶村不存在"

    def test_success_pdf_and_audit(self, dossier_client):
        client, db, _holder = dossier_client
        village = _seed_village(db)
        with patch("app.services.dossier_service.record_dossier_audit") as audit:
            resp = client.get(f"/api/v1/supported-villages/{village.id}/dossier.pdf")
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("application/pdf")
        assert "attachment; filename*=UTF-8''" in resp.headers["content-disposition"]
        assert resp.content.startswith(PDF_MAGIC)
        audit.assert_called_once_with(_holder["user"], "supported_village", village.id, "甲村")

    def test_generation_failure_500_generic(self, dossier_client):
        client, db, _holder = dossier_client
        village = _seed_village(db)
        with patch(
            "app.services.dossier_service.DossierService.render_village_pdf",
            side_effect=RuntimeError("内部数据库连接串泄露"),
        ):
            resp = client.get(f"/api/v1/supported-villages/{village.id}/dossier.pdf")
        assert resp.status_code == 500
        assert resp.json()["detail"] == "档案册生成失败，请稍后重试"
        assert "内部数据库连接串泄露" not in resp.text


class TestSchoolDossierEndpoint:
    def test_not_found_404(self, dossier_client):
        client, _db, _holder = dossier_client
        resp = client.get("/api/v1/schools/9999/dossier.pdf")
        assert resp.status_code == 404
        assert resp.json()["detail"] == "学校不存在"

    def test_out_of_scope_404(self, dossier_client):
        client, db, holder = dossier_client
        school = _seed_school(db)
        holder["user"] = _outside_user()
        resp = client.get(f"/api/v1/schools/{school.id}/dossier.pdf")
        assert resp.status_code == 404
        assert resp.json()["detail"] == "学校不存在"

    def test_success_pdf_and_audit(self, dossier_client):
        client, db, _holder = dossier_client
        school = _seed_school(db)
        with patch("app.services.dossier_service.record_dossier_audit") as audit:
            resp = client.get(f"/api/v1/schools/{school.id}/dossier.pdf")
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("application/pdf")
        assert "attachment; filename*=UTF-8''" in resp.headers["content-disposition"]
        assert resp.content.startswith(PDF_MAGIC)
        audit.assert_called_once_with(_holder["user"], "school", school.id, "希望小学")

    def test_generation_failure_500_generic(self, dossier_client):
        client, db, _holder = dossier_client
        school = _seed_school(db)
        with patch(
            "app.services.dossier_service.DossierService.render_school_pdf",
            side_effect=ValueError("secret path /etc/passwd"),
        ):
            resp = client.get(f"/api/v1/schools/{school.id}/dossier.pdf")
        assert resp.status_code == 500
        assert resp.json()["detail"] == "档案册生成失败，请稍后重试"
        assert "secret path" not in resp.text
