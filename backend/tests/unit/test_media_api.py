# -*- coding: utf-8 -*-
"""影像库 API 单测（W22 · 契约 §2 ``/media/photos``）

覆盖 ``app.api.v1.media``：列表（筛选/分页/envelope）、注册（EXIF 补全）、
更新 / 软删（404 / 403）、多期对比列表、对比图 POST/GET（PNG）、参数校验。
"""

import io
import uuid
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image

from app.api.v1.media import router as media_router
from app.core.data_permission import OrgScopeFilter, get_org_scope
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.media import PhotoArchive
from app.models.supported_village import SupportedVillage
from app.utils.paths import get_runtime_uploads_path


def _png_bytes(size=(100, 200), color="red"):
    buffer = io.BytesIO()
    Image.new("RGB", size, color).save(buffer, format="PNG")
    return buffer.getvalue()


def _jpeg_with_exif(gps=None, datetime_original="2024:01:15 10:30:00"):
    image = Image.new("RGB", (64, 48), "white")
    exif = Image.Exif()
    if datetime_original:
        exif[36867] = datetime_original
    if gps is not None:
        exif[34853] = gps
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", exif=exif)
    return buffer.getvalue()


def _save_upload(content: bytes, suffix=".png") -> str:
    relative = f"media_api_test/{uuid.uuid4().hex}{suffix}"
    path = get_runtime_uploads_path(relative)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return f"/uploads/{relative}"


def _user(user_id=1, org_id=1, role="user", is_superuser=False):
    return SimpleNamespace(
        id=user_id,
        username=f"user{user_id}",
        role=role,
        is_superuser=is_superuser,
        organization_id=org_id,
        data_scope="org",
    )


def _add_photo(db, **overrides):
    data = {
        "file_url": _save_upload(_png_bytes()),
        "file_name": "photo.png",
        "shot_source": "manual",
        "organization_id": 1,
        "created_by": 1,
        "uploader_id": 1,
        "is_active": True,
    }
    data.update(overrides)
    photo = PhotoArchive(**data)
    db.add(photo)
    db.commit()
    db.refresh(photo)
    return photo


@pytest.fixture
def api_app(real_db_session):
    app = FastAPI()
    app.include_router(media_router)
    app.dependency_overrides[get_db] = lambda: real_db_session
    return app


def _client(api_app, scope=None, user=None):
    api_app.dependency_overrides[get_current_user] = lambda: (user or _user())
    api_app.dependency_overrides[get_org_scope] = lambda: (
        scope if scope is not None else OrgScopeFilter(is_admin=True)
    )
    return TestClient(api_app)


# ════════════════════════════════════════════════════════════════════
#  列表
# ════════════════════════════════════════════════════════════════════
class TestListPhotosApi:
    def test_list_envelope(self, api_app, real_db_session):
        _add_photo(real_db_session, tag="a")
        _add_photo(real_db_session, tag="b")
        response = _client(api_app).get("/media/photos")
        assert response.status_code == 200
        body = response.json()
        assert body["code"] == 200
        data = body["data"]
        assert data["total"] == 2
        assert len(data["items"]) == 2
        assert data["items"][0]["file_url"].startswith("/uploads/")
        assert "taken_at" in data["items"][0]

    def test_list_with_filters_and_pagination(self, api_app, real_db_session):
        from datetime import date, datetime, timezone

        _add_photo(
            real_db_session,
            village_id=5,
            tag="t1",
            taken_at=datetime(2024, 5, 1, tzinfo=timezone.utc),
        )
        _add_photo(real_db_session, village_id=6, tag="t2")
        response = _client(api_app).get(
            "/media/photos",
            params={
                "page": 1,
                "page_size": 1,
                "village_id": 5,
                "tag": "t1",
                "date_from": date(2024, 1, 1).isoformat(),
                "date_to": date(2024, 12, 31).isoformat(),
            },
        )
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["total"] == 1
        assert data["items"][0]["village_id"] == 5
        assert data["page"] == 1 and data["page_size"] == 1

    def test_list_respects_org_scope(self, api_app, real_db_session):
        _add_photo(real_db_session, organization_id=1)
        _add_photo(real_db_session, organization_id=2)
        client = _client(api_app, scope=OrgScopeFilter(is_admin=False, org_ids=[1]))
        assert client.get("/media/photos").json()["data"]["total"] == 1

    def test_list_includes_reference_names(self, api_app, real_db_session):
        from app.models.project import Project
        from app.models.school import School

        village = SupportedVillage(
            village_name="名称村", latitude=30.0, longitude=120.0, is_active=True
        )
        school = School(name="名称学校", is_active=True)
        project = Project(name="名称项目", is_active=True)
        real_db_session.add_all([village, school, project])
        real_db_session.commit()
        for row in (village, school, project):
            real_db_session.refresh(row)
        _add_photo(
            real_db_session,
            village_id=village.id,
            school_id=school.id,
            project_id=project.id,
        )
        item = _client(api_app).get("/media/photos").json()["data"]["items"][0]
        assert item["village_name"] == "名称村"
        assert item["school_name"] == "名称学校"
        assert item["project_name"] == "名称项目"


