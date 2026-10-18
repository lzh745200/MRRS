# -*- coding: utf-8 -*-
"""影像库服务层单测（W22 · 契约 §1.4 / §2）

覆盖 ``app.services.media_service``：
- EXIF 解析（DateTimeOriginal / GPS 十进制度 / 无 EXIF / 非法 GPS）；
- 上传目录路径安全（非 /uploads、``..``、URL 编码穿越、文件缺失/不可读）；
- GPS 就近匹配帮扶村（≤5km、最近优先、数据域约束）；
- 注册归档（EXIF 补全、payload 覆盖、spot_key 生成、缺失文件降级 manual）；
- 列表筛选 / 分页 / 软删 / 数据域；点查 404 / 越权 403；软删；
- 同拍摄点多期对比；对比图合成（尺寸、布局、日期标注、缺图/非图片/超限）。
"""

import io
import uuid
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from PIL import Image

from app.core.data_permission import OrgScopeFilter
from app.models.media import PhotoArchive
from app.models.supported_village import SupportedVillage
from app.schemas.media import PhotoArchiveCreate
from app.services import media_service
from app.utils.paths import get_runtime_uploads_path


# ── 通用 helpers ─────────────────────────────────────────────────────
def _png_bytes(size=(100, 200), color="red"):
    buffer = io.BytesIO()
    Image.new("RGB", size, color).save(buffer, format="PNG")
    return buffer.getvalue()


def _jpeg_with_exif(datetime_original=None, datetime_tag=None, gps=None):
    image = Image.new("RGB", (64, 48), "white")
    exif = Image.Exif()
    if datetime_original is not None:
        exif[36867] = datetime_original
    if datetime_tag is not None:
        exif[306] = datetime_tag
    if gps is not None:
        exif[34853] = gps
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", exif=exif)
    return buffer.getvalue()


def _save_upload(content: bytes, suffix: str = ".png") -> str:
    """把内容写入上传目录（模拟 /files/upload 落盘），返回 /uploads URL"""
    relative = f"media_service_test/{uuid.uuid4().hex}{suffix}"
    path = get_runtime_uploads_path(relative)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return f"/uploads/{relative}"


def _remote_upload_url() -> str:
    relative = f"media_service_test/{uuid.uuid4().hex}.png"
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


def _admin_scope():
    return OrgScopeFilter(is_admin=True)


def _org_scope(org_ids, self_only=False, user_id=None):
    return OrgScopeFilter(
        is_admin=False, org_ids=list(org_ids), self_only=self_only, user_id=user_id
    )


