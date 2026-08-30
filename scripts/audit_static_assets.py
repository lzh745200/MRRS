#!/usr/bin/env python3
"""
静态资源"断链"审计脚本 - 验证所有引用的文件是否存在。

功能：
1. 解析 index.html，提取所有 <script> 和 <link> 标签的 src/href
2. 递归扫描所有 JS 文件，通过正则提取动态 import() 的 chunk 文件名
3. 对比提取出的所有资源路径与实际存在的文件
4. 输出详细审计报告，如有缺失以 exit code 1 退出

使用方法：
    python scripts/audit_static_assets.py [--dir resources/frontend] [--verbose]
    python scripts/audit_static_assets.py --verify-manifest resources/frontend-manifest.sha256
"""

from __future__ import annotations

import argparse
import hashlib
import os
import re
import sys

# ── Windows GBK 终端编码兼容 ──
# 在中文 Windows CMD 中，默认编码为 GBK，无法输出 emoji 等 Unicode 字符。
# 通过设置环境变量和环境编码确保 Unicode 输出正常。
if sys.platform == "win32":
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        if stream and hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass
from pathlib import Path
from typing import Set


# ---------------------------------------------------------------
# 工具函数
# ---------------------------------------------------------------

def _rel(path: str, base: str) -> str:
    """将绝对路径转为相对于 base 的路径，用于友好输出。"""
    try:
        return os.path.relpath(path, base)
    except ValueError:
        return path


def _extract_static_refs_from_html(html_path: str, frontend_dir: str) -> Set[str]:
    """从 index.html 中提取所有静态资源引用路径。

    提取 <script src="...">, <link href="...">，并去掉前导 '/' 以便
    与磁盘上的相对路径对比（index.html 中的路径如 /assets/js/foo.js
    对应于磁盘上 frontend_dir/assets/js/foo.js）。
    """
    refs: Set[str] = set()
    try:
        with open(html_path, "r", encoding="utf-8") as f:
            content = f.read()
    except (OSError, UnicodeDecodeError) as e:
        print(f"[ERROR] 无法读取 {html_path}: {e}")
        return refs

    # 匹配 <script src="..."> 和 <link href="...">
    patterns = [
        r'<script[^>]+src="([^"]+)"',
        r'<link[^>]+href="([^"]+)"',
        # modulepreload 的 href
        r'<link[^>]+rel="modulepreload"[^>]+href="([^"]+)"',
    ]
    for pattern in patterns:
        for match in re.finditer(pattern, content, re.IGNORECASE):
            url = match.group(1)
            # 跳过外部 URL（http/https）
            if url.startswith(("http://", "https://", "data:", "blob:")):
                continue
            # 跳过 Vite 默认资源（非关键，生产环境使用 favicon.ico）
            if url.endswith("vite.svg"):
                continue
            # 去掉前导 /
            if url.startswith("/"):
                url = url[1:]
            refs.add(url)
    return refs


