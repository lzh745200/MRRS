"""Config validation helpers.

Ensures the application settings are consistent and provides early
feedback for misconfigurations.
"""

import logging
import os
from typing import List, Tuple

logger = logging.getLogger(__name__)


def validate_config(
    settings=None,
) -> Tuple[bool, List[str]]:
    """Validate the current application configuration.

    Args:
        settings: Optional :class:`Settings` instance.  If *None* the
            function imports the global settings singleton.

    Returns:
        A tuple ``(is_valid, warnings)`` where *warnings* is a list of
        human-readable messages about potential issues.
    """
    if settings is None:
        try:
            from app.core.config import settings  # type: ignore[import-untyped]
        except Exception as e:
            logging.getLogger(__name__).error("无法加载配置模块: %s", e)
            return False, ["无法加载配置模块"]

    warnings: List[str] = []

    # --- SECRET_KEY ---
    secret = getattr(settings, "SECRET_KEY", None)
    if not secret:
        warnings.append("SECRET_KEY 未设置，建议通过环境变量或 .env 文件配置")
    elif len(secret) < 16:
        warnings.append("SECRET_KEY 过短（建议 >= 16 字符）")

    # --- DATABASE_URL ---
    db_url = getattr(settings, "DATABASE_URL", "")
    if not db_url:
        warnings.append("DATABASE_URL 未设置")
    elif "sqlite" in db_url:
        # Warn about SQLite absolute path issues on Windows
        import sys

        if sys.platform == "win32" and db_url.startswith("sqlite:///") and "\\" in db_url:
            warnings.append("DATABASE_URL 使用了 Windows 反斜杠路径，建议使用正斜杠")

    # --- PORT ---
    port = getattr(settings, "PORT", 8000)
    if not (1024 <= port <= 65535):
        warnings.append(f"PORT={port} 不在有效范围 (1024-65535)")

    # --- CORS ---
    origins = getattr(settings, "CORS_ORIGINS", "")
    if not origins:
        warnings.append("CORS_ORIGINS 未设置，跨域请求可能失败")

    # --- FILE UPLOAD ---
    max_size = getattr(settings, "MAX_FILE_SIZE", 0)
    if max_size <= 0:
        warnings.append("MAX_FILE_SIZE 未设置或无效")

    # --- LOGGING ---
    log_level = getattr(settings, "LOG_LEVEL", "INFO").upper()
    valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
    if log_level not in valid_levels:
        warnings.append(f"LOG_LEVEL={log_level} 无效，应为 {sorted(valid_levels)} 之一")

    is_valid = len([w for w in warnings if "未设置" in w or "无效" in w]) == 0

    for w in warnings:
        logger.warning("配置警告: %s", w)

    return is_valid, warnings


def check_required_dirs(settings=None) -> List[str]:
    """Verify that directories referenced in config exist (or can be created).

    Returns a list of problem descriptions (empty list means all good).
    """
    if settings is None:
        try:
            from app.core.config import settings  # type: ignore[import-untyped]
        except Exception as e:
            return [f"无法加载配置: {e}"]

    problems: List[str] = []
    dir_attrs = [
        ("CACHE_DIR", "缓存"),
        ("UPLOAD_DIR", "上传文件"),
        ("LOG_DIR", "日志"),
        ("EXPORT_DIR", "导出"),
    ]

    for attr, label in dir_attrs:
        path = getattr(settings, attr, None)
        if not path:
            continue
        if not os.path.isabs(path):
            problems.append(f"{label}目录 ({attr}) 不是绝对路径: {path}")
            continue
        try:
            os.makedirs(path, exist_ok=True)
        except OSError as e:
            problems.append(f"无法创建 {label}目录 ({attr}={path}): {e}")

    return problems


REQUIRED_ENV_VARS = ["SECRET_KEY"]
