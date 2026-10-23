"""v1.12.22 分支闭合：历史错误/边界分支的针对性回归。

背景：一批历史分支此前仅由并发会话的未提交测试覆盖，HEAD 自洽的提交集在
不同 worker 分配下出现少量 branch 缺口（branch 门禁 fail_under=100）。
本文件按「真实行为」逐条覆盖这些边界，不依赖测试顺序/其它模块状态。
"""
import asyncio
import io
import os
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import sys

import pytest
from fastapi import HTTPException

CWD_TMP = os.path.join(os.path.dirname(os.path.abspath(__file__)), '_tmp_restore')


def _admin(**kw):
    base = dict(id=1, username="admin", role="admin", is_superuser=True,
                is_active=True, organization_id=1)
    base.update(kw)
    return SimpleNamespace(**base)


class TestHelpSnippetBoundaries:
    def test_snippet_branches(self, monkeypatch):
        from app.api.v1.system import help as help_mod

        articles = [
            # 仅标题命中 → snippet_start = -1（1025 false）
            {"id": 1, "category": "c", "title": "QQ 指引", "content": "正文无关键词", "tags": []},
            # 内容开头命中 → start=0（1029 false），end<len（1031 true）
            {"id": 2, "category": "c", "title": "t2", "content": "qq " + "a" * 100, "tags": []},
            # 内容末尾命中 → start>0（1029 true），end==len（1031 false）
            {"id": 3, "category": "c", "title": "t3", "content": "b" * 100 + " qq", "tags": []},
            # 内容中部命中 → start>0、end<len（两个 true）
            {"id": 4, "category": "c", "title": "t4", "content": "b" * 50 + "qq" + "c" * 100, "tags": []},
        ]
        monkeypatch.setattr(help_mod, "_HELP_ARTICLES", articles)
        resp = asyncio.run(help_mod.search_help_articles(q="qq", limit=20, current_user=_admin()))
        data = resp.get("data") if isinstance(resp, dict) else None
        items = (data or resp).get("items", [])
        by_id = {i["id"]: i for i in items}
        assert by_id[1]["snippet"] == "..."
        assert by_id[2]["snippet"].startswith("qq")
        assert by_id[3]["snippet"].startswith("...")
        assert by_id[3]["snippet"].endswith("qq")
        assert by_id[4]["snippet"].startswith("...") and by_id[4]["snippet"].endswith("...")


class TestBatchValidateTableWhitelist:
    def test_unknown_table_rejected(self):
        from app.api.v1 import batch_operations as mod

        with pytest.raises(HTTPException) as ei:
            asyncio.run(mod.validate_batch(
                table_name="sqlite_master", ids=[1],
                db=MagicMock(), current_user=_admin(),
            ))
        assert ei.value.status_code == 400


class TestCacheNoneSentinel:
    def test_cache_none_lookup_uses_get_entry(self):
        from app.core import cache as cache_mod

        calls = {"n": 0}

        def fn():
            calls["n"] += 1
            return None

        inst = MagicMock()
        inst.cache_none = True
        inst.get_entry.return_value = (True, None)
        decorated = cache_mod.cached(cache_instance=inst, cache_none=True)(fn)
        assert decorated() is None
        assert calls["n"] == 0  # get_entry 判定命中，不再重算


class TestVillageAttachmentBlockedExt:
    def test_blocked_extension_rejected(self, monkeypatch):
        from app.api.v1 import supported_village as mod

        monkeypatch.setattr(mod, "_get_village_or_404", lambda *a, **k: SimpleNamespace(id=1))
        monkeypatch.setattr(mod, "read_upload_with_limit", AsyncMock(return_value=b"<html>"))
        upload = SimpleNamespace(filename="evil.html")
        with pytest.raises(HTTPException) as ei:
            asyncio.run(mod.upload_section_attachment(
                village_id=1, section="basic", file=upload,
                current_user=_admin(), db=MagicMock(),
            ))
        assert ei.value.status_code == 400


