"""回收站通用路由工厂：为软删资源挂载 恢复 / 彻底删除(预览+执行) 三端点。

统一语义（与帮扶村回收站一致，见 supported_village.py 同名端点）：
- 仅管理员可操作；
- restore 仅对已软删记录生效；
- purge 仅对已软删记录生效 + 当前用户密码二次确认，
  经 CascadePurgeService 按元数据外键图级联物理清除；
- purge 前提供 preview 端点返回级联统计供前端警示；
- purge 后写安全审计日志并触发即时备份。

用法（在各资源路由模块底部）::

    from app.api.v1.recycle_bin import register_recycle_bin_routes
    register_recycle_bin_routes(
        router, model=Project, resource="项目",
        table_name=Project.__tablename__,
    )
"""

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.permission_utils import require_admin
from app.core.response import success_response
from app.core.security import get_current_user
from app.models.user import User

logger = logging.getLogger(__name__)


class RecyclePurgeRequest(BaseModel):
    confirm_password: str = ""
    ids: list[int] = []


def register_recycle_bin_routes(
    router: APIRouter,
    *,
    model,
    resource: str,
    table_name: str | None = None,
    on_changed=None,
):
    """向 router 注册 /{rid}/purge/preview、/{rid}/restore、/{rid}/purge。"""
    table = table_name or model.__tablename__
    pk = "id"

    def _get_or_404(db: Session, rid: int):
        rec = db.query(model).filter(getattr(model, pk) == rid).first()
        if not rec:
            raise HTTPException(status_code=404, detail=f"{resource}不存在")
        return rec

    def _require_in_recycle_bin(rec):
        if getattr(rec, "is_active", True):
            raise HTTPException(status_code=400, detail=f"该{resource}不在回收站中")

    def _verify_password(data, current_user):
        from app.core.security import verify_password as _vp

        if not data.confirm_password or not _vp(
            data.confirm_password,
            getattr(current_user, "hashed_password", "") or "",
        ):
            raise HTTPException(status_code=400, detail="二次确认失败：密码不正确")

    @router.get(
        "/{rid}/purge/preview",
        summary=f"彻底删除预览：{resource}级联统计",
    )
    def purge_preview(
        rid: int,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
    ):
        require_admin(current_user)
        rec = _get_or_404(db, rid)
        _require_in_recycle_bin(rec)
        from app.services.cascade_purge_service import CascadePurgeService

        refs = CascadePurgeService(db).preview(table, rid)
        return success_response(data={
            "id": rid,
            "name": getattr(rec, "village_name", None)
            or getattr(rec, "name", None)
            or f"#{rid}",
            **refs,
        })

    @router.post("/{rid}/restore", summary=f"从回收站恢复{resource}")
    async def restore_rec(
        rid: int,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
    ):
        require_admin(current_user)
        rec = _get_or_404(db, rid)
        _require_in_recycle_bin(rec)
        return await _restore_record(db, model, resource, table, rid, current_user, on_changed)

    @router.post("/{rid}/purge", summary=f"彻底删除{resource}（级联物理清除）")
    async def purge_rec(
        rid: int,
        data: RecyclePurgeRequest,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
    ):
        require_admin(current_user)
        _verify_password(data, current_user)
        rec = _get_or_404(db, rid)
        _require_in_recycle_bin(rec)
        return await _purge_record(db, model, resource, table, rid, data, current_user, on_changed)

    # ── 批量恢复 / 批量彻底删除 ──

    @router.post("/batch-restore", summary=f"批量从回收站恢复{resource}")
    async def batch_restore(
        body: RecyclePurgeRequest,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
    ):
        require_admin(current_user)
        ids = getattr(body, "ids", [])
        if not ids:
            raise HTTPException(status_code=400, detail="请提供要恢复的 ID 列表")
        return await _batch_restore_records(db, model, resource, ids, current_user, on_changed)

    @router.post("/batch-purge", summary=f"批量彻底删除{resource}（级联物理清除）")
    async def batch_purge(
        body: RecyclePurgeRequest,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
    ):
        require_admin(current_user)
        _verify_password(body, current_user)
        ids = getattr(body, "ids", [])
        if not ids:
            raise HTTPException(status_code=400, detail="请提供要彻底删除的 ID 列表")
        return await _batch_purge_records(db, model, resource, table, ids, current_user, on_changed)


