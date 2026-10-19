"""单位授权矩阵 API（R33）。

四个端点：
- `POST /org-grants/import`      导入授权包（下级，离线摆渡进来的文件）
- `POST /org-grants/{id}/export` 生成授权包并下载（上级）
- `GET  /org-grants/{id}`        查看某单位的授权矩阵与版本元信息
- `PUT  /org-grants/{id}`        直接设置矩阵（上级在线配置；导入后的下级侧为只读）

⚠️ 路由声明顺序：`/import` 必须写在 `/{org_id}` **之前**，否则 "import" 会被当成
`org_id` 解析成 int 而 422。
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.v1.deps import get_current_active_user, get_db
from app.core.config import settings
from app.core.data_permission import _get_org_subtree, assert_org_reachable
from app.core.permission_utils import require_admin
from app.core.response import success_response
from app.models.org_grant import VALID_GRANT_LEVELS, OrgGrant
from app.models.organization import Organization
from app.services.effective_grant_service import clear_cache
from app.services.grant_package_service import (
    GrantPackageError,
    apply_package,
    build_package,
    export_package_bytes,
)
from app.services.system_config_service import SystemConfigService
from app.services.work_log_service import write_work_log
from app.utils.upload_helper import read_upload_with_limit

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/org-grants", tags=["单位授权"])

# 授权包文件上限（授权矩阵是纯文本，1MB 绰绰有余）
_MAX_PACKAGE_BYTES = 1024 * 1024


class GrantSetRequest(BaseModel):
    """直接设置授权矩阵的请求体。"""

    grants: dict[str, str]


def _require_admin_and_reach(db: Session, current_user, org_id: int, action: str) -> Organization:
    require_admin(current_user, error_message="仅管理员可管理单位授权")
    assert_org_reachable(
        db, current_user, org_id, action=action, subtree_resolver=_get_org_subtree
    )
    org = db.query(Organization).filter(Organization.id == org_id).first()
    if org is None:
        raise HTTPException(status_code=404, detail="单位不存在")
    return org


def _matrix_of(db: Session, org_id: int) -> dict:
    rows = db.query(OrgGrant).filter(OrgGrant.organization_id == org_id).all()
    return {row.module_key: row.level for row in rows}


def _local_org_code(db: Session) -> str:
    """本机单位编号（系统配置 organization_code）；取不到则返回空串。"""
    try:
        value = SystemConfigService(db).get("organization_code")
    except Exception:  # pragma: no cover - 配置服务异常不应阻断导入
        logger.warning("读取 organization_code 失败，跳过单位一致性校验", exc_info=True)
        return ""
    return str(value).strip() if value else ""


@router.post("/import", summary="导入授权包（下级）")
async def import_grant_package(
    file: UploadFile = File(..., description="授权包 JSON 文件"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """下级单位导入上级下发的授权包。导入后矩阵只读，本机不提供编辑入口。"""
    require_admin(current_user, error_message="仅管理员可导入授权包")

    # 必须走分块限长读取：`await file.read()` 会先把整个 SpooledTemporaryFile
    # 物化进内存再判长度，单机离线部署下单请求即可 OOM（P1 门禁 check_unbounded_read
    # 与 check_upload_endpoints 都禁止裸 read）。
    content = await read_upload_with_limit(
        file,
        _MAX_PACKAGE_BYTES,
        status_code=400,
        error_detail="授权包超过 1MB 上限",
    )
    if not content:
        raise HTTPException(status_code=400, detail="授权包内容为空")

    try:
        result = apply_package(
            db,
            content,
            public_key=settings.GRANT_PUBKEY,
            allow_unsigned=settings.GRANT_ALLOW_UNSIGNED,
            expected_org_code=_local_org_code(db) or None,
        )
    except GrantPackageError as exc:
        # 面向运维的可读原因，不暴露内部实现细节
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    try:
        write_work_log(
            db, "system_config", "import", 0,
            "导入单位授权包 v%s（%s 个模块）" % (result["version"], result["modules"]),
            user_id=getattr(current_user, "id", None),
            username=getattr(current_user, "username", ""),
        )
    except Exception:  # pragma: no cover - 审计失败不阻断主流程
        logger.warning("记录授权包导入审计日志失败", exc_info=True)

    return success_response(data=result, message="授权包已应用")


@router.post("/{org_id}/export", summary="生成授权包（上级）")
def export_grant_package(
    org_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """把某单位当前矩阵导出为授权包（版本号自动 +1）。"""
    org = _require_admin_and_reach(db, current_user, org_id, "生成授权包")

    if not org.code:
        raise HTTPException(
            status_code=400,
            detail="该单位未填写单位编号（code），无法作为授权包目标",
        )

    grants = _matrix_of(db, org_id)
    version = (org.grant_version or 0) + 1
    try:
        package = build_package(
            org_code=org.code,
            grants=grants,
            version=version,
            org_name=org.name,
            private_key=settings.GRANT_SIGNING_KEY,
        )
    except GrantPackageError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    payload = export_package_bytes(package)
    filename = "grant-%s-v%d.json" % (org.code, version)
    return Response(
        content=payload,
        media_type="application/json",
        headers={"Content-Disposition": 'attachment; filename="%s"' % filename},
    )


@router.get("/{org_id}", summary="查看单位授权矩阵")
def get_org_grants(
    org_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    org = _require_admin_and_reach(db, current_user, org_id, "查看单位授权")
    return success_response(
        data={
            "organization_id": org.id,
            "org_code": org.code,
            "grant_version": org.grant_version or 0,
            "grant_source": org.grant_source,
            "grant_applied_at": (
                org.grant_applied_at.isoformat() if org.grant_applied_at else None
            ),
            "signed": bool(org.grant_signature),
            "grants": _matrix_of(db, org_id),
        }
    )


@router.put("/{org_id}", summary="设置单位授权矩阵")
def set_org_grants(
    org_id: int,
    body: GrantSetRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """上级在线配置单位矩阵（替换语义）。导入后的下级侧不应调用本端点。"""
    org = _require_admin_and_reach(db, current_user, org_id, "设置单位授权")

    for key, level in body.grants.items():
        if not key or level not in VALID_GRANT_LEVELS:
            raise HTTPException(
                status_code=400,
                detail="模块 %s 的授权级别 %r 非法（仅支持 %s）"
                % (key, level, "/".join(sorted(VALID_GRANT_LEVELS))),
            )

    db.query(OrgGrant).filter(OrgGrant.organization_id == org_id).delete()
    for key, level in body.grants.items():
        db.add(OrgGrant(organization_id=org_id, module_key=key, level=level))

    org.grant_version = (org.grant_version or 0) + 1
    org.grant_source = "local"
    db.commit()
    clear_cache()

    return success_response(
        data={"organization_id": org_id, "grant_version": org.grant_version,
              "modules": len(body.grants)},
        message="授权矩阵已更新",
    )