class TestImportDetectModelFallbacks:
    def test_models_without_org_or_timestamps(self, monkeypatch):
        from app.api.v1.data.data import data_packages as mod
        from app.services import data_package_service as svc_mod

        from sqlalchemy import Boolean, Column, DateTime, Integer
        from sqlalchemy.orm import declarative_base

        Base = declarative_base()

        class NoCreated(Base):
            __tablename__ = "closure_no_created"
            id = Column(Integer, primary_key=True)
            organization_id = Column(Integer)
            updated_at = Column(DateTime)

        class NoOrgNoId(Base):
            __tablename__ = "closure_no_org_no_id"
            id = Column(Integer, primary_key=True)
            updated_at = Column(DateTime)
            created_at = Column(DateTime)
            is_active = Column(Boolean)

        class WithCreatedActive(Base):
            __tablename__ = "closure_with_created_active"
            id = Column(Integer, primary_key=True)
            organization_id = Column(Integer)
            updated_at = Column(DateTime)
            created_at = Column(DateTime)
            is_active = Column(Boolean)

        monkeypatch.setattr(svc_mod, "DATA_TYPE_MODELS", {
            "no_created": NoCreated,
            "with_created_active": WithCreatedActive,
        })
        service = MagicMock()
        service.get_package.return_value = SimpleNamespace(created_at=None)
        q = MagicMock()
        q.filter.return_value = q
        q.scalar.return_value = 0
        service.db.query.return_value = q
        result = asyncio.run(mod.incremental_detect_changes(
            base_package_id=1, org_id=1, data_types=["no_created", "with_created_active"],
            current_user=_admin(), service=service, permission_service=MagicMock(),
        ))
        assert result is not None


class TestControlPackageConfigType:
    def test_non_dict_system_config_rejected(self, monkeypatch):
        import json
        import zipfile
        from app.api.v1 import control_package as mod
        from app.core.package_integrity import sign_manifest

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("manifest.json", json.dumps(sign_manifest({"package_type": "control"}, None)))
            zf.writestr("system_config.json", json.dumps(["not-a-dict"]))
        payload = buf.getvalue()
        monkeypatch.setattr(mod, "read_upload_with_limit", AsyncMock(return_value=payload))
        upload = SimpleNamespace(filename="cp.zip", read=AsyncMock(return_value=payload))
        with pytest.raises(HTTPException) as ei:
            asyncio.run(mod.import_control_package(
                file=upload, db=MagicMock(), current_user=_admin(),
            ))
        assert ei.value.status_code == 400
        assert "system_config.json" in ei.value.detail


class TestDataPackageFriendlyErrors:
    def test_manifest_business_error_maps_to_400(self, monkeypatch):
        from app.api.v1.data.data import data_packages as mod
        from app.core.exceptions import BusinessError

        monkeypatch.setattr(mod, "read_upload_with_limit", AsyncMock(return_value=b"zip-bytes"))
        service = MagicMock()
        service.import_package = AsyncMock(side_effect=BusinessError("manifest.json missing"))
        permission = MagicMock()
        permission.can_access_organization.return_value = True
        upload = SimpleNamespace(filename="pkg.zip", read=AsyncMock(return_value=b"zip-bytes"))
        with pytest.raises(HTTPException) as ei:
            asyncio.run(mod.import_data_package(
                file=upload, org_id=1, request=None, current_user=_admin(),
                service=service, history_service=MagicMock(), permission_service=permission,
            ))
        assert ei.value.status_code == 400
        assert "清单" in ei.value.detail


class TestDataPackageGenericBusinessError:
    def test_generic_business_error_keeps_detail(self, monkeypatch):
        from app.api.v1.data.data import data_packages as mod
        from app.core.exceptions import BusinessError

        monkeypatch.setattr(mod, "read_upload_with_limit", AsyncMock(return_value=b"zip-bytes"))
        service = MagicMock()
        service.import_package = AsyncMock(side_effect=BusinessError("导入校验未通过：数量超限"))
        permission = MagicMock()
        permission.can_access_organization.return_value = True
        upload = SimpleNamespace(filename="pkg.zip", read=AsyncMock(return_value=b"zip-bytes"))
        with pytest.raises(HTTPException) as ei:
            asyncio.run(mod.import_data_package(
                file=upload, org_id=1, request=None, current_user=_admin(),
                service=service, history_service=MagicMock(), permission_service=permission,
            ))
        assert ei.value.status_code == 400
        assert ei.value.detail == "导入校验未通过：数量超限"


class TestEncryptedUploadCleanup:
    def _call(self, mod, service, monkeypatch, exists=True):
        upload = SimpleNamespace(filename="enc.rrs", read=AsyncMock(return_value=b"x"))
        request = SimpleNamespace(headers={})
        monkeypatch.setattr(mod, "get_org_with_fallback", lambda **kw: 1)
        if not exists:
            monkeypatch.setattr(mod.os.path, "exists", lambda p: False)
        return asyncio.run(mod.upload_encrypted_package(
            request=request, file=upload, password=None,
            current_user=_admin(), service=service,
        ))

    def test_http_exception_with_existing_temp_file(self, monkeypatch):
        from app.api.v1.data.data import data_packages as mod

        service = MagicMock()
        monkeypatch.setattr(
            mod, "read_upload_with_limit",
            AsyncMock(side_effect=HTTPException(status_code=413, detail="too large")),
        )
        with pytest.raises(HTTPException) as ei:
            self._call(mod, service, monkeypatch, exists=True)
        assert ei.value.status_code == 413

    def test_http_exception_without_temp_file(self, monkeypatch):
        from app.api.v1.data.data import data_packages as mod

        service = MagicMock()
        monkeypatch.setattr(
            mod, "read_upload_with_limit",
            AsyncMock(side_effect=HTTPException(status_code=413, detail="too large")),
        )
        with pytest.raises(HTTPException) as ei:
            self._call(mod, service, monkeypatch, exists=False)
        assert ei.value.status_code == 413

    def test_generic_error_without_temp_file(self, monkeypatch):
        from app.api.v1.data.data import data_packages as mod

        service = MagicMock()
        service._create_package_record.side_effect = RuntimeError("boom")
        monkeypatch.setattr(mod, "read_upload_with_limit", AsyncMock(return_value=b"x"))
        with pytest.raises(HTTPException) as ei:
            self._call(mod, service, monkeypatch, exists=False)
        assert ei.value.status_code == 500


