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

# ── 关键修复（2026-10-02）：必须同时声明 BUMOFU_DEV_MODE，否则 Linux CI 隔离整体失效 ──
# paths.get_app_data_dir() / get_cache_path() 的首个分支是：
#     if is_bundled() or (is_linux() and not os.environ.get("BUMOFU_DEV_MODE")):
# 在 ubuntu-latest（Linux）上该条件恒真 → 直接 return Path.home() / ".bumofu"，
# **根本不经过上面的 get_project_backend_dir()**，于是 BUMOFU_BACKEND_DIR_OVERRIDE
# 完全失效；而在开发者本机（Windows）is_linux() 为假 → 走 else 分支 → override 生效。
# 后果（Linux CI 与 Windows 本地的口径分叉）：
#   1) Settings 在 import 期把 DATABASE_URL/CACHE_DIR/UPLOAD_DIR/EXPORT_DIR 固化为
#      /home/runner/.bumofu/...，测试数据写进 runner 家目录而非本会话临时根；
#   2) 依赖隔离的用例与覆盖率分支在 Linux 上走另一条路径 → 本地全绿、CI 恒红
#      （PR Checks backend-test / Nightly backend-full / build-windows smoke-test
#       三个作业同在 ubuntu-latest 跑全量，长期同时红；windows-smoke 只跑 5 文件子集故绿）。
# 声明 BUMOFU_DEV_MODE 让两平台都落到 else 分支、统一由 override 收口，口径即一致。
# 必须在任何 app.* 导入之前设置——Settings 构造期完成路径归一，晚设无效。
# 回归守护：tests/unit/test_paths.py::TestSessionIsolationContract
_os.environ["BUMOFU_DEV_MODE"] = "1"

# W4-T6（2026-10-18）：测试库统一为**会话临时根下的绝对路径**（每个 pytest 进程 /
# xdist worker 各自 mkdtemp 一份 → 天然按 worker 隔离）。历史写法是相对字面量
# `sqlite:///./test.db`：Settings 在 import 期已按临时根归一成绝对路径建好全局引擎，
# 但下面的 mock_settings fixture 又把 settings/env 强制回相对值 —— 任何**运行期现场
# 解析**数据库路径的代码（paths.get_database_path、备份/恢复、升级排练）于是落到
# CWD 的 backend/test.db，与引擎所指不是同一个文件；该相对文件还会被同一机器上的
# 并发行共享，是 seed_admin / soft_delete / audit 顺序耦合抖动的来源。
# 模块级与 fixture 统一引用本常量，两条路径不再分叉。
# W4-T6 补充（2026-10-20）：文件名显式带 xdist worker 标识（gw0/gw1/...），
# 即使未来有人把临时根改成进程间共享（或 --dist loadgroup 复用 worker），
# 也不会再出现"两个 worker 指向同一个库文件"的退化。
_XDIST_WORKER = _os.environ.get("PYTEST_XDIST_WORKER", "")
TEST_DATABASE_URL = (
    f"sqlite:///{(_APP_DATA_ROOT / ('test_' + _XDIST_WORKER + '.db' if _XDIST_WORKER else 'test.db')).as_posix()}"
)
_os.environ["DATABASE_URL"] = TEST_DATABASE_URL
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

# ── fd 级捕获 + 非 UTF-8 日志句柄（W27：本轮踩到并修的测试基建缺陷） ──────
# 症状：一批**与本主题无关**的用例集体 ERROR，堆栈落在 pytest 的
#   `FDCapture.snap() → tmpfile.read()`：
#   UnicodeDecodeError: 'utf-8' codec can't decode byte 0xb8 in position 64
# 根因：应用日志在 import 期就把 `logging.StreamHandler` 绑到了**当时的** sys.stdout
#   （Windows 控制台默认 cp936）。此后 pytest 用 `capfd` 类用例切到 fd 级捕获，
#   日志里的中文按 GBK 字节写进捕获临时文件，而 pytest 用 **utf-8** 读取 → 直接抛错。
#   报错发生在捕获层，因此表现为"日志无关的用例莫名其妙全红"，极难定位。
# 修法：把已存在的 StreamHandler 重新绑定到上面刚 reconfigure 成 utf-8 的流。
#   只处理指向真实标准流的句柄（文件/轮转句柄不动）。
def _rebind_stream_handlers() -> None:
    import logging as _logging

    real = {id(_sys.__stdout__): _sys.stdout, id(_sys.__stderr__): _sys.stderr}
    roots = [_logging.getLogger()]
    roots.extend(_logging.Logger.manager.loggerDict.values())
    for logger in roots:
        if not isinstance(logger, _logging.Logger):
            continue
        for handler in list(getattr(logger, "handlers", [])):
            if not isinstance(handler, _logging.StreamHandler):
                continue
            if isinstance(handler, _logging.FileHandler):
                continue
            stream = getattr(handler, "stream", None)
            replacement = real.get(id(stream))
            if replacement is not None:
                try:
                    handler.setStream(replacement)
                except Exception:  # pragma: no cover - 防御：个别句柄不支持换流
                    pass


