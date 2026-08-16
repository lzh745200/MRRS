"""
上报数据包后端闭环测试

覆盖：
1. 导出按用户过滤（普通用户仅本人录入 / 管理员全组织）+ manifest 新字段 export_scope/exported_by_name
2. 字段级校验与自动纠正（必填/电话/日期/枚举/数值）
3. confirm_import：rejected 行不入库、corrected 行以纠正值入库、skipped_counts 计入拒绝数
4. 接收权限收紧：非管理员 import/confirm/received → 403
5. GET /data-packages/received 分页与字段
6. 旧格式 manifest（无 export_scope/exported_by_name）仍可 validate + confirm
"""

import io
import json
import zipfile
from datetime import datetime
from unittest.mock import Mock

from app.api.v1.data.data.data_packages import _export_owner_scope, get_package_service
from app.models.data_package import DataPackage
from app.models.organization import Organization
from app.models.school import School
from app.models.supported_village import SupportedVillage
from app.models.user import User
from app.services.data_package_service import DataPackageService
from app.services.package_record_validator import validate_records

BASE = "/api/v1/data-packages"


# ──────────────────────────── 工具函数 ────────────────────────────


def _make_org(db, name="测试单位", code="ORG100"):
    org = Organization(name=name, code=code, is_active=True)
    db.add(org)
    db.commit()
    db.refresh(org)
    return org


def _make_user(db, username, full_name):
    user = User(username=username, hashed_password="x", full_name=full_name, role="user")
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _add_village(db, org_id, name, created_by):
    v = SupportedVillage(village_name=name, organization_id=org_id, created_by=created_by)
    db.add(v)
    db.commit()
    db.refresh(v)
    return v


