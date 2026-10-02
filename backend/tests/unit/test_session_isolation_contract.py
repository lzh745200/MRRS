"""测试会话数据根隔离契约（conftest.py）的回归守护。

为什么单独一个模块、而不写进 tests/unit/test_paths.py：
    后者带模块级 ``pytestmark = pytest.mark.real_backend_dir``，conftest 的
    autouse fixture ``_honor_real_backend_dir_marker`` 会为**该模块全部用例**
    临时删除 ``BUMOFU_BACKEND_DIR_OVERRIDE``（它专测"未被覆盖的真实 backend
    目录"）。因此在本模块之外才能观察到会话根隔离的真实生效状态。

事件背景（2026-10-02）：
    conftest.py 顶部用 ``BUMOFU_BACKEND_DIR_OVERRIDE`` 把数据根指向会话临时目录，
    但 ``app/utils/paths.get_app_data_dir()`` 的首分支是
        ``is_bundled() or (is_linux() and not os.environ.get("BUMOFU_DEV_MODE"))``
    —— 在 Linux（CI 的 ubuntu-latest）上该条件恒真，直接短路返回
    ``Path.home() / ".bumofu"``，**根本不经过 get_project_backend_dir()**，
    于是 override 形同虚设；而开发者本机（Windows）``is_linux()`` 为假 → 走 else
    分支 → override 正常生效。两平台口径分叉，且 Linux 上测试数据写进 runner
    家目录（跨用例共享、跨运行残留），Settings 亦在 import 期把
    DATABASE_URL/CACHE_DIR/UPLOAD_DIR/EXPORT_DIR 一并固化到那里。

修复：conftest.py 同时声明 ``BUMOFU_DEV_MODE=1``，令两平台都落到 else 分支、
统一由 override 收口；必须在任何 ``app.*`` 导入之前设置（Settings 构造期即完成
路径归一）。下方两条用例分别在「值」与「实效」两个层面锁定该契约。
"""
import os
from pathlib import Path

from app.core.config import settings
from app.utils.paths import get_app_data_dir, get_cache_path


def test_conftest_declares_dev_mode():
    """conftest.py 必须声明 BUMOFU_DEV_MODE=1，否则 Linux 上数据根逃逸到 ~/.bumofu。"""
    assert os.environ.get("BUMOFU_DEV_MODE") == "1", (
        "conftest.py 未声明 BUMOFU_DEV_MODE=1 —— Linux 上 get_app_data_dir() 会短路到 "
        "~/.bumofu，BUMOFU_BACKEND_DIR_OVERRIDE 失效（2026-10-02 已发生）"
    )


def test_session_data_root_is_isolated():
    """会话根在运行期真实生效：函数返回值与 Settings 固化路径均落在会话临时根内。

    不 monkeypatch、不模拟平台 —— 直接断言当前真实环境，故：
      * 在 Linux（CI）上，若 conftest 漏声明 BUMOFU_DEV_MODE，本条立即失败
        （Windows 上 is_linux() 为假，不受该开关影响，此为设计使然）；
      * 亦覆盖"声明晚于 app 导入"的时序错位：Settings 在 import 期已固化路径，
        晚设 env 只影响运行期函数、不影响 Settings，一并断言即可拦住。
    """
    override = os.environ.get("BUMOFU_BACKEND_DIR_OVERRIDE")
    assert override, "conftest 未设置 BUMOFU_BACKEND_DIR_OVERRIDE，会话隔离缺失"
    root = Path(override).resolve()

    assert get_app_data_dir().resolve() == root, (
        f"数据根逃逸到 {get_app_data_dir()}（应为 {root}）—— Linux 上即 BUMOFU_DEV_MODE 缺失"
    )
    assert get_cache_path().resolve().is_relative_to(root), f"缓存根逃逸到 {get_cache_path()}"

    # 断言 Settings 在 import 期固化的三个目录字段。
    # 不含 DATABASE_URL：conftest 的 autouse fixture 会**有意**把它重置为相对形式
    # ``sqlite:///./test.db``（配合被改指内存库的 SessionLocal，见 conftest 中
    # "强制覆盖 settings 对象，防止模块已在 env 设置前实例化" 一段），因此它在
    # 测试会话里天然不指向会话根，断言它会误报。
    root_str = str(root).replace("\\", "/")
    for field in ("CACHE_DIR", "UPLOAD_DIR", "EXPORT_DIR"):
        value = str(getattr(settings, field)).replace("\\", "/")
        assert value.startswith(root_str), (
            f"settings.{field} 逃逸出会话根: {value}（会话根 {root_str}）—— "
            "Linux 上即 BUMOFU_DEV_MODE 缺失或声明晚于 app 导入"
        )
