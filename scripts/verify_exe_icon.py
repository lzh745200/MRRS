#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""Windows 可执行文件"图标资源"门禁（2026-11-15）。

## 为什么需要

现场反馈「安装后图标缺失」。排查发现构建链本身有图标（exe 的 .rsrc 内 7 档齐全、
`resources/app-circle.ico` 也在位），问题出在安装后的缓存与兜底；
但只要 electron-builder 的 rcedit 步骤在某些环境静默失败（权限/杀软/PE 被占用），
exe 就会退回 Electron 默认图标或空图标，肉眼只能靠"看起来不对"发现。

本脚本把"图标到底在不在"变成可判定的构建门禁：

1. 解析 PE，定位 `.rsrc`；
2. 统计其中的图标流（PNG 压缩条目按 IHDR 读宽高，BMP 条目按 16 字节头读宽高）；
3. 要求：至少 `--min-sizes` 档（默认 5），且必须包含 256×256（Windows 大图标/桌面必需）；
4. 可选 `--resources-dir`：校验随包 `app-circle.ico` 存在且内含 256 档
   （安装器给快捷方式用的就是这份文件）。

用法::

    python scripts/verify_exe_icon.py                       # 校验 dist/electron/win-unpacked 下的主程序
    python scripts/verify_exe_icon.py --exe path/to/app.exe --resources-dir path/to/resources
"""

import argparse
import struct
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_EXE = ROOT / "dist" / "electron" / "win-unpacked" / "帮扶管理系统.exe"
DEFAULT_RES = ROOT / "dist" / "electron" / "win-unpacked" / "resources"


def _sections(data: bytes):
    """返回 [(name, raw_ptr, raw_size)]；非 PE 返回 None。"""
    if len(data) < 0x40 or data[:2] != b"MZ":
        return None
    try:
        e = struct.unpack_from("<I", data, 0x3C)[0]
        if data[e : e + 4] != b"PE\0\0":
            return None
        n = struct.unpack_from("<H", data, e + 6)[0]
        opt = struct.unpack_from("<H", data, e + 20)[0]
        base = e + 24 + opt
        out = []
        for i in range(n):
            o = base + i * 40
            name = data[o : o + 8].rstrip(b"\0").decode("latin1")
            raw_size, raw_ptr = struct.unpack_from("<II", data, o + 16)
            out.append((name, raw_ptr, raw_size))
        return out
    except (struct.error, IndexError):
        return None


def _sizes_from_group_icon(seg: bytes) -> list[int] | None:
    """在 .rsrc 里找 RT_GROUP_ICON 目录（GRPICONDIR），返回各条目宽度。

    结构：reserved(2)=0, type(2)=1, count(2)=N，随后 N 个 14 字节条目，
    每个条目首字节是宽度（0 表示 256），末尾 2 字节是 RT_ICON 资源 id。
    图标资源是 Windows 唯一认的"图标组"，比按 PNG 签名扫描更权威，
    也能覆盖 BMP(DIB) 编码的小尺寸条目。
    """
    n = len(seg)
    for i in range(0, n - 6):
        if seg[i] != 0 or seg[i + 1] != 0 or seg[i + 2] != 1 or seg[i + 3] != 0:
            continue
        count = struct.unpack_from("<H", seg, i + 4)[0]
        if not (3 <= count <= 20):
            continue
        end = i + 6 + count * 14
        if end > n:
            continue
        sizes: list[int] = []
        plausible = True
        for k in range(count):
            o = i + 6 + k * 14
            w = seg[o] or 256
            planes, bpp = struct.unpack_from("<HH", seg, o + 4)
            nbytes = struct.unpack_from("<I", seg, o + 8)[0]
            if w not in (16, 20, 24, 32, 40, 48, 60, 64, 96, 128, 256):
                plausible = False
                break
            if planes not in (0, 1) or bpp not in (0, 4, 8, 24, 32) or nbytes == 0 or nbytes > 2_000_000:
                plausible = False
                break
            sizes.append(w)
        if plausible and sizes:
            return sorted(set(sizes))
    return None


def icon_sizes_in_resource(data: bytes) -> list[int] | None:
    """返回 exe 内置图标的宽度列表；不是合法 PE 时返回 None。

    优先按 RT_GROUP_ICON 解析（BMP/PNG 混合编码都能识别），
    退化到扫描 PNG 压缩条目（部分精简 PE 里没有资源目录树）。
    """
    sections = _sections(data)
    if sections is None:
        return None
    rsrc = [s for s in sections if s[0] == ".rsrc"]
    if not rsrc:
        return []
    _, ptr, size = rsrc[0]
    seg = data[ptr : ptr + size]

    group = _sizes_from_group_icon(seg)
    if group:
        return group

    sizes: list[int] = []
    idx = 0
    while True:
        i = seg.find(b"\x89PNG\r\n\x1a\n", idx)
        if i < 0:
            break
        idx = i + 1
        if seg[i + 12 : i + 16] == b"IHDR":
            w, h = struct.unpack_from(">II", seg, i + 16)
            if 0 < w <= 512 and 0 < h <= 512:
                sizes.append(w)
    return sorted(set(sizes))


def ico_sizes(path: Path) -> list[int]:
    """读 ICO 目录，返回各条目宽度（0 表示 256）。"""
    b = path.read_bytes()
    if len(b) < 6 or struct.unpack_from("<H", b, 2)[0] != 1:
        return []
    count = struct.unpack_from("<H", b, 4)[0]
    out = []
    for i in range(count):
        off = 6 + i * 16
        if off + 16 > len(b):
            break
        w = b[off]
        out.append(256 if w == 0 else w)
    return sorted(set(out))


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="校验 Windows 主程序与随包 ICO 的图标资源")
    ap.add_argument("--exe", default=str(DEFAULT_EXE))
    ap.add_argument("--resources-dir", default=str(DEFAULT_RES))
    ap.add_argument("--min-sizes", type=int, default=5)
    args = ap.parse_args(argv)

    exe = Path(args.exe)
    problems: list[str] = []
    if not exe.exists():
        print(f"[verify-icon] FAIL 找不到主程序：{exe}", file=sys.stderr)
        return 1

    data = exe.read_bytes()
    sizes = icon_sizes_in_resource(data)
    if sizes is None:
        problems.append("不是合法 PE（无法解析节表）")
    elif not sizes:
        problems.append(".rsrc 中没有 PNG 图标条目（rcedit 可能未生效 / 图标被剥离）")
    else:
        print(f"[verify-icon] exe 图标档位：{sizes}")
        if len(sizes) < args.min_sizes:
            problems.append(f"图标档位仅 {len(sizes)} 档，低于要求 {args.min_sizes} 档")
        if 256 not in sizes:
            problems.append("缺少 256×256 档（桌面大图标/资源管理器会退回低清或空白）")

    ico_path = Path(args.resources_dir) / "app-circle.ico"
    if not ico_path.exists():
        problems.append(f"随包图标缺失：{ico_path}（快捷方式会回退 exe 图标）")
    else:
        isz = ico_sizes(ico_path)
        print(f"[verify-icon] 随包 ico 档位：{isz}（{ico_path.stat().st_size:,} B）")
        if 256 not in isz:
            problems.append("随包 app-circle.ico 缺少 256×256 档")

    if problems:
        print("[verify-icon] FAIL：", file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        return 1
    print("[verify-icon] OK 图标资源完整")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
