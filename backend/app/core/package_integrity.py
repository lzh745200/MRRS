"""包完整性校验（W27，修复 W26-P0-7）。

## 背景（W26 全栈检测）

四类「人带 U 盘」包中只有**单位授权包**有密码学完整性（`core/grant_signing` 的
Ed25519，`GRANT_ALLOW_UNSIGNED=False` fail-closed）；另外三类**完全没有校验**：

| 包类型 | 生成/导入端点 | 原完整性 |
|---|---|---|
| 单位授权包 `org_grants.py` | ✅ Ed25519 签名 + fail-closed | — |
| 管控配置包 `control_package.py` | ❌ 无 | 仅管理员 + ZIP |
| 系统配置包 `system/config_package.py` | ❌ 无 | 仅管理员 |
| 权限包 `permission_package.py` | ❌ 无 | 管理员 + loopback |

且 `manifest.checksum` 全仓**只写不校验**。

## 本模块策略（分层，兼顾安全与可用性）

1. **checksum（强制，无需密钥）**：对 manifest 的规范化 JSON 计算 SHA-256 并记录；
   导入时重算比对。可检出截断/损坏/简单篡改，且**不改变任何现有工作流**
   （应用内生成的包也能被校验）。
2. **Ed25519 签名（可选启用）**：
   * 配置了 ``PACKAGE_PUBKEY`` → 导入**要求**签名且验签通过，否则拒绝（fail-closed）；
   * 未配置 → 仅在日志中提示「未启用签名校验」，但 **checksum 仍强制**。
      理由：这三类包常由**同一个管理员**在另一台机器上生成后带回，若默认强制签名，
      在没有密钥基建的现场部署会**直接拒收自己刚生成的包**（功能中断）。
      需要防「载体被替换」的部署应配置 ``PACKAGE_PUBKEY``（生成方用私钥签名）。
3. 签名对象与 `grant_signing` 完全一致（规范化 JSON：`sort_keys` + 紧凑分隔符 + UTF-8），
   两套机制共用同一套规范化实现，避免"同一份包两种验签结果"。

## 与 `grant_signing` 的关系

直接复用 :func:`app.core.grant_signing.sign_payload` / :func:`verify_payload`，
**不重复实现** Ed25519 逻辑。
"""

import hashlib
import json
import logging
from typing import Any, Dict, Optional

from app.core.grant_signing import sign_payload, verify_payload

logger = logging.getLogger(__name__)

SIGNATURE_FIELD = "signature"
CHECKSUM_FIELD = "checksum"
# 参与签名/校验和计算的字段之外的两个元字段
_META_FIELDS = frozenset({SIGNATURE_FIELD, CHECKSUM_FIELD})


class PackageIntegrityError(ValueError):
    """包完整性校验失败（调用方应转 400 并给出可操作提示）。"""


def _canonical_bytes(manifest: Dict[str, Any]) -> bytes:
    """规范化 JSON 字节（与 ``grant_signing.canonical_bytes`` 同语义）。

    只剔除 ``signature`` 与 ``checksum`` 两个元字段 —— 其余字段（含 contents 计数）
    全部纳入校验范围。
    """
    body = {k: v for k, v in manifest.items() if k not in _META_FIELDS}
    return json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def compute_checksum(manifest: Dict[str, Any]) -> str:
    """manifest 的 SHA-256（hex），用于检出截断/损坏/简单篡改。"""
    return hashlib.sha256(_canonical_bytes(manifest)).hexdigest()


def sign_manifest(manifest: Dict[str, Any], private_key_hex: Optional[str]) -> Dict[str, Any]:
    """为 manifest 补 ``checksum``（必填）与 ``signature``（有私钥时），返回新字典。

    生成端调用：`manifest = sign_manifest(manifest, settings.PACKAGE_SIGNING_KEY)`。
    无私钥时只写 checksum —— 保证任何部署都能做完整性校验。
    """
    if not isinstance(manifest, dict):
        raise PackageIntegrityError("manifest 必须是对象")
    sealed = {k: v for k, v in manifest.items() if k not in _META_FIELDS}
    sealed[CHECKSUM_FIELD] = compute_checksum(sealed)
    if private_key_hex:
        sealed[SIGNATURE_FIELD] = sign_payload(sealed, private_key_hex)
    return sealed


