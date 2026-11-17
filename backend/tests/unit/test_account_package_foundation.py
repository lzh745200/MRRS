"""账号开通包地基：带哈希建号（2026-11-17）

账号开通包只携带「包专用初始密码」的 bcrypt 哈希，明文由源机管理员另渠道交付，
因此导入链路需要一个只接受已哈希口令的建号入口，且必须拒绝明文误传。

注意：本文件**不导入 bcrypt/passlib**。本机（Windows + coverage）下 bcrypt 的 PyO3
模块在插桩进程中二次导入会报 "PyO3 modules ... may only be initialized once"，
与被测代码无关；这里用字面量 bcrypt 形态的哈希，避免把环境问题混进业务测试。
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models.base import Base
from app.services.user_service import UserService

# 形态合法的 bcrypt 哈希（60 字符），内容不参与任何密码校验
FAKE_BCRYPT_HASH = "$2b$12$" + "a" * 53


def _session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)()


def test_creates_user_with_precomputed_hash():
    db = _session()
    service = UserService(db)

    user = service.create_user_with_password_hash(
        "provisioned1",
        FAKE_BCRYPT_HASH,
        role="user",
        data_scope="self",
        full_name="导入用户",
    )

    assert user.id is not None
    assert user.must_change_password is True
    # 哈希原样落库，不能再被哈希一次
    assert user.hashed_password == FAKE_BCRYPT_HASH
    assert user.data_scope == "self"


def test_rejects_plaintext_password():
    db = _session()
    service = UserService(db)

    for value in ("InitPass#2026", "", None):
        try:
            service.create_user_with_password_hash("plain", value)  # type: ignore[arg-type]
        except ValueError as exc:
            assert "bcrypt" in str(exc)
        else:  # pragma: no cover - 失败分支
            raise AssertionError("明文口令必须被拒绝")


def test_rejects_invalid_role_and_scope():
    db = _session()
    service = UserService(db)

    try:
        service.create_user_with_password_hash("badrole", FAKE_BCRYPT_HASH, role="god")
    except ValueError as exc:
        assert "角色" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("非法角色必须被拒绝")

    try:
        service.create_user_with_password_hash(
            "badscope", FAKE_BCRYPT_HASH, data_scope="everything"
        )
    except ValueError as exc:
        assert "数据范围" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("非法数据范围必须被拒绝")


def test_rejects_duplicate_username():
    db = _session()
    service = UserService(db)
    service.create_user_with_password_hash("dup", FAKE_BCRYPT_HASH)

    try:
        service.create_user_with_password_hash("dup", FAKE_BCRYPT_HASH)
    except ValueError as exc:
        assert "已存在" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("重名必须被拒绝")


def test_commit_false_only_flushes():
    db = _session()
    service = UserService(db)

    user = service.create_user_with_password_hash(
        "txn_user",
        FAKE_BCRYPT_HASH,
        commit=False,
    )

    assert user.id is not None
    assert db.query(type(user)).filter(type(user).username == "txn_user").first() is not None


def test_returns_none_without_session():
    assert UserService(None).create_user_with_password_hash("x", FAKE_BCRYPT_HASH) is None


def test_rejects_blank_username():
    service = UserService(_session())
    try:
        service.create_user_with_password_hash("   ", FAKE_BCRYPT_HASH)
    except ValueError as exc:
        assert "用户名" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("空用户名必须被拒绝")
