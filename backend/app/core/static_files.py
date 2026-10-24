import os
import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.core.config import settings
from app.utils.paths import get_uploads_path


def find_frontend_dir() -> str | None:
    """查找前端构建产物目录，返回包含 index.html 的目录路径或 None。"""
    # PyInstaller 打包后 _MEIPASS 才可用，否则跳过以免匹配到相对路径
    _meipass = getattr(sys, '_MEIPASS', '')
    candidates = [
        os.environ.get("FRONTEND_DIST_PATH", ""),
        # PyInstaller 冻结态：资源在 _MEIPASS 中（仅冻结环境启用）。
        # 说明：当前 assistance-backend.spec **不打包** resources/frontend（由 Electron
        # extraResources 单独提供），所以这条候选在 NSIS 安装包里不会命中；
        # 它服务于"后端独立分发、前端随 spec 内嵌"的形态（test_frozen_meipass 锁定）。
        # 真正的 onedir 布局由下面两条候选覆盖，勿删本条以免收窄兼容面。
        str(Path(_meipass) / "resources" / "frontend") if _meipass else "",
        # PyInstaller onedir 实际结构（Windows NSIS / Linux deb 同构）：
        #   <resources>/backend/assistance-backend/_internal   ← _MEIPASS
        #   <resources>/frontend                              ← 前端产物
        # 自 _MEIPASS 上溯三级即 <resources>。缺此候选时，一旦 Electron 侧的
        # FRONTEND_DIST_PATH 未传（手工启动后端 / 升级后环境变量遗漏），
        # 浏览器访问 "/" 会 404 —— 桌面端表现为白屏。
        str(Path(_meipass).parent.parent.parent / "frontend") if _meipass else "",
        # 冻结态可执行文件同级上溯（应对 onedir 目录被改名/移动）。
        # 注意与 _MEIPASS 分支的级数差：sys.executable 指向**文件**
        # <resources>/backend/assistance-backend/_internal/assistance-backend.exe，
        # 需先 parent 去掉文件名，再上溯三级才到 <resources>，合计 **4 级**。
        # 只上溯三级会落到 <resources>/backend/frontend（不存在），前端依旧 404。
        (
            str(Path(sys.executable).resolve().parent.parent.parent.parent / "frontend")
            if getattr(sys, "frozen", False)
            else ""
        ),
        str(Path(__file__).resolve().parent.parent.parent.parent / "frontend" / "dist"),
        str(Path(__file__).resolve().parent.parent.parent.parent / "resources" / "frontend"),
        # 项目根目录下的 resources/frontend（从任意 CWD 启动均可靠）
        str(Path(__file__).resolve().parent.parent.parent.parent / ".." / "resources" / "frontend"),
    ]
    for candidate in candidates:
        if candidate and os.path.isfile(os.path.join(candidate, "index.html")):
            return candidate
    return None


def setup_static_files(app: FastAPI) -> str | None:
    """挂载上传目录静态文件并返回前端目录路径（或 None）。

    前端路由和 SPA fallback 由 main.py 负责注册。
    """
    uploads_dir = settings.UPLOAD_DIR

    if not os.path.isabs(uploads_dir) or (
        getattr(sys, "frozen", False) and uploads_dir.startswith(os.path.dirname(sys.executable))
    ):
        uploads_dir = str(get_uploads_path())

    try:
        os.makedirs(uploads_dir, exist_ok=True)
    except PermissionError:
        uploads_dir = str(get_uploads_path())
        os.makedirs(uploads_dir, exist_ok=True)

    app.mount("/uploads", StaticFiles(directory=uploads_dir), name="uploads")

    return find_frontend_dir()
