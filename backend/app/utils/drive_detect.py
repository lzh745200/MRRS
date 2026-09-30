"""
可移动磁盘/可用备份目标检测工具

单机版场景: 用户需要把备份写到 U 盘/移动硬盘/共享目录, 防止本机硬盘故障导致数据丢失。
本模块跨平台检测可访问的存储位置, 供备份目标选择页使用。
"""
from __future__ import annotations

import os
import platform
import string
from typing import Dict, List

# 常见挂载点(非 Windows)
_LINUX_MOUNT_BASES = ["/media", "/mnt", "/run/media", "/Volumes"]


def _drive_type_windows(drive_letter: str) -> str:
    """Windows 盘符类型: removable/fixed/network/unknown"""
    try:
        import ctypes

        DRIVE_REMOVABLE = 2
        DRIVE_FIXED = 3
        DRIVE_REMOTE = 4
        drive = drive_letter + ":\\"
        t = ctypes.windll.kernel32.GetDriveTypeW(drive)
        if t == DRIVE_REMOVABLE:
            return "removable"
        if t == DRIVE_FIXED:
            return "fixed"
        if t == DRIVE_REMOTE:
            return "network"
        return "unknown"
    except Exception:  # pragma: no cover - 非 Windows 或 ctypes 不可用
        return "unknown"


def _list_linux_mounts() -> List[Dict[str, str]]:
    """Linux/macOS 常见挂载点枚举"""
    results: List[Dict[str, str]] = []
    for base in _LINUX_MOUNT_BASES:
        if not os.path.isdir(base):
            continue
        try:
            for entry in os.listdir(base):
                full = os.path.join(base, entry)
                if os.path.isdir(full) and os.access(full, os.W_OK):
                    # list_backup_dirs 的契约是每项含 path/type/available；
                    # 非 Windows 分支此前漏掉 available，消费方取键即 KeyError
                    # （深审 #84）。此处循环已用 os.access 验证可写。
                    results.append({"path": full, "type": "removable", "available": True})
        except OSError:  # pragma: no cover
            continue
    return results


def list_backup_dirs() -> List[Dict[str, str]]:
    """
    枚举可用的备份目标目录。

    Returns:
        [{path, type, available}] type: removable(可移动)/fixed(固定盘)/network(网络)/other
        available: 目录当前是否存在且可写
    """
    results: List[Dict[str, str]] = []
    system = platform.system()

    if system == "Windows":
        for letter in string.ascii_uppercase:
            root = f"{letter}:\\"
            if not os.path.exists(root):
                continue
            dtype = _drive_type_windows(letter)
            # 跳过光驱等无写入意义的盘符; 未知类型仍列出供用户选择
            results.append(
                {
                    "path": root,
                    "type": dtype,
                    "available": os.access(root, os.W_OK),
                }
            )
    else:
        results.extend(_list_linux_mounts())
        # 当前目录所在盘也作为候选
        try:
            cwd = os.path.abspath(os.getcwd())
            results.append(
                {
                    "path": os.path.dirname(cwd) if os.path.dirname(cwd) else cwd,
                    "type": "fixed",
                    "available": os.access(os.path.dirname(cwd) or cwd, os.W_OK),
                }
            )
        except OSError:  # pragma: no cover
            pass

    # 去重
    seen = set()
    deduped = []
    for r in results:
        key = os.path.normcase(r["path"])
        if key not in seen:
            seen.add(key)
            deduped.append(r)
    return deduped


def ensure_target_dir(path: str) -> bool:
    """确保目标目录存在并可写; 不存在则创建"""
    if not path:
        return False
    try:
        os.makedirs(path, exist_ok=True)
        return os.path.isdir(path) and os.access(path, os.W_OK)
    except OSError:  # pragma: no cover
        return False
