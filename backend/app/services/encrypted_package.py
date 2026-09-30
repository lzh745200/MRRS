"""离线加密数据包 — AES-256-GCM + SHA256 完整性校验.

格式 (.rrs):
    [4B MAGIC "RRS\0"][3B VERSION "1.0"][16B salt][4B metadata_len][encrypted_metadata]
    [encrypted_data][32B SHA256 checksum over metadata+data plaintext]

用于多机U盘物理拷贝同步，支持防篡改和密码保护。
"""
import hashlib
import json
import logging
import struct
from typing import Any, Dict

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from app.services.aes_gcm_cipher import AESGCMCipher

logger = logging.getLogger(__name__)

MAGIC = b"RRS\x00"
VERSION = b"1.0"

# 文件头固定长度: 4B MAGIC + 3B VERSION + 16B salt + 4B metadata_len
_HEADER_LEN = 4 + 3 + 16 + 4
# checksum 固定长度（SHA256）
_CHECKSUM_LEN = 32
# metadata 密文长度上限（16 MiB）。真实 metadata 只有 {"format_version","timestamp"}
# 几十字节；无上界时一个损坏/恶意文件可让 meta_len 声明为 4GiB，f.read(meta_len)
# 直接吃满内存（深审 #63）。
MAX_METADATA_BYTES = 16 * 1024 * 1024


def _derive_key(password: str, salt: bytes) -> bytes:
    """PBKDF2-SHA256 密钥派生."""
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=600_000,
    )
    return kdf.derive(password.encode("utf-8"))


def create_encrypted_package(
    data: Dict[str, Any],
    output_path: str,
    password: str,
) -> None:
    """创建加密数据包.

    Args:
        data: 要导出的数据字典（会被序列化为 JSON）
        output_path: 输出文件路径 (.rrs)
        password: 加密密码
    """
    import os as _os

    salt = _os.urandom(16)
    key = _derive_key(password, salt)
    cipher = AESGCMCipher(key=key)

    # 序列化并加密
    metadata = {"format_version": "1.0", "timestamp": ""}
    metadata_json = json.dumps(metadata, ensure_ascii=False).encode("utf-8")
    data_json = json.dumps(data, ensure_ascii=False).encode("utf-8")

    # 完整性校验 (before encryption)
    checksum = hashlib.sha256(metadata_json + data_json).digest()

    encrypted_metadata = cipher.encrypt(metadata_json)
    encrypted_data = cipher.encrypt(data_json)

    with open(output_path, "wb") as f:
        f.write(MAGIC)                          # 4 字节
        f.write(VERSION)                         # 3 字节
        f.write(salt)                            # 16 字节
        f.write(struct.pack(">I", len(encrypted_metadata)))  # 4 字节
        f.write(encrypted_metadata)
        f.write(encrypted_data)
        f.write(checksum)                        # 32 字节


def extract_encrypted_package(
    input_path: str,
    password: str,
) -> Dict[str, Any]:
    """解析并解密数据包，自动验证完整性.

    Raises:
        ValueError: 密码错误、格式损坏或数据被篡改
    """
    with open(input_path, "rb") as f:
        # 1) 先校验文件头是否读满，避免对短文件 struct.unpack 抛 struct.error
        header = f.read(_HEADER_LEN)
        if len(header) < _HEADER_LEN:
            raise ValueError(
                f"数据包损坏: 文件过短（{len(header)} 字节，至少需要 {_HEADER_LEN} 字节）"
            )

        magic = header[:4]
        if magic != MAGIC:
            raise ValueError(f"无效的文件格式: {magic!r}, 期望 {MAGIC!r}")

        version = header[4:7]
        if version != VERSION:
            raise ValueError(f"不支持的版本: {version}")

        salt = header[7:23]
        meta_len = struct.unpack(">I", header[23:27])[0]

        # 2) meta_len 上界校验：损坏文件可能声明超大长度，直接 read 会 OOM
        if meta_len > MAX_METADATA_BYTES:
            raise ValueError(
                f"数据包损坏: metadata 长度异常（{meta_len} 字节，上限 {MAX_METADATA_BYTES}）"
            )

        encrypted_metadata = f.read(meta_len)
        if len(encrypted_metadata) < meta_len:
            raise ValueError("数据包损坏: metadata 内容不完整")

        # 剩余数据 = encrypted_data + checksum (32 bytes)
        remaining = f.read()
        if len(remaining) < _CHECKSUM_LEN:
            raise ValueError("数据包损坏: 内容不完整")
        encrypted_data = remaining[:-_CHECKSUM_LEN]
        stored_checksum = remaining[-_CHECKSUM_LEN:]

    if not encrypted_data:
        raise ValueError("数据包损坏: 缺少数据段")

    key = _derive_key(password, salt)
    cipher = AESGCMCipher(key=key)

    try:
        metadata_json = cipher.decrypt(encrypted_metadata)
        data_json = cipher.decrypt(encrypted_data)
    except Exception as e:
        raise ValueError(f"解密失败（密码错误或数据损坏）: {e}") from e

    # 完整性校验
    computed_checksum = hashlib.sha256(metadata_json + data_json).digest()
    if computed_checksum != stored_checksum:
        raise ValueError("完整性校验失败: 数据可能被篡改")

    data = json.loads(data_json.decode("utf-8"))
    return data
