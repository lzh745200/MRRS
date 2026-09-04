"""
测试 Fixtures 和配置

提供测试所需的共享 fixtures 和配置。
"""
# ── 关键修复：强制 UTF-8 编码，消除 Windows 控制台 GBK 导致的 UnicodeEncodeError ──
import os as _os
_os.environ.setdefault("PYTHONIOENCODING", "utf-8")
# ── 关键修复：全部 app 数据目录必须在任何 app 模块导入之前重定向到会话临时根 ──
# 机制：app/core/config.py 的 Settings 在构造期（首次 import 时）把 DATABASE_URL /
# CACHE_DIR / UPLOAD_DIR / EXPORT_DIR 的相对默认值统一归一为 _get_default_data_dir()
# 下的绝对路径，而该函数最终调用 paths.get_app_data_dir() → get_project_backend_dir()。
# 因此只要在任何 app.* 导入之前替换 get_project_backend_dir，即可一次收口上述全部路径。
#
# 历史缺陷：替换若放在函数级 fixture 里就太晚 —— Settings 已在 import 期把真实
# backend/data 固化进 settings.*，于是缓存库、集成测试库、备份/恢复全都写在开发者
# 真目录（现场证据：backend/data/ 里的 rural_revitalization.db.bak_*、
# rural_revitalization_recovered.db、test_integration.db、cache/*/cache.db，
# logs/app.log 单次全量跑涨到 4.8MB；以及下方注释记录的“并发 pytest 进程曾因此
# 把开发库写坏：btreeInitPage 页损坏 / database disk image is malformed”）。
#
# 唯一不经该漏斗的是日志文件：config.py 仅在 sys.frozen 时才重写 LOG_DIR/LOG_FILE，
# 开发/测试态 LOG_FILE 保持相对 "./logs/app.log"（按 CWD 解析到 backend/logs/）。
# 这里**只**覆盖 LOG_FILE（logging handler 实际读取的字段），刻意不设 LOG_DIR ——
# 一旦设了 LOG_DIR，config.py 的 `if self.LOG_DIR.startswith("./")` 就判定为假，
# 整个 sys.frozen 分支被短路；那是打包后应用真正走的路径，且
# tests/unit/test_config_core.py::test_frozen_log_dir_uses_data_dir 专门覆盖它
# （断言 LOG_DIR 以 "/logs" 结尾、不含反斜杠）。路径统一用 as_posix() 输出正斜杠，
# 与 config.py 的 `.replace("\\", "/")` 归一口径一致。
import tempfile as _tempfile
from pathlib import Path as _Path

_APP_DATA_ROOT = _Path(_tempfile.mkdtemp(prefix="bumofu_pytest_appdata_"))
(_APP_DATA_ROOT / "logs").mkdir(parents=True, exist_ok=True)

# 用 env 覆盖而非替换模块属性：paths.get_project_backend_dir() 在调用时读取本变量，
# 因此 `from app.utils.paths import get_project_backend_dir` 的直接绑定名与模块属性
# 始终一致。替换属性的做法会让测试模块把名字冻结成替身，与后来被还原的模块属性
# 分叉（实测导致 test_paths.py 两处断言失败）。
_os.environ["BUMOFU_BACKEND_DIR_OVERRIDE"] = str(_APP_DATA_ROOT)

_os.environ["DATABASE_URL"] = "sqlite:///./test.db"
_os.environ["LOG_FILE"] = (_APP_DATA_ROOT / "logs" / "app.log").as_posix()

# ── 前端构建产物桩：让 main.py 的前端服务分支在 Linux CI 上也能执行 ──
# 机制：app/core/static_files.find_frontend_dir() 的首选项即 FRONTEND_DIST_PATH 环境变量。
# frontend/dist 与 resources/frontend 均为 gitignore 的构建产物，Linux CI 的后端作业不构建
# 前端 → 二者皆不存在 → main.py 的 `if _frontend_dir:` 整块（约 50 行：/assets /images
# /static 三处挂载 + favicon / version.json / SPA fallback 三个端点）在导入期被整体跳过、
# 永不执行 → 击穿 .coveragerc 的 fail_under=100（这正是 ubuntu 上 backend-test 覆盖率门禁
# 恒红的最大单一缺口）。此处在任何 app.* 导入之前落地一个最小可用 dist，使导入期走 IF 分支、
# 端点完成注册、各分支随后可被测试命中。刻意不写 favicon.ico —— 让导入期 _favicon_path 为
# None，覆盖 favicon 的 404 默认分支；test_favicon_with_file 再设 m._favicon_path 覆盖 200 分支。
# 与开发者本机（真实 dist 存在 → 同样走 IF 分支）行为一致，故 Windows/Linux 覆盖率口径统一。
_FRONTEND_DIST = _APP_DATA_ROOT / "frontend_dist"
for _dist_sub in ("assets", "images", "static"):
    (_FRONTEND_DIST / _dist_sub).mkdir(parents=True, exist_ok=True)
