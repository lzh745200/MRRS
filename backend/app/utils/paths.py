"""
应用路径工具模块

解决不同平台的数据目录权限问题：
- 开发环境：使用项目目录（./data, ./backups, ./cache）
- Windows 生产环境：使用用户数据目录（%APPDATA%/bumofu-assistance/）
- Linux 生产环境（麒麟V10 ARM64）：使用家目录隐藏文件夹（~/.bumofu/）
"""

import os
import platform
import sys
from pathlib import Path


class PathTraversalError(ValueError):
    """路径遍历安全异常"""


def _safe_join(base: Path, sub_path: str) -> Path:
    """
    安全地拼接路径，防止路径遍历攻击。

    Args:
        base: 基础目录
        sub_path: 子路径

    Returns:
        Path: 拼接后的路径

    Raises:
        PathTraversalError: 如果子路径试图逃逸基础目录
    """
    if not sub_path:
        return base

    resolved = (base / sub_path).resolve()
    base_resolved = base.resolve()

    # 确保解析后的路径仍在基础目录内
    try:
        resolved.relative_to(base_resolved)
    except ValueError:
        raise PathTraversalError(
            f"路径遍历被拒绝: '{sub_path}' 试图逃逸 '{base}'"
        )

    return resolved


def is_bundled() -> bool:
    """检测是否在 PyInstaller 打包环境中运行

    注意：以前同时检查 sys.frozen 和 sys._MEIPASS，但 _MEIPASS 仅在
    onefile 模式下存在。onedir 模式下 sys.frozen=True 但 _MEIPASS 不存在，
    导致打包后 is_bundled() 误判为 False，进而使用 CWD（如 Program Files
    只读目录）作为数据目录，引发 PermissionError。
    现仅检查 sys.frozen，兼容 onefile 和 onedir 两种模式。
    """
    return getattr(sys, "frozen", False)


def is_linux() -> bool:
    """检测是否在 Linux 平台上运行"""
    return platform.system() == "Linux"


def get_project_backend_dir() -> Path:
    """基于模块文件位置推断 backend 项目根目录（与 CWD 无关）。

    本文件位于 ``backend/app/utils/paths.py``，因此向上三级父目录即 backend
    根目录：

        parents[0] = backend/app/utils
        parents[1] = backend/app
        parents[2] = backend      ← 返回此目录

    历史缺陷（任务#6 风险1·数据消失直接诱因）：开发环境曾用 ``Path.cwd()``
    作为数据根目录，导致实际读写哪个数据库完全取决于启动时的工作目录。标准
    命令 ``cd backend; python start.py``（start.py 内部会 chdir 到 backend）
    指向正确的 ``backend/data/rural_revitalization.db``；但若经 uvicorn /
    alembic / pytest 等入口从项目根启动，CWD=项目根 → 解析到陈旧的
    ``<root>/data/rural_revitalization.db``（数据更少）→ 用户观感“数据消失”。
    改为基于 ``__file__`` 推断后，无论从哪个 CWD 启动，开发环境都稳定指向
    backend 目录。

    ``BUMOFU_BACKEND_DIR_OVERRIDE`` 可显式覆盖该推断结果，供测试与特殊部署
    重定向全部数据目录（本模块所有 dev 分支路径都由本函数派生）。必须是
    **调用时**读取而非导入时绑定：若改用「替换模块属性」的方式覆盖，此后所有
    ``from app.utils.paths import get_project_backend_dir`` 的模块会把名字冻结
    成替身，与后来被还原的模块属性分叉。未设置时行为与既往完全一致。
    """
    override = os.environ.get("BUMOFU_BACKEND_DIR_OVERRIDE", "")
    if override:
        return Path(override)
    return Path(__file__).resolve().parents[2]


def get_app_data_dir() -> Path:
    """
    获取应用数据目录

    返回:
        Path: 可写的应用数据目录路径
    """
    if is_bundled() or (is_linux() and not os.environ.get("BUMOFU_DEV_MODE")):
        if is_linux():
            # Linux（麒麟V10 ARM64）：使用家目录隐藏文件夹
            data_dir = Path.home() / ".bumofu"
        else:
            # Windows：使用 AppData/Local
            base_dir = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
            if base_dir:
                data_dir = Path(base_dir) / "bumofu-assistance"
            else:
                data_dir = Path.home() / ".bumofu"
    else:
        # 开发/测试环境：基于项目结构固定指向 backend 目录，不依赖 CWD。
        # 打包模式（Electron 注入绝对 DATABASE_URL）与 Linux 生产模式在上面
        # 分支已提前返回，不受此处影响。
        data_dir = get_project_backend_dir()

    # 确保目录存在
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


def get_data_path(sub_path: str = "") -> Path:
    """
    获取数据文件路径

    Args:
        sub_path: 相对于数据目录的子路径

    返回:
        Path: 完整的数据文件路径

    Raises:
        PathTraversalError: 如果子路径试图逃逸基础目录
    """
    base = get_app_data_dir() / "data"
    if sub_path:
        path = _safe_join(base, sub_path)
        # 如果子路径包含目录部分，确保目录存在
        if path.parent != base:
            path.parent.mkdir(parents=True, exist_ok=True)
        return path
    return base


