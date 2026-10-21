"""授权包构建 / 解析 / 应用（R33）。

## 为什么是"文件包"而不是接口

下级单位**没有超级管理员、完全离线**：上级无法把授权推过去，只能生成一个文件包，
经 U 盘或内网摆渡送达，下级导入后**只读执行**。

## 包格式（JSON，便于审计与人工核对）

```json
{
  "format": "r33-grant-package",
  "format_version": 1,
  "org_code": "C001",
  "org_name": "某某县民政局",
  "parent_codes": ["S001", "M001"],
  "version": 5,
  "issued_at": "2026-10-19T08:00:00+00:00",
  "grants": {"projects": "edit", "funds": "view"},
  "signature": "<ed25519 hex>"
}
```

## 导入时的六道校验（任一不过即拒绝）

1. 格式与版本号受支持；
2. 必填字段齐备、`grants` 级别合法；
3. 签名有效（未签名且未显式允许 → 拒绝）；
4. `org_code` 与本机单位一致；
5. `version` **严格大于**本机当前版本（拒绝降级，防"用旧包回滚扩权"）；
6. 写入后递增 `grant_version` 并清缓存。

## 为什么拒绝降级

旧包里可能有已被收回的授权。允许降级导入 = 允许拿一份历史包把权限"倒回去"，
这是离线分发场景下最容易被利用的路径。
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Union

from sqlalchemy.orm import Session

from app.core.grant_signing import (
    SIGNATURE_FIELD,
    sign_payload,
    verify_payload,
)
from app.core.transaction import safe_commit
from app.models.org_grant import VALID_GRANT_LEVELS, OrgGrant
from app.models.organization import Organization

PACKAGE_FORMAT = "r33-grant-package"
PACKAGE_FORMAT_VERSION = 1
SUPPORTED_FORMAT_VERSIONS = frozenset({1})

REQUIRED_FIELDS = ("format", "format_version", "org_code", "version", "grants")


class GrantPackageError(ValueError):
    """授权包不合法 / 不可应用。消息直接面向运维人员，需可读。"""


def _validate_grants(grants: Any) -> Dict[str, str]:
    if not isinstance(grants, dict):
        raise GrantPackageError("grants 必须是对象（module_key -> level）")
    cleaned: Dict[str, str] = {}
    for key, level in grants.items():
        if not isinstance(key, str) or not key:
            raise GrantPackageError("grants 的 module_key 必须是非空字符串")
        if level not in VALID_GRANT_LEVELS:
            raise GrantPackageError(
                "模块 %s 的授权级别 %r 非法（仅支持 %s）"
                % (key, level, "/".join(sorted(VALID_GRANT_LEVELS)))
            )
        cleaned[key] = level
    return cleaned


def build_package(
    *,
    org_code: str,
    grants: Dict[str, str],
    version: int,
    org_name: Optional[str] = None,
    parent_codes: Optional[list] = None,
    issued_at: Optional[str] = None,
    private_key: str = "",
) -> Dict[str, Any]:
    """构建授权包；给了 `private_key` 就签名（上级侧用）。"""
    if not org_code:
        raise GrantPackageError("org_code 不能为空")
    if not isinstance(version, int) or isinstance(version, bool) or version <= 0:
        raise GrantPackageError("version 必须是正整数")

    package: Dict[str, Any] = {
        "format": PACKAGE_FORMAT,
        "format_version": PACKAGE_FORMAT_VERSION,
        "org_code": org_code,
        "version": version,
        "grants": _validate_grants(grants),
        "issued_at": issued_at or datetime.now(timezone.utc).isoformat(),
    }
    if org_name:
        package["org_name"] = org_name
    if parent_codes:
        package["parent_codes"] = list(parent_codes)

    if private_key:
        package[SIGNATURE_FIELD] = sign_payload(package, private_key)
    return package


def export_package_bytes(package: Dict[str, Any]) -> bytes:
    """导出为可读 JSON（缩进 + 排序键），便于人工核对与归档。

    注意：签名校验不依赖序列化格式（`verify_payload` 用规范化字节重算），
    所以这里缩进美化不会破坏签名。
    """
    return json.dumps(package, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")


def parse_package(raw: Union[bytes, str, Dict[str, Any]]) -> Dict[str, Any]:
    """解析并做结构校验（不验签、不碰库）。"""
    if isinstance(raw, dict):
        package = raw
    else:
        try:
            text = raw.decode("utf-8") if isinstance(raw, (bytes, bytearray)) else raw
            package = json.loads(text)
        except (ValueError, UnicodeDecodeError) as exc:
            raise GrantPackageError("授权包不是合法的 JSON 文件") from exc

    if not isinstance(package, dict):
        raise GrantPackageError("授权包根节点必须是对象")
    for field in REQUIRED_FIELDS:
        if field not in package:
            raise GrantPackageError("授权包缺少必填字段: %s" % field)
    if package["format"] != PACKAGE_FORMAT:
        raise GrantPackageError("不是本系统的授权包（format=%r）" % package["format"])
    if package["format_version"] not in SUPPORTED_FORMAT_VERSIONS:
        raise GrantPackageError(
            "授权包格式版本 %r 不受支持（本机支持 %s）"
            % (package["format_version"], sorted(SUPPORTED_FORMAT_VERSIONS))
        )
    if not isinstance(package["org_code"], str) or not package["org_code"]:
        raise GrantPackageError("org_code 必须是非空字符串")
    if not isinstance(package["version"], int) or isinstance(package["version"], bool) or package["version"] <= 0:
        raise GrantPackageError("version 必须是正整数")
    package["grants"] = _validate_grants(package["grants"])
    return package


def apply_package(
    db: Session,
    raw: Union[bytes, str, Dict[str, Any]],
    *,
    public_key: str = "",
    allow_unsigned: bool = False,
    expected_org_code: Optional[str] = None,
) -> Dict[str, Any]:
    """校验并应用授权包；成功后**替换**该单位的授权矩阵并递增版本号。"""
    package = parse_package(raw)
    signature = package.get(SIGNATURE_FIELD) or ""

    if signature:
        if not public_key:
            raise GrantPackageError("本机未配置验签公钥，无法校验授权包来源")
        if not verify_payload(package, signature, public_key):
            raise GrantPackageError("授权包签名校验失败（可能被篡改或来自非授权上级）")
    elif not allow_unsigned:
        raise GrantPackageError("授权包未签名；如确需导入请显式开启 allow_unsigned")

    org_code = package["org_code"]
    if expected_org_code and org_code != expected_org_code:
        raise GrantPackageError(
            "授权包目标单位（%s）与本机单位（%s）不一致" % (org_code, expected_org_code)
        )

    org = db.query(Organization).filter(Organization.code == org_code).first()
    if org is None:
        raise GrantPackageError("本机不存在单位编号为 %s 的组织，无法应用授权包" % org_code)

    current_version = org.grant_version or 0
    if package["version"] <= current_version:
        raise GrantPackageError(
            "拒绝降级导入：包版本 %d 不大于本机当前版本 %d" % (package["version"], current_version)
        )

    db.query(OrgGrant).filter(OrgGrant.organization_id == org.id).delete()
    for module_key, level in package["grants"].items():
        db.add(OrgGrant(organization_id=org.id, module_key=module_key, level=level))

    org.grant_version = package["version"]
    org.grant_signature = signature or None
    org.grant_applied_at = datetime.now(timezone.utc)
    org.grant_source = "import"
    # safe_commit：失败自动 rollback，避免"矩阵已替换但版本号/签名未落库"的半提交态
    safe_commit(db)

    # 版本号已变 → 旧缓存自然失效；显式清一次更稳妥（同版本重复导入的边界）
    from app.services.effective_grant_service import clear_cache

    clear_cache()

    return {
        "org_code": org_code,
        "version": package["version"],
        "modules": len(package["grants"]),
        "signed": bool(signature),
    }