class TestBackupUploadCleanup:
    @staticmethod
    def _valid_zip():
        import zipfile

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("data/rural_revitalization.db", b"db")
        return buf.getvalue()

    def _call(self, monkeypatch, *, get_backup_side_effect=None,
              makedirs_side_effect=None, restore_side_effect=None, exists=None):
        from app.api.v1.system import backup as mod
        from app.utils import paths as paths_mod
        from app.core import database as db_mod

        monkeypatch.setattr(db_mod, "check_disk_space", lambda **kw: {"sufficient": True})
        if get_backup_side_effect is not None:
            monkeypatch.setattr(paths_mod, "get_backup_path", MagicMock(side_effect=get_backup_side_effect))
        else:
            monkeypatch.setattr(paths_mod, "get_backup_path", lambda: CWD_TMP)
        if makedirs_side_effect is not None:
            monkeypatch.setattr(mod.os, "makedirs", MagicMock(side_effect=makedirs_side_effect))
        if exists is not None:
            monkeypatch.setattr(mod.os.path, "exists", lambda p: exists)
        if restore_side_effect is not None:
            monkeypatch.setattr(mod, "get_backup_service", lambda db: MagicMock(
                restore_backup=MagicMock(side_effect=restore_side_effect)))
        content = self._valid_zip()
        upload = SimpleNamespace(filename="b.zip", read=AsyncMock(side_effect=[content, b""]))
        return mod, upload

    def test_value_error_before_path(self, monkeypatch):
        mod_, upload = self._call(monkeypatch, get_backup_side_effect=ValueError("disk"))
        with pytest.raises(HTTPException) as ei:
            asyncio.run(mod_.upload_and_restore(file=upload, password=None, db=MagicMock(), current_user=_admin()))
        assert ei.value.status_code == 400

    def test_http_exception_before_path(self, monkeypatch):
        mod_, upload = self._call(monkeypatch, makedirs_side_effect=HTTPException(status_code=409, detail="x"))
        with pytest.raises(HTTPException) as ei:
            asyncio.run(mod_.upload_and_restore(file=upload, password=None, db=MagicMock(), current_user=_admin()))
        assert ei.value.status_code == 409

    def test_generic_before_path(self, monkeypatch):
        mod_, upload = self._call(monkeypatch, makedirs_side_effect=RuntimeError("boom"))
        with pytest.raises(HTTPException) as ei:
            asyncio.run(mod_.upload_and_restore(file=upload, password=None, db=MagicMock(), current_user=_admin()))
        assert ei.value.status_code == 500

    def test_value_error_with_missing_file(self, monkeypatch, tmp_path):
        mod_, upload = self._call(monkeypatch, restore_side_effect=ValueError("bad"), exists=False)
        with pytest.raises(HTTPException) as ei:
            asyncio.run(mod_.upload_and_restore(file=upload, password=None, db=MagicMock(), current_user=_admin()))
        assert ei.value.status_code == 400

    def test_generic_with_missing_file(self, monkeypatch):
        mod_, upload = self._call(monkeypatch, restore_side_effect=RuntimeError("boom"), exists=False)
        with pytest.raises(HTTPException) as ei:
            asyncio.run(mod_.upload_and_restore(file=upload, password=None, db=MagicMock(), current_user=_admin()))
        assert ei.value.status_code == 500


class TestConfigLogFileRelative:
    def test_relative_log_file_rewritten_when_frozen(self, monkeypatch):
        import sys
        from app.core import config as cfg

        monkeypatch.setattr(sys, "frozen", True, raising=False)
        monkeypatch.setenv("LOG_DIR", "./logs")
        monkeypatch.setenv("LOG_FILE", "./app.log")
        settings = cfg.Settings()
        assert settings.LOG_FILE.endswith("logs/app.log")


