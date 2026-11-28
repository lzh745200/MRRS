"""账号开通包签发密钥与跨机信任管理。

设计要点（与 `deliverables/跨机账号包-模块与权限设计.md` 的 S8 一致）：

* **私钥只在本机**：首次使用时自动生成 Ed25519 密钥并持久化到
  ``runtime_secrets.json``，不再要求现场配置 ``ACCOUNT_PACKAGE_SIGNING_KEY``。
  环境变量仍然优先，便于高级部署把私钥放到受控介质。
* **公钥不自动信任**：账号包包头内嵌签发公钥，只用于让目标机做完整性验签；
  是否信任该来源由人工带外核对的指纹决定，确认导入后才写入本机信任列表。
  这样既避免"包内自带公钥=自动信任"的伪造风险，也不要求目标机提前配环境变量。
* **本机公钥隐式信任**：本机签发的包在本机导入时无需再次核对。

本模块只做密钥/指纹/信任列表，不碰数据库；业务错误由 service 层映射。
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from typing import Iterable, List, Optional

from app.core.config import settings
from app.core.grant_signing import derive_public_key, generate_keypair
from app.utils import runtime_secrets

logger = logging.getLogger(__name__)

LOCAL_PRIVATE_KEY_NAME = "ACCOUNT_PACKAGE_SIGNING_KEY"
TRUSTED_PUBKEYS_NAME = "ACCOUNT_PACKAGE_TRUSTED_PUBKEYS"

_HEX64_RE = re.compile(r"^[0-9a-fA-F]{64}$")
_KEY_SPLIT_RE = re.compile(r"[\s,;]+")


class AccountPackageKeyError(RuntimeError):
    """签发密钥/信任公钥不可用（格式非法、无法持久化等）。"""


def _normalize_public_key(value: str) -> str:
    key = (value or "").strip()
    if not _HEX64_RE.match(key):
        raise AccountPackageKeyError("公钥格式非法（需 32 字节 hex，共 64 个十六进制字符）")
    return key.lower()


def key_fingerprint(public_hex: str) -> str:
    """公钥指纹：SHA-256 前 128 bit，按 4 位一组展示，便于人工核对。"""
    normalized = _normalize_public_key(public_hex)
    digest = hashlib.sha256(bytes.fromhex(normalized)).hexdigest().upper()
    short = digest[:32]
    return "-".join(short[i : i + 4] for i in range(0, 32, 4))


def _split_public_keys(raw: Optional[str]) -> List[str]:
    if not raw:
        return []
    return [item for item in _KEY_SPLIT_RE.split(str(raw)) if item]


def _validated_private_key(value: str) -> str:
    key = (value or "").strip()
    if not _HEX64_RE.match(key):
        raise AccountPackageKeyError("签名私钥格式非法（需 32 字节 hex，共 64 个十六进制字符）")
    try:
        derive_public_key(key)
    except Exception as exc:  # noqa: BLE001 - 统一转成业务可读错误
        raise AccountPackageKeyError("签名私钥无法解析") from exc
    return key


def _runtime_trusted_keys() -> List[str]:
    raw = runtime_secrets.get_secret(TRUSTED_PUBKEYS_NAME)
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        logger.warning("账号包信任公钥列表不是合法 JSON，已忽略")
        return []
    if not isinstance(parsed, list):
        logger.warning("账号包信任公钥列表不是数组，已忽略")
        return []
    result: List[str] = []
    for item in parsed:
        try:
            result.append(_normalize_public_key(str(item)))
        except AccountPackageKeyError:
            logger.warning("账号包信任公钥列表包含非法条目，已跳过")
    return result


def local_private_key(*, create: bool = False) -> str:
    """返回本机签发私钥；``create=False`` 时未配置返回空串。"""
    env_value = str(getattr(settings, "ACCOUNT_PACKAGE_SIGNING_KEY", "") or "").strip()
    if env_value:
        return _validated_private_key(env_value)

    stored = runtime_secrets.get_secret(LOCAL_PRIVATE_KEY_NAME)
    if stored:
        return _validated_private_key(stored)

    if not create:
        return ""

    private_hex, _ = generate_keypair()
    try:
        return runtime_secrets.get_or_create_secret(
            LOCAL_PRIVATE_KEY_NAME,
            generate=lambda: private_hex,
            require_persisted=True,
        )
    except Exception as exc:  # noqa: BLE001
        raise AccountPackageKeyError(
            "无法生成并持久化本机签发密钥，请检查数据目录写入权限"
        ) from exc


def local_public_key(*, create: bool = False) -> str:
    private_hex = local_private_key(create=create)
    return derive_public_key(private_hex) if private_hex else ""


def signing_key_source() -> str:
    """``environment`` / ``runtime`` / ``none``（不触发生成）。"""
    if str(getattr(settings, "ACCOUNT_PACKAGE_SIGNING_KEY", "") or "").strip():
        return "environment"
    if runtime_secrets.get_secret(LOCAL_PRIVATE_KEY_NAME):
        return "runtime"
    return "none"


def signing_key_info(*, create: bool = False) -> dict:
    """返回本机签发密钥摘要（含公钥与指纹），供页面展示/复制。"""
    private_hex = local_private_key(create=create)
    if not private_hex:
        return {
            "public_key": "",
            "fingerprint": "",
            "source": "none",
            "ready": False,
        }
    public_key = derive_public_key(private_hex)
    return {
        "public_key": public_key,
        "fingerprint": key_fingerprint(public_key),
        "source": signing_key_source(),
        "ready": True,
    }


def trusted_public_keys() -> List[str]:
    """本机信任的签发公钥（环境变量 + 信任列表 + 本机公钥），已去重。"""
    candidates: List[str] = []
    for raw in _split_public_keys(str(getattr(settings, "ACCOUNT_PACKAGE_PUBKEY", "") or "")):
        try:
            candidates.append(_normalize_public_key(raw))
        except AccountPackageKeyError:
            logger.warning("ACCOUNT_PACKAGE_PUBKEY 含非法公钥，已跳过")
    candidates.extend(_runtime_trusted_keys())
    local_public = local_public_key(create=False)
    if local_public:
        candidates.append(local_public)
    return _dedupe(candidates)


def verification_public_keys(extra: Optional[Iterable[str]] = None) -> List[str]:
    keys = trusted_public_keys()
    if extra:
        for raw in extra:
            try:
                keys.append(_normalize_public_key(raw))
            except AccountPackageKeyError:
                logger.warning("验签候选公钥含非法条目，已跳过")
    return _dedupe(keys)


def add_trusted_public_key(public_hex: str) -> str:
    """把公钥加入本机信任列表，返回指纹；重复添加幂等。"""
    normalized = _normalize_public_key(public_hex)
    keys = _runtime_trusted_keys()
    if normalized not in keys:
        keys.append(normalized)
        _write_trusted_keys(keys)
    return key_fingerprint(normalized)


def remove_trusted_public_key(fingerprint: str) -> bool:
    """按指纹移除信任公钥；返回是否真的移除了。"""
    target = (fingerprint or "").strip().upper().replace(" ", "")
    if not target:
        return False
    keys = _runtime_trusted_keys()
    remaining = [key for key in keys if key_fingerprint(key) != target]
    if len(remaining) == len(keys):
        return False
    _write_trusted_keys(remaining)
    return True


def trusted_key_info() -> List[dict]:
    return [
        {"public_key": key, "fingerprint": key_fingerprint(key)}
        for key in _runtime_trusted_keys()
    ]


def _write_trusted_keys(keys: List[str]) -> None:
    try:
        runtime_secrets.set_secret(TRUSTED_PUBKEYS_NAME, json.dumps(keys))
    except Exception as exc:  # noqa: BLE001
        raise AccountPackageKeyError("无法持久化信任公钥列表，请检查数据目录写入权限") from exc


def _dedupe(items: Iterable[str]) -> List[str]:
    seen = set()
    result: List[str] = []
    for item in items:
        if item and item not in seen:
            seen.add(item)
            result.append(item)
    return result