def _write_package_zip(path, manifest: dict, data: dict):
    """写出标准数据包 zip（manifest.json + data/{type}.json）"""
    with zipfile.ZipFile(str(path), "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False))
        for data_type, records in data.items():
            zf.writestr(f"data/{data_type}.json", json.dumps(records, ensure_ascii=False))


def _add_package_row(db, org_id, file_path, status="validated", **kwargs):
    pkg = DataPackage(
        package_code=kwargs.pop("package_code", f"PKG-{datetime.now().timestamp()}"),
        org_id=org_id,
        file_path=str(file_path),
        file_name=kwargs.pop("file_name", "pkg.zip"),
        status=status,
        type=kwargs.pop("type", "report"),
        version="1.0",
        data_types=kwargs.pop("data_types", json.dumps(["schools"])),
        record_count=kwargs.pop("record_count", 0),
        created_by=kwargs.pop("created_by", 1),
        **kwargs,
    )
    db.add(pkg)
    db.commit()
    db.refresh(pkg)
    return pkg


# ──────────────────────── 1. 导出按用户过滤 ────────────────────────


class TestExportOwnerScope:
    def test_owner_scope_admin_returns_none(self):
        admin = Mock()
        admin.role = "admin"
        admin.is_superuser = False
        admin.id = 1
        assert _export_owner_scope(admin) is None

    def test_owner_scope_regular_user_returns_id(self):
        user = Mock()
        user.role = "user"
        user.is_superuser = False
        user.id = 42
        assert _export_owner_scope(user) == 42

    async def test_export_owner_id_filters_self_records(self, real_db_session, tmp_path):
        """普通用户导出：仅含本人录入记录，manifest 标记 export_scope=self"""
        db = real_db_session
        org = _make_org(db)
        u1 = _make_user(db, "zhangsan", "张三")
        u2 = _make_user(db, "lisi", "李四")
        _add_village(db, org.id, "张三的村", u1.id)
        _add_village(db, org.id, "李四的村", u2.id)

        service = DataPackageService(db, upload_dir=str(tmp_path))
        result = await service.export_package(
            org_id=org.id, data_types=["villages"], export_by=u1.id,
            owner_id=u1.id, exported_by_name=u1.full_name,
        )

        assert result.manifest.export_scope == "self"
        assert result.manifest.exported_by_name == "张三"
        assert result.manifest.record_counts["villages"] == 1

        with zipfile.ZipFile(result.file_path) as zf:
            records = json.loads(zf.read("data/villages.json").decode("utf-8"))
        assert len(records) == 1
        assert records[0]["village_name"] == "张三的村"
        assert records[0]["created_by"] == u1.id

    async def test_export_no_owner_id_exports_whole_org(self, real_db_session, tmp_path):
        """管理员导出（owner_id=None）：全组织记录，export_scope=org"""
        db = real_db_session
        org = _make_org(db, code="ORG101")
        u1 = _make_user(db, "admin1", "管理员")
        u2 = _make_user(db, "user1", "普通用户")
        _add_village(db, org.id, "村A", u1.id)
        _add_village(db, org.id, "村B", u2.id)

        service = DataPackageService(db, upload_dir=str(tmp_path))
        result = await service.export_package(
            org_id=org.id, data_types=["villages"], export_by=u1.id,
        )

        assert result.manifest.export_scope == "org"
        assert result.manifest.record_counts["villages"] == 2


# ──────────────────────── 2. 字段级校验与纠正 ────────────────────────


class TestRecordValidator:
    def test_required_field_missing_rejected(self):
        """必填字段缺失（villages.village_name）→ rejected 且原因可见"""
        result = validate_records("villages", [{"id": 1, "county": "某县"}])
        assert not result["ok"] and not result["corrected"]
        assert len(result["rejected"]) == 1
        assert result["rejected"][0]["row"] == 0
        assert any("village_name" in r for r in result["rejected"][0]["reasons"])

    def test_phone_separators_corrected(self):
        """手机号 "138-1234-5678" → 纠正为 13812345678"""
        result = validate_records(
            "schools", [{"id": 1, "name": "学校A", "contact_phone": "138-1234-5678"}]
        )
        assert not result["rejected"]
        assert len(result["corrected"]) == 1
        assert result["corrected"][0]["data"]["contact_phone"] == "13812345678"
        assert any("contact_phone" in f for f in result["corrected"][0]["fixes"])

    def test_phone_landline_ok(self):
        """带区号座机合法"""
        result = validate_records(
            "projects", [{"id": 1, "name": "项目A", "contact_phone": "0851-1234567"}]
        )
        assert not result["rejected"]
        assert result["corrected"][0]["data"]["contact_phone"] == "08511234567"

    def test_phone_invalid_rejected(self):
        result = validate_records(
            "schools", [{"id": 1, "name": "学校A", "contact_phone": "123"}]
        )
        assert len(result["rejected"]) == 1
        assert any("电话格式不正确" in r for r in result["rejected"][0]["reasons"])

    def test_date_slash_normalized(self):
        """日期 "2024/3/5" → 归一 ISO"""
        result = validate_records(
            "projects", [{"id": 1, "name": "项目A", "start_date": "2024/3/5"}]
        )
        assert not result["rejected"]
        normalized = result["corrected"][0]["data"]["start_date"]
        assert normalized.startswith("2024-03-05")

    def test_date_compact_normalized(self):
        """YYYYMMDD 也可归一"""
        result = validate_records(
            "funds", [{"id": 1, "date": "20240305"}]
        )
        assert not result["rejected"]
        assert result["corrected"][0]["data"]["date"].startswith("2024-03-05")

    def test_date_unparseable_rejected(self):
        result = validate_records(
            "projects", [{"id": 1, "name": "项目A", "start_date": "不是日期"}]
        )
        assert len(result["rejected"]) == 1
        assert any("日期格式无法识别" in r for r in result["rejected"][0]["reasons"])

    def test_enum_invalid_rejected(self):
        """枚举字段非法值 → rejected"""
        result = validate_records(
            "projects", [{"id": 1, "name": "项目A", "status": "bogus_status"}]
        )
        assert len(result["rejected"]) == 1
        assert any("取值非法" in r for r in result["rejected"][0]["reasons"])

    def test_enum_valid_passes(self):
        result = validate_records(
            "projects", [{"id": 1, "name": "项目A", "status": "in_progress", "type": "education"}]
        )
        assert not result["rejected"]
        assert len(result["ok"]) == 1

    def test_numeric_string_converted(self):
        """数字字符串转数值"""
        result = validate_records(
            "schools", [{"id": 1, "name": "学校A", "student_count": "100"}]
        )
        assert not result["rejected"]
        assert result["corrected"][0]["data"]["student_count"] == 100

    def test_negative_amount_rejected(self):
        """金额字段负数拦截"""
        result = validate_records("funds", [{"id": 1, "amount": -5}])
        assert len(result["rejected"]) == 1
        assert any("负数" in r for r in result["rejected"][0]["reasons"])

    def test_trim_and_empty_string_to_none(self):
        """字符串 trim + 可空列空字符串转 None"""
        result = validate_records(
            "villages", [{"id": 1, "village_name": "  村A  ", "county": ""}]
        )
        assert not result["rejected"]
        data = result["corrected"][0]["data"]
        assert data["village_name"] == "村A"
        assert data["county"] is None

    def test_unknown_type_passthrough(self):
        """未知数据类型不做字段级校验，原样放行"""
        result = validate_records("unknown_type", [{"id": 1}])
        assert result["ok"] == [{"id": 1}]
        assert not result["rejected"]

    def test_non_dict_record_rejected(self):
        result = validate_records("villages", ["not-a-dict"])
        assert len(result["rejected"]) == 1


# ──────────────── 3. confirm_import 校验接入（真实库） ────────────────


class TestConfirmImportValidation:
    async def test_rejected_skipped_corrected_imported(self, real_db_session, tmp_path):
        """confirm 后：rejected 行不在库中、corrected 行以纠正值入库、skipped 计数正确"""
        db = real_db_session
        org = _make_org(db)

        manifest = {
            "version": "1.0",
            "package_type": "report",
            "org_code": org.code,
            "org_name": org.name,
            "data_types": ["schools"],
            "record_counts": {"schools": 3},
            "export_time": datetime.now().isoformat(),
            "checksum": "",
            "encryption": "none",
            "compression": "zip",
        }
        records = [
            {"id": 1, "name": "学校A"},  # ok
            {
                "id": 2,
                "name": " 学校B ",
                "contact_phone": "138-1234-5678",
                "support_start_date": "2024/3/5",
                "student_count": "100",
            },  # corrected
            {"id": 3},  # rejected：缺必填 name
        ]
        zip_path = tmp_path / "confirm_test.zip"
        _write_package_zip(zip_path, manifest, {"schools": records})
        pkg = _add_package_row(db, org.id, zip_path, record_count=3)

        service = DataPackageService(db, upload_dir=str(tmp_path))
        result = await service.confirm_import(pkg.id, confirmed_by=1)

        assert result.success is True
        assert result.imported_counts["schools"] == 2
        assert result.skipped_counts["schools"] == 1
        # rejected 明细进入 errors（行号 + 中文原因）
        assert any("第3行" in (e.message if hasattr(e, "message") else str(e)) for e in result.errors)

        schools = {s.id: s for s in db.query(School).all()}
        assert set(schools.keys()) == {1, 2}
        assert 3 not in schools  # rejected 行不入库
        s2 = schools[2]
        assert s2.name == "学校B"  # trim 纠正生效
        assert s2.contact_phone == "13812345678"
        assert s2.student_count == 100
        assert s2.support_start_date is not None
        assert s2.support_start_date.year == 2024
        assert s2.support_start_date.month == 3
        assert s2.support_start_date.day == 5
        # 组织改写为本地组织
        assert s2.organization_id == org.id

    async def test_legacy_manifest_validate_and_confirm(self, real_db_session, tmp_path):
        """旧格式 manifest（无 export_scope/exported_by_name）仍能 validate + confirm"""
        db = real_db_session
        org = _make_org(db, code="ORG102")

        legacy_manifest = {
            "version": "1.0",
            "package_type": "report",
            "org_code": org.code,
            "org_name": org.name,
            "data_types": ["villages"],
            "record_counts": {"villages": 1},
        }
        records = [{"id": 1, "village_name": "旧包村"}]
        zip_path = tmp_path / "legacy.zip"
        _write_package_zip(zip_path, legacy_manifest, {"villages": records})

        service = DataPackageService(db, upload_dir=str(tmp_path))
        validation = await service.validate_package(str(zip_path))
        assert validation.is_valid is True
        assert validation.manifest.export_scope is None  # 旧包无新字段，不报错

        pkg = _add_package_row(db, org.id, zip_path, data_types=json.dumps(["villages"]), record_count=1)
        result = await service.confirm_import(pkg.id, confirmed_by=1)
        assert result.success is True
        assert result.imported_counts["villages"] == 1
        assert db.query(SupportedVillage).filter_by(village_name="旧包村").count() == 1

    async def test_validate_warnings_include_field_summary(self, real_db_session, tmp_path):
        """validate_package 的 warnings 含字段级校验摘要（additive，不影响 is_valid）"""
        db = real_db_session
        service = DataPackageService(db, upload_dir=str(tmp_path))

        manifest = {
            "version": "1.0",
            "data_types": ["villages"],
            "record_counts": {"villages": 2},
        }
        records = [{"id": 1, "village_name": "村A"}, {"id": 2}]
        zip_path = tmp_path / "validate_test.zip"
        _write_package_zip(zip_path, manifest, {"villages": records})

        result = await service.validate_package(str(zip_path))
        assert result.is_valid is True
        assert any("字段校验" in w and "拒绝1条" in w for w in result.warnings)
        assert any("第2行" in w for w in result.warnings)


# ──────────────────── 4. 接收权限收紧（403） ────────────────────


class TestReceivePermission:
    def test_import_forbidden_for_regular_user(self, client_with_regular_user_auth):
        resp = client_with_regular_user_auth.post(
            f"{BASE}/import", files={"file": ("a.zip", b"data", "application/zip")}
        )
        assert resp.status_code == 403
        assert "仅管理员可接收数据包" in resp.json()["detail"]

    def test_confirm_forbidden_for_regular_user(self, client_with_regular_user_auth):
        resp = client_with_regular_user_auth.post(f"{BASE}/1/confirm", json={})
        assert resp.status_code == 403
        assert "仅管理员可接收数据包" in resp.json()["detail"]

    def test_received_forbidden_for_regular_user(self, client_with_regular_user_auth):
        resp = client_with_regular_user_auth.get(f"{BASE}/received")
        assert resp.status_code == 403


# ──────────────────── 5. /received 接收记录 ────────────────────


class TestReceivedList:
    def test_received_pagination_and_fields(self, auth_client_with_db):
        client, db = auth_client_with_db
        org = _make_org(db, code="ORG200")
        importer = _make_user(db, "receiver", "接收人甲")

        for idx in range(3):
            _add_package_row(
                db,
                org.id,
                f"/tmp/pkg_{idx}.zip",
                package_code=f"PKG-R-{idx}",
                file_name=f"report_{idx}.zip",
                file_size=1024 + idx,
                record_count=10 + idx,
                manifest={
                    "org_code": "ORG200",
                    "org_name": "测试单位",
                    "export_scope": "self",
                    "exported_by_name": "上报人乙",
                    "validation_summary": ["villages: 字段校验 通过1条/纠正0条/拒绝0条"],
                },
                imported_by=importer.id,
                imported_at=datetime(2026, 1, 1),
            )
        # 非 report 类型不出现在接收记录
        _add_package_row(db, org.id, "/tmp/task_pkg.zip", package_code="PKG-T-1", type="task")

        resp = client.get(f"{BASE}/received?page=1&page_size=2")
        assert resp.status_code == 200
        payload = resp.json()
        data = payload.get("data", payload)
        assert data["total"] == 3
        assert len(data["items"]) == 2
        assert data["page"] == 1
        assert data["page_size"] == 2

        item = data["items"][0]
        assert item["package_code"] == "PKG-R-2"  # 按创建时间倒序
        assert item["file_name"] == "report_2.zip"
        assert item["file_size"] == 1026
        assert item["record_count"] == 12
        assert item["imported_by"] == "接收人甲"
        assert item["org_code"] == "ORG200"
        assert item["org_name"] == "测试单位"
        assert item["export_scope"] == "self"
        assert item["exported_by_name"] == "上报人乙"
        assert item["validation_summary"]
        assert item["imported_at"] is not None

        # 第二页
        resp2 = client.get(f"{BASE}/received?page=2&page_size=2")
        data2 = resp2.json().get("data", resp2.json())
        assert data2["total"] == 3
        assert len(data2["items"]) == 1

    def test_received_manifest_missing_fields_tolerated(self, auth_client_with_db):
        """manifest 缺失新字段时不报错，对应字段返回 None"""
        client, db = auth_client_with_db
        org = _make_org(db, code="ORG201")
        _add_package_row(db, org.id, "/tmp/legacy_pkg.zip", package_code="PKG-L-1", manifest=None)

        resp = client.get(f"{BASE}/received")
        assert resp.status_code == 200
        data = resp.json().get("data", resp.json())
        assert data["total"] == 1
        item = data["items"][0]
        assert item["export_scope"] is None
        assert item["exported_by_name"] is None
        assert item["imported_by"] is None
        assert item["validation_summary"] is None


# ──────────────── 6. 一键上报端到端（owner 过滤） ────────────────


class TestOneClickReportOwnerFilter:
    def _override_service(self, client, db, tmp_path):
        """数据包服务落盘目录重定向到临时目录，避免污染应用数据目录"""
        client.app.dependency_overrides[get_package_service] = (
            lambda: DataPackageService(db, upload_dir=str(tmp_path))
        )

    def test_regular_user_report_only_own_records(self, client_with_db, tmp_path):
        """普通用户一键上报：包内仅含本人录入的村庄"""
        client, db = client_with_db
        org = _make_org(db, code="ORG300")
        u1 = _make_user(db, "reporter", "上报人")
        u2 = _make_user(db, "otheruser", "其他人")
        _add_village(db, org.id, "上报人的村", u1.id)
        _add_village(db, org.id, "其他人的村", u2.id)

        regular = Mock()
        regular.id = u1.id
        regular.username = u1.username
        regular.full_name = u1.full_name
        regular.role = "user"
        regular.is_superuser = False
        regular.is_active = True
        regular.organization_id = org.id

        from app.core.security import get_current_user

        self._override_service(client, db, tmp_path)
        client.app.dependency_overrides[get_current_user] = lambda: regular
        try:
            resp = client.post(f"{BASE}/one-click-report", json={"data_types": ["villages"]})
        finally:
            client.app.dependency_overrides.pop(get_current_user, None)

        assert resp.status_code == 200
        with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
            manifest = json.loads(zf.read("manifest.json").decode("utf-8"))
            records = json.loads(zf.read("data/villages.json").decode("utf-8"))

        assert manifest["export_scope"] == "self"
        assert manifest["exported_by_name"] == "上报人"
        assert len(records) == 1
        assert records[0]["village_name"] == "上报人的村"

    def test_admin_report_whole_org(self, auth_client_with_db, tmp_path):
        """管理员一键上报：全组织记录，export_scope=org（行为不变）"""
        client, db = auth_client_with_db
        org = _make_org(db, code="ORG301")
        u1 = _make_user(db, "userx", "用户X")
        _add_village(db, org.id, "村甲", u1.id)
        _add_village(db, org.id, "村乙", u1.id)

        self._override_service(client, db, tmp_path)
        try:
            resp = client.post(f"{BASE}/one-click-report", json={"data_types": ["villages"]})
        finally:
            client.app.dependency_overrides.pop(get_package_service, None)

        assert resp.status_code == 200
        with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
            manifest = json.loads(zf.read("manifest.json").decode("utf-8"))
            records = json.loads(zf.read("data/villages.json").decode("utf-8"))

        assert manifest["export_scope"] == "org"
        assert len(records) == 2