def verify_manifest(
    manifest: Dict[str, Any],
    *,
    public_key_hex: Optional[str] = None,
    allow_unsigned: bool = True,
    package_label: str = "数据包",
) -> None:
    """校验 manifest 完整性，不通过抛 :class:`PackageIntegrityError`。

    Args:
        manifest: 从包内读出的 manifest.json 解析结果。
        public_key_hex: 部署内置的验签公钥；提供时**强制要求签名**。
        allow_unsigned: 允许无签名（仅在未配置公钥时生效）。
        package_label: 错误信息中的包类型名（"管控配置包" 等）。

    Raises:
        PackageIntegrityError: manifest 非对象 / checksum 缺失或不符 /
            配置了公钥但签名缺失或不匹配。
    """
    if not isinstance(manifest, dict):
        raise PackageIntegrityError(f"{package_label}的 manifest 不是有效对象")

    declared = manifest.get(CHECKSUM_FIELD)
    if not declared:
        raise PackageIntegrityError(
            f"{package_label}缺少 checksum，无法校验完整性；请用新版客户端重新生成该包"
        )
    actual = compute_checksum(manifest)
    if str(declared).lower() != actual:
        raise PackageIntegrityError(
            f"{package_label}完整性校验失败（checksum 不匹配）：包内容可能已被截断或篡改，"
            "请重新获取原始文件"
        )

    signature = manifest.get(SIGNATURE_FIELD)
    if public_key_hex:
        if not signature:
            raise PackageIntegrityError(
                f"本机已启用签名校验，但{package_label}未签名，已拒绝导入"
            )
        if not verify_payload(
            {k: v for k, v in manifest.items() if k != SIGNATURE_FIELD},
            str(signature),
            public_key_hex,
        ):
            raise PackageIntegrityError(
                f"{package_label}签名验证失败：来源不可信或包已被篡改，已拒绝导入"
            )
        return

    if not allow_unsigned:
        raise PackageIntegrityError(
            f"未配置包验签公钥（PACKAGE_PUBKEY），且当前策略禁止导入未签名包（{package_label}）"
        )
    if not signature:
        logger.info(
            "%s checksum 校验通过，但本机未配置 PACKAGE_PUBKEY，未做来源签名校验",
            package_label,
        )


def verify_optional_signature(
    manifest: Dict[str, Any],
    *,
    public_key_hex: Optional[str] = None,
    package_label: str = "数据包",
) -> None:
    """仅校验**可选签名**（适用于自带 checksum 机制的包，如权限配置包）。

    权限配置包已有 ``content_checksum``（`permission_package_service._verify_content_checksum`）
    负责内容完整性，本函数只补"来源可信"这一层：

    * 未配置 ``PACKAGE_PUBKEY`` → 不做签名校验（仅 debug 日志），
      保留旧包与无密钥基建的现场可用性；
    * 已配置 → 签名**必须存在且验签通过**，否则拒绝（fail-closed）。

    Raises:
        PackageIntegrityError: 已配置公钥但签名缺失/不匹配。
    """
    if not isinstance(manifest, dict):
        raise PackageIntegrityError(f"{package_label}的 manifest 不是有效对象")
    if not public_key_hex:
        logger.debug("%s 未配置 PACKAGE_PUBKEY，跳过签名校验（内容校验另由 checksum 承担）", package_label)
        return
    signature = manifest.get(SIGNATURE_FIELD)
    if not signature:
        raise PackageIntegrityError(
            f"本机已启用签名校验，但{package_label}未签名，已拒绝导入"
        )
    if not verify_payload(
        {k: v for k, v in manifest.items() if k != SIGNATURE_FIELD},
        str(signature),
        public_key_hex,
    ):
        raise PackageIntegrityError(
            f"{package_label}签名验证失败：来源不可信或包已被篡改，已拒绝导入"
        )


# W27：此处原有 verify_file_digest（ZIP 成员 SHA-256 校验）—— 因**从未接线**
# 到任何导入端点（仅有定义、无调用），属未使用死代码，已移除。
# 若将来需要"包内文件级校验"，应连同真实验签调用点一起加回并补回归测试，
# 不要留下"看起来能校验、实际没人调用"的假能力。