(_FRONTEND_DIST / "index.html").write_text(
    "<!DOCTYPE html><html><head><title>test</title></head>"
    "<body><div id='app'></div></body></html>",
    encoding="utf-8",
)
(_FRONTEND_DIST / "version.json").write_text('{"version":"test"}', encoding="utf-8")
_os.environ["FRONTEND_DIST_PATH"] = str(_FRONTEND_DIST)

# ── 关键修复：无头测试环境强制 matplotlib 使用 Agg 后端 ──
# 默认后端（如 TkAgg）会在测试期间初始化 tkinter 资源，解释器关闭时
# 触发 "main thread is not in main loop" 的 ResourceWarning。
_os.environ.setdefault("MPLBACKEND", "Agg")
import sys as _sys
if _sys.stdout and hasattr(_sys.stdout, 'reconfigure'):
    try:
        _sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass
if _sys.stderr and hasattr(_sys.stderr, 'reconfigure'):
    try:
        _sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

import pytest

# ── 根因修复：会话启动时清理遗留 test.db（跨会话残留导致顺序敏感偶发失败） ──
import os as _cleanup_os
import glob as _cleanup_glob
for _db in _cleanup_glob.glob(_cleanup_os.path.join(_cleanup_os.path.dirname(__file__), "..", "test.db")):
    try:
        _cleanup_os.remove(_db)
    except OSError:
        pass
import sys
from pathlib import Path
from unittest.mock import Mock
import os


# ── 根因修复：移除超过 Windows 环境变量长度限制（32767 字符）的超长变量 ──
# WorkBuddy 桌面端会注入 ACC_PRODUCT_CONFIG_V3（~288KB）等超长环境变量。
# unittest.mock.patch.dict(os.environ) 在 teardown 时会保存并还原 *全部*
# 环境变量，触发 ValueError: the environment variable is longer than 32767
# characters，导致任何使用 patch.dict(os.environ) 的测试在退出时崩溃。
# 这些超长变量是宿主注入的、被测应用不依赖，测试会话开始时一次性删除即可。
@pytest.fixture(autouse=True, scope="session")
def _strip_oversized_env_vars():
    _WIN_ENV_LIMIT = 32767
    for _key in [k for k, v in list(os.environ.items()) if len(v) > _WIN_ENV_LIMIT]:
        del os.environ[_key]
    yield


# ── real_backend_dir 豁免：为专测路径解析逻辑的测试临时移除数据目录覆盖 ──
# 模块级已设 BUMOFU_BACKEND_DIR_OVERRIDE 把全部数据目录指向会话临时根（见本文件
# 顶部），但 tests/unit/test_paths.py 断言 get_app_data_dir() == 真实的
# get_project_backend_dir() 以及其 .name == "backend"，必须看到未被覆盖的、
# 由 __file__ 推断出的真实值。monkeypatch.delenv 会在测试结束后自动还原。
@pytest.fixture(autouse=True)
def _honor_real_backend_dir_marker(request, monkeypatch):
    if request.node.get_closest_marker("real_backend_dir"):
        monkeypatch.delenv("BUMOFU_BACKEND_DIR_OVERRIDE", raising=False)


# ── 根因修复：每个测试结束后 join 残留的 immediate-backup daemon 线程 ──
# 机制：purge / 批量删除 / 导入等端点成功后调用 trigger_immediate_backup(delay=1.0)，
# 派生名为 "immediate-backup" 的 daemon 线程；该线程 sleep 1s 后经 get_db_context()
# → SessionLocal() 落到 client fixture 指向的**同一条 in-memory StaticPool 连接**
# （conftest 把 app.core.database.SessionLocal 也改指测试内存库）。若线程在 delay 窗口内
# 残留到下一个测试，会与下一个测试的会话并发访问同一连接，破坏 SQLite 单连接的事务状态
# —— 曾致 recycle_bin purge 测试偶发 "记录不存在" 400 与 AuditLog ObjectDeletedError 500
# （隔离运行恒过、全量 xdist 分布下偶发；删除 async_executor 后收集顺序变化才暴露）。
# 这里在每个测试 teardown join 该线程，杜绝跨测试污染。test_immediate_backup.py 用
# FakeThread 打桩、不派生真实线程，故不受影响；immediate_backup.py 主体覆盖率由其保证。
import threading as _threading


