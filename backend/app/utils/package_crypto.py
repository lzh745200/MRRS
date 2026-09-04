"""权限包加密/机器码绑定辅助 (Phase E)。

S1 修复：口令密钥派生从裸 SHA-256 升级为 PBKDF2-HMAC-SHA256（随机 salt +
迭代拉伸），复用系统统一的 :class:`PasswordEncryptionService`（OWASP 推荐
100000 次迭代 / 32 字节随机 salt），杜绝离线字典破解风险。

向后兼容：历史权限包以裸 Fernet token（无包头）形式落盘，用旧 SHA-256 派生
密钥加密。本模块用「魔术包头」区分新旧格式：
  * 新格式：``_MAGIC`` + 4 字节迭代数(大端) + 32 字节 salt + Fernet token，
    走 PBKDF2 解密；
  * 旧格式：无魔术包头（裸 Fernet token），回退 SHA-256 解密。
:func:`looks_encrypted` 同时识别两种格式，确保旧加密包仍可导入。
"""
from cryptography.fernet import Fernet, InvalidToken
import base64
import hashlib
import struct

from app.services.password_encryption_service import PasswordEncryptionService

# 新格式魔术包头（二进制，绝不与裸 Fernet token 的 base64url 文本或 ZIP 的
# 'PK' 前缀冲突）。长度固定，便于 looks_encrypted 快速判定。
_MAGIC = b"BKPKGv2\x00"

# PBKDF2 迭代次数（与系统数据包加密保持同一强度口径）
_ITERATIONS = PasswordEncryptionService.DEFAULT_ITERATIONS
_SALT_LEN = PasswordEncryptionService.SALT_LENGTH  # 32 字节

# 新格式包头固定长度 = 魔术头 + 4 字节迭代数 + salt。短于此即截断/损坏。
_HEADER_LEN = len(_MAGIC) + 4 + _SALT_LEN


def _legacy_fernet_from_password(password: str) -> Fernet:
    """[已弃用] 由口令直接派生 Fernet 密钥（SHA-256 → urlsafe-b64）。

    仅保留用于解密历史旧格式权限包（向后兼容），新加密一律走 PBKDF2。
    """
    digest = hashlib.sha256(password.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt_bytes(data: bytes, password: str) -> bytes:
    """加密权限包字节（新格式：PBKDF2 + 随机 salt + 迭代拉伸）。

    输出结构::

        _MAGIC | iterations(uint32 BE) | salt(32B) | fernet_token
    """
    salt = PasswordEncryptionService.generate_salt()
    token = PasswordEncryptionService.encrypt_data(data, password, salt, _ITERATIONS)
    return _MAGIC + struct.pack(">I", _ITERATIONS) + salt + token


def decrypt_bytes(token: bytes, password: str) -> bytes:
    """解密权限包字节；密码错误抛 InvalidToken（新格式）或 InvalidPasswordError。

    自动识别格式：带 ``_MAGIC`` 包头走 PBKDF2；无包头回退旧 SHA-256（兼容旧包）。
    """
    if _is_new_format(token):
        iterations, salt, cipher = _parse_header(token)
        # 统一以 InvalidToken 语义抛出（与旧格式一致，调用方按“密码错误/损坏”处理）
        try:
            return PasswordEncryptionService.decrypt_data(cipher, password, salt, iterations)
        except Exception as exc:  # InvalidPasswordError → 归一化为 InvalidToken
            raise InvalidToken(str(exc)) from exc
    # 旧格式：裸 Fernet token（SHA-256 派生），密码错误抛 InvalidToken
    return _legacy_fernet_from_password(password).decrypt(token)


def _is_new_format(raw: bytes) -> bool:
    return bool(raw) and raw.startswith(_MAGIC)


def _parse_header(raw: bytes):
    """解析新格式包头，返回 (iterations, salt, cipher_bytes)。

    Raises:
        InvalidToken: 包头被截断（长度不足 _HEADER_LEN）。必须以 InvalidToken
            抛出而非让 struct.error 逃逸 —— 该异常发生在 decrypt_bytes 的 try
            块之前，逃逸后会变成未分类 500，而调用方按 InvalidToken 语义
            统一处理为「密码错误或包已损坏」。
    """
    if len(raw) < _HEADER_LEN:
        raise InvalidToken("权限包格式损坏（包头被截断）")
    offset = len(_MAGIC)
    iterations = struct.unpack(">I", raw[offset:offset + 4])[0]
    offset += 4
    salt = raw[offset:offset + _SALT_LEN]
    offset += _SALT_LEN
    cipher = raw[offset:]
    return iterations, salt, cipher


def looks_encrypted(raw: bytes) -> bool:
    """判断字节流是否为加密权限包（识别新旧两种格式）。"""
    if not raw:
        return False
    # ZIP 以 'PK' 开始 → 明文
    if raw.startswith(b"PK"):
        return False
    # 新格式：魔术包头
    if _is_new_format(raw):
        return True
    # 旧格式：Fernet token 以版本字节 0x80 开始且 base64url 字符集
    try:
        raw_b64 = base64.urlsafe_b64decode(raw)
        return raw_b64[:1] == b"\x80"
    except Exception:
        return False