class TestVoucherWithoutProject:
    def test_upload_skips_project_check(self, monkeypatch):
        from app.api.v1 import fund_lifecycle as mod

        voucher = SimpleNamespace(id=7, project_id=None, fund_id=3, voucher_no="V-1")
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = voucher
        import types
        upload_helper = types.ModuleType("app.utils.upload_helper")
        upload_helper.save_upload_file = AsyncMock(return_value={
            "file_name": "a.pdf", "file_path": "/uploads/a.pdf",
            "file_size": 10, "file_type": "application/pdf", "url": "/uploads/a.pdf",
        })
        monkeypatch.setitem(sys.modules, "app.utils.upload_helper", upload_helper)
        monkeypatch.setattr(mod, "_require_manager", lambda u: None)
        upload = SimpleNamespace(filename="a.pdf")
        result = asyncio.run(mod.upload_voucher_attachment(
            voucher_id=7, file=upload, category="bank_receipt",
            description=None, current_user=_admin(), db=db,
        ))
        assert result is not None


class TestImportPreviewOver50Rows:
    def test_preview_keeps_first_50_rows(self, monkeypatch):
        from app.api.v1.import_export import import_data as mod

        rows = [{"name": "v%d" % i} for i in range(1, 61)]
        importer = MagicMock()
        importer.parse_excel.return_value = (rows, [])
        monkeypatch.setattr(mod, "ExcelImporterService", MagicMock(return_value=importer))
        validator = MagicMock()
        validator.validate_file_format.return_value = (True, "")
        monkeypatch.setattr(mod, "_setup_preview_entity", lambda *a, **k: (validator, "name", None))
        monkeypatch.setattr(mod, "_existing_names", lambda *a, **k: set())
        monkeypatch.setattr(mod, "_build_preview_row_response", lambda row, idx, *a, **k: ([], False))
        monkeypatch.setattr(mod, "read_upload_with_limit", AsyncMock(return_value=b"xlsx"))
        upload = SimpleNamespace(filename="data.xlsx", read=AsyncMock(return_value=b"xlsx"))
        result = asyncio.run(mod.preview_import_data(
            file=upload, entity_type="supported_village", current_user=_admin(), db=MagicMock(),
        ))
        assert len(result.rows) == 50


class TestPolicyImportNonDictResult:
    def test_non_dict_result_returns_as_is(self, monkeypatch):
        import types
        from app.api.v1 import policy as mod

        svc = types.ModuleType("app.services.policy_import_service")
        svc.import_policies_from_excel = AsyncMock(return_value=["raw-list"])
        monkeypatch.setitem(sys.modules, "app.services.policy_import_service", svc)
        monkeypatch.setattr(mod, "require_policy_operator_role", lambda u: None)
        monkeypatch.setattr(mod, "submit_entity_change_approval", MagicMock(return_value=99))
        upload = SimpleNamespace(filename="p.xlsx")
        result = asyncio.run(mod.import_policies(file=upload, current_user=_admin(), db=MagicMock()))
        assert result == ["raw-list"]


class TestRegisterClaimRace:
    def test_claim_false_returns_400(self, monkeypatch):
        import types
        from app.api.v1.auth import auth as mod

        monkeypatch.setattr(mod, "check_rate_limit", AsyncMock(return_value=True))
        # v1.16.4 起自助注册默认关闭，注册链路用例需显式开启
        from app.core.config import settings as _settings

        monkeypatch.setattr(_settings, "SELF_REGISTER_MODE", "controlled", raising=False)
        machine_svc = MagicMock()
        machine_svc.get_machine_code.return_value = "MC-1"
        machine_svc.verify_pass_code.return_value = SimpleNamespace(id=5, organization_id=None)
        machine_svc.activate_machine_code.return_value = False
        machine_cls = MagicMock(return_value=machine_svc)
        svc_mod = types.ModuleType("app.services.machine_code_service")
        svc_mod.MachineCodeService = machine_cls
        monkeypatch.setitem(sys.modules, "app.services.machine_code_service", svc_mod)

        created = SimpleNamespace(id=9, username="newbie9")
        user_svc = MagicMock()
        user_svc.get_user_by_username.return_value = None
        user_svc.get_user_by_email.return_value = None
        user_svc.create_user.return_value = created
        monkeypatch.setattr(mod, "UserService", MagicMock(return_value=user_svc))
        monkeypatch.setattr(mod, "_discard_orphan_user", lambda db, u: None)
        request = SimpleNamespace(headers={}, client=SimpleNamespace(host="127.0.0.1"))
        monkeypatch.setattr(mod, "get_client_ip", lambda req: "127.0.0.1")
        db = MagicMock()
        with pytest.raises(HTTPException) as ei:
            asyncio.run(mod.register_user(
                request=request, username="newbie9", password="Verify#2026Mrrs",
                pass_code="PASS-CODE", full_name=None, email=None, org_name=None, db=db,
            ))
        assert ei.value.status_code == 400
        assert "通行码已被使用" in ei.value.detail
