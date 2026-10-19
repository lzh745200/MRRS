"""授权包签名（R33）—— Ed25519。

## 为什么需要

授权包要经 U 盘/内网摆渡在单位之间传递，**可被截获但不可被篡改**。上级用私钥签名，
下级把公钥内置在安装件里，导入时验签 —— 拿到包的人无法伪造"更高权限"的包。

## 威胁模型边界

只防**篡改**，不防**逆向**：公钥内置在安装包里可以被提取，但提取公钥无法伪造签名。
若需要防逆向，得配合代码签名与安全启动，不在本模块职责内。

## 规范化

签名对象是**规范化 JSON**（`sort_keys` + 紧凑分隔符 + UTF-8），保证同样的语义在任何
机器上产出同样的字节序列 —— 否则同一份授权包在不同环境验签结果会不一致。
"""

from __future__ import annotations

import json
from typing import Any, Dict, Tuple

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

# 签名覆盖的字段（签名本身不参与签名）
SIGNATURE_FIELD = "signature"


class GrantSigningError(ValueError):
    """签名/验签相关错误（密钥格式非法、签名不匹配等）。"""


def canonical_bytes(payload: Dict[str, Any]) -> bytes:
    """规范化 JSON 字节：排序键 + 紧凑分隔符 + UTF-8。"""
    body = {k: v for k, v in payload.items() if k != SIGNATURE_FIELD}
    return json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def generate_keypair() -> Tuple[str, str]:
    """生成 (私钥 hex, 公钥 hex)，均为 32 字节原始私钥/公钥。"""
    private_key = Ed25519PrivateKey.generate()
    private_hex = private_key.private_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PrivateFormat.Raw,
        encryption_algorithm=serialization.NoEncryption(),
    ).hex()
    public_hex = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    ).hex()
    return private_hex, public_hex


def _load_private(private_hex: str) -> Ed25519PrivateKey:
    try:
        raw = bytes.fromhex(private_hex)
        return Ed25519PrivateKey.from_private_bytes(raw)
    except (ValueError, TypeError) as exc:
        raise GrantSigningError("签名私钥格式非法（需 32 字节 hex）") from exc


def _load_public(public_hex: str) -> Ed25519PublicKey:
    try:
        raw = bytes.fromhex(public_hex)
        return Ed25519PublicKey.from_public_bytes(raw)
    except (ValueError, TypeError) as exc:
        raise GrantSigningError("验签公钥格式非法（需 32 字节 hex）") from exc


def sign_payload(payload: Dict[str, Any], private_hex: str) -> str:
    """对 payload（不含 signature 字段）签名，返回签名 hex。"""
    if not private_hex:
        raise GrantSigningError("未配置签名私钥")
    return _load_private(private_hex).sign(canonical_bytes(payload)).hex()


def verify_payload(payload: Dict[str, Any], signature_hex: str, public_hex: str) -> bool:
    """验签。签名/密钥格式非法或签名不匹配均返回 False（不抛异常，便于调用方统一报错）。"""
    if not signature_hex or not public_hex:
        return False
    try:
        signature = bytes.fromhex(signature_hex)
        public_key = _load_public(public_hex)
        public_key.verify(signature, canonical_bytes(payload))
        return True
    except (InvalidSignature, ValueError, TypeError, GrantSigningError):
        return False
