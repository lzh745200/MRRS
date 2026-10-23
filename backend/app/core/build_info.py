"""构建元数据 — 由 CI 打包前生成，运行时提供版本指纹。

开发环境下使用默认值（dev），CI 构建时由 generate_build_info.py 脚本覆写。
"""

import logging
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)

_BUILD_INFO_FILE = Path(__file__).with_name("_build_info.json")


def _load() -> dict:
    if _BUILD_INFO_FILE.exists():
        import json

        try:
            data = json.loads(_BUILD_INFO_FILE.read_text(encoding="utf-8"))
            # 合法但非对象的 JSON（如 ["a"]、"1.2.3"、123）是**真值**，会让调用方的
            # dev fallback 被跳过，并在 info.setdefault(...) 处抛 AttributeError，
            # 把版本查询（含未鉴权的 /health）打成 500。此处按「无有效元数据」处理。
            if not isinstance(data, dict):
                logger.warning("构建信息文件不是 JSON 对象（%s），按缺失处理", type(data).__name__)
                return {}
            return data
        except Exception:
            logger.debug("读取构建信息文件失败", exc_info=True)
    return {}


_cached: dict | None = None


def _has_git_worktree(start: Path | None = None) -> bool:
    """探测给定位置（默认本文件位置 + CWD）是否处于 git 工作树中。

    R28 低危项：``get_build_info()`` 原实现**无条件**执行
    ``subprocess.check_output(["git", "rev-parse", ...], timeout=5)``。
    打包环境（PyInstaller/Electron，无 git、无 .git）与未装 git 的离线终端上，
    这次调用只会白等到超时/抛异常后才回退 ``"dev"``，把进程内首次版本查询
    （含未鉴权的 ``/health``）拖慢数秒。改为：只有**确实存在 .git** 才尝试。

    要点：
      * worktree / submodule 的 ``.git`` 是**文件**而非目录，故用 ``exists()``；
      * 起点取「本文件位置」与「CWD」两处，各向上找 4 层，覆盖
        ``backend/app/core/build_info.py``（仓库根在 3 层之上）与从仓库任意
        子目录启动两种情形。
    """
    bases = [Path(__file__).resolve().parent, Path.cwd()] if start is None else [start]
    for base in bases:
        for parent in (base, *list(base.parents)[:4]):
            if (parent / ".git").exists():
                return True
    return False


def get_build_info() -> dict:
    """返回构建元数据：version / git_hash / build_time / builder。"""
    global _cached
    if _cached is not None:
        return _cached

    info = _load()
    if not info:
        git_hash = "dev"
        if _has_git_worktree():
            try:
                git_hash = (
                    subprocess.check_output(
                        ["git", "rev-parse", "--short", "HEAD"],
                        stderr=subprocess.DEVNULL,
                        timeout=2,
                    )
                    .decode()
                    .strip()
                )
            except Exception:
                logger.debug("获取git hash失败", exc_info=True)
        info = {
            "git_hash": git_hash,
            "build_time": None,
            "builder": "dev",
        }

    from app.core.config import settings

    # 版本号唯一权威来源是 settings.PROJECT_VERSION（根 package.json 同步）。
    # 构建指纹只提供 git_hash / build_time / builder：外壳里残留的旧
    # _build_info.json（CI 产物、已 gitignore）不得让 /health 报出旧版本。
    fingerprint_version = info.get("version")
    if fingerprint_version and fingerprint_version != settings.PROJECT_VERSION:
        logger.debug(
            "构建指纹版本(%s)与运行时版本(%s)不一致，以运行时为准",
            fingerprint_version,
            settings.PROJECT_VERSION,
        )
    info["version"] = settings.PROJECT_VERSION

    _cached = info
    return info
