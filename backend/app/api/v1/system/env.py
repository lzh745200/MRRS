"""
运行环境检查路由

从 main.py 迁移至此，保持路径不变：GET /api/v1/env/check
"""

import os
import platform
import sys
from typing import Dict

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user

router = APIRouter(prefix="/env", tags=["运行环境"])

REQUIRED_PACKAGES = [
    "fastapi",
    "uvicorn",
    "pandas",
    "openpyxl",
    "fpdf2",
    "sqlalchemy",
    "pytest",
]


def _get_installed_packages() -> dict:
    """使用 importlib.metadata 获取已安装的包及版本"""
    from importlib.metadata import distributions

    return {dist.metadata["Name"].lower(): dist.version for dist in distributions()}


def _collect_system_info() -> Dict[str, Dict[str, str] | str]:
    """收集系统信息

    收集当前系统的Python版本、平台信息和相关环境变量。

    Returns:
        Dict: 包含系统信息的字典
            - python_version: Python版本信息
            - platform: 系统平台信息
            - os_environ: 过滤后的环境变量
    """
    return {
        "python_version": sys.version,
        "platform": platform.platform(),
        "env_mode": os.environ.get("ENV", "production"),
    }


@router.get("/check", summary="检查运行环境")
def check_env(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """检查系统运行环境

    检查当前系统的Python环境、已安装的包和缺失的依赖包。

    Returns:
        Dict: 环境检查结果
            - system: 系统信息字典
            - packages: 已安装的包及其版本
            - missing_packages: 缺失的必需包列表
            - fix_command: 修复命令（如果有缺失包）
    """
    installed = _get_installed_packages()
    missing = [pkg for pkg in REQUIRED_PACKAGES if pkg not in installed]

    result = {
        "system": _collect_system_info(),
        "packages": installed,
        "missing_packages": missing,
    }
    if missing:
        result["fix_command"] = f"pip install {' '.join(missing)}"

    return result
