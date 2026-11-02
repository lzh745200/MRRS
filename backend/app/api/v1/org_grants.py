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

import hashlib
import io
import json
import logging
import zipfile
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.v1.deps import get_current_active_user, get_db
from app.core.config import settings
from app.core.data_permission import _get_org_subtree, assert_org_reachable
from app.core.permission_utils import require_admin
from app.core.response import success_response
from app.core.transaction import safe_commit
from app.models.org_grant import VALID_GRANT_LEVELS, OrgGrant
from app.models.organization import Organization
from app.services.effective_grant_service import (
    VISIBLE_LEVELS,
    clear_cache,
    get_grant_matrix_for_org,
)
from app.services.org_grant_tree_service import (
    matrix_of,
    parent_codes,
    subtree_orgs,
    tree_node,
)
from app.services.grant_package_service import (
    GrantPackageError,
    apply_package,
    build_package,
    export_package_bytes,
)
from app.services.system_config_service import SystemConfigService
from app.services.work_log_service import write_work_log
from app.utils.upload_helper import read_upload_with_limit
from app.services.package_import_guard import (
    assert_content_not_duplicate,
    record_import,
)

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


def _matrix_brief(grants: dict) -> str:
    """授权矩阵的可读摘要（审计日志用；排序保证同一矩阵输出稳定）。"""
    return ",".join("%s=%s" % (k, grants[k]) for k in sorted(grants))


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
    # 同一校验和的授权包再次导入必须显式确认
    force: bool = False,
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

    # P2：授权包查重（内容哈希；重复且未 force → 409）
    checksum = assert_content_not_duplicate(db, content, force=force)

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

    # P2：写导入台账（失败不阻断）
    record_import(
        db,
        checksum=checksum,
        package_type="grant_package",
        user_id=getattr(current_user, "id", None),
        username=getattr(current_user, "username", ""),
        file_name=getattr(file, "filename", "") or "",
        source_org_code=result.get("org_code") if isinstance(result, dict) else None,
        record_count=result.get("modules", 0) if isinstance(result, dict) else 0,
    )

    return success_response(data=result, message="授权包已应用")


