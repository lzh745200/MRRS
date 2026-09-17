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


def get_build_info() -> dict:
    """返回构建元数据：version / git_hash / build_time / builder。"""
    global _cached
    if _cached is not None:
        return _cached

    info = _load()
    if not info:
        git_hash = "dev"
        try:
            git_hash = (
                subprocess.check_output(
                    ["git", "rev-parse", "--short", "HEAD"],
                    stderr=subprocess.DEVNULL,
                    timeout=5,
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

    info.setdefault("version", settings.PROJECT_VERSION)
    _cached = info
    return info
