#!/usr/bin/env python3
"""
帮扶管理系统 - Nuitka ARM64 编译脚本

使用 Nuitka 将 Python 后端编译为 ARM64 原生二进制文件。
相比 PyInstaller，Nuitka 编译的二进制性能更好、依赖更少。

使用方法：
    python build_nuitka_arm64.py

前置条件：
    pip install nuitka ordered-set zstandard
"""

import os
import platform
import subprocess
import sys
from pathlib import Path


def check_environment():
    """检查编译环境"""
    print("=" * 60)
    print("  帮扶管理系统 - Nuitka ARM64 编译")
    print("=" * 60)
    print()

    # Python 版本
    py_version = sys.version_info
    print(f"  Python: {py_version.major}.{py_version.minor}.{py_version.micro}")
    if py_version < (3, 9):
        print("  错误: 需要 Python 3.9+")
        sys.exit(1)

    # Nuitka
    try:
        import nuitka  # noqa: F401
        print("  Nuitka: 已安装 ✓")
    except ImportError:
        print("  错误: Nuitka 未安装")
        print("  请执行: pip install nuitka ordered-set zstandard")
        sys.exit(1)

    # 架构
    arch = platform.machine()
    print(f"  架构: {arch}")
    if arch != "aarch64":
        print(f"  警告: 当前架构为 {arch}，非 aarch64。")
        print("  生成的二进制可能不兼容 ARM64 目标平台。")

    # 操作系统
    os_name = platform.system()
    print(f"  操作系统: {os_name}")
    if os_name != "Linux":
        print("  警告: 非 Linux 环境，编译的 ARM64 二进制需要在 Linux 上测试。")

    print()
    print("  环境检查通过 ✓")
    print()


def build_backend():
    """使用 Nuitka 编译后端"""
    print("[1/4] 编译后端 (Nuitka)...")

    backend_dir = Path("backend")
    if not backend_dir.exists():
        print("  错误: backend/ 目录不存在")
        sys.exit(1)

    # Nuitka 编译参数
    nuitka_args = [
        sys.executable, "-m", "nuitka",
        # 输出配置
        "--standalone",                    # 独立模式（包含所有依赖）
        "--onefile",                       # 单文件模式（可选，生成单个可执行文件）
        "--output-filename=bumofu-server",
        "--output-dir=dist/nuitka",

        # 入口点
        "backend/start.py",

        # 包含的数据文件
        f"--include-data-dir={backend_dir}/app=app",
        f"--include-data-dir={backend_dir}/data=data",

        # 隐式导入（Nuitka 可能无法自动检测到的模块）
        "--enable-plugin=anti-bloat",
        "--nofollow-import-to=tkinter",
        "--nofollow-import-to=matplotlib.backends",
        "--nofollow-import-to=IPython",
        "--nofollow-import-to=scipy",

        # 隐式导入 FastAPI 及其依赖
        "--include-module=fastapi",
        "--include-module=uvicorn",
        "--include-module=uvicorn.logging",
        "--include-module=uvicorn.loops",
        "--include-module=uvicorn.loops.auto",
        "--include-module=uvicorn.protocols",
        "--include-module=uvicorn.protocols.http",
        "--include-module=uvicorn.protocols.http.auto",
        "--include-module=uvicorn.protocols.websockets",
        "--include-module=uvicorn.protocols.websockets.auto",
        "--include-module=uvicorn.lifespan",
        "--include-module=uvicorn.lifespan.on",
        "--include-module=uvicorn.lifespan.off",

        # SQLAlchemy 隐式导入
        "--include-module=sqlalchemy",
        "--include-module=sqlalchemy.dialects.sqlite",
        "--include-module=sqlalchemy.ext.declarative",

        # 数据处理库（如使用 polars 替代 pandas）
        "--include-module=numpy",
        # "--include-module=polars",  # 如果使用 polars

        # 其他依赖
        "--include-module=bcrypt",
        "--include-module=pydantic",
        "--include-module=starlette",
        "--include-module=anyio",
        "--include-module=anyio._backends",
        "--include-module=anyio._backends._asyncio",
        "--include-module=httptools",
        "--include-module=websockets",
        "--include-module=dotenv",
        "--include-module=passlib",
        "--include-module=passlib.handlers",
        "--include-module=passlib.handlers.bcrypt",
        "--include-module=jose",
        "--include-module=_diskcache",

        # 优化选项
        "--lto=yes",                       # 链接时优化
        "--assume-yes-for-downloads",      # 自动下载依赖

        # 移除调试信息（生产构建）
        "--remove-output",
        "--no-pyi-file",
    ]

    print(f"  执行: {' '.join(nuitka_args[:10])} ...")
    print()

    result = subprocess.run(nuitka_args)

    if result.returncode != 0:
        print("  错误: Nuitka 编译失败")
        sys.exit(1)

    print("  后端编译成功 ✓")
    print()


def copy_resources():
    """复制资源文件到输出目录"""
    print("[2/4] 复制资源文件...")

    output_dir = Path("dist/nuitka")
    if not output_dir.exists():
        print("  错误: 输出目录不存在")
        sys.exit(1)

    # GeoJSON 数据
    geojson_src = Path("backend/data/guizhou_regions.geojson")
    if geojson_src.exists():
        geojson_dst = output_dir / "data"
        geojson_dst.mkdir(exist_ok=True)
        subprocess.run(["cp", str(geojson_src), str(geojson_dst)])
        print(f"  复制: {geojson_src} → {geojson_dst}")

    print("  资源复制完成 ✓")
    print()


def build_frontend():
    """构建前端"""
    print("[3/4] 构建前端 (Vite)...")

    frontend_dir = Path("frontend")
    if not frontend_dir.exists():
        print("  警告: frontend/ 目录不存在，跳过前端构建")
        return

    result = subprocess.run(
        ["npm", "run", "build"],
        cwd=frontend_dir,
    )

    if result.returncode != 0:
        print("  警告: 前端构建失败")
    else:
        print("  前端构建成功 ✓")

    print()


def package_app():
    """打包应用"""
    print("[4/4] 打包应用...")

    output_dir = Path("dist/nuitka")
    version = "1.10.0"
    arch = platform.machine()

    # 创建压缩包
    archive_name = f"bumofu-assistance-{version}-{arch}.tar.gz"
    subprocess.run([
        "tar", "-czf", str(Path("dist") / archive_name),
        "-C", str(output_dir),
        ".",
    ])

    print(f"  生成: dist/{archive_name}")
    print()
    print("=" * 60)
    print("  编译完成!")
    print("=" * 60)
    print()
    print(f"  输出文件: dist/{archive_name}")
    print()
    print("  部署方法:")
    print(f"    tar -xzf dist/{archive_name} -C ~/.bumofu/")
    print("    ~/.bumofu/bumofu-server")
    print()


if __name__ == "__main__":
    check_environment()
    build_backend()
    copy_resources()
    build_frontend()
    package_app()
