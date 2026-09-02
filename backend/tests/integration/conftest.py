"""
集成测试共享夹具
使用 SQLite in-memory 数据库 + FastAPI TestClient
"""
import os
import sys
import pytest

# 确保 backend 目录在 sys.path 中
backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

# 记录本 conftest 要设置的测试环境变量原值（teardown 时快照恢复，
# 避免无条件 pop 破坏环境中预先存在的值；根 conftest 的 mock_settings 不管理 CSRF_SECRET_KEY）
_saved_test_env = {
    k: os.environ.get(k)
    for k in ("ENVIRONMENT", "DATABASE_URL", "SECRET_KEY", "CSRF_SECRET_KEY", "CSRF_ENABLED", "DEBUG")
}

# 设置测试环境变量（在导入 app 之前）
os.environ["ENVIRONMENT"] = "test"
os.environ["DATABASE_URL"] = "sqlite:///./test_integration.db"
os.environ["SECRET_KEY"] = "test-secret-key-for-integration-tests"
os.environ["CSRF_SECRET_KEY"] = "test-csrf-secret-key"
os.environ["CSRF_ENABLED"] = "false"  # 测试环境禁用 CSRF
os.environ["DEBUG"] = "true"

# 记录 app.core.database 原始全局对象（供 teardown 恢复，避免污染其他测试）
import app.core.database as _db_mod_orig  # noqa: E402

_db_mod_orig._orig_session_local = _db_mod_orig.SessionLocal
_db_mod_orig._orig_engine = _db_mod_orig.engine

from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from app.models.base import Base
from app.core.database import get_db
from app.core.security import hash_password, decode_token
from app.main import app as fastapi_app

# ==================== 测试数据库引擎 ====================

TEST_DATABASE_URL = "sqlite://"  # in-memory

engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


async def override_get_current_user(
    credentials=None,
):
    """Override get_current_user to use the test in-memory database.

    The real get_current_user calls SessionLocal() directly, which bypasses
    the FastAPI dependency-override for get_db.  This override uses the
    testing session factory so that test users are found.
    """
    from fastapi import HTTPException
    from starlette import status
    from app.models.user import User

    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="未提供认证凭证",
        )
    payload = decode_token(credentials.credentials)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效或过期的令牌",
        )
    username = payload.get("sub")
    if username is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的令牌内容",
        )
    db = TestingSessionLocal()
    try:
        user = db.query(User).filter(User.username == username).first()
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="用户不存在",
            )
        return user
    finally:
        db.close()


# ==================== 夹具 ====================

