"""
扩展的测试框架配置
在现有 conftest.py 基础上添加:
- SQLite内存数据库 fixture
- 异步测试客户端 fixture
- 数据隔离 fixture
"""

import pytest
import sys
from pathlib import Path

# 添加项目根目录
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


# ══════════════════════════════════════════════════════════════
#  数据库 Fixtures
# ══════════════════════════════════════════════════════════════

@pytest.fixture(scope="function")
def test_db():
    """SQLite内存数据库 —— 每次测试独立，测试后自动回滚"""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})

    # 启用WAL模式（内存数据库也支持）
    @event.listens_for(engine, "connect")
    def set_pragma(conn, record):
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")

    from app.models.base import Base

    Base.metadata.create_all(bind=engine)

    Session = sessionmaker(bind=engine)
    session = Session()

    yield session

    session.rollback()
    session.close()
    engine.dispose()


# ══════════════════════════════════════════════════════════════
#  API 测试 Fixtures
# ══════════════════════════════════════════════════════════════

@pytest.fixture
def test_app(test_db):
    """创建测试用 FastAPI 应用"""
    from fastapi.testclient import TestClient
    from app.main import app
    from app.core.database import get_db

    # 覆盖数据库依赖
    def override_get_db():
        yield test_db

    _original_overrides = app.dependency_overrides.copy()
    app.dependency_overrides[get_db] = override_get_db

    client = TestClient(app)
    yield client

    app.dependency_overrides = _original_overrides


# ══════════════════════════════════════════════════════════════
#  认证 Fixtures
# ══════════════════════════════════════════════════════════════

@pytest.fixture
def auth_headers(test_app):
    """获取认证token并返回带认证头的headers"""
    # 创建测试用户
    response = test_app.post("/api/v1/auth/login", json={
        "username": "admin",
        "password": "admin123",
    })
    if response.status_code == 200:
        token = response.json().get("access_token", "")
        return {"Authorization": f"Bearer {token}"}
    return {}


# ══════════════════════════════════════════════════════════════
#  数据隔离 Fixtures
# ══════════════════════════════════════════════════════════════

@pytest.fixture
def org_a_user(test_db):
    """创建组织A的测试用户"""
    from app.models.user import User
    from app.core.security import hash_password

    user = User(
        username="org_a_user",
        hashed_password=hash_password("test123"),
        role="operator",
        organization_id=1,
        is_active=True,
    )
    test_db.add(user)
    test_db.commit()
    return user


@pytest.fixture
def org_b_user(test_db):
    """创建组织B的测试用户"""
    from app.models.user import User
    from app.core.security import hash_password

    user = User(
        username="org_b_user",
        hashed_password=hash_password("test123"),
        role="operator",
        organization_id=2,
        is_active=True,
    )
    test_db.add(user)
    test_db.commit()
    return user
