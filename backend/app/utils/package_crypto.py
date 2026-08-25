"""权限包加密/机器码绑定辅助 (Phase E)。"""
from cryptography.fernet import Fernet
import base64
import hashlib


def _fernet_from_password(password: str) -> Fernet:
    """由口令派生 Fernet 密钥（SHA-256 → urlsafe-b64）。"""
    digest = hashlib.sha256(password.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt_bytes(data: bytes, password: str) -> bytes:
    return _fernet_from_password(password).encrypt(data)


def decrypt_bytes(token: bytes, password: str) -> bytes:
    """解密；密码错误抛 InvalidToken。"""
    return _fernet_from_password(password).decrypt(token)


def looks_encrypted(raw: bytes) -> bool:
    # Fernet token 以版本字节 0x80 开始且 base64url 字符集；ZIP 以 'PK' 开始
    if raw.startswith(b"PK"):
        return False
    try:
        raw_b64 = base64.urlsafe_b64decode(raw)
        return raw_b64[:1] == b"\x80"
    except Exception:
        return False