def _extract_dynamic_imports_from_js(js_dir: str, frontend_dir: str) -> Set[str]:
    """递归扫描 JS 文件，提取动态 import() 引用的 chunk 路径。

    Vite 动态导入格式：
      - import("./chunk-name-hash.js")
      - import("/assets/js/chunk-name-hash.js")
      - import(/* webpackChunkName: "name" */ './module')

    提取后转换为相对于 frontend_dir 的路径用于比对。
    """
    refs: Set[str] = set()
    # 匹配 import("...") 或 import('...')
    import_re = re.compile(
        r"""import\s*\(\s*["']([^"']+)["']\s*\)""",
    )

    js_dir_path = Path(js_dir)
    if not js_dir_path.is_dir():
        return refs

    js_files = list(js_dir_path.rglob("*.js"))
    total = len(js_files)
    for i, js_file in enumerate(js_files):
        # 每 200 个文件打印一次进度（stderr，避免污染 stdout 审计报告）
        if i > 0 and i % 200 == 0:
            print(f"    扫描进度: {i}/{total}", file=sys.stderr)
        try:
            # 只阅读前 200KB（与原始窗口大小一致），动态 import 通常在文件头部附近；
            # f.read(N) 在文件小于 N 时安全返回全部内容，无需事先 stat()
            with open(js_file, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read(200 * 1024)
        except (OSError, UnicodeDecodeError):
            continue

        for match in import_re.finditer(content):
            import_path = match.group(1)
            # 跳过外部 URL 和 CSS 文件
            if import_path.startswith(("http://", "https://", "data:", "blob:")):
                continue
            # 跳过非 JS 资源（CSS 通过 link 加载即可）
            if import_path.endswith(".css"):
                continue

            # 去掉前导 / 使其成为相对路径
            if import_path.startswith("/"):
                import_path = import_path[1:]

            # 跳过 node_modules 引用
            if "node_modules" in import_path:
                continue

            # 规范化路径：如果是相对路径（以 ./ 或 ../ 开头），
            # 需要相对于当前 JS 文件所在目录计算绝对路径，再转为相对 frontend_dir
            if import_path.startswith("./") or import_path.startswith("../"):
                try:
                    js_file_rel = js_file.relative_to(frontend_dir)
                    js_file_dir = str(Path(js_file_rel).parent)
                    resolved = os.path.normpath(
                        os.path.join(js_file_dir, import_path)
                    ).replace("\\", "/")
                    refs.add(resolved)
                except ValueError:
                    # 无法计算相对路径，跳过
                    pass
            else:
                refs.add(import_path)

    return refs


def _get_actual_files(frontend_dir: str) -> Set[str]:
    """获取 frontend_dir 下所有实际文件的相对路径集合。

    排除目录和 .gz/.br 预压缩文件（浏览器请求的是原始文件）。
    """
    actual: Set[str] = set()
    frontend_path = Path(frontend_dir)
    if not frontend_path.is_dir():
        return actual

    for entry in frontend_path.rglob("*"):
        if entry.is_file():
            rel = str(entry.relative_to(frontend_dir)).replace("\\", "/")
            actual.add(rel)
    return actual


# ---------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------

def audit(frontend_dir: str, verbose: bool = False, quick: bool = False) -> int:
    """执行静态资源断链审计。

    Args:
        frontend_dir: 前端静态文件目录
        verbose: 详细输出
        quick: 快速模式 — 仅校验 index.html 直接引用，跳过 JS 动态 import 扫描

    Returns:
        0: 所有引用文件都存在
        1: 存在缺失文件
        2: 严重错误（如 index.html 不存在）
    """
    frontend_dir = os.path.abspath(frontend_dir)
    index_html = os.path.join(frontend_dir, "index.html")

    if not os.path.isfile(index_html):
        print(f"[FATAL] index.html 不存在: {index_html}")
        print("请确认 frontend_dir 路径正确或先执行 npm run build")
        return 2

    # Step 1: 从 index.html 提取引用
    print("=" * 60)
    print("静态资源断链审计")
    print("=" * 60)
    print(f"扫描目录: {frontend_dir}")
    print()

    print("[1/3] 从 index.html 提取静态资源引用...")
    html_refs = _extract_static_refs_from_html(index_html, frontend_dir)
    print(f"  提取到 {len(html_refs)} 个引用")
    if verbose:
        for ref in sorted(html_refs):
            print(f"    - {ref}")

    # Step 2: 从 JS 文件提取动态 import（快速模式下跳过）
    print()
    if quick:
        print("[2/3] 动态 import 扫描已跳过（快速模式）")
        js_refs: Set[str] = set()
    else:
        print("[2/3] 扫描 JS 文件中的动态 import() 引用...")
        assets_dir = os.path.join(frontend_dir, "assets")
        js_refs = _extract_dynamic_imports_from_js(assets_dir, frontend_dir)
        print(f"  提取到 {len(js_refs)} 个动态 import 引用")
        if verbose:
            for ref in sorted(js_refs):
                print(f"    - {ref}")

    # Step 3: 获取实际文件列表
    print()
    print("[3/3] 对比引用与实际文件...")
    actual_files = _get_actual_files(frontend_dir)
    print(f"  磁盘上实际存在 {len(actual_files)} 个文件")

    # 合并所有引用（index.html 中的直接引用 + JS 中的动态 import）
    all_refs = html_refs | js_refs

    # 对比：找出引用但不存在于磁盘的文件
    missing_files: list[str] = []
    for ref in sorted(all_refs):
        if ref not in actual_files:
            missing_files.append(ref)

    # 同时找出磁盘上存在但未被引用的文件（可能是过时产物）
    # 跳过 .gz .br 预压缩文件、index.html 自身、favicon.ico
    unreferenced_patterns = {".gz", ".br", ".map"}
    unreferenced_files: list[str] = []
    for f in sorted(actual_files):
        name = os.path.basename(f)
        if name == "index.html":
            continue
        # 跳过预压缩文件
        if any(f.endswith(ext) for ext in unreferenced_patterns):
            continue
        if f not in all_refs:
            unreferenced_files.append(f)

    # 输出报告
    print()
    print("=" * 60)
    print("审计报告")
    print("=" * 60)
    print(f"  index.html 引用数:    {len(html_refs)}")
    print(f"  动态 import 引用数:   {len(js_refs)}")
    print(f"  合并引用总数:         {len(all_refs)}")
    print(f"  磁盘实际文件数:       {len(actual_files)}")
    print(f"  缺失文件数:           {len(missing_files)}")
    print(f"  未引用文件数:         {len(unreferenced_files)}")
    print()

    if missing_files:
        print("-" * 60)
        print(f"❌ 缺失文件 ({len(missing_files)} 个) — 将导致 404 错误！")
        print("-" * 60)
        for f in missing_files:
            print(f"  ❌ {f}")
        print()
        print("建议：")
        print("  1. 重新构建前端: cd frontend && npm run build")
        print("  2. 运行同步脚本: scripts/build/sync-frontend-dist.bat")
        print("  3. 清除浏览器缓存后重试")

    if unreferenced_files and verbose:
        print()
        print("-" * 60)
        print(f"⚠️ 未引用文件 ({len(unreferenced_files)} 个) — 可能是过时产物")
        print("-" * 60)
        for f in unreferenced_files[:20]:  # 最多显示 20 个
            print(f"  ⚠️  {f}")
        if len(unreferenced_files) > 20:
            print(f"  ... 以及另外 {len(unreferenced_files) - 20} 个文件")
        print()
        print("建议：使用 sync-frontend-dist 脚本替代手动复制，它会先清理目标目录。")

    if not missing_files:
        print("✅ 所有引用文件均存在，静态资源完整性检查通过！")
        return 0
    else:
        return 1


def verify_manifest(frontend_dir: str, manifest_path: str) -> int:
    """W6-T5: 逐文件 SHA256 manifest 复核（与 sync-frontend-dist 落盘的 manifest 配套）。

    manifest 格式为 sha256sum -c 兼容行：`<64位小写hex>  <POSIX 相对路径>`。
    任一 文件缺失 / 哈希不匹配 / 目录多出文件 均以 exit 1 退出。
    """
    print("=" * 60)
    print("SHA256 Manifest 复核（W6-T5 完整性链）")
    print("=" * 60)
    print(f"目录: {frontend_dir}")
    print(f"manifest: {manifest_path}")

    if not os.path.isfile(manifest_path):
        print("[FATAL] manifest 文件不存在")
        return 2

    with open(manifest_path, encoding="utf-8") as f:
        entries: dict[str, str] = {}
        for line in f:
            line = line.rstrip("\n")
            if not line.strip():
                continue
            hash_part, _, path_part = line.partition("  ")
            if len(hash_part) != 64 or not path_part:
                print(f"[FATAL] manifest 行格式非法: {line[:80]}")
                return 2
            entries[path_part.replace("\\", "/")] = hash_part.lower()

    actual_files: set[str] = set()
    for root, _dirs, files in os.walk(frontend_dir):
        for name in files:
            full = os.path.join(root, name)
            actual_files.add(os.path.relpath(full, frontend_dir).replace("\\", "/"))

    errors: list[str] = []
    for rel, expected in entries.items():
        full = os.path.join(frontend_dir, *rel.split("/"))
        if not os.path.isfile(full):
            errors.append(f"缺失文件: {rel}")
            continue
        h = hashlib.sha256()
        with open(full, "rb") as fh:
            for chunk in iter(lambda: fh.read(1024 * 1024), b""):
                h.update(chunk)
        if h.hexdigest().lower() != expected:
            errors.append(f"哈希不匹配: {rel} (期望 {expected[:12]}…, 实际 {h.hexdigest()[:12]}…)")

    for rel in sorted(actual_files - set(entries)):
        errors.append(f"多出文件（不在 manifest 中）: {rel}")

    print(f"manifest 条目: {len(entries)}, 实际文件: {len(actual_files)}")
    if errors:
        print(f"[错误] 发现 {len(errors)} 处不一致：")
        for e in errors[:40]:
            print(f"  ✗ {e}")
        if len(errors) > 40:
            print(f"  ... 以及另外 {len(errors) - 40} 处")
        return 1
    print("✅ 全部文件 SHA256 与 manifest 一致")
    return 0


def main():
    parser = argparse.ArgumentParser(
        description="静态资源断链审计 — 验证所有引用的文件是否存在",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python scripts/audit_static_assets.py
  python scripts/audit_static_assets.py --dir resources/frontend --verbose
  python scripts/audit_static_assets.py --dir frontend/dist
        """,
    )
    parser.add_argument(
        "--dir",
        default=None,
        help="前端静态文件目录（默认自动探测 resources/frontend 或 frontend/dist）",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="详细输出：列出所有引用文件和未引用文件",
    )
    parser.add_argument(
        "--quick", "-q",
        action="store_true",
        help="快速模式：仅校验 index.html 直接引用的资源，跳过 JS 动态 import 扫描（适合启动时校验）",
    )
    parser.add_argument(
        "--verify-manifest",
        default=None,
        metavar="PATH",
        help="W6-T5: 逐文件 SHA256 manifest 复核模式（manifest 由 sync-frontend-dist 落盘），"
             "任一缺失/哈希不匹配/多出文件均退出非零",
    )
    args = parser.parse_args()

    # 自动探测前端目录
    if args.dir:
        frontend_dir = args.dir
    else:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(script_dir)
        candidates = [
            os.path.join(project_root, "resources", "frontend"),
            os.path.join(project_root, "frontend", "dist"),
        ]
        frontend_dir = None
        for candidate in candidates:
            if os.path.isfile(os.path.join(candidate, "index.html")):
                frontend_dir = candidate
                break
        if frontend_dir is None:
            print("[FATAL] 未找到包含 index.html 的前端目录")
            print(f"尝试过的路径: {candidates}")
            sys.exit(2)

    if args.verify_manifest:
        sys.exit(verify_manifest(frontend_dir, args.verify_manifest))

    exit_code = audit(frontend_dir, verbose=args.verbose, quick=args.quick)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
