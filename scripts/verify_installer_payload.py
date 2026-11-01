#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""Windows 安装包"是否带载荷"校验（2026-11-01 打包完整性门禁）。

## 为什么需要

2026-11-01 现场：双击 `MRRS-Setup-1.18.33-x64.exe` 弹出
「NSIS Error — Error writing temporary file. Make sure your temp folder is valid.」，
而 `%TEMP%` 本身可用（对照实验：NSIS 能自动创建缺失的末级目录）。

实测该文件只有 **489 KB**：PE 附加数据 280 KB、**没有 7z 载荷**；
同版本正常包是 332 MB、7z 流位于 487,771 字节偏移处。
即：构建过程中断（超时 / 进程被杀 / 并发写同一输出）后，makensis 留下了
"只有外壳没有内容"的半成品，而流水线把"文件存在"当成"构建成功"。
用户双击这种包，NSIS 在解包阶段写临时文件失败，报错文案指向 TEMP —— 与 TEMP 无关。

## 判定规则（任一不满足即失败）

1. 文件存在且总大小 ≥ `--min-total-mb`（默认 50 MB，正常 330 MB 量级）；
2. 是合法 PE，能算出附加数据（overlay）边界；
3. overlay 中存在 7z 流签名 `37 7A BC AF 27 1C`（electron-builder 的 app-64.7z）；
4. 7z 流之后的剩余字节 ≥ `--min-payload-mb`（默认 20 MB）——防止"签名在、内容被截断"；
5. 7z **起始头**自洽：主版本为 0、StartHeaderCRC 与 12..31 字节吻合、NextHeader 落在文件内
   ——防止"签名后面跟一段垃圾"或解包到一半被截断；
6. 文件名里的版本号与 `package.json` 一致（`--expect-version` 可覆盖）。

`--quarantine` 会把未通过的产物改名为 `<原名>.invalid`，避免现场误双击；
构建脚本默认开启，CI 不开启（失败即中断，产物留给工件留存排障）。

用法::

    python scripts/verify_installer_payload.py                 # 校验 dist/electron 下当前版本 x64 包
    python scripts/verify_installer_payload.py path/to/setup.exe
    python scripts/verify_installer_payload.py --arch arm64 --quarantine
