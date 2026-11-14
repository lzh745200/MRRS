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
from pathlib import Path
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


def _as_text(raw: bytes) -> str:
    """把文件头里的裸字节转成可读文本，绝不抛错。

    用于错误消息：直接把 bytes 塞进 f-string 会渲染成 ``b'\\x01\\x02'``，
    用户看不懂，也无法据此判断"是版本不对还是文件坏了"。

    控制字符必须转义成 ``\\xNN``：``b"\\x02".decode("ascii")`` 是合法的 U+0002，
    直接拼进消息会变成**看不见的空白** —— 那比原来的 ``b'\\x02'`` 更难排查。
    """
    try:
        text = raw.decode("ascii")
    except UnicodeDecodeError:
        text = ""
    if text and text.isprintable():
        return text
    return raw.decode("latin-1").encode("unicode_escape").decode("ascii")


def _derive_key(password: str, salt: bytes) -> bytes:
    """PBKDF2-SHA256 密钥派生."""
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=600_000,
    )
    return kdf.derive(password.encode("utf-8"))


def _file_sha256(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _signature_payload(path: str) -> Dict[str, str]:
    """对最终文件字节摘要签名，避免包格式改动破坏旧客户端。"""
    return {"package_sha256": _file_sha256(path)}


def create_encrypted_package(
    data: Dict[str, Any],
    output_path: str,
    password: str,
    *,
    signing_key: str = "",
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

    # 可选来源签名：独立 .rrs.sig，不改动 .rrs 格式，旧客户端可忽略。
    # 未配置私钥时不生成签名，导入侧按 SYNC_PACKAGE_PUBKEY 决定 warn/fail。
    if signing_key:
        from app.core.grant_signing import sign_payload

        signature = sign_payload(_signature_payload(output_path), signing_key)
        Path(f"{output_path}.sig").write_text(signature, encoding="ascii")


def _verify_source_signature(
    input_path: str,
    *,
    public_key: str = "",
    allow_unsigned: bool = True,
) -> None:
    sig_path = Path(f"{input_path}.sig")
    if not public_key:
        if not sig_path.exists():
            logger.warning("数据包未签名（未配置 SYNC_PACKAGE_PUBKEY），仅做 AES-GCM/SHA256 校验")
        return
    if not sig_path.exists():
        if allow_unsigned:
            logger.warning("数据包未签名，但当前允许未签名导入（过渡期）")
            return
        raise ValueError("数据包缺少来源签名，已拒绝导入")
    from app.core.grant_signing import verify_payload

    if not verify_payload(
        _signature_payload(input_path),
        sig_path.read_text(encoding="ascii").strip(),
        public_key,
    ):
        raise ValueError("数据包来源签名验证失败：包已被替换或签名不匹配")


def extract_encrypted_package(
    input_path: str,
    password: str,
    *,
    public_key: str = "",
    allow_unsigned: bool = True,
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
            # 2026-10-28：此前直接 f-string 拼 bytes，用户看到的是 `b'\x02'` 这种
            # 乱码而不是「版本号」。按 ASCII 解码（非法字节用 \xNN 表示）后给出可读提示。
            raise ValueError(
                f"不支持的版本: {_as_text(version)}（本机支持 {_as_text(VERSION)}）"
            )

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

    _verify_source_signature(input_path, public_key=public_key, allow_unsigned=allow_unsigned)

    data = json.loads(data_json.decode("utf-8"))
    return data