@pytest.fixture(autouse=True)
def _join_immediate_backup_threads():
    yield
    for _t in _threading.enumerate():
        if _t.name == "immediate-backup" and _t.is_alive():
            _t.join(timeout=10)


# ── 根因修复：会话启动时强制导入全部模型子模块，确保 SQLAlchemy mapper 注册表完整 ──
# app/models/__init__.py 采用懒加载，但部分模型用字符串 relationship 引用其他模型
# （如 ImportExportHistory→"DataPackage"）。若目标模型未导入，mapper 配置时会抛
# InvalidRequestError，且失败后整个会话的 mapper 都不可用。在 conftest 加载时
# （早于任何测试）导入全部 59 个模型子模块，从源头保证 mapper 注册表完整。
import importlib as _importlib
import pkgutil as _pkgutil
try:
    import app.models as _models_pkg
    for _mod_info in _pkgutil.iter_modules(_models_pkg.__path__):
        _importlib.import_module(f"app.models.{_mod_info.name}")
except Exception:
    pass  # 容错：个别模型导入失败不应阻塞测试收集


# 排除非 pytest 的独立测试脚本
# test_system_api.py 是手动全模块 API 测试脚本，含模块级 sys.exit(1)
# collect_ignore removed


def pytest_collection_modifyitems(config, items):
    """将依赖 mock/TestClient 的测试文件移至集合最前，避免跨测试污染。

    test_rbac_transactional.py 使用纯 MagicMock 数据库；
    test_audit_integration.py 使用 TestClient + 依赖覆盖。
    一旦其他测试触发 SQLAlchemy mapper 初始化或 FastAPI app 状态变更，
    这些测试的 mock 链就会失效。提前运行可免受污染。
    """
    _POLLUTION_SENSITIVE = {
        "test_rbac_transactional",
        "test_audit_integration",
        "test_unified_template",
        "test_fund_budgets_api",
        "test_project_milestones_api",
        "test_statistics_api",
        "test_coverage_gap_batch3",  # asyncio 事件循环敏感——其他测试破坏 loop 后失败
        "test_data_dashboard_api",
    }
    first = []
    rest = []
    for item in items:
        fname = item.nodeid.split("::")[0].split("/")[-1].replace(".py", "")
        if fname in _POLLUTION_SENSITIVE:
            first.append(item)
        else:
            rest.append(item)
    items[:] = first + rest

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from fastapi.testclient import TestClient


# 保留旧的mock_db用于不需要真实数据库的测试
@pytest.fixture
def mock_db():
    """模拟数据库会话 - 改进版，支持更多ORM操作"""
    db = Mock()
    db._storage = {}
    db._next_id = [1]

    def mock_query(model):
        query_mock = Mock()
        def mock_filter(*conditions):
            filter_mock = Mock()
            def mock_first():
                records = list(db._storage.get(model, []))
                if not conditions:
                    return records[0] if records else None
                for record in records:
                    matched = True
                    for cond in conditions:
                        try:
                            if hasattr(cond, '_comparable') and cond._comparable:
                                col = list(cond._comparable)[0]
                                col_name = col.key
                                expected_val = cond._comparable[col]
                            elif hasattr(cond, '_entity'):
                                col_name = getattr(cond._entity, 'key', str(cond._entity))
                                expected_val = getattr(cond, 'right', None)
                                if hasattr(expected_val, 'value'):
                                    expected_val = expected_val.value
                                else:
                                    expected_val = str(expected_val) if expected_val else None
                            else:
                                continue
                            if hasattr(record, col_name):
                                if str(getattr(record, col_name)) != str(expected_val):
                                    matched = False
                                    break
                        except:
                            pass
                    if matched:
                        return record
                return None
            def mock_all():
                return list(db._storage.get(model, []))
            def mock_count():
                return len(db._storage.get(model, []))
            filter_mock.first = mock_first
            filter_mock.all = mock_all
            filter_mock.count = mock_count
            filter_mock.filter = mock_filter
            filter_mock.order_by = lambda *x: filter_mock
            filter_mock.limit = lambda x: filter_mock
            filter_mock.offset = lambda x: filter_mock
            return filter_mock
        query_mock.filter = mock_filter
        return query_mock

    db.query = mock_query

    def mock_add(obj):
        model = type(obj)
        if model not in db._storage:
            db._storage[model] = []
        if hasattr(obj, 'id') and obj.id is None:
            obj.id = db._next_id[0]
            db._next_id[0] += 1
        db._storage[model].append(obj)
        return obj
    db.add = mock_add

    db.commit = Mock()
    db.flush = Mock()

    def mock_refresh(obj):
        model = type(obj)
        if hasattr(obj, 'id'):
            for stored in db._storage.get(model, []):
                if stored.id == obj.id:
                    for attr in dir(stored):
                        if not attr.startswith('_'):
                            try:
                                setattr(obj, attr, getattr(stored, attr))
                            except:
                                pass
                    break
    db.refresh = mock_refresh

    def mock_delete(obj):
        model = type(obj)
        if hasattr(obj, 'id'):
            db._storage[model] = [r for r in db._storage.get(model, []) if r.id != obj.id]
        return obj
    db.delete = mock_delete

    db.rollback = Mock()
    db.close = Mock()
    db.execute = Mock()
    db.scalar = Mock(return_value=1)
    db.get = Mock()
    return db