@pytest.fixture(autouse=True)
def setup_database():
    """每个测试前创建所有表，测试后清除"""

    # 清理全局状态
    from app.core.security import _rate_limit_store
    from app.core.token_blacklist import clear as clear_token_blacklist
    clear_token_blacklist()
    _rate_limit_store.clear()

    # 清理 token_manager 缓存，避免跨测试污染
    try:
        from app.core.token_manager import _token_cache, _blacklist_cache
        _token_cache.clear()
        _blacklist_cache.clear()
    except ImportError:
        pass

    # 保存原始依赖覆盖
    _original_overrides = fastapi_app.dependency_overrides.copy()

    # 设置数据库依赖覆盖（在每个测试前确保生效）
    from unittest.mock import Mock
    from app.core.security import get_current_user as _orig_get_current_user
    from app.core.security import get_current_active_user as _orig_get_current_active_user
    fastapi_app.dependency_overrides[get_db] = override_get_db

    # Create a mock admin user for dependency override
    _test_auth_user = Mock()
    _test_auth_user.id = 1
    _test_auth_user.username = "testadmin"
    _test_auth_user.role = "admin"
    _test_auth_user.is_superuser = True
    _test_auth_user.is_active = True
    _test_auth_user.organization_id = 1
    _test_auth_user.email = "testadmin@example.com"
    _test_auth_user.full_name = "测试管理员"
    _test_auth_user.failed_login_count = 0
    _test_auth_user.locked_until = None
    _test_auth_user.department = "系统管理部"
    _test_auth_user.permissions_list = ["*"]

    # Bypass auth by always returning the mock user (credentials argument is ignored)
    fastapi_app.dependency_overrides[_orig_get_current_user] = lambda credentials=None: _test_auth_user
    fastapi_app.dependency_overrides[_orig_get_current_active_user] = lambda current_user=None: _test_auth_user

    # Also override the dep from deps module
    try:
        from app.api.v1.deps import get_current_active_user as _deps_active_user
        fastapi_app.dependency_overrides[_deps_active_user] = lambda: _test_auth_user
    except ImportError:
        pass

    # Patch SessionLocal and db_manager so that code using SessionLocal()
    # directly (outside of FastAPI Depends) also uses the test database.
    import app.core.database as _db_mod
    _db_mod.SessionLocal = TestingSessionLocal
    _db_mod.engine = engine

    # 导入所有模型以确保表定义已注册
    import app.models  # noqa: F401
    Base.metadata.create_all(bind=engine)
    yield
    # SQLite 默认不强制外键，但 SQLAlchemy drop_all 仍会尝试排序；
    # permission_packs ↔ users 存在 FK 环无法排序（SAWarning），SQLite 实际
    # 删除不受影响 —— 每个集成测试 teardown 都会触发一次，窄域抑制。
    # （治本需给模型 FK 加 use_alter=True，属 schema 变更，不在测试层做）
    import warnings as _warnings
    from sqlalchemy.exc import SAWarning as _SAWarning
    from sqlalchemy import text as _text
    with engine.connect() as _conn:
        _conn.execute(_text("PRAGMA foreign_keys = OFF"))
    with _warnings.catch_warnings():
        _warnings.simplefilter("ignore", _SAWarning)
        Base.metadata.drop_all(bind=engine)
    fastapi_app.dependency_overrides.clear()
    # 恢复被替换的全局数据库对象，并快照恢复本 conftest 设置的测试环境变量
    import app.core.database as _db_mod
    _db_mod.SessionLocal = _db_mod._orig_session_local
    _db_mod.engine = _db_mod._orig_engine
    for _k, _v in _saved_test_env.items():
        if _v is None:
            os.environ.pop(_k, None)
        else:
            os.environ[_k] = _v


@pytest.fixture
def db():
    """提供测试数据库会话"""
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client():
    """提供 FastAPI TestClient"""
    return TestClient(fastapi_app)


@pytest.fixture
def admin_user(db):
    """创建管理员用户并返回 (user, password)"""
    from app.models.user import User
    password = "Admin@123456"
    now = datetime.now(timezone.utc)
    user = User(
        username="testadmin",
        email="testadmin@example.com",
        hashed_password=hash_password(password),
        full_name="测试管理员",
        role="admin",
        is_active=True,
        is_superuser=True,
        department="系统管理部",
        failed_login_count=0,
        locked_until=None,
        created_at=now,
        updated_at=now,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user, password


@pytest.fixture
def normal_user(db):
    """创建普通用户并返回 (user, password)"""
    from app.models.user import User
    password = "User@123456"
    now = datetime.now(timezone.utc)
    user = User(
        username="testuser",
        email="testuser@example.com",
        hashed_password=hash_password(password),
        full_name="测试用户",
        role="user",
        is_active=True,
        is_superuser=False,
        department="测试部",
        failed_login_count=0,
        locked_until=None,
        created_at=now,
        updated_at=now,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user, password


@pytest.fixture
def admin_token(client, admin_user):
    """获取管理员 JWT access_token"""
    user, password = admin_user
    resp = client.post("/api/v1/auth/login", json={
        "username": user.username,
        "password": password,
    })
    assert resp.status_code == 200
    return resp.json()["data"]["access_token"]


@pytest.fixture
def admin_refresh_token(client, admin_user):
    """获取管理员 JWT refresh_token"""
    user, password = admin_user
    resp = client.post("/api/v1/auth/login", json={
        "username": user.username,
        "password": password,
    })
    assert resp.status_code == 200
    return resp.json()["refresh_token"]


@pytest.fixture
def user_token(client, normal_user):
    """获取普通用户 JWT token"""
    user, password = normal_user
    resp = client.post("/api/v1/auth/login", json={
        "username": user.username,
        "password": password,
    })
    assert resp.status_code == 200
    return resp.json()["data"]["access_token"]


@pytest.fixture
def admin_headers(admin_token):
    """管理员请求头"""
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture
def user_headers(user_token):
    """普通用户请求头"""
    return {"Authorization": f"Bearer {user_token}"}