async def _restore_record(db, model, resource, table, rid, current_user, on_changed):
    """执行单条恢复（通用）。"""
    rec = db.query(model).get(rid)
    if rec is None:
        raise HTTPException(status_code=404, detail=f"{resource}不存在")
    rec.is_active = True
    if hasattr(rec, "deleted_at"):
        rec.deleted_at = None
    from app.core.transaction import safe_commit

    safe_commit(db)
    if on_changed:
        await on_changed()
    from app.utils.audit_logger import AuditLogger

    AuditLogger.log(
        action=f"{table}_restore",
        user_id=current_user.id,
        username=current_user.username,
        resource_type=table,
        resource_id=rid,
        details={"name": getattr(rec, "name", None) or str(rid)},
    )
    return success_response(data={"id": rid}, message="恢复成功")


async def _purge_record(db, model, resource, table, rid, data, current_user, on_changed):
    """执行单条彻底删除（级联物理清除 + 审计 + 备份）。"""
    from app.services.cascade_purge_service import CascadePurgeService

    stats = CascadePurgeService(db).purge(table, rid)
    if not stats.get("success"):
        raise HTTPException(status_code=404, detail=stats.get("message", "彻底删除失败"))
    if on_changed:
        await on_changed()

    from app.utils.audit_logger import AuditLogger

    AuditLogger.log(
        action=f"{table}_purge",
        user_id=current_user.id,
        username=current_user.username,
        resource_type=table,
        resource_id=rid,
        details={
            "deleted_records": stats.get("deleted_records"),
            "cascade_details": stats.get("details"),
        },
    )
    try:
        from app.services.immediate_backup import trigger_immediate_backup

        trigger_immediate_backup(
            description=f"彻底删除{resource}#{rid}及关联数据后备份", delay=1.0
        )
    except Exception:  # pragma: no cover —— 备份失败不阻断删除结果
        logger.warning("彻底删除后即时备份触发失败", exc_info=True)

    return success_response(
        data={
            "id": rid,
            "deleted_records": stats.get("deleted_records", 0),
            "details": stats.get("details", {}),
        },
        message=f"已彻底删除并清理 {stats.get('deleted_records', 0)} 条关联数据",
    )


async def _batch_restore_records(db, model, resource, ids, current_user, on_changed):
    """批量恢复（is_active 置 True，清 deleted_at）。"""
    from app.core.transaction import safe_commit

    count = (
        db.query(model)
        .filter(model.id.in_(ids), model.is_active == False)  # noqa: E712
        .update(
            {"is_active": True, "deleted_at": None},
            synchronize_session=False,
        )
    )
    safe_commit(db)
    if on_changed:
        await on_changed()
    return success_response(
        data={"restored": count},
        message=f"已恢复 {count} 条{resource}记录",
    )


async def _batch_purge_records(db, model, resource, table, ids, current_user, on_changed):
    """批量彻底删除（逐条级联物理清除 + 审计 + 备份）。"""
    from app.services.cascade_purge_service import CascadePurgeService

    svc = CascadePurgeService(db)
    total = 0
    purged_ids = []
    for rid in ids:
        rec = (
            db.query(model)
            .filter(model.id == rid, model.is_active == False)  # noqa: E712
            .first()
        )
        if not rec:
            continue
        stats = svc.purge(table, rid)
        if stats.get("success"):
            total += 1
            purged_ids.append(rid)

    if on_changed:
        await on_changed()

    from app.utils.audit_logger import AuditLogger

    AuditLogger.log(
        action=f"{table}_batch_purge",
        user_id=current_user.id,
        username=current_user.username,
        resource_type=table,
        resource_id=0,
        details={"purged_count": total, "purged_ids": purged_ids},
    )
    try:
        from app.services.immediate_backup import trigger_immediate_backup

        trigger_immediate_backup(
            description=f"批量彻底删除{resource} {total} 条后备份", delay=1.0
        )
    except Exception:  # pragma: no cover
        logger.warning("批量彻底删除后备份触发失败", exc_info=True)

    return success_response(
        data={"purged": total, "ids": purged_ids},
        message=f"已彻底删除 {total} 条{resource}及关联数据",
    )
