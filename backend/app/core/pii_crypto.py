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
                require_persisted=True,
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


#: W18-offline P1-1：解密失败的可观测信号。原实现只写一条 error 日志就原样
#: 返回密文 —— 换机/重装（密钥漂移）后用户在 UI 看到 "enc.v1:..." 却不知所以，
#: 继续编辑保存会把密文固化成永久损坏。这里累计失败次数与首末时间，诊断包
#: （/system/diagnostics）据此能说出「当前密钥解不开 N 个字段」这一事实。
_decrypt_failures: dict = {"count": 0, "first_seen": None, "last_seen": None}


def decrypt_failure_stats() -> dict:
    """解密失败累计统计（只读快照，供诊断包消费）。"""
    return dict(_decrypt_failures)


def reset_decrypt_failure_stats() -> None:
    """清零统计（测试用 / 密钥修复后由运维动作调用）。"""
    _decrypt_failures.update({"count": 0, "first_seen": None, "last_seen": None})


def decrypt_pii(value: Optional[str]) -> Optional[str]:
    """标记密文 → 明文；未标记（历史明文/异常数据）原样返回；解密失败记日志后原样返回。

    W18-offline P1-1：解密失败不再只是静默 —— 除日志外累计失败计数与时间，
    供诊断包/预检暴露「密钥漂移」这一现场事实。
    """
    # 先排除 None：mypy 无法从 is_encrypted 收窄 Optional，且 None 本就该原样返回
    if value is None or not is_encrypted(value):
        return value
    try:
        raw = base64.b64decode(value[len(MARKER):])
        return _aessiv().decrypt(raw, [_ASSOC_DATA]).decode("utf-8")
    except Exception as e:
        from datetime import datetime, timezone

        logger.error("PII 字段解密失败（密钥不匹配或数据损坏）: %s", e)
        _stats = _decrypt_failures
        _stats["count"] += 1
        _now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        if _stats["first_seen"] is None:
            _stats["first_seen"] = _now
        _stats["last_seen"] = _now
        return value


def reset_key_cache() -> None:
    """重置密钥缓存（测试用）"""
    global _key_cache
    _key_cache = None


def key_fingerprint() -> str:
    """当前 PII 密钥的指纹（SHA-256 前 16 位十六进制）。

    W18-B：换机/重装后「库里的密文还能不能解」取决于密钥是否同一把，
    但密钥本身不能出机器。指纹只用于**比对**：两台机器、或备份清单与当前
    机器指纹不一致，就说明密钥漂移了，无需暴露密钥内容。
    """
    return hashlib.sha256(_load_key()).hexdigest()[:16]


def self_check(probe: str = "pii-self-check") -> None:
    """自检：当前密钥必须能完成一次「加密 → 解密」往返。

    为什么需要：轮换密钥/重启换环境后，`decrypt_pii` 的失败是**逐字段静默降级**
    （原样返回密文，页面显示 enc.v1:…），运维看到的是"数据变成乱码"而不是"密钥错了"。
    在危险操作（密钥轮换）后跑一次往返，能把「成功但不可用」变成**当场可见的失败**。
    """
    cipher = encrypt_pii(probe)
    if not cipher or not is_encrypted(cipher):
        raise RuntimeError("PII 自检失败：加密结果没有密文标记，当前密钥不可用于写入")
    back = decrypt_pii(cipher)
    if back != probe:
        raise RuntimeError("PII 自检失败：解密往返不一致，当前密钥与写入密钥不匹配")