_rebind_stream_handlers()

import pytest


def pytest_runtest_setup(item):  # noqa: ARG001
    """每个用例开始前惰性重绑日志句柄。

    为什么不用 session 级 autouse fixture：那会在**会话一开始**就 `import app.main`，
    强行提前触发应用初始化（日志/种子/中间件），改变既有用例的执行顺序敏感点
    —— 实测全量跑时 `test_seed_default_admin::test_top_org_fetch_failure` 因
    `commit` 调用次数变为 2 而红（单跑 88 例全绿），正是这类顺序扰动。
    改为 runtest 钩子：句柄由真正用到 `app.*` 的用例在导入期建立，钩子在下一个
    用例开始前把它重绑到 utf-8 流即可，**不强制提前导入任何模块**。
    """
    _rebind_stream_handlers()



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


# ── 根因修复：回滚「测试把 app.* 模块替换成 MagicMock」造成的跨用例污染（W27 第 12 轮）──
# 症状（W27 第 9~11 轮反复出现）：单进程全量跑时，偶发某个**与本主题无关**的用例失败，
# 且**每次换一个文件/方法**；单跑、整文件跑都全绿。典型断言是
#   Expected 'commit' to have been called once. Called 2 times.
#
# 已定位的机制：某些用例直接写 `sys.modules["app.services.lockout_service"] = MagicMock(...)`
# （用替身模拟"模块不可用"），若没在 teardown 还原，后续用例再
# `patch("app.services.lockout_service.get_lockout_service")` 就打到**替身**上，
# 真实服务照常运行并多提交一次 —— 于是计数翻倍。
#
# 处置：每个用例结束后，把被**替换成 Mock 或删除**的 app.* 模块还原为原始对象，
# 并给出警告（附用例 id），让污染可见而不是靠后续用例"莫名变红"来暴露。
# 只针对 Mock/删除两种形态，不做全量 sys.modules 快照（性能与误伤都不可接受）。
_MODULE_SWAP_MARKER = "allow_module_swap"


def _is_mock_object(obj) -> bool:
    from unittest.mock import Base

    return isinstance(obj, Base)


@pytest.fixture(autouse=True)
def _rollback_app_module_swaps(request):
    _allowed = request.node.get_closest_marker(_MODULE_SWAP_MARKER) is not None
    snapshot = {
        k: v for k, v in sys.modules.items() if k == "app" or k.startswith("app.")
    }
    yield
    if _allowed:
        return

    import warnings as _warnings

    def _restore(name, original, how):
        try:
            if original is None:
                # 用例**首次导入**后又被换成 Mock：删掉即可，下次 import 会重新加载真模块
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = original
        except Exception:  # pragma: no cover - 防御
            return
        _warnings.warn(
            f"[test-isolation] {request.node.nodeid} 把 sys.modules[{name!r}] "
            f"{how}且未还原，已自动还原 —— 这类污染会让**后续无关用例**偶发失败"
            f"（W27 已实际遇到：commit/close 计数翻倍）。请改用 monkeypatch"
            f"或在 teardown 还原；确需跨用例保留时打 @pytest.mark.{_MODULE_SWAP_MARKER}。",
            stacklevel=1,
        )

    # ① 快照里有的：被删除 或 被替换成 Mock → 还原
    for name, original in snapshot.items():
        current = sys.modules.get(name)
        if current is original:
            continue
        if current is None or _is_mock_object(current):
            _restore(name, original, "替换为 Mock" if current is not None else "删除")

    # ② 快照里没有的（用例内**首次导入**）：若现在是 Mock → 删掉，让下次 import 重新加载
    for name, current in list(sys.modules.items()):
        if name in snapshot:
            continue
        if not (name == "app" or name.startswith("app.")):
            continue
        if _is_mock_object(current):
            _restore(name, None, "替换为 Mock（用例内首次导入）")


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


