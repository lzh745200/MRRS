"""
运行环境检查路由

从 main.py 迁移至此，保持路径不变：GET /api/v1/env/check

**R15（2026-09-14 修复）**：依赖清单与校验口径统一到
`app/core/required_packages.py`（单一事实源）。此前本文件自持一份包含
`fpdf2`（应用不 import、requirements.txt 里也没有）与 `pytest`（仅开发期）的清单，
并用 `importlib.metadata.distributions()` 枚举判定，导致：

- 任何环境下都恒报"缺失依赖"（幻影依赖，用户照提示也装不出来）；
- PyInstaller 冻结运行时里 bundled 包元数据不全 —— 能 import 的包同样被判缺失，
  安装包首启即误报"缺失 7 个依赖"。

现在：必需 / 可选 / 仅开发 三级分开，按 **import 名** 校验（find_spec，冻结运行时也可靠），
冻结运行时不再给出不适用的 `pip install` 建议。
"""

import os
import platform
import sys
from typing import Dict

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.required_packages import (
    DEV_ONLY_PACKAGES,
    OPTIONAL_RUNTIME_PACKAGES,
    REQUIRED_RUNTIME_PACKAGES,
    describe,
    fix_command,
    is_frozen,
    missing_dev,
    missing_optional,
    missing_runtime,
)
from app.core.response import success_response
from app.core.security import get_current_user

router = APIRouter(prefix="/env", tags=["运行环境"])

# 兼容别名（既有引用与测试）：运行时必需依赖的分发名清单
REQUIRED_PACKAGES = [dep.distribution for dep in REQUIRED_RUNTIME_PACKAGES]


def _get_installed_packages() -> dict:
    """使用 importlib.metadata 获取已安装的包及版本（附带诊断信息，不用于判定缺失）"""
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
        "frozen": is_frozen(),
    }


@router.get("/check", summary="检查运行环境")
def check_env(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """检查系统运行环境

    依赖分三级返回，**只有 `missing_packages`（运行时必需）才算故障**：

    Returns:
        Dict: 环境检查结果
            - system: 系统信息字典（含 frozen 标记）
            - packages: 登记的依赖 → 版本（未安装为空串）
            - dependencies: 逐条明细（分发名/import 名/用途/是否安装/版本）
            - missing_packages: 运行时必需但缺失（红色告警）
            - optional_missing: 运行时可选但缺失（功能降级提示）
            - dev_missing: 仅开发期依赖缺失（开发环境诊断）
            - runtime_ok: 运行时依赖是否齐备
            - fix_command: 修复命令（缺失时给出；冻结运行时为 None，自包含运行时无 pip）
    """
    runtime_missing = missing_runtime()
    optional_missing = missing_optional()
    dev_missing = missing_dev()

    items = (
        describe(REQUIRED_RUNTIME_PACKAGES)
        + describe(OPTIONAL_RUNTIME_PACKAGES)
        + describe(DEV_ONLY_PACKAGES)
    )

    result = {
        "system": _collect_system_info(),
        "packages": {item["distribution"]: (item["version"] or "") for item in items},
        "dependencies": items,
        "missing_packages": [dep.distribution for dep in runtime_missing],
        "optional_missing": [dep.distribution for dep in optional_missing],
        "dev_missing": [dep.distribution for dep in dev_missing],
        "runtime_ok": not runtime_missing,
    }
    command = fix_command(list(runtime_missing) + list(optional_missing) + list(dev_missing))
    if command:
        result["fix_command"] = command

    return success_response(data=result)
