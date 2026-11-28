"""账号开通包真实链路回归：勾选 → 签发 → 全新库导入 → 导入账号实际可见的菜单。

为什么需要这组用例：v1.18.63 的"导入账号只剩工作台"发生时，账号包相关测试全绿——
它们只断言矩阵标志位，没有人去算导入账号最终能看到哪些菜单。这里不 mock 建库与落库：
签发与导入分别跑在两个独立数据库上，最后用菜单解析的真实函数核对结果。
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.models as models
from app.api.v1.menus import (
    MENU_DEFINITIONS,
    _PUBLIC_ACCESS_KEYS,
    _build_sections,
    _get_role_default_menu_keys,
    _get_user_accessible_menu_keys,
    _visible_keys,
)
from app.core.account_package import KDF_MIN_ITERATIONS, build_manifest, seal_package
from app.core.account_package_authz import get_authorization_catalog
from app.core.config import settings
from app.core.grant_signing import generate_keypair
from app.core.security import get_password_hash
from app.models import Base
from app.models.organization import Organization
from app.models.user import User
from app.services.account_package_service import (
    AccountPackageBusinessError,
    AccountPackageService,
)
from app.services.effective_grant_service import clear_cache, get_grant_matrix

PASSWORD = "Package#Pass2026"
MACHINE_CODE = "MC-REGRESS-0001"
ORG_CODE = "522701"


@pytest.fixture(autouse=True)
def _isolated_settings(monkeypatch, tmp_path):
    """开启账号包并配好签名密钥；包文件落到临时目录；迭代数取下限以缩短用例。"""
    private_key, public_key = generate_keypair()
    monkeypatch.setattr(settings, "ACCOUNT_PACKAGE_ENABLED", True)
    monkeypatch.setattr(settings, "ACCOUNT_PACKAGE_SIGNING_KEY", private_key)
    monkeypatch.setattr(settings, "ACCOUNT_PACKAGE_PUBKEY", public_key)
    monkeypatch.setattr(settings, "ACCOUNT_PACKAGE_KDF_ITERATIONS", KDF_MIN_ITERATIONS)
    monkeypatch.setattr(
        AccountPackageService, "package_dir", classmethod(lambda cls: tmp_path)
    )
    clear_cache()
    yield
    clear_cache()


def _fresh_db(path):
    """全新库。模型是懒加载的：先导入全部模型再建表，否则会漏表。"""
    for name in list(models._MODULE_MAP.keys()):
        getattr(models, name)
    engine = create_engine(f"sqlite:///{path.as_posix()}")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)()


def _seed_source(db) -> User:
    org = Organization(code=ORG_CODE, name="目标单位", level="1", is_active=True, sort_order=0)
    db.add(org)
    issuer = User(
        username="root", hashed_password="x", role="super_admin", is_superuser=True, is_active=True
    )
    db.add(issuer)
    db.commit()
    return issuer


def _pick_pages():
    """从真实授权目录里挑：工作台、一个可操作的普通页、一个带子页签的控制台页。"""
    pages = {page["key"]: page for page in get_authorization_catalog()["pages"]}
    editable = next(
        key
        for key, page in pages.items()
        if page["kind"] == "page" and page["can_edit"] and key != "dashboard"
    )
    selection = {"dashboard": "view", editable: "edit"}
    console = next(
        (key for key, page in pages.items() if page["kind"] == "console" and page["tabs"]),
        None,
    )
    if console is not None:
        selection[console] = "edit" if pages[console]["can_edit"] else "view"
    return pages, selection, editable


def test_checked_pages_decide_imported_account_menus(tmp_path):
    source = _fresh_db(tmp_path / "source.db")
    issuer = _seed_source(source)
    pages, selection, editable = _pick_pages()

    package_id = str(uuid.uuid4())
    AccountPackageService(source).export_package(
        package_id=package_id,
        organization_code=ORG_CODE,
        organization_name="目标单位",
        parent_code="",
        admin_username="unit_admin",
        admin_full_name="单位管理员",
        target_machine_code=MACHINE_CODE,
        grants=selection,
        password=PASSWORD,
        issued_by=issuer,
        accounts=[
            {"username": "unit_admin", "full_name": "单位管理员", "role": "admin", "data_scope": "org"},
            {"username": "staff", "full_name": "工作人员", "role": "user", "data_scope": "org"},
        ],
    )
    raw = AccountPackageService.package_path(package_id).read_bytes()

    target = _fresh_db(tmp_path / "target.db")
    AccountPackageService(target).confirm(raw, password=PASSWORD, machine_code=MACHINE_CODE)

    granted_pages = set(selection)
    ungranted_pages = set(pages) - granted_pages
    for username in ("unit_admin", "staff"):
        user = target.query(User).filter(User.username == username).first()
        keys = _get_user_accessible_menu_keys(user, target)
        # T05：矩阵授权再按角色收窄 —— 勾选页中属于该角色的部分可见，
        # admin 专属页（如控制台）不会漏给普通用户；未勾选的页面一个都不可见。
        role_keys = _get_role_default_menu_keys(user.role)
        expected_pages = {k for k in granted_pages if k in role_keys or k == "dashboard"}
        assert expected_pages <= keys
        assert not keys & ungranted_pages
        assert not (keys - granted_pages - {"dashboard"} - {
            t["key"]
            for e in MENU_DEFINITIONS
            for t in (e.get("tabs") or []) + (e.get("children") or [])
        })
        # 组装后的导航结构里确实带着该角色可见的勾选页面（工作台恒定可见）
        assert (expected_pages - {"dashboard"}) <= set(
            _visible_keys(_build_sections(keys))
        )
        assert user.allowed_menus is None

    admin = target.query(User).filter(User.username == "unit_admin").first()
    org = target.query(Organization).filter(Organization.code == ORG_CODE).first()
    assert org.grant_version == 1
    matrix = get_grant_matrix(target, admin)
    assert matrix.active
    assert matrix.can_edit(editable)
    assert matrix.can_view("dashboard")
    assert not matrix.can_edit("dashboard")
    source.close()
    target.close()


def test_legacy_empty_grants_fall_back_to_role_default(tmp_path):
    """旧版空授权包（菜单留空写成空数组）导入后不得激活矩阵，可见范围回落角色默认。"""
    manifest = build_manifest(
        package_id=str(uuid.uuid4()),
        organization_code=ORG_CODE,
        organization_name="旧包单位",
        target_machine_code=MACHINE_CODE,
        grants={},
        items=[
            {
                "username": "legacy_admin",
                "full_name": "旧包管理员",
                "credential_hash": get_password_hash("Initial#Pass2026"),
                "role": "admin",
                "data_scope": "org",
                "allowed_menus": [],
            }
        ],
    )
    raw = seal_package(
        manifest,
        password=PASSWORD,
        private_key_hex=settings.ACCOUNT_PACKAGE_SIGNING_KEY,
        iterations=KDF_MIN_ITERATIONS,
    )
    target = _fresh_db(tmp_path / "legacy.db")
    AccountPackageService(target).confirm(raw, password=PASSWORD, machine_code=MACHINE_CODE)

    user = target.query(User).filter(User.username == "legacy_admin").first()
    org = target.query(Organization).filter(Organization.code == ORG_CODE).first()
    assert org.grant_version == 0
    assert user.allowed_menus is None
    assert not get_grant_matrix(target, user).active
    assert _get_user_accessible_menu_keys(user, target) == (
        _get_role_default_menu_keys("admin") | _PUBLIC_ACCESS_KEYS
    )
    target.close()


def test_unknown_grant_key_rejected_before_writing(tmp_path):
    """包内出现目标机不认识的授权项：整包拒绝，且不留半成品（不建单位、不建账号）。"""
    manifest = build_manifest(
        package_id=str(uuid.uuid4()),
        organization_code=ORG_CODE,
        organization_name="非法包单位",
        target_machine_code=MACHINE_CODE,
        grants={"no-such-page": "view"},
        items=[
            {
                "username": "ghost",
                "credential_hash": get_password_hash("Initial#Pass2026"),
                "role": "admin",
                "data_scope": "org",
            }
        ],
    )
    raw = seal_package(
        manifest,
        password=PASSWORD,
        private_key_hex=settings.ACCOUNT_PACKAGE_SIGNING_KEY,
        iterations=KDF_MIN_ITERATIONS,
    )
    target = _fresh_db(tmp_path / "reject.db")
    with pytest.raises(AccountPackageBusinessError) as exc:
        AccountPackageService(target).confirm(raw, password=PASSWORD, machine_code=MACHINE_CODE)
    assert exc.value.code == "AP_GRANT_INVALID"
    assert target.query(Organization).count() == 0
    assert target.query(User).count() == 0
    target.close()