@pytest.fixture
def admin_user():
    """模拟管理员用户"""
    user = Mock()
    user.id = 1
    user.username = "admin"
    user.email = "admin@example.com"
    user.full_name = "管理员"
    user.role = "admin"
    user.is_active = True
    user.is_superuser = True
    user.organization_id = 1
    user.permissions_list = ["*"]
    user.failed_login_count = 0
    user.locked_until = None
    return user


@pytest.fixture
def regular_user():
    """模拟普通用户"""
    user = Mock()
    user.id = 2
    user.username = "user"
    user.email = "user@example.com"
    user.full_name = "普通用户"
    user.role = "user"
    user.is_active = True
    user.is_superuser = False
    user.organization_id = 2
    user.permissions_list = ["read"]
    user.failed_login_count = 0
    user.locked_until = None
    return user


@pytest.fixture
def viewer_user():
    """模拟查看者用户"""
    user = Mock()
    user.id = 3
    user.username = "viewer"
    user.email = "viewer@example.com"
    user.full_name = "查看者"
    user.role = "viewer"
    user.is_active = True
    user.is_superuser = False
    user.organization_id = 2
    user.permissions_list = ["view"]
    user.failed_login_count = 0
    user.locked_until = None
    return user


@pytest.fixture
def mock_token_payload():
    """模拟 JWT Token payload"""
    return {
        "sub": "admin",
        "type": "access",
        "exp": 9999999999,
        "iat": 1609459200,
    }


