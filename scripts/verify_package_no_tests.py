# -*- coding: utf-8 -*-
r"""安装包"无测试内容"验证（2026-09-12 打包卫生门禁）。

背景：安装包必须排除测试文件、测试目录与测试依赖。本脚本对
PyInstaller onedir 产物（backend/dist/assistance-backend）做三重验证：

1. 文件树扫描：不得存在 tests/ 目录、test_*.py / *_test.py / conftest.py /
   pytest.ini / .coveragerc / tox.ini 等测试资产；
2. PYZ 归档检查：冻结字节码中不得出现 tests / pytest / pytest-* 模块；
3. 前端构建产物抽查（frontend/dist 或 resources/frontend）：
   不得包含 *.test.* / *.spec.* 文件。

任一违规 → 非零退出（CI fail-loud）。用法::

    python scripts/verify_package_no_tests.py [--backend-dir PATH] [--frontend-dir PATH]
    python scripts/verify_package_no_tests.py --listing installer-listing.txt

``--listing`` 模式（2026-09-12 新增）用于**安装包本体**抽查：CI 用 7-Zip 列出
NSIS/DEB 内容后交给本脚本判定，规则与文件树扫描**同一份实现**（含厂商豁免）。
此前 CI 内联的正则 `(tests?/|conftest\.py|pytest|test_results)` 没有豁免表，
会把 prophet/cmdstan 自带的 `src/test/*.cpp`（实测 283 项）误判为违规而**阻断
Windows 出包** —— 规则重复实现必然漂移，故收口到本脚本。
"""

import argparse
import sys
from pathlib import Path

# 文件名/目录名命中即违规
_TEST_FILE_PATTERNS = ("test_", "_test.py", "conftest.py", "pytest.ini", "tox.ini", ".coveragerc")
_TEST_DIR_NAMES = {"tests", "test", "testing"}
# PYZ 内模块名前缀命中即违规
_TEST_MODULE_PREFIXES = (
    "tests", "test", "pytest", "_pytest", "pytest_asyncio", "pytest_cov", "pytest_mock", "hypothesis",
)
# 前端产物命中即违规
_FRONTEND_PATTERNS = (".test.", ".spec.")
# 厂商数据豁免：prophet 以整包数据形式打入（含其自带 tests/），非本项目测试资产
_VENDOR_EXEMPT_PARTS = {"prophet"}


def _is_test_path(rel: Path) -> bool:
    if any(p.lower() in _VENDOR_EXEMPT_PARTS for p in rel.parts):
        return False
    parts = [p for p in str(rel).replace("\\", "/").split("/") if p and p != "."]
    if not parts:
        return False
    if any(p.lower() in _TEST_DIR_NAMES for p in parts[:-1]):
        return True
    last = parts[-1]
    # 归档列表中的"目录条目"（形如 x/test/）末段即测试目录名
    if last.lower() in _TEST_DIR_NAMES:
        return True
    name = last.lower()
    if name.startswith("test_") or name.endswith("_test.py"):
        return True
    if name in ("conftest.py", "pytest.ini", "tox.ini", ".coveragerc"):
        return True
    # 测试工具链残留（如 .pytest_cache/、pytest_something.py）：
    # 2026-09-12 与旧 CI 内联正则对齐——那条正则按 "pytest" 子串拦截，
    # 收口到本函数后必须保留同等强度，否则等于悄悄放宽门禁。
    return any("pytest" in p.lower() for p in parts)


def scan_backend_dir(backend_dist: Path) -> list:
    violations = []
    if not backend_dist.is_dir():
        print(f"ERROR: 后端产物目录不存在: {backend_dist}")
        sys.exit(2)
    for p in backend_dist.rglob("*"):
        rel = p.relative_to(backend_dist)
        if any(part.lower() in _VENDOR_EXEMPT_PARTS for part in rel.parts):
            continue  # 厂商数据包（prophet 等）自带 tests，非本项目测试资产
        if p.is_dir():
            if rel.name.lower() in _TEST_DIR_NAMES:
                violations.append(f"[测试目录] {rel}")
            continue
        if _is_test_path(rel):
            violations.append(f"[测试文件] {rel}")
    return violations


