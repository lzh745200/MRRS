# -*- coding: utf-8 -*-
"""`scripts/verify_installer_payload.py` 的回归（2026-11-01 打包完整性门禁）。

背景（现场事故）：`MRRS-Setup-1.18.33-x64.exe` 只有 489 KB —— NSIS 外壳在、
`app-64.7z` 载荷不在。双击后 NSIS 在解包阶段报
「Error writing temporary file. Make sure your temp folder is valid.」，
现场据此去查 `%TEMP%`（实际正常：对照实验证明 NSIS 会自动创建缺失的末级目录）。
本文件锁死四类判定，防止门禁被削弱后残缺包再次流出：

1. 正常包（PE + 自洽的 7z 起始头 + 足量载荷）→ 通过；
2. 空壳包（PE 无载荷）→ 失败且给出可读原因；
3. 载荷被截断 / 头部损坏 / NextHeader 越界 → 失败；
4. `--quarantine` 必须把失败产物改名 `.invalid`，避免现场误双击。
"""

import importlib.util
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts" / "verify_installer_payload.py"

_spec = importlib.util.spec_from_file_location("verify_installer_payload", SCRIPT)
mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mod)

SEVEN_ZIP_SIG = b"7z\xbc\xaf\x27\x1c"


def _seven_zip_payload(body: bytes = b"A" * 4096, next_offset: int = 0, next_size: int = 0) -> bytes:
    """构造一个 7z 起始头自洽的载荷（StartHeaderCRC 按真实算法计算）。"""
    head = bytearray(32)
    head[0:6] = SEVEN_ZIP_SIG
    head[6] = 0  # major
    head[7] = 4  # minor
    head[12:20] = next_offset.to_bytes(8, "little")
    head[20:28] = next_size.to_bytes(8, "little")
    head[8:12] = (zlib.crc32(bytes(head[12:32])) & 0xFFFFFFFF).to_bytes(4, "little")
    return bytes(head) + body


def _fake_pe(payload: bytes = b"", section_size: int = 0x200) -> bytes:
    """构造最小合法 PE：1 个节，节数据之后追加 payload（模拟 NSIS 附加数据）。"""
    e_lfanew = 0x80
    head = bytearray(0x400)
    head[0:2] = b"MZ"
    head[0x3C:0x40] = e_lfanew.to_bytes(4, "little")
    head[e_lfanew : e_lfanew + 4] = b"PE\0\0"
    head[e_lfanew + 6 : e_lfanew + 8] = (1).to_bytes(2, "little")  # NumberOfSections
    opt_size = 0xE0
    head[e_lfanew + 20 : e_lfanew + 22] = opt_size.to_bytes(2, "little")
    table = e_lfanew + 24 + opt_size
    head[table : table + 8] = b".text\0\0\0"
    head[table + 16 : table + 20] = section_size.to_bytes(4, "little")  # SizeOfRawData
    head[table + 20 : table + 24] = (0x400).to_bytes(4, "little")  # PointerToRawData
    return bytes(head) + b"\x00" * section_size + payload


class TestPeOverlay:
    def test_non_pe_returns_none(self):
        assert mod.pe_overlay_size(b"not-a-pe") is None

    def test_overlay_counts_bytes_after_last_section(self):
        data = _fake_pe(payload=_seven_zip_payload(body=b"A" * 64))
        assert mod.pe_overlay_size(data) == 32 + 64


class TestSevenZipHeader:
    def test_valid_header_passes(self):
        payload = _seven_zip_payload()
        assert mod.seven_zip_header_issue(payload[:32], 1024, 100) is None

    def test_short_header_is_rejected(self):
        issue = mod.seven_zip_header_issue(b"7z\xbc", 1024, 0)
        assert issue and "不足 32 字节" in issue

    def test_corrupted_crc_is_rejected(self):
        payload = bytearray(_seven_zip_payload())
        payload[8] ^= 0xFF  # 破坏 StartHeaderCRC
        issue = mod.seven_zip_header_issue(bytes(payload[:32]), 1024, 0)
        assert issue and "CRC 不匹配" in issue

    def test_next_header_beyond_eof_is_rejected(self):
        payload = _seven_zip_payload(next_offset=10**9)
        issue = mod.seven_zip_header_issue(payload[:32], len(payload), 0)
        assert issue and "越界" in issue

    def test_unexpected_major_version_is_rejected(self):
        payload = bytearray(_seven_zip_payload())
        payload[6] = 9
        issue = mod.seven_zip_header_issue(bytes(payload[:32]), 1024, 0)
        assert issue and "主版本异常" in issue


