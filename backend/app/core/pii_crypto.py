"""
PII 字段透明加密（W5-T7 / ADR-0005）

设计要点：
- **确定性加密（AES-SIV, RFC 5297）**：同一明文恒得同一密文，等值查询
  （WHERE phone = :v）经 TypeDecorator 绑定参数加密后可直接命中密文，
  ORM 读写与既有查询零改动。
- **密文标记前缀** `enc.v1:`：迁移回填与读取侧据此识别是否已加密，
  兼容历史明文行（未标记的值解密侧原样返回，不再二次加密）。
- **密钥来源**（与 encryption_service._get_cipher 同优先级语义）：
  1. 显式配置的 ENCRYPTION_KEY（SHA-512 派生 64 字节 AESSIV 密钥）
     —— 多机离线同步部署应配置相同 ENCRYPTION_KEY，密文才可跨机互导；
  2. 运行时密钥存储持久化的 PII_AESSIV_KEY（单机部署自动生成，跨重启保持）。
- 泄漏面：确定性加密暴露等值关系（同号可识别），不暴露明文；
  身份证/电话无范围查询需求，属可接受权衡（见 ADR-0005）。
"""
import base64
import hashlib
import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

MARKER = "enc.v1:"
_ASSOC_DATA = b"pii-field"
_key_cache: Optional[bytes] = None


def _load_key() -> bytes:
    """加载或生成 64 字节 AESSIV 密钥（SHA-512 派生，带缓存）"""
    global _key_cache
    if _key_cache is not None:
        return _key_cache

    from app.core.config import settings

    secret = (getattr(settings, "ENCRYPTION_KEY", None) or "").strip()
    if secret:
        logger.info("PII 加密密钥已从 ENCRYPTION_KEY 派生")
    else:
        try:
            from app.utils.runtime_secrets import get_or_create_secret

            secret = get_or_create_secret(
                "PII_AESSIV_KEY",
                generate=lambda: base64.b64encode(os.urandom(64)).decode(),
            )
            logger.info("PII 加密密钥已从运行时密钥存储加载")
        except Exception as e:
            raise RuntimeError(
                "PII 加密密钥初始化失败：既无显式 ENCRYPTION_KEY，也无法读写 runtime_secrets.json。"
                "请检查文件权限和磁盘空间。"
            ) from e

    _key_cache = hashlib.sha512(secret.encode("utf-8")).digest()  # 512-bit → AESSIV-512
    return _key_cache


def _aessiv():
    from cryptography.hazmat.primitives.ciphers.aead import AESSIV

    return AESSIV(_load_key())


def is_encrypted(value: Optional[str]) -> bool:
    return isinstance(value, str) and value.startswith(MARKER)


def encrypt_pii(value: Optional[str]) -> Optional[str]:
    """明文 → 标记密文；None 与已加密值原样返回"""
    if value is None or is_encrypted(value):
        return value
    ct = _aessiv().encrypt(value.encode("utf-8"), [_ASSOC_DATA])
    return MARKER + base64.b64encode(ct).decode("ascii")


def decrypt_pii(value: Optional[str]) -> Optional[str]:
    """标记密文 → 明文；未标记（历史明文/异常数据）原样返回；解密失败记日志后原样返回"""
    if not is_encrypted(value):
        return value
    try:
        raw = base64.b64decode(value[len(MARKER):])
        return _aessiv().decrypt(raw, [_ASSOC_DATA]).decode("utf-8")
    except Exception as e:
        logger.error("PII 字段解密失败（密钥不匹配或数据损坏）: %s", e)
        return value


def reset_key_cache() -> None:
    """重置密钥缓存（测试用）"""
    global _key_cache
    _key_cache = None