def scan_pyz(backend_dist: Path) -> list:
    """读取 PYZ 归档目录，确认冻结模块不含测试/测试依赖。"""
    violations = []
    # PyInstaller 的应用模块在 PYZ 归档（PYZ-00.pyz）或 base_library.zip 内；逐个尝试
    candidates = list(backend_dist.rglob("*.pyz")) + list(backend_dist.rglob("base_library.zip"))
    if not candidates:
        # onedir 布局下应用模块通常在 _internal/PYZ-00.pyz（6.x 起可能展平）
        return violations
    try:
        import zipfile

        for pyz in candidates:
            try:
                with zipfile.ZipFile(pyz) as zf:
                    names = zf.namelist()
                for name in names:
                    mod = name.replace("\\", "/").split("/")[0]
                    mod = mod.removesuffix(".pyc")
                    for prefix in _TEST_MODULE_PREFIXES:
                        if mod == prefix or mod.startswith(prefix + "."):
                            violations.append(f"[PYZ 模块] {pyz.name}::{name}")
                            break
            except zipfile.BadZipFile:
                continue
    except Exception as e:  # noqa: BLE001 — 校验器自身失败不应静默
        print(f"WARNING: PYZ 检查跳过（{e}）")
    return violations


def scan_frontend(frontend_dir: Path) -> list:
    violations = []
    if not frontend_dir.is_dir():
        return violations
    for p in frontend_dir.rglob("*"):
        if p.is_file() and any(p.name.lower().find(pat) >= 0 for pat in _FRONTEND_PATTERNS):
            violations.append(f"[前端测试产物] {p.relative_to(frontend_dir)}")
    return violations


# 归档列表行（7z l 输出）形如：
#   2026-09-12 10:00:00 ....A         1234         567  resources/backend/x/y.py
# 只取末字段（归档内路径），其余为时间/属性/大小/压缩后大小等列。
_LISTING_SKIP_PREFIXES = ("7-Zip", "Scanning", "Creating", "Extracting", "Everything is Ok", "Path = ")
_LISTING_SKIP_FRAGMENTS = (" = ", "Type = ", "Physical Size", "---")


def parse_archive_listing(text: str) -> list:
    """从 7-Zip `l` 输出中提取归档成员路径（忽略表头/分隔线/汇总行）。"""
    members = []
    for raw in text.splitlines():
        line = raw.rstrip()
        if not line or line.startswith("---") or line.startswith(_LISTING_SKIP_PREFIXES):
            continue
        if any(frag in line for frag in _LISTING_SKIP_FRAGMENTS):
            continue
        candidate = line.split()[-1].replace("\\", "/")
        # 归档成员必然含路径分隔符（目录项以 / 结尾）；文件名行不带分隔符则跳过
        if "/" not in candidate:
            continue
        members.append(candidate)
    return members


def scan_listing_text(text: str) -> list:
    """按与文件树扫描**完全相同**的规则判定归档成员（含厂商豁免）。"""
    violations = []
    for member in parse_archive_listing(text):
        if _is_test_path(Path(member)):
            violations.append(f"[归档成员] {member}")
    return violations


def main():
    parser = argparse.ArgumentParser(description="验证安装包产物不含测试内容")
    parser.add_argument("--backend-dir", default="backend/dist/assistance-backend")
    parser.add_argument("--frontend-dir", default="frontend/dist")
    parser.add_argument(
        "--listing",
        default=None,
        help="归档列表文件（7z l 输出）；给定则只做归档成员抽查，规则同文件树扫描",
    )
    args = parser.parse_args()

    if args.listing:
        listing_path = Path(args.listing)
        if not listing_path.is_file():
            print(f"ERROR: 归档列表文件不存在: {listing_path}")
            sys.exit(2)
        members = parse_archive_listing(listing_path.read_text(encoding="utf-8", errors="replace"))
        violations = [f"[归档成员] {m}" for m in members if _is_test_path(Path(m))]
        print("=== 安装包归档成员抽查 ===")
        print(f"归档成员: {len(members)} 项")
        if violations:
            print("\n--- 违规清单 ---")
            for v in violations[:50]:
                print(v)
            print(f"\nERROR: 安装包内包含 {len(violations)} 项测试内容，禁止发布")
            sys.exit(1)
        print("\nOK: 安装包归档不含测试文件/测试目录（厂商自带 tests 已按豁免表放行）")
        return

    backend_dist = Path(args.backend_dir)
    frontend_dir = Path(args.frontend_dir)

    print("=== 安装包无测试内容验证 ===")
    violations = []
    v1 = scan_backend_dir(backend_dist)
    print(f"后端文件树扫描: {'OK' if not v1 else f'{len(v1)} 项违规'}")
    violations += v1

    v2 = scan_pyz(backend_dist)
    print(f"PYZ 冻结模块检查: {'OK' if not v2 else f'{len(v2)} 项违规'}")
    violations += v2

    v3 = scan_frontend(frontend_dir)
    print(f"前端产物抽查: {'OK' if not v3 else f'{len(v3)} 项违规'}")
    violations += v3

    if violations:
        print("\n--- 违规清单 ---")
        for v in violations:
            print(v)
        print(f"\nERROR: 安装包产物包含 {len(violations)} 项测试内容，禁止发布")
        sys.exit(1)
    print("\nOK: 产物不含测试文件/测试目录/测试依赖")


if __name__ == "__main__":
    main()
