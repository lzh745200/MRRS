# -*- coding: utf-8 -*-
"""`scripts/verify_exe_icon.py` 的回归（2026-11-15 图标资源门禁）。

背景：现场反馈"安装后图标缺失"。构建链本身有图标（exe .rsrc 7 档齐全），
但 rcedit 在权限/杀软/PE 占用等情况下可能静默失败，肉眼只能靠"看起来不对"发现。
本文件锁死判定规则，防止门禁被削弱：

1. 正常 exe（.rsrc 内 7 档含 256）+ 随包 ico → 通过；
2. 缺 256 档 / 档位过少 / 无 .rsrc / 非 PE → 失败；
3. 随包 app-circle.ico 缺 256 档 → 失败。
"""

import importlib.util
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts" / "verify_exe_icon.py"

_spec = importlib.util.spec_from_file_location("verify_exe_icon", SCRIPT)
mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mod)

PNG_SIG = b"\x89PNG\r\n\x1a\n"


def _png_icon(size: int) -> bytes:
    """伪造一个 PNG 图标流：签名 + 长度 + IHDR + 宽高。"""
    body = struct.pack(">II", size, size) + b"\x08\x06\x00\x00\x00"
    return PNG_SIG + struct.pack(">I", len(body)) + b"IHDR" + body


def _fake_pe(rsrc: bytes = b"", section_name: str = ".rsrc") -> bytes:
    """最小 PE：1 个节，节数据即 rsrc。"""
    e_lfanew = 0x80
    head = bytearray(0x400)
    head[0:2] = b"MZ"
    head[0x3C:0x40] = e_lfanew.to_bytes(4, "little")
    head[e_lfanew : e_lfanew + 4] = b"PE\0\0"
    head[e_lfanew + 6 : e_lfanew + 8] = (1).to_bytes(2, "little")
    opt_size = 0xE0
    head[e_lfanew + 20 : e_lfanew + 22] = opt_size.to_bytes(2, "little")
    table = e_lfanew + 24 + opt_size
    head[table : table + 8] = section_name.encode().ljust(8, b"\0")[:8]
    head[table + 16 : table + 20] = len(rsrc).to_bytes(4, "little")
    head[table + 20 : table + 24] = (0x400).to_bytes(4, "little")
    return bytes(head) + rsrc


def _write_ico(path: Path, sizes=(16, 24, 32, 48, 64, 128, 256)) -> None:
    count = len(sizes)
    header = struct.pack("<HHH", 0, 1, count)
    entries = b""
    payload = b""
    offset = 6 + 16 * count
    for s in sizes:
        data = _png_icon(s)
        entries += struct.pack("<BBBBHHII", 0 if s == 256 else s, 0 if s == 256 else s,
                               0, 0, 1, 32, len(data), offset + len(payload))
        payload += data
    path.write_bytes(header + entries + payload)


class TestIconSizesInResource:
    def test_counts_all_png_entries(self):
        rsrc = b"".join(_png_icon(s) for s in (16, 24, 32, 48, 64, 128, 256))
        assert mod.icon_sizes_in_resource(_fake_pe(rsrc)) == [16, 24, 32, 48, 64, 128, 256]

    def test_non_pe_returns_none(self):
        assert mod.icon_sizes_in_resource(b"not-a-pe") is None

    def test_no_rsrc_section_returns_empty(self):
        assert mod.icon_sizes_in_resource(_fake_pe(b"", section_name=".text")) == []


class TestIcoSizes:
    def test_reads_directory(self, tmp_path):
        p = tmp_path / "a.ico"
        _write_ico(p)
        assert mod.ico_sizes(p) == [16, 24, 32, 48, 64, 128, 256]

    def test_zero_width_means_256(self, tmp_path):
        p = tmp_path / "b.ico"
        _write_ico(p, sizes=(256,))
        assert mod.ico_sizes(p) == [256]

    def test_invalid_file_returns_empty(self, tmp_path):
        p = tmp_path / "c.ico"
        p.write_bytes(b"nope")
        assert mod.ico_sizes(p) == []


class TestMain:
    def _prepare(self, tmp_path, exe_sizes=(16, 24, 32, 48, 64, 128, 256), ico_sizes_=(16, 24, 32, 48, 64, 128, 256)):
        exe = tmp_path / "app.exe"
        exe.write_bytes(_fake_pe(b"".join(_png_icon(s) for s in exe_sizes)))
        res = tmp_path / "resources"
        res.mkdir()
        _write_ico(res / "app-circle.ico", sizes=ico_sizes_)
        return exe, res

    def test_complete_icons_pass(self, tmp_path):
        exe, res = self._prepare(tmp_path)
        assert mod.main(["--exe", str(exe), "--resources-dir", str(res)]) == 0

    def test_missing_256_is_rejected(self, tmp_path):
        exe, res = self._prepare(tmp_path, exe_sizes=(16, 24, 32, 48, 64))
        assert mod.main(["--exe", str(exe), "--resources-dir", str(res)]) == 1

    def test_too_few_sizes_rejected(self, tmp_path):
        exe, res = self._prepare(tmp_path, exe_sizes=(16, 256))
        assert mod.main(["--exe", str(exe), "--resources-dir", str(res)]) == 1

    def test_missing_exe_rejected(self, tmp_path):
        assert mod.main(["--exe", str(tmp_path / "absent.exe"), "--resources-dir", str(tmp_path)]) == 1

    def test_packaged_ico_missing_rejected(self, tmp_path):
        exe, _ = self._prepare(tmp_path)
        assert mod.main(["--exe", str(exe), "--resources-dir", str(tmp_path / "nope")]) == 1

    def test_packaged_ico_without_256_rejected(self, tmp_path):
        exe, res = self._prepare(tmp_path, ico_sizes_=(16, 32, 48))
        assert mod.main(["--exe", str(exe), "--resources-dir", str(res)]) == 1

def _group_icon(sizes=(16, 24, 32, 48, 64, 128, 256)) -> bytes:
    """伪造 RT_GROUP_ICON 目录：reserved/type/count + N×14 字节条目。"""
    out = struct.pack("<HHH", 0, 1, len(sizes))
    for i, s in enumerate(sizes, start=1):
        out += struct.pack("<BBBBHHIH", 0 if s == 256 else s, 0 if s == 256 else s,
                           0, 0, 1, 32, 1024, i)
    return out


class TestGroupIconParsing:
    """BMP 编码的小尺寸条目只能靠 RT_GROUP_ICON 发现，PNG 扫描看不到。"""

    def test_group_icon_sizes_detected(self):
        seg = _group_icon()
        assert mod.icon_sizes_in_resource(_fake_pe(seg)) == [16, 24, 32, 48, 64, 128, 256]

    def test_group_icon_ignores_implausible_entries(self):
        bad = struct.pack("<HHH", 0, 1, 3) + struct.pack("<BBBBHHIH", 7, 7, 0, 0, 1, 32, 100, 1) * 3
        # 宽度 7 不在允许集合内 → 该候选被丢弃，回退 PNG 扫描（此处为空）
        assert mod.icon_sizes_in_resource(_fake_pe(bad)) == []

    def test_empty_rsrc_returns_empty(self):
        assert mod.icon_sizes_in_resource(_fake_pe(b"")) == []
