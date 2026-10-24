# -*- coding: utf-8 -*-
"""系统初始化：根组织编码校验的四个分支（v1.17.2 新增逻辑）。"""

import pytest
from fastapi import HTTPException

from app.api.v1.system.init import _ensure_root_organization, _resolve_root_org_code


class TestResolveRootOrgCode:
    """编码校验：缺失 / 非法 / 非省级 / 正常。"""

    def test_missing_code_400(self):
        with pytest.raises(HTTPException) as exc:
            _resolve_root_org_code(None)
        assert exc.value.status_code == 400
        assert "6 位行政区划代码" in exc.value.detail

    def test_blank_code_400(self):
        with pytest.raises(HTTPException) as exc:
            _resolve_root_org_code("   ")
        assert exc.value.status_code == 400

    def test_invalid_code_400(self):
        with pytest.raises(HTTPException) as exc:
            _resolve_root_org_code("abcdef")
        assert exc.value.status_code == 400

    def test_non_province_400(self):
        with pytest.raises(HTTPException) as exc:
            _resolve_root_org_code("520100")  # 市州级
        assert exc.value.status_code == 400
        assert "省级" in exc.value.detail

    def test_valid_province_ok(self):
        assert _resolve_root_org_code("520000") == "520000"

    def test_strips_whitespace(self):
        assert _resolve_root_org_code("  520000 ") == "520000"


class _Req:
    def __init__(self, code=None, name="测试单位"):
        self.organization_code = code
        self.organization_name = name


class _FakeQuery:
    def __init__(self, existing):
        self._existing = existing

    def filter(self, *a, **k):
        return self

    def order_by(self, *a, **k):
        return self

    def first(self):
        return self._existing


class _FakeDb:
    def __init__(self, existing=None, raises=None):
        self._existing = existing
        self._raises = raises
        self.rolled_back = False

    def query(self, *a, **k):
        if self._raises:
            raise self._raises
        return _FakeQuery(self._existing)

    def rollback(self):
        self.rolled_back = True


class TestEnsureRootOrganization:
    """根组织保障：复用 / 新建 / 参数错误上抛 / 内部错误包 500。"""

    @pytest.mark.asyncio
    async def test_reuse_existing(self):
        db = _FakeDb(existing=type("O", (), {"id": 7})())
        steps = []
        rid = await _ensure_root_organization(db, _Req(), steps)
        assert rid == 7
        assert steps[0]["status"] == "skipped"

    @pytest.mark.asyncio
    async def test_create_new(self, monkeypatch):
        class _OrgSvc:
            def __init__(self, db):
                pass

            async def create_organization(self, data, created_by=0):
                assert data.code == "520000"
                return type("O", (), {"id": 9})()

        monkeypatch.setattr(
            "app.services.organization_service.OrganizationService", _OrgSvc
        )
        db = _FakeDb(existing=None)
        steps = []
        rid = await _ensure_root_organization(db, _Req(code="520000"), steps)
        assert rid == 9
        assert steps[0]["status"] == "success"

    @pytest.mark.asyncio
    async def test_http_exception_passthrough(self):
        db = _FakeDb(existing=None)
        with pytest.raises(HTTPException) as exc:
            await _ensure_root_organization(db, _Req(code=None), [])
        assert exc.value.status_code == 400
        assert db.rolled_back is True

    @pytest.mark.asyncio
    async def test_internal_error_wrapped_500(self):
        db = _FakeDb(raises=RuntimeError("db down"))
        with pytest.raises(HTTPException) as exc:
            await _ensure_root_organization(db, _Req(code="520000"), [])
        assert exc.value.status_code == 500
        assert db.rolled_back is True