def get_backup_path(sub_path: str = "") -> Path:
    """
    获取备份文件路径

    自动备份调度由 BACKUP_ENABLED 环境变量控制（见 auto_backup.py）。
    手动备份（管理员 API）始终使用此目录，不受该环境变量影响。
    """
    base = get_app_data_dir() / "backups"
    if sub_path:
        path = _safe_join(base, sub_path)
        if path.parent != base:
            path.parent.mkdir(parents=True, exist_ok=True)
        return path
    return base


# 向后兼容的别名
get_backup_directory = get_backup_path


def get_cache_path(sub_path: str = "") -> Path:
    """
    获取缓存文件路径

    Args:
        sub_path: 相对于缓存目录的子路径

    返回:
        Path: 完整的缓存文件路径
    """
    # 缓存使用 Local 目录（不漫游）
    if is_bundled() or (is_linux() and not os.environ.get("BUMOFU_DEV_MODE")):
        if is_linux():
            base = Path.home() / ".bumofu" / "cache"
        else:
            base_dir = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
            if base_dir:
                base = Path(base_dir) / "bumofu-assistance" / "cache"
            else:
                base = Path.home() / ".bumofu" / "cache"
    else:
        # 开发环境：与其他路径函数保持一致
        base = get_app_data_dir() / "data" / "cache"

    if sub_path:
        path = _safe_join(base, sub_path)
        if path.parent != base:
            path.parent.mkdir(parents=True, exist_ok=True)
        return path
    return base


def get_uploads_path(sub_path: str = "") -> Path:
    """
    获取上传文件路径

    Args:
        sub_path: 相对于上传目录的子路径

    返回:
        Path: 完整的上传文件路径

    Raises:
        PathTraversalError: 如果子路径试图逃逸基础目录
    """
    base = get_app_data_dir() / "uploads"
    if sub_path:
        path = _safe_join(base, sub_path)
        if path.parent != base:
            path.parent.mkdir(parents=True, exist_ok=True)
        return path
    return base


def get_database_path() -> Path:
    """
    获取数据库文件路径

    解析优先级（2026-08-30 路径双源修复，详见 ADR-0008 关联工单）：
    1. DATABASE_URL 环境变量（Electron 启动时注入，指向真实在用的数据库）
    2. settings.DATABASE_URL（覆盖 .env 文件配置的场景）
    3. 传统推断：<app_data_dir>/data/rural_revitalization.db（兜底，行为与
       旧版本一致）

    历史缺陷：本函数只做静态推断，而应用实际使用的库由 DATABASE_URL 决定，
    打包 + Electron 注入环境下两者分叉，导致备份/恢复/健康检查/维护任务
    全部作用在一个陈旧的错误文件上。

    返回:
        Path: 数据库文件的完整路径
    """
    url = os.environ.get("DATABASE_URL", "")
    if not url:
        try:
            # 延迟导入避免循环依赖；Settings 首次构造期间可能尚未就绪，静默跳过
            from app.core.config import settings

            url = settings.DATABASE_URL or ""
        except Exception:
            url = ""
    candidate = db_file_from_url(url)
    if candidate is not None:
        candidate.parent.mkdir(parents=True, exist_ok=True)
        return candidate
    return get_data_path("rural_revitalization.db")


def db_file_from_url(url: str):
    """从 SQLAlchemy URL 解析本地 SQLite 文件路径。

    仅接受指向绝对路径的 sqlite URL；内存库、非 SQLite、相对路径一律返回
    None，由调用方走兜底逻辑。
    """
    if not url or not url.startswith("sqlite"):
        return None
    prefix = "sqlite:///"
    if not url.startswith(prefix):
        return None
    raw = url[len(prefix):]
    raw = raw.split("?", 1)[0]
    if not raw or ":memory:" in raw:
        return None
    from urllib.parse import unquote

    path = Path(unquote(raw))
    if not path.is_absolute():
        return None
    return path


def get_runtime_uploads_path(sub_path: str = "") -> Path:
    """
    获取运行时上传根目录（与 files.py 写入、static_files.py 服务的目录一致）

    解析优先级与 get_database_path 相同：UPLOAD_DIR 环境变量 →
    settings.UPLOAD_DIR（须为绝对路径）→ 传统推断 get_uploads_path()。
    备份/统计/权限包等跨模块消费方必须使用本函数，避免路径双源分叉。
    """
    upload_dir = os.environ.get("UPLOAD_DIR", "")
    if not upload_dir:
        try:
            from app.core.config import settings

            upload_dir = settings.UPLOAD_DIR or ""
        except Exception:
            upload_dir = ""
    if upload_dir:
        path = Path(upload_dir)
        if path.is_absolute():
            base = path
        else:
            base = get_uploads_path()
    else:
        base = get_uploads_path()
    if sub_path:
        result = _safe_join(base, sub_path)
        if result.parent != base:
            result.parent.mkdir(parents=True, exist_ok=True)
        return result
    return base


def get_log_path(sub_path: str = "") -> Path:
    """
    获取日志文件路径

    Args:
        sub_path: 相对于日志目录的子路径

    返回:
        Path: 完整的日志文件路径

    Raises:
        PathTraversalError: 如果子路径试图逃逸基础目录
    """
    base = get_app_data_dir() / "logs"
    base.mkdir(parents=True, exist_ok=True)
    if sub_path:
        path = _safe_join(base, sub_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        return path
    return base
