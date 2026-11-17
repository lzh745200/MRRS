"""账号开通包（account package）—— 外层明文头 + 密文体 + Ed25519 签名。

设计要点（对应 ``deliverables/账号开通包实施方案.md`` §十六/§十七）：

1. **签名面**：签名只覆盖**外层公开头**（含 ``cipher_sha256``），因为真正的清单在密文里，
   目标机在解密前读不到它。校验顺序固定为「验签 → 校验 KDF 参数 → 派生 → 解密 → 内层校验」。
2. **凭据**：包内只有每个账号的 **bcrypt(包专用 OTP)**；OTP 明文一次性展示给管理员，
   不落库、不进日志。
3. **KDF 下限**：``package_crypto`` 的包头下限只有 1 万（兼容历史包），账号包在本层
   强制 310k~1,000,000、默认 600,000，且**先校验再派生**，避免伪造低迭代拖垮本机或
   降低离线破解成本。
4. **fail-closed**：未配置公钥时**拒绝解开**（不存在"未签名也能导"的兼容路径）。

本模块只做格式与密码学，不做数据库与 HTTP。
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import struct
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, Optional, cast

from cryptography.fernet import InvalidToken

from app.core.grant_signing import sign_payload, verify_payload
from app.services.password_encryption_service import (
    InvalidPasswordError,
    PasswordEncryptionService,
)

#: 文件魔术头（版本 1），用于快速识别与拒绝非本类文件
PACKAGE_MAGIC = b"ACCTPKG1"

#: 包格式版本
FORMAT_VERSION = 1

#: KDF 参数（账号包专用，不复用 package_crypto 的 100k 默认值）
KDF_ALGORITHM = "pbkdf2_hmac_sha256"
KDF_DEFAULT_ITERATIONS = 600_000
KDF_MIN_ITERATIONS = 310_000
KDF_MAX_ITERATIONS = 1_000_000
SALT_LENGTH = 32

#: 默认有效期（天）
DEFAULT_VALID_DAYS = 7

#: OTP 字节数（128 bit）
OTP_BYTES = 16

_HEADER_LEN_SIZE = 4
MAX_PACKAGE_BYTES = 10 * 1024 * 1024
MAX_HEADER_BYTES = 64 * 1024


class AccountPackageError(ValueError):
    """账号包格式/校验失败；``code`` 供 API 层映射为稳定的错误码。"""

    code = "ACCOUNT_PACKAGE_INVALID"

    def __init__(self, message: str, *, code: Optional[str] = None) -> None:
        super().__init__(message)
        if code:
            self.code = code


class AccountPackageExpired(AccountPackageError):
    code = "ACCOUNT_PACKAGE_EXPIRED"


class AccountPackageUnsigned(AccountPackageError):
    code = "ACCOUNT_PACKAGE_UNSIGNED"


class AccountPackageBadSignature(AccountPackageError):
    code = "ACCOUNT_PACKAGE_BAD_SIGNATURE"


class AccountPackageBadKdf(AccountPackageError):
    code = "ACCOUNT_PACKAGE_BAD_KDF"


def generate_otp() -> str:
    """生成 128-bit 包专用一次性口令（32 位十六进制）。"""
    return secrets.token_bytes(OTP_BYTES).hex()


def canonical_bytes(payload: Dict[str, Any]) -> bytes:
    """规范 JSON（sort_keys + 紧凑分隔符），签名与校验共用。"""
    return json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def _sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat()


def _parse_iso(value: Any, field: str) -> datetime:
    if not isinstance(value, str) or not value:
        raise AccountPackageError(f"包头的 {field} 缺失或非法")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:  # pragma: no cover - 防御非法时间串
        raise AccountPackageError(f"包头的 {field} 不是合法时间") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _validate_kdf(kdf: Any) -> int:
    """校验并返回迭代数；不合规一律拒绝（先校验后派生）。"""
    if not isinstance(kdf, dict):
        raise AccountPackageBadKdf("包头的 KDF 参数缺失")
    if kdf.get("algorithm") != KDF_ALGORITHM:
        raise AccountPackageBadKdf("不支持的 KDF 算法")
    iterations = kdf.get("iterations")
    if not isinstance(iterations, int) or isinstance(iterations, bool):
        raise AccountPackageBadKdf("KDF 迭代数缺失或非整数")
    if not (KDF_MIN_ITERATIONS <= iterations <= KDF_MAX_ITERATIONS):
        raise AccountPackageBadKdf(
            f"KDF 迭代数超出允许区间（{KDF_MIN_ITERATIONS}~{KDF_MAX_ITERATIONS}）"
        )
    return iterations


def build_manifest(
    *,
    package_id: str,
    organization_code: str,
    target_machine_code: str,
    items: Iterable[Dict[str, Any]],
    created_at: Optional[datetime] = None,
    valid_days: int = DEFAULT_VALID_DAYS,
) -> Dict[str, Any]:
    """组装内层清单（会被加密）。

    ``items`` 每项至少包含 ``username`` / ``credential_hash`` / ``role`` / ``data_scope``；
    其余字段原样保留，由导入端做白名单校验，不在此处信任。
    """
    created = created_at or _utcnow()
    expires = created + timedelta(days=max(1, int(valid_days)))
    prepared = []
    for item in items:
        if not isinstance(item, dict):
            raise AccountPackageError("清单条目必须是对象")
        prepared.append(dict(item))
    if not prepared:
        raise AccountPackageError("清单为空，账号包至少要包含一个账号")
    return {
        "format": "account-package",
        "version": FORMAT_VERSION,
        "package_id": package_id,
        "organization_code": organization_code,
        "target_machine_code": target_machine_code,
        "created_at": _iso(created),
        "expires_at": _iso(expires),
        "items": prepared,
    }


def seal_package(
    manifest: Dict[str, Any],
    *,
    password: str,
    private_key_hex: str,
    iterations: int = KDF_DEFAULT_ITERATIONS,
    salt: Optional[bytes] = None,
) -> bytes:
    """加密 + 签名，返回落盘字节。

    结构：``MAGIC | uint32(header_len) | header_json | fernet_token``。
    签名只覆盖 header；header 里带 ``cipher_sha256`` 与 ``manifest_sha256``，
    因此密文或清单任一被改都会在解密前后被发现。
    """
    if not password:
        raise AccountPackageError("账号包必须设置导入口令")
    if not private_key_hex:
        raise AccountPackageUnsigned("导出端未配置签名私钥，拒绝生成未签名账号包")
    if not (KDF_MIN_ITERATIONS <= iterations <= KDF_MAX_ITERATIONS):
        raise AccountPackageBadKdf("导出端 KDF 迭代数超出允许区间")

    manifest_bytes = canonical_bytes(manifest)
    salt_bytes = salt or os.urandom(SALT_LENGTH)
    cipher = PasswordEncryptionService.encrypt_data(
        manifest_bytes, password, salt_bytes, iterations
    )

    header: Dict[str, Any] = {
        "format": "account-package",
        "version": FORMAT_VERSION,
        "package_id": manifest.get("package_id"),
        "organization_code": manifest.get("organization_code"),
        "target_machine_code": manifest.get("target_machine_code"),
        "created_at": manifest.get("created_at"),
        "expires_at": manifest.get("expires_at"),
        "item_count": len(manifest.get("items") or []),
        "kdf": {
            "algorithm": KDF_ALGORITHM,
            "iterations": iterations,
            "salt_hex": salt_bytes.hex(),
        },
        "manifest_sha256": _sha256_hex(manifest_bytes),
        "cipher_sha256": _sha256_hex(cipher),
        "cipher_len": len(cipher),
    }
    header["signature"] = sign_payload(header, private_key_hex)
    header_bytes = canonical_bytes(header)

    return (
        PACKAGE_MAGIC
        + struct.pack(">I", len(header_bytes))
        + header_bytes
        + cipher
    )


def _split_package(raw: bytes) -> tuple[Dict[str, Any], bytes]:
    if not isinstance(raw, (bytes, bytearray)):
        raise AccountPackageError("账号包内容不是字节流")
    data = bytes(raw)
    if len(data) > MAX_PACKAGE_BYTES:
        raise AccountPackageError("账号包超过大小上限", code="ACCOUNT_PACKAGE_TOO_LARGE")
    if not data.startswith(PACKAGE_MAGIC):
        raise AccountPackageError("不是账号开通包（魔术头不匹配）", code="ACCOUNT_PACKAGE_BAD_MAGIC")
    offset = len(PACKAGE_MAGIC)
    if len(data) < offset + _HEADER_LEN_SIZE:
        raise AccountPackageError("账号包被截断（缺少包头长度）")
    (header_len,) = struct.unpack(">I", data[offset : offset + _HEADER_LEN_SIZE])
    offset += _HEADER_LEN_SIZE
    if header_len <= 0 or header_len > MAX_HEADER_BYTES:
        raise AccountPackageError("包头长度非法")
    if len(data) < offset + header_len:
        raise AccountPackageError("账号包被截断（包头不完整）")
    try:
        header = json.loads(data[offset : offset + header_len].decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AccountPackageError("包头不是合法 JSON") from exc
    if not isinstance(header, dict) or header.get("format") != "account-package":
        raise AccountPackageError("包头格式不正确")
    return header, data[offset + header_len :]


def inspect_package(raw: bytes) -> Dict[str, Any]:
    """只读查看外层头（不需要口令，也不解密），用于 UI 预览"包是给谁的"。"""
    header, cipher = _split_package(raw)
    public = {k: v for k, v in header.items() if k != "signature"}
    public["cipher_len"] = len(cipher)
    public["signed"] = bool(header.get("signature"))
    return public


def _verify_header_signature(header: Dict[str, Any], public_key_hex: Optional[str]) -> None:
    """验签只覆盖包头（含 cipher_sha256）；未签名或未配公钥都拒绝。"""
    signature = header.get("signature")
    if not signature:
        raise AccountPackageUnsigned("账号包未签名，拒绝导入")
    if not public_key_hex:
        raise AccountPackageUnsigned(
            "本机未配置 ACCOUNT_PACKAGE_PUBKEY，无法校验账号包来源（fail-closed）"
        )
    unsigned_header = {k: v for k, v in header.items() if k != "signature"}
    if not verify_payload(unsigned_header, signature, public_key_hex):
        raise AccountPackageBadSignature("账号包签名校验失败（可能被篡改或来源不符）")


def _extract_salt(kdf: Dict[str, Any]) -> bytes:
    try:
        salt = bytes.fromhex(kdf.get("salt_hex") or "")
    except (TypeError, ValueError) as exc:
        raise AccountPackageBadKdf("KDF salt 不是合法十六进制") from exc
    if len(salt) != SALT_LENGTH:
        raise AccountPackageBadKdf("KDF salt 长度不正确")
    return salt


def _decode_manifest(plain: bytes, header: Dict[str, Any]) -> Dict[str, Any]:
    try:
        manifest = json.loads(plain.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AccountPackageError("账号包清单不是合法 JSON") from exc
    if not isinstance(manifest, dict) or manifest.get("format") != "account-package":
        raise AccountPackageError("账号包清单格式不正确")
    if not isinstance(manifest.get("items"), list) or not manifest["items"]:
        raise AccountPackageError("账号包清单为空")
    if manifest.get("package_id") != header.get("package_id"):
        raise AccountPackageBadSignature("包头与清单的 package_id 不一致")
    return manifest


def open_package(
    raw: bytes,
    *,
    password: str,
    public_key_hex: Optional[str],
    now: Optional[datetime] = None,
) -> Dict[str, Any]:
    """验签 → 校验 KDF → 解密 → 校验清单，返回内层 manifest。

    任何一步失败都抛 :class:`AccountPackageError` 子类；调用方不应把底层异常细节透给用户。
    """
    if not password:
        raise AccountPackageError("请输入账号包导入口令")
    header, cipher = _split_package(raw)

    if int(header.get("version") or 0) != FORMAT_VERSION:
        raise AccountPackageError("账号包版本不受支持")

    _verify_header_signature(header, public_key_hex)

    expected_cipher_sha = header.get("cipher_sha256")
    if not isinstance(expected_cipher_sha, str) or not hmac.compare_digest(
        _sha256_hex(cipher), expected_cipher_sha
    ):
        raise AccountPackageBadSignature("账号包密文校验失败（密文被替换或截断）")

    expires_at = _parse_iso(header.get("expires_at"), "expires_at")
    if (now or _utcnow()) > expires_at:
        raise AccountPackageExpired("账号包已过期，请让源机管理员重新导出")

    kdf = header.get("kdf")
    iterations = _validate_kdf(kdf)
    salt = _extract_salt(cast(Dict[str, Any], kdf))

    try:
        plain = PasswordEncryptionService.decrypt_data(cipher, password, salt, iterations)
    except (InvalidPasswordError, InvalidToken, ValueError, TypeError) as exc:  # 统一按口令错/损坏处理
        raise AccountPackageError(
            "账号包解密失败（口令错误或文件损坏）", code="ACCOUNT_PACKAGE_DECRYPT_FAILED"
        ) from exc

    if not hmac.compare_digest(_sha256_hex(plain), str(header.get("manifest_sha256") or "")):
        raise AccountPackageError("账号包清单校验失败（解密后内容与包头不一致）")

    return _decode_manifest(plain, header)