# ════════════════════════════════════════════════════════════════════
#  注册
# ════════════════════════════════════════════════════════════════════
class TestCreatePhotoApi:
    def test_create_reads_exif_and_matches_village(self, api_app, real_db_session):
        village = SupportedVillage(
            village_name="测试村",
            latitude=30.258333,
            longitude=120.170833,
            organization_id=1,
            is_active=True,
        )
        real_db_session.add(village)
        real_db_session.commit()
        real_db_session.refresh(village)

        file_url = _save_upload(
            _jpeg_with_exif(gps={1: "N", 2: (30.0, 15.0, 30.0), 3: "E", 4: (120.0, 10.0, 15.0)}),
            suffix=".jpg",
        )
        response = _client(api_app).post(
            "/media/photos",
            json={"file_url": file_url, "file_name": "现场.jpg", "tag": "入户"},
        )
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["file_url"] == file_url
        assert data["shot_source"] == "exif"
        assert data["village_id"] == village.id
        assert data["spot_key"] == "30.2583,120.1708"
        assert data["organization_id"] == 1
        assert data["created_by"] == 1
        assert data["taken_at"].startswith("2024-01-15T10:30:00")

    def test_create_manual_without_exif(self, api_app):
        response = _client(api_app).post(
            "/media/photos", json={"file_url": _save_upload(_png_bytes())}
        )
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["shot_source"] == "manual"
        assert data["spot_key"] is None

    def test_create_rejects_traversal(self, api_app):
        response = _client(api_app).post(
            "/media/photos", json={"file_url": "/uploads/../etc/passwd"}
        )
        assert response.status_code == 400

    def test_create_rejects_out_of_range_gps(self, api_app):
        response = _client(api_app).post(
            "/media/photos",
            json={"file_url": _save_upload(_png_bytes()), "gps_lat": 91.0},
        )
        assert response.status_code == 422

    def test_create_requires_file_url(self, api_app):
        response = _client(api_app).post("/media/photos", json={})
        assert response.status_code == 422


# ════════════════════════════════════════════════════════════════════
#  更新 / 软删
# ════════════════════════════════════════════════════════════════════
class TestUpdateDeleteApi:
    def test_update_photo(self, api_app, real_db_session):
        photo = _add_photo(real_db_session, tag="old")
        response = _client(api_app).put(
            f"/media/photos/{photo.id}", json={"tag": "new", "spot_key": "spot-1"}
        )
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["tag"] == "new"
        assert data["spot_key"] == "spot-1"

    def test_update_missing_404(self, api_app):
        response = _client(api_app).put("/media/photos/999999", json={"tag": "x"})
        assert response.status_code == 404

    def test_update_cross_org_403(self, api_app, real_db_session):
        photo = _add_photo(real_db_session, organization_id=1, created_by=1)
        response = _client(api_app, user=_user(user_id=9, org_id=2)).put(
            f"/media/photos/{photo.id}", json={"tag": "x"}
        )
        assert response.status_code == 403

    def test_delete_soft_deletes(self, api_app, real_db_session):
        photo = _add_photo(real_db_session)
        response = _client(api_app).delete(f"/media/photos/{photo.id}")
        assert response.status_code == 200
        assert response.json()["data"]["id"] == photo.id
        # 软删后再删 → 404
        assert _client(api_app).delete(f"/media/photos/{photo.id}").status_code == 404


# ════════════════════════════════════════════════════════════════════
#  多期对比 / 对比图
# ════════════════════════════════════════════════════════════════════
class TestCompareApi:
    def test_compare_list(self, api_app, real_db_session):
        from datetime import datetime, timezone

        _add_photo(
            real_db_session,
            spot_key="gate",
            taken_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        )
        _add_photo(
            real_db_session,
            spot_key="gate",
            taken_at=datetime(2024, 6, 1, tzinfo=timezone.utc),
        )
        response = _client(api_app).get("/media/photos/compare", params={"spot_key": "gate"})
        assert response.status_code == 200
        rows = response.json()["data"]
        assert len(rows) == 2
        assert set(rows[0]) == {"id", "file_url", "taken_at"}

    def test_compare_image_post(self, api_app, real_db_session):
        first = _add_photo(real_db_session, file_url=_save_upload(_png_bytes(size=(100, 200))))
        second = _add_photo(real_db_session, file_url=_save_upload(_png_bytes(size=(200, 100))))
        response = _client(api_app).post(
            "/media/photos/compare-image", json={"ids": [first.id, second.id]}
        )
        assert response.status_code == 200
        assert response.headers["content-type"] == "image/png"
        assert response.headers["content-disposition"] == 'attachment; filename="compare.png"'
        canvas = Image.open(io.BytesIO(response.content))
        assert canvas.width == 720 * 2

    def test_compare_image_get(self, api_app, real_db_session):
        photo = _add_photo(real_db_session, file_url=_save_upload(_png_bytes(size=(20, 20))))
        response = _client(api_app).get(
            "/media/photos/compare-image", params={"ids": f"{photo.id},,{photo.id}"}
        )
        assert response.status_code == 200
        assert response.headers["content-type"] == "image/png"
        assert response.headers["content-disposition"] == 'attachment; filename="compare.png"'
        assert response.content.startswith(b"\x89PNG")

    def test_compare_image_get_invalid_ids(self, api_app):
        response = _client(api_app).get(
            "/media/photos/compare-image", params={"ids": "1,abc"}
        )
        assert response.status_code == 400
        assert "整数" in response.json()["detail"]

    def test_compare_image_get_empty_ids(self, api_app):
        response = _client(api_app).get("/media/photos/compare-image", params={"ids": ""})
        assert response.status_code == 400

    def test_compare_image_post_empty_ids_422(self, api_app):
        response = _client(api_app).post("/media/photos/compare-image", json={"ids": []})
        assert response.status_code == 422