"""

import argparse
import json
import mmap
import struct
import sys
import zlib
from pathlib import Path

# Windows 管道默认 ANSI 代码页，中文 print 会 UnicodeEncodeError → 假失败
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
DIST_DIR = ROOT / "dist" / "electron"
SEVEN_ZIP_SIGNATURE = b"7z\xbc\xaf\x27\x1c"
MB = 1024 * 1024


def pe_overlay_size(data: bytes) -> int | None:
    """返回 PE 附加数据（overlay）字节数；不是合法 PE 时返回 None。

    NSIS 安装器把整个 app-64.7z 追加在 PE 最后一个节之后，因此
    「总大小 - 节表末尾」就是载荷体积。构建中断时该值会掉到几百 KB。
    """
    if len(data) < 0x40 or data[:2] != b"MZ":
        return None
    try:
        e_lfanew = int.from_bytes(data[0x3C:0x40], "little")
        if data[e_lfanew : e_lfanew + 4] != b"PE\0\0":
            return None
        num_sections = int.from_bytes(data[e_lfanew + 6 : e_lfanew + 8], "little")
        opt_size = int.from_bytes(data[e_lfanew + 20 : e_lfanew + 22], "little")
        table = e_lfanew + 24 + opt_size
        end = 0
        for i in range(num_sections):
            header = table + i * 40
            if header + 40 > len(data):
                return None
            raw_size = int.from_bytes(data[header + 16 : header + 20], "little")
            raw_ptr = int.from_bytes(data[header + 20 : header + 24], "little")
            end = max(end, raw_ptr + raw_size)
        if end <= 0 or end > len(data):
            return None
        return len(data) - end
    except (IndexError, ValueError):
        return None


def seven_zip_header_issue(header: bytes, total_size: int, offset: int) -> str | None:
    """校验 7z 起始头（32 字节）：版本、StartHeaderCRC、NextHeader 边界。

    electron-builder 把整个 app-64.7z 追加在 exe 末尾；只要这 32 字节的 CRC 对得上、
    NextHeader 落在文件内，就能确认"载荷不是签名后面跟一堆垃圾/被截断"。
    """
    if len(header) < 32:
        return "7z 起始头不足 32 字节（文件在载荷处被截断）"
    if header[6] != 0:
        return f"7z 主版本异常: {header[6]}"
    stored_crc = struct.unpack_from("<I", header, 8)[0]
    if stored_crc != (zlib.crc32(header[12:32]) & 0xFFFFFFFF):
        return "7z 起始头 CRC 不匹配（载荷头已损坏）"
    next_offset, next_size = struct.unpack_from("<QQ", header, 12)
    end = offset + 32 + next_offset + next_size
    if end > total_size:
        return f"7z NextHeader 越界（需要到 {end:,} B，文件仅 {total_size:,} B）——载荷被截断"
    return None


def inspect(path: Path, min_total: int, min_payload: int) -> list[str]:
    """返回问题列表；空列表表示通过。"""
    problems: list[str] = []
    if not path.exists():
        return [f"文件不存在: {path}"]

    size = path.stat().st_size
    if size < min_total:
        problems.append(
            f"文件仅 {size:,} B，低于最小总大小 {min_total:,} B —— 典型残缺包（正常约 330 MB）"
        )

    # 安装包 330 MB 量级：用 mmap 扫描，避免把整份文件读进内存（CI runner 也能跑）
    with open(path, "rb") as fh, mmap.mmap(fh.fileno(), 0, access=mmap.ACCESS_READ) as data:
        overlay = pe_overlay_size(data)
        if overlay is None:
            problems.append("不是合法 PE（无法解析节表），文件可能已损坏")
            return problems

        pos = data.find(SEVEN_ZIP_SIGNATURE)
        if pos < 0:
            problems.append(
                f"未找到 7z 载荷签名（overlay 仅 {overlay:,} B）——安装包只有 NSIS 外壳，没有应用本体"
            )
            return problems

        payload = len(data) - pos
        header_issue = seven_zip_header_issue(data[pos : pos + 32], len(data), pos)
    if payload < min_payload:
        problems.append(
            f"7z 载荷仅 {payload:,} B（签名偏移 {pos:,}），低于最小载荷 {min_payload:,} B —— 载荷被截断"
        )
    if header_issue:
        problems.append(header_issue)
    return problems


def resolve_target(explicit: str | None, version: str | None, arch: str) -> Path:
    if explicit:
        return Path(explicit)
    if not version:
        pkg = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))
        version = str(pkg["version"])
    return DIST_DIR / f"MRRS-Setup-{version}-{arch}.exe"


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="校验 Windows 安装包是否包含 7z 载荷")
    parser.add_argument("target", nargs="?", help="安装包路径（默认按 package.json 版本推导）")
    parser.add_argument("--arch", default="x64", help="架构，默认 x64")
    parser.add_argument("--expect-version", default=None, help="期望版本号（默认取 package.json）")
    parser.add_argument("--min-total-mb", type=float, default=50.0, help="最小总大小（MB）")
    parser.add_argument("--min-payload-mb", type=float, default=20.0, help="最小载荷大小（MB）")
    parser.add_argument("--quarantine", action="store_true", help="校验失败时把产物改名为 .invalid")
    args = parser.parse_args(argv)

    target = resolve_target(args.target, args.expect_version, args.arch)
    # 版本一致性只在「自动推导路径」或显式 --expect-version 时强制：
    # 显式传入历史产物路径（排障/回归）不应被当前版本号误判。
    enforce_version = args.expect_version is not None or args.target is None
    version = args.expect_version
    if version is None:
        try:
            version = str(json.loads((ROOT / "package.json").read_text(encoding="utf-8"))["version"])
        except (OSError, KeyError, ValueError):
            version = None

    print(f"[verify-installer] 目标: {target}")
    problems = inspect(target, int(args.min_total_mb * MB), int(args.min_payload_mb * MB))

    if enforce_version and version and target.exists() and f"-{version}-" not in target.name:
        problems.append(f"文件名不含期望版本 -{version}-（可能校验到了旧产物）")

    if not problems:
        size = target.stat().st_size
        with open(target, "rb") as fh:
            mm = mmap.mmap(fh.fileno(), 0, access=mmap.ACCESS_READ)
            try:
                pos = mm.find(SEVEN_ZIP_SIGNATURE)
            finally:
                mm.close()
        print(
            f"[verify-installer] OK 总大小={size:,} B 7z偏移={pos:,} 载荷={size - pos:,} B"
        )
        return 0

    print("[verify-installer] FAIL 安装包不完整：", file=sys.stderr)
    for item in problems:
        print(f"  - {item}", file=sys.stderr)
    print(
        "[verify-installer] 处置：删除该文件后重跑 `npm run build:win`（构建请放后台/勿中断）；"
        "残缺包双击会报「Error writing temporary file」，与 %TEMP% 无关。",
        file=sys.stderr,
    )

    if args.quarantine and target.exists():
        quarantine = target.with_suffix(target.suffix + ".invalid")
        try:
            if quarantine.exists():
                quarantine.unlink()
            target.rename(quarantine)
            print(f"[verify-installer] 已隔离为 {quarantine.name}，避免误双击", file=sys.stderr)
        except OSError as exc:  # pragma: no cover - 文件被占用等系统错误
            print(f"[verify-installer] 隔离失败（{exc}），请手动删除", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