class TestInspect:
    def test_complete_package_passes(self, tmp_path):
        target = tmp_path / "MRRS-Setup-1.0.0-x64.exe"
        target.write_bytes(_fake_pe(payload=_seven_zip_payload()))
        assert mod.inspect(target, min_total=1, min_payload=1) == []

    def test_missing_file_is_reported(self, tmp_path):
        problems = mod.inspect(tmp_path / "absent.exe", 1, 1)
        assert any("文件不存在" in p for p in problems)

    def test_shell_without_payload_is_rejected(self, tmp_path):
        """现场形态：PE 完整、但没有 7z 载荷（489 KB 空壳）。"""
        target = tmp_path / "stub.exe"
        target.write_bytes(_fake_pe(payload=b""))
        problems = mod.inspect(target, min_total=1, min_payload=1)
        assert any("未找到 7z 载荷签名" in p for p in problems)

    def test_truncated_payload_is_rejected(self, tmp_path):
        target = tmp_path / "cut.exe"
        target.write_bytes(_fake_pe(payload=_seven_zip_payload(body=b"A" * 10)))
        problems = mod.inspect(target, min_total=1, min_payload=1024)
        assert any("载荷被截断" in p for p in problems)

    def test_garbage_after_signature_is_rejected(self, tmp_path):
        """签名后跟垃圾：体积够但 7z 头不自洽，必须拦住。"""
        target = tmp_path / "garbage.exe"
        target.write_bytes(_fake_pe(payload=SEVEN_ZIP_SIG + b"\xff" * 4096))
        problems = mod.inspect(target, min_total=1, min_payload=1)
        assert any("7z" in p for p in problems)

    def test_tiny_file_hits_size_floor(self, tmp_path):
        target = tmp_path / "tiny.exe"
        target.write_bytes(_fake_pe(payload=_seven_zip_payload(body=b"A" * 10)))
        problems = mod.inspect(target, min_total=10_000_000, min_payload=1)
        assert any("典型残缺包" in p for p in problems)

    def test_broken_pe_is_rejected(self, tmp_path):
        target = tmp_path / "broken.exe"
        target.write_bytes(b"MZ" + b"\x00" * 200)
        problems = mod.inspect(target, min_total=1, min_payload=1)
        assert any("不是合法 PE" in p for p in problems)


class TestMain:
    def test_ok_returns_zero(self, tmp_path, capsys):
        target = tmp_path / "MRRS-Setup-1.0.0-x64.exe"
        target.write_bytes(_fake_pe(payload=_seven_zip_payload()))
        code = mod.main([str(target), "--min-total-mb", "0.0001", "--min-payload-mb", "0.0001"])
        assert code == 0
        assert "OK" in capsys.readouterr().out

    def test_failure_quarantines_artifact(self, tmp_path):
        target = tmp_path / "MRRS-Setup-1.0.0-x64.exe"
        target.write_bytes(_fake_pe(payload=b""))
        code = mod.main(
            [str(target), "--min-total-mb", "0.0001", "--min-payload-mb", "0.0001", "--quarantine"]
        )
        assert code == 1
        assert not target.exists()
        assert target.with_suffix(target.suffix + ".invalid").exists()

    def test_version_mismatch_is_rejected(self, tmp_path):
        target = tmp_path / "MRRS-Setup-1.0.0-x64.exe"
        target.write_bytes(_fake_pe(payload=_seven_zip_payload()))
        code = mod.main(
            [
                str(target),
                "--expect-version",
                "9.9.9",
                "--min-total-mb",
                "0.0001",
                "--min-payload-mb",
                "0.0001",
            ]
        )
        assert code == 1
