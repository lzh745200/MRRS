"""深审 #63：.rrs 加密数据包解析的健壮性（截断文件 / 超长 meta_len）。

原实现 `struct.unpack(">I", f.read(4))` 在文件不足 27 字节时抛 struct.error
（非 ValueError，调用方 except ValueError 捕获不到，冒泡成 500）；且 meta_len
无上界，损坏文件声明 4GiB 会直接吃满内存。
"""
import struct

import pytest

from app.services.encrypted_package import (
    MAGIC,
    MAX_METADATA_BYTES,
    VERSION,
    create_encrypted_package,
    extract_encrypted_package,
)

PASSWORD = "pwd-深审-63"


def _valid_package(tmp_path, payload=None):
    out = tmp_path / "pkg.rrs"
    create_encrypted_package(payload or {"hello": "世界"}, str(out), PASSWORD)
    return out


class TestRoundTrip:
    def test_create_then_extract(self, tmp_path):
        out = _valid_package(tmp_path, {"village": "测试村", "count": 3})
        assert extract_encrypted_package(str(out), PASSWORD) == {
            "village": "测试村",
            "count": 3,
        }

    def test_wrong_password_raises_value_error(self, tmp_path):
        out = _valid_package(tmp_path)
        with pytest.raises(ValueError, match="解密失败"):
            extract_encrypted_package(str(out), "wrong-password")


class TestTruncatedFileHandling:
    """所有"文件过短"输入必须抛 ValueError（可被调用方捕获），不得抛 struct.error。"""

    def test_empty_file(self, tmp_path):
        p = tmp_path / "empty.rrs"
        p.write_bytes(b"")
        with pytest.raises(ValueError, match="文件过短"):
            extract_encrypted_package(str(p), PASSWORD)

    def test_only_magic(self, tmp_path):
        p = tmp_path / "magic.rrs"
        p.write_bytes(MAGIC)
        with pytest.raises(ValueError, match="文件过短"):
            extract_encrypted_package(str(p), PASSWORD)

    def test_header_one_byte_short(self, tmp_path):
        """正好差 1 字节到 27 字节头部 → 必须给出明确 ValueError 而非 struct.error。"""
        p = tmp_path / "short.rrs"
        p.write_bytes(MAGIC + VERSION + b"\x00" * 15)  # 4+3+15 = 22 字节
        with pytest.raises(ValueError, match="文件过短"):
            extract_encrypted_package(str(p), PASSWORD)

    def test_metadata_truncated(self, tmp_path):
        """头部完整但 metadata 密文声明长度大于实际剩余。"""
        p = tmp_path / "trunc.rrs"
        body = MAGIC + VERSION + b"\x11" * 16 + struct.pack(">I", 500) + b"short"
        p.write_bytes(body)
        with pytest.raises(ValueError, match="metadata 内容不完整"):
            extract_encrypted_package(str(p), PASSWORD)

    def test_no_checksum_left(self, tmp_path):
        """metadata 完整但尾部不足 32 字节 checksum。"""
        p = tmp_path / "nock.rrs"
        meta = b"x" * 10
        p.write_bytes(MAGIC + VERSION + b"\x11" * 16 + struct.pack(">I", len(meta)) + meta + b"tiny")
        with pytest.raises(ValueError, match="内容不完整"):
            extract_encrypted_package(str(p), PASSWORD)

    def test_no_data_segment(self, tmp_path):
        """metadata 完整 + 恰好 32 字节 checksum，但 encrypted_data 为空。"""
        p = tmp_path / "nodata.rrs"
        meta = b"x" * 10
        p.write_bytes(
            MAGIC + VERSION + b"\x11" * 16
            + struct.pack(">I", len(meta)) + meta + b"\x00" * 32
        )
        with pytest.raises(ValueError, match="缺少数据段"):
            extract_encrypted_package(str(p), PASSWORD)


class TestMetadataLengthBound:
    def test_oversized_meta_len_rejected_without_reading(self, tmp_path):
        """meta_len 声明 4GiB → 立即拒绝，不执行 f.read(4GiB)。"""
        p = tmp_path / "huge.rrs"
        p.write_bytes(
            MAGIC + VERSION + b"\x11" * 16 + struct.pack(">I", 0xFFFFFFFF)
        )
        with pytest.raises(ValueError, match="metadata 长度异常"):
            extract_encrypted_package(str(p), PASSWORD)

    def test_boundary_just_above_limit_rejected(self, tmp_path):
        p = tmp_path / "over.rrs"
        p.write_bytes(
            MAGIC + VERSION + b"\x11" * 16 + struct.pack(">I", MAX_METADATA_BYTES + 1)
        )
        with pytest.raises(ValueError, match="metadata 长度异常"):
            extract_encrypted_package(str(p), PASSWORD)

    def test_limit_is_sane(self):
        """上限应为有限值（防止有人改成无穷）。"""
        assert 0 < MAX_METADATA_BYTES <= 64 * 1024 * 1024


class TestFormatErrors:
    def test_bad_magic(self, tmp_path):
        p = tmp_path / "bad.rrs"
        p.write_bytes(b"XXXX" + VERSION + b"\x00" * 20)
        with pytest.raises(ValueError, match="无效的文件格式"):
            extract_encrypted_package(str(p), PASSWORD)

    def test_unsupported_version(self, tmp_path):
        p = tmp_path / "ver.rrs"
        p.write_bytes(MAGIC + b"9.9" + b"\x00" * 20)
        with pytest.raises(ValueError, match="不支持的版本"):
            extract_encrypted_package(str(p), PASSWORD)

    def test_tampered_data_fails_checksum(self, tmp_path):
        out = _valid_package(tmp_path, {"a": 1})
        raw = bytearray(out.read_bytes())
        # 篡改倒数第 33 字节（encrypted_data 末字节），保持长度不变
        raw[-33] ^= 0xFF
        out.write_bytes(bytes(raw))
        with pytest.raises(ValueError, match="解密失败|完整性校验失败"):
            extract_encrypted_package(str(out), PASSWORD)