@pytest.fixture
def admin_token_headers(client, mock_token_payload):
    """管理员认证头"""
    from app.core.security import get_current_user

    user = Mock()
    user.id = 1
    user.username = "admin"
    user.role = "admin"
    user.is_superuser = True
    user.is_active = True
    user.permissions_list = ["*"]
    user.organization_id = 1

    async def mock_get_current_user():
        return user

    client.app.dependency_overrides[get_current_user] = mock_get_current_user

    token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.test"
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def user_token_headers(client):
    """普通用户认证头"""
    from app.core.security import get_current_user

    user = Mock()
    user.id = 2
    user.username = "user"
    user.role = "user"
    user.is_superuser = False
    user.is_active = True
    user.permissions_list = ["read"]
    user.organization_id = 2

    async def mock_get_current_user():
        return user

    client.app.dependency_overrides[get_current_user] = mock_get_current_user

    token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.user"
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def operator_token_headers(client):
    """操作员认证头"""
    from app.core.security import get_current_user

    user = Mock()
    user.id = 3
    user.username = "operator"
    user.role = "operator"
    user.is_superuser = False
    user.is_active = True
    user.permissions_list = ["read", "write"]
    user.organization_id = 1

    async def mock_get_current_user():
        return user

    client.app.dependency_overrides[get_current_user] = mock_get_current_user

    token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.operator"
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def client():
    """FastAPI 测试客户端（无认证）"""
    try:
        from app.main import app

        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        from sqlalchemy.pool import StaticPool

        engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )

        from app.models import Base
        Base.metadata.create_all(bind=engine)

        TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        db = TestingSessionLocal()

        def override_get_db():
            try:
                yield db
            finally:
                pass

        from app.core.database import get_db
        import app.core.database as _db_module

        # 关键修复：AuditLogger._persist_to_db 等绕过 get_db 直接 SessionLocal()
        # 的代码路径，在测试下会连到生产 test.db（0 张表），INSERT 抛
        # OperationalError 被吞。把 module 级 engine/SessionLocal 也指向内存库，
        # 保证审计落库链路在测试环境真正可被断言。
        _original_engine = _db_module.engine
        _original_session_local = _db_module.SessionLocal
        _db_module.engine = engine
        _db_module.SessionLocal = TestingSessionLocal

        # 保存原始的依赖覆盖
        original_overrides = app.dependency_overrides.copy()
        app.dependency_overrides[get_db] = override_get_db

        yield TestClient(app, raise_server_exceptions=False)

        # 清理：恢复原始依赖覆盖与全局 engine/SessionLocal
        app.dependency_overrides = original_overrides
        _db_module.engine = _original_engine
        _db_module.SessionLocal = _original_session_local
        db.close()
    except Exception:
        # 失败必须显式暴露：静默吞掉会让 fixture 返回 None, 所有消费方
        # 测试被悄悄 skip, 呈现"绿但什么都没测"的假象（覆盖率门禁只能
        # 兜底部分场景）。setup 失败应让相关测试真实 ERROR。
        import logging

        logging.getLogger(__name__).exception("client fixture setup/teardown failed")
        raise


@pytest.fixture
def auth_client(client):
    """FastAPI 测试客户端（带管理员认证）"""
    if client is None:
        return None
    from app.core.security import get_current_user

    user = Mock()
    user.id = 1
    user.username = "admin"
    user.role = "admin"
    user.is_superuser = True
    user.is_active = True
    user.permissions_list = ["*"]
    user.organization_id = 1
    user.email = "admin@test.com"
    user.full_name = "Admin"

    async def mock_get_current_user():
        return user

    original_overrides = client.app.dependency_overrides.copy()
    client.app.dependency_overrides[get_current_user] = mock_get_current_user
    yield client
    client.app.dependency_overrides = original_overrides


@pytest.fixture
def client_with_mocked_auth(client):
    """为测试提供模拟认证（需要时显式引入）"""
    if client is None:
        return None
    from app.core.security import get_current_user

    user = Mock()
    user.id = 1
    user.username = "admin"
    user.role = "admin"
    user.is_superuser = True
    user.is_active = True
    user.permissions_list = ["*"]
    user.organization_id = 1
    user.email = "admin@test.com"
    user.full_name = "Admin"

    original_overrides = client.app.dependency_overrides.copy()
    client.app.dependency_overrides[get_current_user] = lambda: user
    yield client
    client.app.dependency_overrides = original_overrides


@pytest.fixture
def client_with_regular_user_auth(client):
    """为测试提供普通用户模拟认证"""
    if client is None:
        return None
    from app.core.security import get_current_user

    user = Mock()
    user.id = 2
    user.username = "regular_user"
    user.role = "user"
    user.is_superuser = False
    user.is_active = True
    user.permissions_list = ["read"]
    user.organization_id = 2
    user.email = "user@test.com"
    user.full_name = "Regular User"

    original_overrides = client.app.dependency_overrides.copy()
    client.app.dependency_overrides[get_current_user] = lambda: user
    yield client
    client.app.dependency_overrides = original_overrides


@pytest.fixture
def user_headers(client):
    """普通用户认证头"""
    user = Mock()
    user.id = 2
    user.username = "user"
    user.role = "user"
    user.is_superuser = False
    user.is_active = True
    user.permissions_list = ["read"]
    user.organization_id = 2

    from app.core.security import get_current_user
    client.app.dependency_overrides[get_current_user] = lambda: user

    token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.user"
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def normal_user():
    """普通用户（用于权限测试）"""
    user = Mock()
    user.id = 2
    user.username = "user"
    user.role = "user"
    user.is_superuser = False
    user.is_active = True
    user.permissions_list = ["read"]
    user.organization_id = 2
    return user


@pytest.fixture
def mock_cache():
    """模拟缓存服务"""
    cache = Mock()
    cache.get.return_value = None
    cache.set = Mock(return_value=True)
    cache.delete = Mock(return_value=True)
    cache.clear = Mock(return_value=True)
    return cache