def _add_photo(db, **overrides):
    data = {
        "file_url": _remote_upload_url(),
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


def _add_village(db, name, lat, lng, org_id=1, is_active=True):
    village = SupportedVillage(
        village_name=name,
        latitude=lat,
        longitude=lng,
        organization_id=org_id,
        is_active=is_active,
    )
    db.add(village)
    db.commit()
    db.refresh(village)
    return village


# ════════════════════════════════════════════════════════════════════
#  EXIF 解析
# ════════════════════════════════════════════════════════════════════
class TestExifParsing:
    def test_datetime_original_and_gps(self):
        meta = media_service.parse_exif(_jpeg_with_exif(
            datetime_original="2024:01:15 10:30:00",
            gps={1: "N", 2: (30.0, 15.0, 30.0), 3: "E", 4: (120.0, 10.0, 15.0)},
        ))
        assert meta["taken_at"].isoformat() == "2024-01-15T10:30:00+00:00"
        assert meta["gps_lat"] == pytest.approx(30.258333)
        assert meta["gps_lng"] == pytest.approx(120.170833)
        assert meta["shot_source"] == "exif"

    def test_south_west_refs_are_negative(self):
        meta = media_service.parse_exif(_jpeg_with_exif(
            datetime_original="2024:01:15 10:30:00",
            gps={1: "S", 2: (30.0, 0.0, 0.0), 3: "W", 4: (120.0, 0.0, 0.0)},
        ))
        assert meta["gps_lat"] == pytest.approx(-30.0)
        assert meta["gps_lng"] == pytest.approx(-120.0)

    def test_fallback_datetime_tag(self):
        meta = media_service.parse_exif(_jpeg_with_exif(datetime_tag="2024:02:20 08:00:00"))
        assert meta["taken_at"] is not None
        assert meta["shot_source"] == "exif"

    def test_no_exif_is_manual(self):
        meta = media_service.parse_exif(_jpeg_with_exif())
        assert meta == {
            "taken_at": None,
            "gps_lat": None,
            "gps_lng": None,
            "shot_source": "manual",
        }

    @pytest.mark.parametrize("content", [None, b"", b"not-an-image"])
    def test_unreadable_or_empty_is_manual(self, content):
        meta = media_service.parse_exif(content)
        assert meta["shot_source"] == "manual"

    def test_invalid_gps_range_ignored(self):
        meta = media_service.parse_exif(_jpeg_with_exif(
            datetime_original="2024:01:15 10:30:00",
            gps={1: "N", 2: (200.0, 0.0, 0.0), 3: "E", 4: (500.0, 0.0, 0.0)},
        ))
        assert meta["gps_lat"] is None
        assert meta["gps_lng"] is None
        # 时间存在 → 仍标记为 exif 来源
        assert meta["shot_source"] == "exif"

    def test_parse_datetime_bytes_and_second_format(self):
        aware = media_service._parse_exif_datetime(b"2024-01-15 10:30:00")
        assert aware.isoformat() == "2024-01-15T10:30:00+00:00"
        assert media_service._parse_exif_datetime(None) is None
        assert media_service._parse_exif_datetime("not-a-time") is None

    def test_gps_ref_bytes_and_spaces(self):
        assert media_service._gps_ref(b" s ") == "S"
        assert media_service._gps_ref(None) == ""
        assert media_service._gps_ref("N") == "N"

    def test_decimal_degrees_edge_cases(self):
        assert media_service._decimal_degrees(None, "N") is None
        assert media_service._decimal_degrees(("abc", 0, 0), "N") is None
        assert media_service._decimal_degrees((30.0, 15.0), "N") is None
        assert media_service._decimal_degrees((30.0, 15.0, 30.0), "N") == pytest.approx(30.258333)

    def test_haversine_km(self):
        # 纬度 1 度 ≈ 111.19km
        assert media_service.haversine_km(30.0, 120.0, 31.0, 120.0) == pytest.approx(111.19, abs=0.1)
        assert media_service.haversine_km(30.0, 120.0, 30.0, 120.0) == 0.0


# ════════════════════════════════════════════════════════════════════
#  上传目录 / 路径安全
# ════════════════════════════════════════════════════════════════════
class TestUploadPathSafety:
    def test_read_valid_upload(self):
        content = _png_bytes(size=(10, 10))
        url = _save_upload(content)
        assert media_service.read_upload_bytes(url) == content

    @pytest.mark.parametrize("bad_url", [
        "",
        "/etc/passwd",
        "http://evil/x.png",
        "/uploads/",
        "/uploads/../secret.png",
        "/uploads/%2e%2e/secret.png",
        "/uploads/a/../../secret.png",
    ])
    def test_rejects_illegal_urls(self, bad_url):
        with pytest.raises(HTTPException) as exc:
            media_service.resolve_upload_file(bad_url)
        assert exc.value.status_code == 400

    def test_rejects_non_string(self):
        with pytest.raises(HTTPException):
            media_service.resolve_upload_file(None)

    def test_missing_file_returns_none_and_404(self):
        url = _remote_upload_url()
        assert media_service.read_upload_bytes(url) is None
        with pytest.raises(HTTPException) as exc:
            media_service.load_image(url)
        assert exc.value.status_code == 404

    def test_unreadable_file_returns_none(self, monkeypatch):
        url = _save_upload(_png_bytes())
        monkeypatch.setattr(
            media_service.Path, "read_bytes",
            lambda self: (_ for _ in ()).throw(OSError("boom")),
        )
        assert media_service.read_upload_bytes(url) is None

    def test_invalid_image_raises_400(self):
        url = _save_upload(b"not-an-image", suffix=".png")
        with pytest.raises(HTTPException) as exc:
            media_service.load_image(url)
        assert exc.value.status_code == 400

    def test_load_image_returns_rgb(self):
        url = _save_upload(_png_bytes(size=(12, 8), color="blue"))
        image = media_service.load_image(url)
        assert image.mode == "RGB"
        assert image.size == (12, 8)


# ════════════════════════════════════════════════════════════════════
#  GPS → 帮扶村匹配
# ════════════════════════════════════════════════════════════════════
class TestGpsVillageMatching:
    def test_none_coordinates(self, real_db_session):
        assert media_service.match_village_by_gps(
            real_db_session, _admin_scope(), None, 120.0
        ) is None

    def test_nearest_village_within_radius(self, real_db_session):
        db = real_db_session
        far = _add_village(db, "远村", 30.5, 120.5)
        near = _add_village(db, "近村", 30.001, 120.001)
        closer = _add_village(db, "更近村", 30.0001, 120.0001)
        _add_village(db, "无坐标村", None, None)
        _add_village(db, "已删除村", 30.0, 120.0, is_active=False)
        matched = media_service.match_village_by_gps(db, _admin_scope(), 30.0, 120.0)
        assert matched == closer.id
        assert matched != near.id and matched != far.id
        # 已在数据域之外的组织 → 无匹配
        assert media_service.match_village_by_gps(
            db, _org_scope([99]), 30.0, 120.0
        ) is None

    def test_self_only_scope_requires_creator(self, real_db_session):
        db = real_db_session
        _add_village(db, "村", 30.0, 120.0)
        assert media_service.match_village_by_gps(
            db, _org_scope([], self_only=True, user_id=999), 30.0, 120.0
        ) is None

    def test_no_villages_returns_none(self, real_db_session):
        assert media_service.match_village_by_gps(
            real_db_session, _admin_scope(), 30.0, 120.0
        ) is None


# ════════════════════════════════════════════════════════════════════
#  注册归档
# ════════════════════════════════════════════════════════════════════
class TestCreatePhotoArchive:
    def test_create_with_exif_and_village_match(self, real_db_session):
        db = real_db_session
        user = _user()
        _add_village(db, "拍摄村", 30.258333, 120.170833)
        photo = media_service.create_photo_archive(
            db,
            PhotoArchiveCreate(
                file_url=_save_upload(_jpeg_with_exif(
                    datetime_original="2024:01:15 10:30:00",
                    gps={1: "N", 2: (30.0, 15.0, 30.0), 3: "E", 4: (120.0, 10.0, 15.0)},
                ), suffix=".jpg"),
                file_name="现场.jpg",
                file_size=1024,
                mime_type="image/jpeg",
                tag="入户走访",
            ),
            user,
            _admin_scope(),
        )
        assert photo.id is not None
        assert photo.shot_source == "exif"
        assert photo.village_id is not None
        assert photo.spot_key == "30.2583,120.1708"
        assert photo.taken_at.isoformat() == "2024-01-15T10:30:00+00:00"
        assert float(photo.gps_lat) == pytest.approx(30.258333)
        assert photo.organization_id == 1
        assert photo.created_by == user.id
        assert photo.uploader_id == user.id

    def test_create_manual_without_exif(self, real_db_session):
        db = real_db_session
        photo = media_service.create_photo_archive(
            db,
            PhotoArchiveCreate(file_url=_save_upload(_png_bytes())),
            _user(),
            _admin_scope(),
        )
        assert photo.shot_source == "manual"
        assert photo.taken_at is None
        assert photo.gps_lat is None
        assert photo.spot_key is None
        assert photo.village_id is None

    def test_payload_overrides_exif(self, real_db_session):
        db = real_db_session
        from datetime import datetime, timezone

        payload = PhotoArchiveCreate(
            file_url=_save_upload(_jpeg_with_exif(
                datetime_original="2024:01:15 10:30:00",
                gps={1: "N", 2: (30.0, 15.0, 30.0), 3: "E", 4: (120.0, 10.0, 15.0)},
            ), suffix=".jpg"),
            village_id=42,
            spot_key="自定义点位",
            taken_at=datetime(2025, 1, 1, 8, 0, tzinfo=timezone.utc),
            gps_lat=10.0,
            gps_lng=20.0,
            shot_source="manual",
        )
        photo = media_service.create_photo_archive(db, payload, _user(), _admin_scope())
        assert photo.village_id == 42
        assert photo.spot_key == "自定义点位"
        assert photo.taken_at.isoformat() == "2025-01-01T08:00:00+00:00"
        assert float(photo.gps_lat) == pytest.approx(10.0)
        assert photo.shot_source == "manual"

    def test_create_with_missing_file_degrades_to_manual(self, real_db_session):
        photo = media_service.create_photo_archive(
            real_db_session,
            PhotoArchiveCreate(file_url=_remote_upload_url()),
            _user(),
            _admin_scope(),
        )
        assert photo.id is not None
        assert photo.shot_source == "manual"

    def test_create_rejects_traversal_url(self, real_db_session):
        with pytest.raises(HTTPException) as exc:
            media_service.create_photo_archive(
                real_db_session,
                PhotoArchiveCreate(file_url="/uploads/../etc/passwd"),
                _user(),
                _admin_scope(),
            )
        assert exc.value.status_code == 400


# ════════════════════════════════════════════════════════════════════
#  列表 / 点查 / 更新 / 软删
# ════════════════════════════════════════════════════════════════════
class TestListAndCrud:
    def test_build_payloads_with_reference_names(self, real_db_session):
        from app.models.project import Project
        from app.models.school import School

        db = real_db_session
        village = _add_village(db, "示例村", 30.0, 120.0)
        school = School(name="示例学校", is_active=True)
        project = Project(name="示例项目", is_active=True)
        db.add_all([school, project])
        db.commit()
        db.refresh(school)
        db.refresh(project)
        photo = _add_photo(
            db, village_id=village.id, school_id=school.id, project_id=project.id
        )
        payload = media_service.build_photo_payloads(db, [photo])[0]
        assert payload["village_name"] == "示例村"
        assert payload["school_name"] == "示例学校"
        assert payload["project_name"] == "示例项目"

        # 软删的关联对象不再返回名称
        village.is_active = False
        school.is_active = False
        project.is_active = False
        db.commit()
        payload = media_service.build_photo_payloads(db, [photo])[0]
        assert payload["village_name"] is None
        assert payload["school_name"] is None
        assert payload["project_name"] is None

    def test_build_payloads_without_references(self, real_db_session):
        db = real_db_session
        photo = _add_photo(db)
        payload = media_service.build_photo_payloads(db, [photo])[0]
        assert payload["village_name"] is None
        assert payload["school_name"] is None
        assert payload["project_name"] is None
        # 空列表：三个名称解析均走空集合分支
        assert media_service.build_photo_payloads(db, []) == []

    def test_list_filters_and_scope(self, real_db_session):
        from datetime import datetime, timezone

        db = real_db_session
        target = _add_photo(
            db,
            village_id=7,
            school_id=8,
            project_id=9,
            tag="t1",
            taken_at=datetime(2024, 3, 1, tzinfo=timezone.utc),
        )
        _add_photo(db, village_id=99, tag="t2", organization_id=2)
        _add_photo(db, village_id=7, tag="t1", is_active=False)
        _add_photo(db, village_id=7, tag="t1",
                   taken_at=datetime(2023, 1, 1, tzinfo=timezone.utc))

        items, total = media_service.list_photos(
            db,
            _admin_scope(),
            village_id=7,
            school_id=8,
            project_id=9,
            tag="t1",
            date_from=datetime(2024, 2, 1, tzinfo=timezone.utc).date(),
            date_to=datetime(2024, 4, 1, tzinfo=timezone.utc).date(),
        )
        assert total == 1
        assert [item.id for item in items] == [target.id]

        # 无筛选 + 数据域：仅 org=1 的未软删记录
        all_items, all_total = media_service.list_photos(db, _admin_scope())
        assert all_total == 3
        org_items, org_total = media_service.list_photos(db, _org_scope([1]))
        assert org_total == 2
        assert all(item.organization_id == 1 for item in org_items)
        # 仅本人范围：created_by=1 的记录
        mine, mine_total = media_service.list_photos(
            db, _org_scope([], self_only=True, user_id=1)
        )
        assert mine_total == 3
        assert all(item.created_by == 1 for item in mine)
        # 分页
        page_items, page_total = media_service.list_photos(db, _admin_scope(), page=2, page_size=2)
        assert len(page_items) <= 2
        assert page_total >= 3

    def test_get_photo_404_and_403(self, real_db_session):
        db = real_db_session
        photo = _add_photo(db, organization_id=1, created_by=1)
        with pytest.raises(HTTPException) as exc:
            media_service.get_photo(db, 999999, _user())
        assert exc.value.status_code == 404
        # 其他组织用户（org=2、非创建者）→ 403
        with pytest.raises(HTTPException) as exc:
            media_service.get_photo(db, photo.id, _user(user_id=5, org_id=2))
        assert exc.value.status_code == 403
        # 创建者本人可访问
        assert media_service.get_photo(db, photo.id, _user(user_id=1, org_id=2)).id == photo.id

    def test_update_photo_fields(self, real_db_session):
        db = real_db_session
        photo = _add_photo(db, tag="old")
        from app.schemas.media import PhotoArchiveUpdate

        updated = media_service.update_photo(
            db, photo.id, PhotoArchiveUpdate(tag="new", spot_key="spot-x"), _user()
        )
        assert updated.tag == "new"
        assert updated.spot_key == "spot-x"
        # 空更新不应破坏记录
        again = media_service.update_photo(db, photo.id, PhotoArchiveUpdate(), _user())
        assert again.tag == "new"

    def test_update_missing_photo_404(self, real_db_session):
        from app.schemas.media import PhotoArchiveUpdate

        with pytest.raises(HTTPException) as exc:
            media_service.update_photo(real_db_session, 999999, PhotoArchiveUpdate(), _user())
        assert exc.value.status_code == 404

    def test_delete_soft_deletes(self, real_db_session):
        db = real_db_session
        photo = _add_photo(db)
        deleted = media_service.delete_photo(db, photo.id, _user())
        assert deleted.is_active is False
        assert deleted.deleted_at is not None
        with pytest.raises(HTTPException) as exc:
            media_service.get_photo(db, photo.id, _user())
        assert exc.value.status_code == 404

    def test_delete_missing_photo_404(self, real_db_session):
        with pytest.raises(HTTPException):
            media_service.delete_photo(real_db_session, 999999, _user())


# ════════════════════════════════════════════════════════════════════
#  多期对比
# ════════════════════════════════════════════════════════════════════
class TestCompare:
    def test_compare_returns_periods_in_ascending_order(self, real_db_session):
        from datetime import datetime, timezone

        db = real_db_session
        later = _add_photo(
            db, spot_key="village-gate", taken_at=datetime(2025, 1, 1, tzinfo=timezone.utc)
        )
        earlier = _add_photo(
            db, spot_key="village-gate", taken_at=datetime(2023, 1, 1, tzinfo=timezone.utc)
        )
        _add_photo(db, spot_key="other")
        _add_photo(db, spot_key="village-gate", is_active=False)
        _add_photo(db, spot_key="village-gate", organization_id=2)

        rows = media_service.compare_photos(db, _org_scope([1]), "village-gate")
        assert [row["id"] for row in rows] == [earlier.id, later.id]
        assert set(rows[0]) == {"id", "file_url", "taken_at"}

    def test_compare_requires_spot_key(self, real_db_session):
        for key in (None, "", "   "):
            with pytest.raises(HTTPException) as exc:
                media_service.compare_photos(real_db_session, _admin_scope(), key)
            assert exc.value.status_code == 400

    def test_compare_respects_data_scope(self, real_db_session):
        db = real_db_session
        _add_photo(db, spot_key="k", organization_id=2)
        assert media_service.compare_photos(db, _org_scope([1]), "k") == []


# ════════════════════════════════════════════════════════════════════
#  对比图合成
# ════════════════════════════════════════════════════════════════════
class TestComposeCompareImage:
    def test_three_or_less_is_single_row(self, real_db_session):
        from datetime import datetime, timezone

        db = real_db_session
        first = _add_photo(
            db,
            file_url=_save_upload(_png_bytes(size=(100, 200), color="red")),
            taken_at=datetime(2024, 1, 15, tzinfo=timezone.utc),
        )
        second = _add_photo(
            db,
            file_url=_save_upload(_png_bytes(size=(200, 100), color="blue")),
            taken_at=datetime(2024, 6, 15, tzinfo=timezone.utc),
        )
        png = media_service.compose_compare_image(db, _admin_scope(), [first.id, second.id])
        canvas = Image.open(io.BytesIO(png)).convert("RGB")
        # 两张图等比缩放到 360 高：宽度 180 / 720 → 单元格宽 720，横排 2 列
        assert canvas.height == media_service.COMPARE_CELL_HEIGHT + media_service.COMPARE_LABEL_HEIGHT
        assert canvas.width == 720 * 2
        # 第一张下方日期标注带内有非白像素（有文字绘制）
        label_band = canvas.crop((0, media_service.COMPARE_CELL_HEIGHT, 720, canvas.height))
        non_white_colors = [
            color for _count, color in label_band.getcolors(maxcolors=1 << 24)
            if color != (255, 255, 255)
        ]
        assert non_white_colors
        # 保持传入顺序：第一列偏红、第二列偏蓝
        left_pixel = canvas.getpixel((720 // 2, 10))
        right_pixel = canvas.getpixel((720 + 720 // 2, 10))
        assert left_pixel[0] > left_pixel[2]
        assert right_pixel[2] > right_pixel[0]

    def test_four_images_two_columns(self, real_db_session):
        db = real_db_session
        ids = [
            _add_photo(db, file_url=_save_upload(_png_bytes(size=(50, 50), color=color))).id
            for color in ("red", "green", "blue", "yellow")
        ]
        png = media_service.compose_compare_image(db, _admin_scope(), ids)
        canvas = Image.open(io.BytesIO(png)).convert("RGB")
        cell_height = media_service.COMPARE_CELL_HEIGHT + media_service.COMPARE_LABEL_HEIGHT
        assert canvas.width == media_service.COMPARE_CELL_HEIGHT * 2  # 50x50 → 360 宽
        assert canvas.height == cell_height * 2

    def test_unknown_date_label(self, real_db_session):
        db = real_db_session
        photo = _add_photo(
            db, file_url=_save_upload(_png_bytes(size=(20, 20))), taken_at=None
        )
        png = media_service.compose_compare_image(db, _admin_scope(), [photo.id])
        canvas = Image.open(io.BytesIO(png)).convert("RGB")
        assert canvas.width == media_service.COMPARE_CELL_HEIGHT
        assert canvas.height == media_service.COMPARE_CELL_HEIGHT + media_service.COMPARE_LABEL_HEIGHT

    def test_duplicate_ids_are_deduplicated(self, real_db_session):
        db = real_db_session
        photo = _add_photo(db, file_url=_save_upload(_png_bytes(size=(20, 20))))
        png = media_service.compose_compare_image(db, _admin_scope(), [photo.id, photo.id])
        assert png.startswith(b"\x89PNG")

    def test_empty_ids_rejected(self, real_db_session):
        with pytest.raises(HTTPException) as exc:
            media_service.compose_compare_image(real_db_session, _admin_scope(), [])
        assert exc.value.status_code == 400

    def test_too_many_ids_rejected(self, real_db_session):
        with pytest.raises(HTTPException) as exc:
            media_service.compose_compare_image(
                real_db_session, _admin_scope(), list(range(1, media_service.MAX_COMPARE_IMAGES + 2))
            )
        assert exc.value.status_code == 400

    def test_missing_photo_404(self, real_db_session):
        with pytest.raises(HTTPException) as exc:
            media_service.compose_compare_image(real_db_session, _admin_scope(), [999999])
        assert exc.value.status_code == 404

    def test_out_of_scope_photo_404(self, real_db_session):
        db = real_db_session
        photo = _add_photo(db, file_url=_save_upload(_png_bytes()), organization_id=2)
        with pytest.raises(HTTPException) as exc:
            media_service.compose_compare_image(db, _org_scope([1]), [photo.id])
        assert exc.value.status_code == 404

    def test_missing_file_404(self, real_db_session):
        db = real_db_session
        photo = _add_photo(db, file_url=_remote_upload_url())
        with pytest.raises(HTTPException) as exc:
            media_service.compose_compare_image(db, _admin_scope(), [photo.id])
        assert exc.value.status_code == 404

    def test_invalid_image_file_400(self, real_db_session):
        db = real_db_session
        photo = _add_photo(db, file_url=_save_upload(b"broken", suffix=".png"))
        with pytest.raises(HTTPException) as exc:
            media_service.compose_compare_image(db, _admin_scope(), [photo.id])
        assert exc.value.status_code == 400

    def test_format_taken_at(self):
        from datetime import datetime, timezone

        assert media_service._format_taken_at(None) == "未知日期"
        value = datetime(2024, 1, 15, tzinfo=timezone.utc)
        assert media_service._format_taken_at(value) == "2024-01-15"