@router.get("/tree", summary="查看组织策略树")
def get_org_grant_tree(
    root_id: int | None = Query(default=None, description="根单位 ID；缺省为当前用户所属单位"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """返回一棵组织子树：每个节点带自身显式矩阵与元信息，供上级配置界面使用。

    只返回**显式**矩阵；继承后的有效值按选中节点单独取 `GET /org-grants/{id}`，
    避免 98 个单位一次性把 ×15 个模块的有效矩阵全部算出来。
    """
    if root_id is None:
        root_id = getattr(current_user, "organization_id", None)
    if root_id is None and getattr(current_user, "is_superuser", False):
        # 首次初始化的超级管理员不绑定单位（system/init.py 只建号不挂组织），
        # 这里回落到组织树最顶层，避免默认超管打开页面就 400。
        top = (
            db.query(Organization)
            .filter(
                Organization.parent_id.is_(None),
                Organization.is_active.is_(True),
            )
            .order_by(Organization.id.asc())
            .first()
        )
        if top is not None:
            root_id = int(top.id)
    if not isinstance(root_id, int) or isinstance(root_id, bool) or root_id <= 0:
        raise HTTPException(status_code=400, detail="缺少根单位 ID，且当前账号未绑定单位")

    root = _require_admin_and_reach(db, current_user, root_id, "查看组织策略树")
    orgs = subtree_orgs(db, root_id)
    if not orgs:
        raise HTTPException(status_code=404, detail="单位不存在或组织树为空")

    children_by_parent: dict = {}
    for org in orgs:
        children_by_parent.setdefault(org.parent_id, []).append(org)

    return success_response(
        data={"root_id": root_id, "node": tree_node(db, root, children_by_parent)}
    )


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

    grants = matrix_of(db, org_id)
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
    # 版本号必须落库（R34-1 缺陷修复）：原实现只在包里写 `version+1` 而不落库，
    # 连续两次导出会产出**相同版本号**，下级机第二次导入必被
    # `apply_package` 的「拒绝降级导入」挡掉（包版本 <= 本机当前版本）——
    # 多机离线授权分发因此只能成功一次。落库后每次导出都预留新版本。
    # 注意顺序：build_package 可能因矩阵含非法级别抛 400，故落库必须在其后。
    org.grant_version = version
    safe_commit(db)
    # 缓存 key 含 grant_version：版本变了旧 entry 自然不再命中；显式清一次
    # 避免"反复导出但不改矩阵"在 _CACHE 里堆出多个内容相同的 key。
    clear_cache()

    filename = "grant-%s-v%d.json" % (org.code, version)
    return Response(
        content=payload,
        media_type="application/json",
        headers={"Content-Disposition": 'attachment; filename="%s"' % filename},
    )


@router.post("/{org_id}/export-branch", summary="批量导出子树授权包（上级）")
def export_grant_branch(
    org_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """把整棵子树的**有效矩阵**分别打成 v1 授权包，合并为一个 zip 下载。

    每个单位仍是一个独立的 `r33-grant-package` v1 文件（下级导入零改动），
    zip 只是分发容器；`manifest.json` 记录文件名/版本/哈希与跳过原因。
    """
    root = _require_admin_and_reach(db, current_user, org_id, "批量导出子树授权包")
    orgs = subtree_orgs(db, org_id)
    if not orgs:
        raise HTTPException(status_code=404, detail="单位不存在或组织树为空")

    missing = [org for org in orgs if not org.code]
    if missing:
        names = "、".join(str(org.name or org.id) for org in missing)
        raise HTTPException(
            status_code=400,
            detail="以下单位未填写单位编号（code），无法批量导出：%s" % names,
        )

    orgs_by_id = {org.id: org for org in orgs}
    built = []  # [(org, version, package)]
    skipped = []
    for org in orgs:
        matrix = get_grant_matrix_for_org(db, org)
        grants = {
            key: level
            for key, level in matrix.levels.items()
            if level in VISIBLE_LEVELS
        }
        if not grants:
            # 空矩阵导入后会变成「active 但全部 none」→ 下级菜单全空。
            # 宁可跳过并告警，也不下发一个会锁死单位的包。
            skipped.append(
                {
                    "org_code": org.code,
                    "org_name": org.name,
                    "reason": "no_effective_grants",
                }
            )
            continue
        version = (org.grant_version or 0) + 1
        try:
            package = build_package(
                org_code=org.code,
                grants=grants,
                version=version,
                org_name=org.name,
                parent_codes=parent_codes(orgs_by_id, org),
                private_key=settings.GRANT_SIGNING_KEY,
            )
        except GrantPackageError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        built.append((org, version, package))

    # 先在内存里把 zip 完整构建出来，再统一落版本号：任何一步失败都不会
    # 留下「版本号已递增但没有包」的半成品（下级会因此无法再次导入）。
    buffer = io.BytesIO()
    entries = []
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for org, version, package in built:
            payload = export_package_bytes(package)
            filename = "grant-%s-v%d.json" % (org.code, version)
            archive.writestr(filename, payload)
            entries.append(
                {
                    "file": filename,
                    "org_code": org.code,
                    "org_name": org.name,
                    "version": version,
                    "modules": len(package["grants"]),
                    "signed": bool(package.get("signature")),
                    "sha256": hashlib.sha256(payload).hexdigest(),
                }
            )
        manifest = {
            "format": "r33-grant-batch",
            "format_version": 1,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "issuer_org_code": root.code,
            "root_org_code": root.code,
            "packages": entries,
            "skipped": skipped,
        }
        archive.writestr(
            "manifest.json",
            json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8"),
        )

    for org, version, _package in built:
        org.grant_version = version
    safe_commit(db)
    clear_cache()

    filename = "grants-%s.zip" % root.code
    return Response(
        content=buffer.getvalue(),
        media_type="application/zip",
        headers={"Content-Disposition": 'attachment; filename="%s"' % filename},
    )


@router.get("/{org_id}", summary="查看单位授权矩阵")
def get_org_grants(
    org_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    org = _require_admin_and_reach(db, current_user, org_id, "查看单位授权")
    matrix = get_grant_matrix_for_org(db, org)
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
            # 显式矩阵（本机存储）与继承后的有效矩阵分开返回：
            # 前端四态编辑需要同时看到"我写了什么"和"最终生效什么"。
            "grants": matrix_of(db, org_id),
            "active": matrix.active,
            "effective": dict(matrix.levels) if matrix.active else {},
            "sources": dict(matrix.sources) if matrix.active else {},
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

    # 审计需要变更前快照，必须在删除前读取
    before = matrix_of(db, org_id)

    # 裸 delete + 逐条 add 在同一事务内完成：safe_commit 失败会自动 rollback，
    # 不会留下"矩阵已清空但新矩阵未写入"的中间态。
    db.query(OrgGrant).filter(OrgGrant.organization_id == org_id).delete()
    for key, level in body.grants.items():
        db.add(OrgGrant(organization_id=org_id, module_key=key, level=level))

    org.grant_version = (org.grant_version or 0) + 1
    org.grant_source = "local"
    safe_commit(db)
    clear_cache()

    # 授权矩阵决定"哪个单位能看/能改哪个模块"，属权限提升操作，必须留痕（P1-3）。
    # 审计失败不阻断主流程（与 import 端点保持一致）。
    try:
        write_work_log(
            db, "system_config", "grant_set", org_id,
            "设置单位授权矩阵 v%s（%d 个模块）: %s → %s" % (
                org.grant_version, len(body.grants),
                _matrix_brief(before), _matrix_brief(body.grants),
            ),
            user_id=getattr(current_user, "id", None),
            username=getattr(current_user, "username", ""),
        )
    except Exception:  # pragma: no cover - 审计失败不阻断主流程
        logger.warning("记录授权矩阵变更审计日志失败", exc_info=True)

    return success_response(
        data={"organization_id": org_id, "grant_version": org.grant_version,
              "modules": len(body.grants)},
        message="授权矩阵已更新",
    )