# ── W4-T7（2026-10-20）：顺序耦合治理完成 ──────────────────────────────────
# 历史上这里有一段 `_POLLUTION_SENSITIVE` 强制排序（把 8 个"必须先跑"的文件移到
# 集合最前：test_rbac_transactional / test_audit_integration / test_unified_template
# / test_fund_budgets_api / test_project_milestones_api / test_statistics_api /
# test_coverage_gap_batch3 / test_data_dashboard_api），以及 BUMOFU_TEST_NO_ITEM_REORDER
# 逃生舱。这些文件依赖"先跑"的根因是模块级 mock 链/事件循环被其它测试破坏。
# 该排序块已删除：顺序独立性由「全量自然顺序 + pytest-randomly 随机顺序」两轮回归
# 锁定（见 .scratch/w4-quality-gates/007-remove-test-pollution.md Resolution）。
# 新增测试若出现顺序依赖，应修 mock 链，禁止恢复强制排序。

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from fastapi.testclient import TestClient


@pytest.fixture(scope="session", autouse=True)
def _stretch_audit_flush_interval():
    """W4-T7：拉长审计批量落库的**定时**刷写间隔。

    背景：`app/core/audit_middleware` 的 daemon 线程每 5s 刷写一次缓冲，而测试的
    `client` fixture 使用 `sqlite:///:memory:` + StaticPool（全进程共用**一条**连接）。
    定时刷写线程与请求事务在同一连接上交错时，全量 `-n auto` 高压运行中偶发
    `Multi-row INSERT ... did not produce the correct number of INSERTed row`
    （表现为 safe_commit 回滚、审批任务创建失败，单文件运行复现不了）。

    请求结束时的显式 flush（dispatch 尾部 `_flush_pending`）不受影响，
    因此 `test_audit_middleware_batching.py` 等审计落库断言仍走原路径；
    该文件内部按需把常量 patch 回 60s / 0.05s 来验证定时刷写本身。
    """
    try:
        from app.core import audit_middleware as _am

        _am._FLUSH_INTERVAL_SECONDS = 3600.0
    except Exception:  # pragma: no cover - 模块导入异常不应阻塞测试启动
        pass
    yield


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

        try:
            yield TestClient(app, raise_server_exceptions=False)
        finally:
            # 清理必须在 finally：测试体抛异常时若跳过还原，app.dependency_overrides
            # 会残留本用例的内存库覆盖，后续测试复用同一 app 实例时拿到已耗尽
            # mock（side_effect StopIteration）或错误会话 —— 顺序污染的通用根因。
            app.dependency_overrides = original_overrides
            _db_module.engine = _original_engine
            _db_module.SessionLocal = _original_session_local
            db.close()
            # 刻意**不 dispose** 本用例的内存引擎（2026-10-17 曾短暂加上，被 CI 证伪后
            # 回退，勿再引入）。`engine.dispose()` 会把这条 StaticPool 连接**提前**关掉，
            # 而本 fixture 在用例期间把模块级 `app.core.database.SessionLocal` 指向了它
            # —— 运行时才解析 `SessionLocal` 的后台写线程（审计兜底 `audit-log-flusher`
            # 每 5s 一次；`immediate-backup`；`approval-reminder`；`async-export-villages`
            # 等）可能正持有该连接在写。sqlite3 是 C 扩展：连接被提前关闭而线程仍在写
            # = use-after-free，不是 Python 异常而是**进程级 SIGSEGV**。
            # 实测（Build Windows 的 smoke-test，全量 pytest + xdist + --cov）：一次跑崩
            # 两个 worker，栈均为 `_flusher_loop → _persist_batch → safe_commit`；
            # worker 崩掉后其覆盖率数据整体丢失 → 覆盖率假性 83.45% → 发版门禁误红。
            # 逐个 join 写入线程也不成立：上述线程有的无名、有的按需派生，无法穷举。
            # 代价仅是连接留到 GC：每次使用本 fixture 留一条 `unclosed database`
            # ResourceWarning（纯测试期噪音，不影响门禁与产物）。要彻底消除，需先让
            # 后台线程不再通过模块级 SessionLocal 取会话 —— 属测试基建重构，另行立项。
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
    # W4-T6：绝对路径（本 worker 独有的临时库），与模块级常量同源，避免现场解析分叉
    os.environ["DATABASE_URL"] = TEST_DATABASE_URL
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
    settings.DATABASE_URL = TEST_DATABASE_URL
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