class TestInitializeGuards:
    """初始化入口的两个兜底分支。"""

    def test_concurrent_init_returns_409(self, monkeypatch):
        """已有初始化在跑（锁被占用）→ 409，绝不并发双跑。"""
        from fastapi.testclient import TestClient

        from app.api.v1.system import init as init_module
        from app.core.database import get_db
        from app.main import app

        db = type("D", (), {"query": lambda *a, **k: _FakeQuery(None), "rollback": lambda s: None})()
        original = app.dependency_overrides.copy()

        def _get_db():
            yield db

        app.dependency_overrides[get_db] = _get_db
        c = TestClient(app, raise_server_exceptions=False)

        # 外部先占锁，模拟另一次初始化在跑
        acquired = init_module._INIT_LOCK.acquire(blocking=False)
        assert acquired is True
        try:
            resp = c.post(
                "/api/v1/system/init/initialize",
                json={
                    "organization_name": "测试单位",
                    "organization_code": "520000",
                    "admin_password": "Str0ng!Passw0rd#2026",
                },
            )
            assert resp.status_code == 409, resp.text
        finally:
            init_module._INIT_LOCK.release()
            app.dependency_overrides = original

    @pytest.mark.asyncio
    async def test_organization_code_written_to_config(self, monkeypatch):
        """request.organization_code 非空时必须写入配置项 organization_code。"""
        from app.api.v1.system import init as init_module

        written = {}

        class _Svc:
            def __init__(self, db):
                pass

            def is_initialized(self):
                return False

            def initialize_defaults(self):
                pass

            def set(self, key, value, desc=""):
                written[key] = value

            def set_initialized(self, org_id=None):
                written["__org_id__"] = org_id

        async def _fake_org(db, request, steps):
            return 11

        monkeypatch.setattr(init_module, "SystemConfigService", _Svc)
        monkeypatch.setattr(init_module, "_ensure_root_organization", _fake_org)
        monkeypatch.setattr(init_module, "safe_commit", lambda db: None)
        monkeypatch.setattr("app.core.security.get_password_hash", lambda pw: "hashed")

        db = _FakeDb()
        db.add = lambda obj: None
        req = _Req(code="520000", name="测试单位")
        req.admin_username = "admin"
        req.admin_password = "Str0ng!Passw0rd#2026"
        req.admin_email = None
        req.organization_short_name = None
        req.system_name = None
        req.contact_person = None
        req.contact_phone = None

        result = await init_module._run_initialization(req, db)
        assert written.get("organization_code") == "520000"
        assert written.get("__org_id__") == 11
        assert result is not None

    @pytest.mark.asyncio
    async def test_admin_creation_failure_returns_500(self, monkeypatch):
        """创建超级管理员失败必须 500 且错误详情不出站。"""
        from app.api.v1.system import init as init_module

        class _Svc:
            def __init__(self, db):
                pass

            def is_initialized(self):
                return False

            def initialize_defaults(self):
                pass

            def set(self, key, value, desc=""):
                pass

            def set_initialized(self, org_id=None):
                pass

        async def _fake_org(db, request, steps):
            return 11

        def _boom(db):
            raise RuntimeError("db write failed")

        monkeypatch.setattr(init_module, "SystemConfigService", _Svc)
        monkeypatch.setattr(init_module, "_ensure_root_organization", _fake_org)
        monkeypatch.setattr(init_module, "safe_commit", _boom)
        monkeypatch.setattr("app.core.security.get_password_hash", lambda pw: "hashed")

        db = _FakeDb()
        db.add = lambda obj: None
        req = _Req(code="520000", name="测试单位")
        req.admin_username = "admin"
        req.admin_password = "Str0ng!Passw0rd#2026"
        req.admin_email = None
        req.organization_short_name = None
        req.system_name = None
        req.contact_person = None
        req.contact_phone = None

        with pytest.raises(HTTPException) as exc:
            await init_module._run_initialization(req, db)
        assert exc.value.status_code == 500
        assert "db write failed" not in exc.value.detail
        assert db.rolled_back is True

    @pytest.mark.asyncio
    async def test_blank_organization_code_skips_config_write(self, monkeypatch):
        """organization_code 为空时不写该配置项（if 的 False 分支）。"""
        from app.api.v1.system import init as init_module

        written = {}

        class _Svc:
            def __init__(self, db):
                pass

            def is_initialized(self):
                return False

            def initialize_defaults(self):
                pass

            def set(self, key, value, desc=""):
                written[key] = value

            def set_initialized(self, org_id=None):
                written["__org_id__"] = org_id

        async def _fake_org(db, request, steps):
            return 12

        monkeypatch.setattr(init_module, "SystemConfigService", _Svc)
        monkeypatch.setattr(init_module, "_ensure_root_organization", _fake_org)
        monkeypatch.setattr(init_module, "safe_commit", lambda db: None)
        monkeypatch.setattr("app.core.security.get_password_hash", lambda pw: "hashed")

        db = _FakeDb()
        db.add = lambda obj: None
        req = _Req(code=None, name="无码单位")
        req.admin_username = "admin"
        req.admin_password = "Str0ng!Passw0rd#2026"
        req.admin_email = None
        req.organization_short_name = None
        req.system_name = None
        req.contact_person = None
        req.contact_phone = None

        await init_module._run_initialization(req, db)
        assert "organization_code" not in written
        assert written.get("__org_id__") == 12
