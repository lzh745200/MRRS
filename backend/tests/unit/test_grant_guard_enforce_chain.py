"""写守卫强制模式真实链路回归（T04 第 1 步）。

`test_grant_guard_r33.py` 用打桩会话和手造的 `GrantMatrix` 测守卫本体；这里补的是它测不到的
那一段：**账号包导入出来的真实矩阵 → 真实令牌 → 真实模块解析 → 守卫裁决**。
不 mock 建库、落库、矩阵合并与 token 解码。

为什么必须单独有这组用例：守卫默认 `off`，切 `shadow`/`enforce` 前需要证明三件事同时成立 ——
只读页面可见但写请求被拒、可操作页面可写、未下发矩阵的存量单位行为不变。
这三条任何一条坏了，现场表现都是"没报错，但要么写不进去、要么只读形同虚设"。
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

import app.models as models
from app.core.account_package import KDF_MIN_ITERATIONS
from app.core.config import settings
from app.core.grant_guard import enforce_write_grant
from app.core.grant_signing import generate_keypair
from app.core.security import create_access_token
from app.models import Base
from app.models.organization import Organization
from app.models.user import User
from app.services.account_package_service import AccountPackageService
from app.services.effective_grant_service import clear_cache, get_grant_matrix
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

PASSWORD = "Package#Pass2026"
MACHINE_CODE = "MC-ENFORCE-0001"
ORG_CODE = "522701"

EDITABLE = "villages"      # 勾选为可操作
EDITABLE_PATH = "/api/v1/supported-villages"
READ_ONLY = "projects"      # 勾选为只读
READ_ONLY_PATH = "/api/v1/projects"

_IMPORTED_ACCOUNTS = ("unit_admin", "staff")


def _fresh_db(path):
    """全新库。模型是懒加载的：先导入全部模型再建表，否则会漏表。"""
    for name in list(models._MODULE_MAP.keys()):
        getattr(models, name)
    engine = create_engine(f"sqlite:///{path.as_posix()}")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)()


@pytest.fixture(scope="module")
def imported(tmp_path_factory):
    """签发（源库）→ 导入（目标库）一次，整组用例共用这个已激活矩阵的目标库。

    模块级夹具用不了 monkeypatch，直接改 settings 并在收尾还原（只动这四项）。
    """
    tmp_path = tmp_path_factory.mktemp("grant-guard-enforce")
    saved = {
        name: getattr(settings, name)
        for name in (
            "ACCOUNT_PACKAGE_ENABLED",
            "ACCOUNT_PACKAGE_SIGNING_KEY",
            "ACCOUNT_PACKAGE_PUBKEY",
            "ACCOUNT_PACKAGE_KDF_ITERATIONS",
        )
    }
    try:
        private_key, public_key = generate_keypair()
        settings.ACCOUNT_PACKAGE_ENABLED = True
        settings.ACCOUNT_PACKAGE_SIGNING_KEY = private_key
        settings.ACCOUNT_PACKAGE_PUBKEY = public_key
        settings.ACCOUNT_PACKAGE_KDF_ITERATIONS = KDF_MIN_ITERATIONS

        source = _fresh_db(tmp_path / "source.db")
        org = Organization(code=ORG_CODE, name="目标单位", level="1", is_active=True, sort_order=0)
        source.add(org)
        issuer = User(
            username="root", hashed_password="x", role="super_admin", is_superuser=True, is_active=True
        )
        source.add(issuer)
        source.commit()

        package_id = "11111111-1111-4111-8111-111111111111"
        AccountPackageService(source).export_package(
            package_id=package_id,
            organization_code=ORG_CODE,
            organization_name="目标单位",
            parent_code="",
            admin_username="unit_admin",
            admin_full_name="单位管理员",
            target_machine_code=MACHINE_CODE,
            grants={"dashboard": "view", EDITABLE: "edit", READ_ONLY: "view"},
            password=PASSWORD,
            issued_by=issuer,
            accounts=[
                {"username": "unit_admin", "full_name": "单位管理员", "role": "admin", "data_scope": "org"},
                {"username": "staff", "full_name": "工作人员", "role": "user", "data_scope": "org"},
            ],
        )
        raw = AccountPackageService(source).package_path(package_id).read_bytes()
        source.close()

        target = _fresh_db(tmp_path / "target.db")
        AccountPackageService(target).confirm(raw, password=PASSWORD, machine_code=MACHINE_CODE)
        clear_cache()
        yield target
    finally:
        clear_cache()
        for name, value in saved.items():
            setattr(settings, name, value)
        target.close()


@pytest.fixture
def guard(monkeypatch, imported):
    """把守卫用的会话指向导入出来的目标库；返回"按模式和用户发请求"的入口。

    只替换 `GRANT_GUARD_MODE` 一项：守卫后半段还要读组织模块策略，整份 settings
    换成替身会让那段缺属性。
    """
    opened: list = []

    def open_session():
        opened.append(1)
        return imported

    monkeypatch.setattr("app.core.database.SessionLocal", open_session)

    def run(mode: str, method: str, path: str, username: str | None = "staff", auth: str | None = None):
        monkeypatch.setattr(settings, "GRANT_GUARD_MODE", mode)
        if auth is None:
            auth = f"Bearer {create_access_token({'sub': username})}" if username else None
        headers = {} if auth is None else {"authorization": auth}
        request = SimpleNamespace(method=method, url=SimpleNamespace(path=path), headers=headers)
        return request, opened

    return run


def _run(coro):
    import asyncio

    return asyncio.run(coro)


class TestEnforceOnImportedMatrix:
    @pytest.mark.parametrize("username", _IMPORTED_ACCOUNTS)
    def test_read_only_page_visible_but_write_denied(self, imported, guard, username):
        """只读：页面可见（矩阵 can_view），但写请求 403 —— 矩阵对单位内所有角色一致。"""
        user = imported.query(User).filter(User.username == username).first()
        matrix = get_grant_matrix(imported, user)
        assert matrix.active
        assert matrix.can_view(READ_ONLY)

        request, _ = guard("enforce", "POST", f"{READ_ONLY_PATH}/1", username)
        with pytest.raises(HTTPException) as exc:
            _run(enforce_write_grant(request))
        assert exc.value.status_code == 403
        assert "录入权限" in exc.value.detail

    def test_editable_page_write_allowed(self, imported, guard):
        matrix = get_grant_matrix(imported, imported.query(User).filter(User.username == "staff").first())
        assert matrix.can_edit(EDITABLE)

        request, _ = guard("enforce", "POST", EDITABLE_PATH)
        _run(enforce_write_grant(request))

    def test_read_method_not_guarded(self, guard):
        """只读模块的读请求放行：读接口防护是另一件事（T07），不混进写守卫。"""
        request, _ = guard("enforce", "GET", READ_ONLY_PATH)
        _run(enforce_write_grant(request))

    def test_shadow_logs_but_does_not_block(self, guard, caplog):
        import logging

        with caplog.at_level(logging.WARNING, logger="app.core.grant_guard"):
            request, _ = guard("shadow", "POST", f"{READ_ONLY_PATH}/1")
            _run(enforce_write_grant(request))
        hit = [r for r in caplog.records if "R33 授权守卫[shadow]" in r.getMessage()]
        assert hit and f"module={READ_ONLY}" in hit[0].getMessage()
        assert f"{READ_ONLY_PATH}/1" in hit[0].getMessage()

    def test_off_does_not_even_open_a_session(self, guard):
        request, opened = guard("off", "POST", f"{READ_ONLY_PATH}/1")
        _run(enforce_write_grant(request))
        assert opened == []

    def test_unmapped_write_denied_in_enforce(self, guard):
        request, _ = guard("enforce", "POST", "/api/v1/not-a-module/x")
        with pytest.raises(HTTPException) as exc:
            _run(enforce_write_grant(request))
        assert "映射" in exc.value.detail


class TestBehaviourUnchangedWhereItMust:
    def test_account_package_bootstrap_not_blocked(self, guard):
        """登录前导入没有用户可归属单位：自举路径不得被守卫拦，否则强制后无法开通账号。"""
        request, opened = guard("enforce", "POST", "/api/v1/account-packages/confirm", username=None)
        _run(enforce_write_grant(request))
        assert opened == []

    def test_legacy_unit_without_matrix_passes(self, imported, guard):
        """未下发矩阵的存量单位：即使强制模式也不拦。"""
        legacy_org = Organization(code="522702", name="存量单位", level="1", is_active=True, sort_order=0)
        imported.add(legacy_org)
        imported.flush()
        legacy = User(
            username="legacy_staff",
            hashed_password="x",
            role="user",
            is_active=True,
            organization_id=legacy_org.id,
        )
        imported.add(legacy)
        imported.commit()
        clear_cache()
        try:
            assert not get_grant_matrix(imported, legacy).active
            request, _ = guard("enforce", "POST", "/api/v1/funds", "legacy_staff")
            _run(enforce_write_grant(request))
        finally:
            imported.query(User).filter(User.username == "legacy_staff").delete()
            imported.query(Organization).filter(Organization.code == "522702").delete()
            imported.commit()
            clear_cache()

    def test_superuser_exempt(self, imported, guard):
        """超管没有矩阵（守卫对其豁免），强制模式也不拦。"""
        admin = imported.query(User).filter(User.username == "unit_admin").first()
        saved = admin.is_superuser
        admin.is_superuser = True
        imported.commit()
        clear_cache()
        try:
            assert not get_grant_matrix(imported, admin).active
            request, _ = guard("enforce", "POST", "/api/v1/funds", "unit_admin")
            _run(enforce_write_grant(request))
        finally:
            # 守卫用完会关闭会话，上面的 admin 已游离：重新查询后再还原
            row = imported.query(User).filter(User.username == "unit_admin").first()
            row.is_superuser = saved
            imported.commit()
            clear_cache()

    def test_unauthenticated_passes_to_real_auth(self, guard):
        """无令牌：守卫放行，由路由自己的认证返回 401（守卫不做认证）。"""
        request, _ = guard("enforce", "POST", f"{READ_ONLY_PATH}/1", username=None)
        _run(enforce_write_grant(request))
