# -*- coding: utf-8 -*-
"""介质包的来源单位码校验（P2）。

背景：完全离线 + 上下级 + 介质传输场景下，"这包是谁给的"必须在导入前确认。
否则把省里的包导进县里的机（或反之），数据会挂到错误的组织树上，
且事后极难发现。

本模块只负责：
* 解析包内 manifest 的 org_code（行政区划代码）；
* 与目标机本单位/子树的单位码比对，给出"匹配/不匹配/无法判定"三态结论。

判定口径与 organizations.code 规则一致（见 organization_code_service）：
6 位行政区划代码，末位规律决定层级。
"""

from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from app.core.logging import logger
from app.models.organization import Organization

# 匹配结论
MATCH_OK = "ok"
MATCH_MISMATCH = "mismatch"
MATCH_UNKNOWN = "unknown"


def _clean(value: Any) -> str:
    return str(value or "").strip()


def extract_manifest_org_code(manifest: Any) -> str:
    """从 manifest（dict 或 pydantic 对象）里取来源单位码。"""
    if manifest is None:
        return ""
    if isinstance(manifest, dict):
        return _clean(manifest.get("org_code"))
    return _clean(getattr(manifest, "org_code", ""))


def local_org_code(db: Session, org_id: Optional[int]) -> str:
    """取本机某组织的单位码；取不到返回空串。"""
    if not org_id:
        return ""
    try:
        org = db.query(Organization).filter(Organization.id == org_id).first()
    except Exception:  # pragma: no cover - 防御：查询失败按"无法判定"处理
        logger.debug("读取本机单位码失败", exc_info=True)
        return ""
    return _clean(getattr(org, "code", "")) if org is not None else ""


def check_org_code(
    db: Session,
    manifest: Any,
    target_org_id: Optional[int],
) -> Dict[str, Any]:
    """比对包内来源单位码与本机目标单位码。

    Returns:
        {
          "status": MATCH_OK | MATCH_MISMATCH | MATCH_UNKNOWN,
          "package_org_code": 包内单位码,
          "local_org_code": 本机单位码,
          "message": 面向运维的可读说明（status != MATCH_OK 时有值），
        }
    """
    pkg_code = extract_manifest_org_code(manifest)
    local = local_org_code(db, target_org_id)

    if not pkg_code:
        return {
            "status": MATCH_UNKNOWN,
            "package_org_code": "",
            "local_org_code": local,
            "message": "数据包未声明来源单位码（老包无此字段），无法核对来源单位",
        }
    if not local:
        return {
            "status": MATCH_UNKNOWN,
            "package_org_code": pkg_code,
            "local_org_code": "",
            "message": "本机目标单位没有设置单位码，无法核对来源单位",
        }
    if pkg_code == local:
        return {
            "status": MATCH_OK,
            "package_org_code": pkg_code,
            "local_org_code": local,
            "message": "",
        }
    return {
        "status": MATCH_MISMATCH,
        "package_org_code": pkg_code,
        "local_org_code": local,
        "message": (
            "数据包来源单位码为 " + pkg_code + "，与本机单位码 " + local
            + " 不一致，确认导入将把数据挂到本机组织上"
        ),
    }
