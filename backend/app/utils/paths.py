"""
应用路径工具模块

解决不同平台的数据目录权限问题（H11 口径统一，2026-10-14）：
- 开发环境：使用项目目录（./data, ./backups, ./cache）
- Windows 桌面端打包运行时：Electron 注入 DATABASE_URL/UPLOAD_DIR 等环境变量，
  全部数据位于 Electron userData = %APPDATA%\\帮扶管理系统（目录名来自
  package.json 的 productName，Electron 对 app.name 优先取 productName；
  见 electron/main.js getUserDataPath 与 build-scripts NSIS 钩子 H11 注释）。
  本模块在 frozen 且无环境变量时的兜底目录为 %LOCALAPPDATA%\\bumofu-assistance
  （见 get_app_data_dir），桌面端正常不落到该目录，卸载时由 NSIS 钩子一并清理。
- Linux 生产环境（麒麟V10 ARM64）：**显式环境变量优先** ——
  ``BUMOFU_DATA_DIR`` → ``XDG_DATA_HOME/bumofu`` → ``~/.local/share/bumofu``
  （W18-offline P0-2：不再回退 ``~/.bumofu``，避免 standalone 服务用户 HOME
  指向只读安装目录时数据/密钥/备份全部落到不可写路径）。
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

    仅检查 ``sys.frozen``，**不要**用 ``sys._MEIPASS`` 做"是否打包"的布尔判据。

    历史原因：PyInstaller < 6 的 onedir 模式不设置 ``_MEIPASS``（仅 onefile 设置），
    用它判断打包态会在 onedir 下误判为 False，进而把 CWD（如 Program Files
    只读目录）当数据目录，引发 PermissionError。

    版本事实（与 ``assistance-backend.spec`` 的注释口径一致）：PyInstaller 6+
    两种模式都会设置 ``_MEIPASS``，onefile 指向临时解压目录、onedir 指向
    ``<app>/_internal``。它表示的是**资源目录**而非打包标志，取值随版本/模式
    变化；定位前端/瓦片等资源请走 ``static_files.find_frontend_dir`` 与
    ``map._resolve_tiles_dir`` 的候选路径方式，不要自己另写上溯级数。
    """
    return getattr(sys, "frozen", False)


def is_linux() -> bool:
    """检测是否在 Linux 平台上运行"""
    return platform.system() == "Linux"


def _resolve_linux_app_data_dir() -> Path:
    """解析 Linux 生产/打包态的数据根（W18-offline P0-2 收口）。

    优先级（显式环境变量优先，**绝不**再回退 ``Path.home()/.bumofu``）：

    1. ``BUMOFU_DATA_DIR``：部署模板显式指定（麒麟 standalone 为
       ``/var/lib/assistance-management-system``，见 ``deploy/kylin/config/kylin.env``）；
    2. ``XDG_DATA_HOME/bumofu``：遵循 XDG Base Directory 规范；
    3. ``~/.local/share/bumofu``：XDG 默认值（Linux 上通常可写）。

    历史缺陷：旧实现固定 ``Path.home()/.bumofu``。麒麟 standalone 以服务用户运行、
    ``HOME`` 被 systemd 指向 ``/opt/安装目录``（只读）→ 数据库/密钥/备份全部落到
    不可写目录：备份全废、PII 读取 500。``kylin.env`` 下发的 ``DATABASE_URL`` /
    ``BACKUP_DIR`` 等虽被下游消费，但数据根不读它们，仍派生到 ``$HOME/.bumofu``
    （路径双源），本函数把数据根收口到显式环境变量。

    空值/纯空白环境变量按未设置处理（部署脚本常以 ``VAR=`` 占位）。
    """
    explicit = (os.environ.get("BUMOFU_DATA_DIR") or "").strip()
    if explicit:
        return Path(explicit).expanduser()
    xdg = (os.environ.get("XDG_DATA_HOME") or "").strip()
    if xdg:
        return Path(xdg).expanduser() / "bumofu"
    return Path.home() / ".local" / "share" / "bumofu"


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

    Linux/打包态的数据根解析见 ``_resolve_linux_app_data_dir``（显式环境变量优先，
    不再回退 ``~/.bumofu``）；Windows 打包分支保持既有语义
    （``LOCALAPPDATA/bumofu-assistance``，无环境变量时才回退 ``~/.bumofu``）。

    返回:
        Path: 可写的应用数据目录路径
    """
    if is_bundled() or (is_linux() and not os.environ.get("BUMOFU_DEV_MODE")):
        if is_linux():
            # Linux（麒麟V10 ARM64 / standalone）：BUMOFU_DATA_DIR → XDG_DATA_HOME
            # → ~/.local/share/bumofu（W18-offline P0-2，见 _resolve_linux_app_data_dir）
            data_dir = _resolve_linux_app_data_dir()
        else:
            # Windows：使用 AppData/Local（行为保持不变）
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

    解析链（与 ``get_database_path()`` 同款"环境变量优先、不做存在性校验"）：

    1. ``BACKUP_DIR`` 环境变量 —— 部署模板显式下发（麒麟 ``kylin.env`` 指向
       ``/var/lib/assistance-management-system/backups``）；设了就用，**不校验/不创建**
       目录（首次恢复由调用方创建），避免只读介质/延迟挂载时误判；
    2. 推断 ``<app_data_dir>/backups`` —— ``app_data_dir`` 已按
       ``BUMOFU_DATA_DIR``/XDG 解析（见 ``get_app_data_dir``）。

    W18-offline P0-2：历史上 ``BACKUP_DIR`` 从未被本函数接收，麒麟部署的备份实际
    落到 ``$HOME/.bumofu/backups``（服务用户 HOME 只读 → 备份全废）；现已收口。
    空值/纯空白 ``BACKUP_DIR`` 按未设置处理。
    """
    env_backup = (os.environ.get("BACKUP_DIR") or "").strip()
    if env_backup:
        base = Path(env_backup).expanduser()
    else:
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
            # Linux：缓存对齐数据根（BUMOFU_DATA_DIR/XDG），不再写 ~/.bumofu/cache
            # —— 服务用户 HOME 只读时旧路径必然失败（W18-offline P0-2 同源缺陷）。
            base = get_app_data_dir() / "cache"
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
