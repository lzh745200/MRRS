"""磁盘剩余容量探测（W12-T045 磁盘空间感知）

提供 get_disk_free_bytes(path) 统一封装：
- 优先 psutil.disk_usage（跨平台）
- psutil 不可用时回退 os.statvfs（Linux ARM64 兜底，不炸）
- Windows 无 statvfs 时回退 shutil.disk_usage

备份创建 / upload-restore 前调用本模块做容量预检，目标盘 < 阈值拒绝。
"""

from __future__ import annotations

import logging
import os
import shutil

logger = logging.getLogger(__name__)

# 手动备份 / upload-restore 最低剩余空间阈值（500MB）
MIN_FREE_BYTES = 500 * 1024 * 1024


def get_disk_free_bytes(path: str) -> int:
    """返回 path 所在文件系统剩余可用字节数

    容错顺序：psutil.disk_usage → os.statvfs（Linux/Unix）→ shutil.disk_usage
    全部失败返回 -1（调用方按"未知"处理，不强制拒绝）。
    """
    # 1. psutil（最稳，跨平台）
    try:
        import psutil

        return int(psutil.disk_usage(path).free)
    except Exception as e:  # noqa: BLE001 - 任意异常都降级
        logger.debug("psutil.disk_usage 失败，降级 statvfs/shutil: %s", e)

    # 2. Linux/Unix statvfs
    if hasattr(os, "statvfs"):
        try:
            st = os.statvfs(path)
            return int(st.f_bavail * st.f_frsize)
        except Exception as e:  # noqa: BLE001
            logger.debug("os.statvfs 失败，降级 shutil: %s", e)

    # 3. shutil.disk_usage（Windows/Linux 通用，Python 3.3+）
    try:
        return int(shutil.disk_usage(path).free)
    except Exception as e:  # noqa: BLE001
        logger.warning("磁盘容量探测失败 path=%s: %s", path, e)
        return -1


def has_enough_free_space(path: str, required_bytes: int = MIN_FREE_BYTES) -> tuple[bool, int]:
    """检查 path 所在盘剩余空间是否充足

    Returns:
        (ok, free_bytes) —— ok=False 时 free_bytes 为实际剩余（含 -1 未知）
    """
    free = get_disk_free_bytes(path)
    if free < 0:
        # 未知容量：保守放行（不阻断备份），由上层监控兜底
        return True, free
    return free >= required_bytes, free