@pytest.fixture
def db_session(mock_db):
    """数据库会话 fixture（兼容旧测试）"""
    return mock_db


@pytest.fixture
def db(mock_db):
    """数据库 fixture（兼容旧测试）"""
    return mock_db


@pytest.fixture
def real_db_session():
    """真实数据库会话 fixture（用于服务层测试）"""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool
    from app.models import Base

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)

    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = TestingSessionLocal()

    try:
        yield db
    finally:
        try:
            db.rollback()
        except Exception:
            pass
        db.close()
        engine.dispose()  # 释放连接池，防止内存泄漏


@pytest.fixture
def client_with_db():
    """FastAPI 测试客户端（带共享数据库会话，用于审计测试）"""
    from app.main import app
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool
    from app.models import Base
    from app.core.database import get_db
    from fastapi.testclient import TestClient

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)

    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = TestingSessionLocal()

    def override_get_db():
        try:
            yield db
        finally:
            pass

    original_overrides = app.dependency_overrides.copy()
    app.dependency_overrides[get_db] = override_get_db

    yield TestClient(app, raise_server_exceptions=False), db

    app.dependency_overrides = original_overrides
    try:
        db.rollback()
    except Exception:
        pass
    db.close()
    engine.dispose()


@pytest.fixture
def auth_client_with_db(client_with_db):
    """带管理员认证的测试客户端（带共享数据库会话）"""
    if client_with_db is None:
        return None, None
    from app.core.security import get_current_user

    test_client, db = client_with_db

    user = Mock()
    user.id = 1
    user.username = "admin"
    user.role = "admin"
    user.is_superuser = True
    user.is_active = True
    user.permissions_list = ["*"]
    user.organization_id = 1

    test_client.app.dependency_overrides[get_current_user] = lambda: user
    return test_client, db


@pytest.fixture
def admin_token():
    """管理员 token（兼容旧测试）"""
    return "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.admin"


@pytest.fixture
def admin_headers(admin_token_headers):
    """管理员认证头（兼容旧测试，别名为 admin_token_headers）"""
    return admin_token_headers


@pytest.fixture(autouse=True)
def mock_settings():
    """自动使用的模拟设置（通过环境变量 + 强制覆盖 settings 对象）"""
    # 清理全局缓存，防止跨测试缓存污染
    try:
        from app.core.cache import cache_manager
        cache_manager._b.clear()
    except Exception:
        pass
    os.environ["SECRET_KEY"] = "test-secret-key-32-chars-long!!!!!"
    os.environ["ENVIRONMENT"] = "testing"
    os.environ["DEBUG"] = "true"
    os.environ["DATABASE_URL"] = "sqlite:///./test.db"
    os.environ["CSRF_ENABLED"] = "false"
    # 强制覆盖 settings 对象，防止模块已在 env 设置前实例化
    from app.core.config import settings
    _saved = {
        "SECRET_KEY": settings.SECRET_KEY,
        "ENVIRONMENT": settings.ENVIRONMENT,
        "DEBUG": settings.DEBUG,
        "DATABASE_URL": settings.DATABASE_URL,
        "CSRF_ENABLED": settings.CSRF_ENABLED,
    }
    settings.SECRET_KEY = "test-secret-key-32-chars-long!!!!!"
    settings.ENVIRONMENT = "testing"
    settings.DEBUG = True
    settings.DATABASE_URL = "sqlite:///./test.db"
    settings.CSRF_ENABLED = False
    # 确保 test.db 表结构存在（幂等）：直接连 SessionLocal 的测试（如 sync_version
    # 回归测试）依赖该库；全量测试中部分 teardown 可能清空表结构
    try:
        from app.models import Base
        from app.core.database import engine as _test_engine

        Base.metadata.create_all(bind=_test_engine)
    except Exception:
        pass
    yield
    # 恢复 settings 对象属性，防止状态泄漏到其他测试
    for key, val in _saved.items():
        setattr(settings, key, val)
    for key in ["SECRET_KEY", "ENVIRONMENT", "DEBUG", "DATABASE_URL", "CSRF_ENABLED"]:
        os.environ.pop(key, None)
    # 测试结束后再次清理缓存
    try:
        from app.core.cache import cache_manager
        cache_manager._b.clear()
    except Exception:
        pass
