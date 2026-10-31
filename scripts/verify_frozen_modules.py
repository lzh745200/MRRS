#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""冻结后端「模块完整性」门禁。

背景：2026-10-31 v1.18.29 ARM64 安装包可正常安装，但后端一启动就
`ModuleNotFoundError: No module named 'difflib'`。根因是
`backend_linux_arm64_standalone.spec` 把 `difflib` 放进了 excludes，
而 PyInstaller 仍然返回退出码 0 —— 打包成功 ≠ 产物可运行。

本脚本直接读取 onedir 产物的 CArchive/PYZ 模块表，断言关键模块存在。
它不执行后端，因此可在 x64 runner 上检查 ARM64 产物，也不会受
windowed/console 或数据库初始化影响。

用法：
    python scripts/verify_frozen_modules.py --backend-dir backend/dist/assistance-backend
"""

from __future__ import annotations

import argparse
import os
import sys
import tempfile
from pathlib import Path

# 冻结后端启动链最小闭环：入口、路由聚合、数据质量路由、数据清洗服务。
# `difflib` 是 data_cleaning_service 的顶层依赖，必须显式守住。
REQUIRED_MODULES = (
    "difflib",
    "app.main",
    "app.api.v1",
    "app.api.v1.data_quality",
    "app.services.data_cleaning_service",
)


def _find_executable(backend_dir: Path) -> Path:
    candidates = [
        backend_dir / "assistance-backend.exe",
        backend_dir / "assistance-backend",
        backend_dir / "assistance-management-backend.exe",
        backend_dir / "assistance-management-backend",
    ]
    for path in candidates:
        if path.is_file():
            return path
    raise SystemExit(
        f"未找到后端主程序；目录内容：{[p.name for p in backend_dir.iterdir()][:20]}"
    )


def _pyz_modules(exe: Path) -> set[str]:
    try:
        from PyInstaller.archive.readers import CArchiveReader, ZlibArchiveReader
    except ImportError as exc:  # pragma: no cover - CI 构建环境必然安装 PyInstaller
        raise SystemExit(f"无法导入 PyInstaller 归档读取器：{exc}")

    archive = CArchiveReader(str(exe))
    pyz_names = [name for name in archive.toc if "PYZ" in name]
    if not pyz_names:
        raise SystemExit(f"CArchive 中未找到 PYZ：{exe}")

    payload = archive.extract(pyz_names[0])
    fd, tmp_name = tempfile.mkstemp(suffix=".pyz")
    os.close(fd)
    try:
        Path(tmp_name).write_bytes(payload)
        return set(ZlibArchiveReader(tmp_name).toc)
    finally:
        try:
            os.remove(tmp_name)
        except OSError:
            pass


def _iter_app_modules(app_dir: Path) -> list[str]:
    """枚举源码中的 app.* 模块名，确保打包没有漏掉任何业务模块。"""
    modules: list[str] = []
    for path in app_dir.rglob("*.py"):
        rel = path.relative_to(app_dir).with_suffix("")
        parts = list(rel.parts)
        if parts and parts[-1] == "__init__":
            parts.pop()
        if not parts or any(not part.isidentifier() for part in parts):
            continue
        modules.append(".".join(["app", *parts]))
    return modules


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--backend-dir", required=True, help="onedir 后端产物目录")
    parser.add_argument(
        "--app-source",
        default="backend/app",
        help="后端 app 源码目录（默认 backend/app；用于校验全部 app.* 模块均在 PYZ 中）",
    )
    args = parser.parse_args()

    backend_dir = Path(args.backend_dir).resolve()
    if not backend_dir.is_dir():
        print(f"[FAIL] 后端目录不存在：{backend_dir}", file=sys.stderr)
        return 1

    exe = _find_executable(backend_dir)
    modules = _pyz_modules(exe)
    required = list(REQUIRED_MODULES)
    app_source = Path(args.app_source)
    if app_source.is_dir():
        app_modules = _iter_app_modules(app_source)
        required.extend(name for name in app_modules if name not in required)
    else:
        print(f"[WARN] 未找到 app 源码目录，仅校验关键模块：{app_source}")

    missing = [name for name in required if name not in modules]

    print(f"[INFO] 后端主程序：{exe.name}")
    print(f"[INFO] PYZ 模块数：{len(modules)}")
    print(f"[INFO] 校验模块数：{len(required)}")
    if missing:
        print("[FAIL] 冻结产物缺少关键模块：", file=sys.stderr)
        for name in missing:
            print(f"  - {name}", file=sys.stderr)
        print(
            "请检查对应 spec 的 excludes / hiddenimports；这类缺失会导致装机后启动即崩。",
            file=sys.stderr,
        )
        return 1

    for name in REQUIRED_MODULES:
        print(f"[OK] {name}")
    print(f"[OK] app.* 模块全部收录（{len(required) - len(REQUIRED_MODULES)} 个）")
    print("FROZEN_MODULE_CHECK_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
