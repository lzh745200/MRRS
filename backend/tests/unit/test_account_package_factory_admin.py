"""账号包导入时的出厂超管接管（登录前导入路径）。

背景（已实测）：导入账号包后，目标机的出厂超管仍可用出厂密码登录并完成"强制改密"，
等于留着一个谁都知道的超管入口。接管只在"登录前导入 + 仍处出厂状态的超管"时发生，
并且与建号、授权处于同一个事务；任何一步失败，超管密码也不变。
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.models as models
from app.core.account_package import KDF_MIN_ITERATIONS, build_manifest, seal_package
from app.core.config import settings
from app.core.constants import FACTORY_ADMIN_PASSWORD, FACTORY_ADMIN_USERNAME
from app.core.grant_signing import generate_keypair
from app.core.security import get_password_hash, verify_password
from app.models import Base
from app.models.organization import Organization
from app.models.user import User
from app.services.account_package_service import (
    AccountPackageBusinessError,
    AccountPackageService,
)
from app.services.effective_grant_service import clear_cache

PASSWORD = "Package#Pass2026"
NEW_PASSWORD = "Local#Pass2026"
MACHINE_CODE = "MC-TAKEOVER-0001"
ORG_CODE = "522701"


@pytest.fixture(autouse=True)
def _isolated_settings(monkeypatch, tmp_path):
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


def _fresh_db(path, with_factory_admin: bool):
    """全新库；模型是懒加载的，建表前先导入全部模型。"""
    for name in list(models._MODULE_MAP.keys()):
        getattr(models, name)
    engine = create_engine(f"sqlite:///{path.as_posix()}")
    Base.metadata.create_all(bind=engine)
    db = sessionmaker(autocommit=False, autoflush=False, bind=engine)()
    if with_factory_admin:
        db.add(
            User(
                username=FACTORY_ADMIN_USERNAME,
                hashed_password=get_password_hash(FACTORY_ADMIN_PASSWORD),
                role="super_admin",
                is_superuser=True,
                is_active=True,
                must_change_password=True,
                token_version=3,
            )
        )
        db.commit()
    return db


def _sealed_package() -> bytes:
    manifest = build_manifest(
        package_id=str(uuid.uuid4()),
        organization_code=ORG_CODE,
        organization_name="目标单位",
        target_machine_code=MACHINE_CODE,
        grants={"projects": "edit"},
        items=[
            {
                "username": "unit_admin",
                "full_name": "单位管理员",
                "credential_hash": get_password_hash("Initial#Pass2026"),
                "role": "admin",
                "data_scope": "org",
            }
        ],
    )
    return seal_package(
        manifest,
        password=PASSWORD,
        private_key_hex=settings.ACCOUNT_PACKAGE_SIGNING_KEY,
        iterations=KDF_MIN_ITERATIONS,
    )


def _factory_admin(db) -> User:
    return db.query(User).filter(User.username == FACTORY_ADMIN_USERNAME).first()


def test_pristine_import_rotates_factory_admin(tmp_path):
    db = _fresh_db(tmp_path / "target.db", with_factory_admin=True)
    raw = _sealed_package()
    service = AccountPackageService(db)
    preview = service.preview(raw, password=PASSWORD, machine_code=MACHINE_CODE)
    assert preview["factory_admin_rotation_required"] is True

    result = service.confirm(
        raw,
        password=PASSWORD,
        machine_code=MACHINE_CODE,
        factory_admin_password=NEW_PASSWORD,
        require_factory_rotation=True,
    )

    admin = _factory_admin(db)
    assert result["factory_admin_rotated"] is True
    assert verify_password(NEW_PASSWORD, admin.hashed_password) is True
    # 出厂密码立即失效；旧会话随之作废；目标机仍保留超管
    assert verify_password(FACTORY_ADMIN_PASSWORD, admin.hashed_password) is False
    assert admin.must_change_password is False
    assert admin.token_version == 4
    assert admin.is_superuser is True
    assert db.query(User).filter(User.username == "unit_admin").count() == 1
    db.close()


def test_factory_password_required_on_pristine_import(tmp_path):
    db = _fresh_db(tmp_path / "required.db", with_factory_admin=True)
    raw = _sealed_package()
    with pytest.raises(AccountPackageBusinessError) as exc:
        AccountPackageService(db).confirm(
            raw, password=PASSWORD, machine_code=MACHINE_CODE, require_factory_rotation=True
        )
    assert exc.value.code == "AP_FACTORY_PASSWORD_REQUIRED"
    # 在建单位之前就拒绝：没有半成品，出厂超管原样不动
    assert db.query(Organization).count() == 0
    admin = _factory_admin(db)
    assert admin.must_change_password is True
    assert admin.token_version == 3
    db.close()


@pytest.mark.parametrize("bad_password", [FACTORY_ADMIN_PASSWORD, "short"])
def test_factory_password_rejects_factory_and_weak(tmp_path, bad_password):
    db = _fresh_db(tmp_path / "weak.db", with_factory_admin=True)
    raw = _sealed_package()
    with pytest.raises(AccountPackageBusinessError) as exc:
        AccountPackageService(db).confirm(
            raw,
            password=PASSWORD,
            machine_code=MACHINE_CODE,
            factory_admin_password=bad_password,
            require_factory_rotation=True,
        )
    assert exc.value.code == "AP_FACTORY_PASSWORD_WEAK"
    assert db.query(Organization).count() == 0
    db.close()


def test_logged_in_import_never_touches_factory_admin(tmp_path):
    db = _fresh_db(tmp_path / "logged_in.db", with_factory_admin=True)
    raw = _sealed_package()
    result = AccountPackageService(db).confirm(raw, password=PASSWORD, machine_code=MACHINE_CODE)

    admin = _factory_admin(db)
    assert result["factory_admin_rotated"] is False
    assert verify_password(FACTORY_ADMIN_PASSWORD, admin.hashed_password) is True
    assert admin.must_change_password is True
    assert admin.token_version == 3
    db.close()


def test_password_is_ignored_without_unrotated_factory_admin(tmp_path):
    db = _fresh_db(tmp_path / "empty.db", with_factory_admin=False)
    raw = _sealed_package()
    service = AccountPackageService(db)
    preview = service.preview(raw, password=PASSWORD, machine_code=MACHINE_CODE)
    assert preview["factory_admin_rotation_required"] is False

    result = service.confirm(
        raw,
        password=PASSWORD,
        machine_code=MACHINE_CODE,
        factory_admin_password=NEW_PASSWORD,
        require_factory_rotation=True,
    )
    assert result["factory_admin_rotated"] is False
    # 不会凭空造出一个超管
    assert db.query(User).filter(User.is_superuser.is_(True)).count() == 0
    db.close()
