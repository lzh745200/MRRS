"""工作移交服务（人员轮换：我负责/我发起的村、项目、待办、审批中申请一键交接）。

设计口径（与 Lead 裁决一致）：

- **不新增数据表**：交接历史由既有 ``WorkLog`` 承载 —— ``execute`` 用
  :func:`write_work_log` 写一条 ``category="handover"`` 的摘要（移交人/接任人/
  逐项数量），``history`` 按该分类 + 时间过滤返回摘要列表。好处是与全仓审计口径
  一致、不引入 Alembic 迁移（避免并行工单造成多 head 启动失败）；
- **结构化快照**：摘要的 ``attachments`` 列存 JSON 快照（逐项 type/id/title），
  供历史列表回放逐项清单与交接单导出；同时 ``content`` 里写入可读的逐项枚举，
  保证**审计原文本身**就带逐项清单（不依赖 JSON 解析）；
- **单事务**：归属改写、双方站内消息、审批转交记录、交接审计只在最后一次
  ``write_work_log`` 内部提交时统一落库 —— 任何一步抛错都不落库（全量回滚）；
- **数据域 fail-closed**：清单按 ``services.data_scope_query.scoped_filter`` 统一入口过滤（超管全量、
  部门级 admin 仅本组织、普通用户仅本人）；接任人必须与移交人同组织，
  跨组织/组织缺失一律 403（超管豁免）；执行时再次按「本人 + 数据域」复核
  选中项，提交伪造 ID 一律 403，绝不移交不属于本人的资产。
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Tuple

from fastapi import HTTPException
from sqlalchemy import or_
from sqlalchemy.orm import Query, Session

from app.core.permission_utils import is_superuser
from app.core.transaction import safe_commit
from app.models.approval import ApprovalAction, ApprovalRecord, ApprovalStatus, ApprovalTask
from app.models.message import Message, MessageType
from app.models.project import Project
from app.models.supported_village import SupportedVillage
from app.models.todo import Todo
from app.models.user import User
from app.models.work_log import WorkLog
from app.services.data_scope_query import scoped_filter
from app.services.work_log_service import write_work_log

logger = logging.getLogger(__name__)

# 可移交资产类型（顺序即前端展示顺序）
ASSET_TYPES: Tuple[str, ...] = ("village", "project", "todo", "approval")
# 类型 → 中文标签（清单分组、审计文案、交接单共用同一事实源）
ASSET_LABELS: Dict[str, str] = {
    "village": "帮扶村",
    "project": "帮扶项目",
    "todo": "待办事项",
    "approval": "审批中申请",
}
# 交接历史在 WorkLog 中的分类（log_type）
HANDOVER_LOG_CATEGORY = "handover"
# 审批转交记录的操作意见
APPROVAL_TRANSFER_OPINION = "工作移交：审批任务转交接任人"
# 单类资产查询上限（防止一次移交拖动全库；超出部分分多次移交）
_ASSET_QUERY_LIMIT = 500


# ════════════════════════════════════════════════════════════════════
#  基础工具
# ════════════════════════════════════════════════════════════════════


def generate_record_no(now: Optional[datetime] = None) -> str:
    """生成交接单号：``HO-YYYYMMDD-HHMMSS-XXXXXXXX``。

    时间前缀便于人工按日期检索；随机后缀避免同一秒并发重复（无唯一索引，
    单机场景下仍保持可读且足够区分）。
    """
    stamp = (now or datetime.now(timezone.utc)).strftime("%Y%m%d-%H%M%S")
    return f"HO-{stamp}-{uuid.uuid4().hex[:8].upper()}"


def _iso(value: Any) -> Optional[str]:
    """datetime → ISO 字符串（None 原样返回）。"""
    return value.isoformat() if value is not None else None


def _user_brief(user: Any) -> Dict[str, Any]:
    """用户摘要（交接单/消息/快照共用）。"""
    return {
        "id": getattr(user, "id", None),
        "username": getattr(user, "username", None),
        "full_name": getattr(user, "full_name", None),
    }


def _split_scope(scope: Optional[Iterable[str]]) -> List[str]:
    """校验并归一化勾选的资产类型（未知类型 422，重复去重保序）。"""
    if scope is None:
        return list(ASSET_TYPES)
    if not isinstance(scope, (list, tuple, set)):
        raise HTTPException(status_code=422, detail="移交范围格式不合法：应为资产类型数组")
    normalized: List[str] = []
    for raw in scope:
        asset_type = str(raw).strip()
        if asset_type not in ASSET_TYPES:
            raise HTTPException(
                status_code=422,
                detail=f"未知的移交资产类型: {asset_type}（允许值：{'/'.join(ASSET_TYPES)}）",
            )
        if asset_type not in normalized:
            normalized.append(asset_type)
    if not normalized:
        raise HTTPException(status_code=422, detail="请至少勾选一类移交资产")
    return normalized


def _validate_item_ids(item_ids: Optional[Dict[str, Any]], scope: List[str]) -> None:
    """校验逐项选择参数的类型合法性（未知类型 / 非数组 / 已勾选范围外 → 422）。"""
    if item_ids is None:
        return
    if not isinstance(item_ids, dict):
        raise HTTPException(status_code=422, detail="逐项选择格式不合法：应为「类型 → ID 数组」")
    for raw_type, raw_ids in item_ids.items():
        asset_type = str(raw_type).strip()
        if asset_type not in ASSET_TYPES:
            raise HTTPException(
                status_code=422,
                detail=f"未知的移交资产类型: {asset_type}（允许值：{'/'.join(ASSET_TYPES)}）",
            )
        if asset_type not in scope:
            raise HTTPException(
                status_code=422,
                detail=f"资产类型 {asset_type} 不在本次勾选的移交范围内",
            )
        if not isinstance(raw_ids, list):
            raise HTTPException(
                status_code=422, detail=f"资产类型 {asset_type} 的选中项应为 ID 数组"
            )


# ════════════════════════════════════════════════════════════════════
#  接任人校验（跨组织 fail-closed）
# ════════════════════════════════════════════════════════════════════


def assert_handover_target(actor: Any, target: Optional[Any]) -> None:
    """校验接任人可接任：存在/启用/非本人/同组织（超管豁免跨组织）。

    跨组织与「双方组织缺失」一律 403 —— fail-closed（ADR-0002）：
    数据域无法证明同域时宁可直接拒绝，也不把工作交到不可见组织的人手里。
    """
    if target is None:
        raise HTTPException(status_code=404, detail="接任人不存在")
    if getattr(target, "id", None) == getattr(actor, "id", None):
        raise HTTPException(status_code=422, detail="接任人不能是移交人本人")
    if getattr(target, "is_active", True) is False:
        raise HTTPException(status_code=404, detail="接任人不存在或已停用")
    if is_superuser(actor):
        return
    actor_org = getattr(actor, "organization_id", None)
    target_org = getattr(target, "organization_id", None)
    if actor_org is None or target_org != actor_org:
        raise HTTPException(
            status_code=403,
            detail="跨组织移交被拒绝：接任人必须与移交人同属一个组织（数据域 fail-closed）",
        )


def list_candidates(
    db: Session, actor: Any, keyword: Optional[str] = None, limit: int = 200
) -> List[Dict[str, Any]]:
    """可选接任人列表（本组织启用用户；超管可选全部组织）。"""
    query = db.query(User).filter(User.is_active == True, User.id != getattr(actor, "id", None))  # noqa: E712
    if not is_superuser(actor):
        actor_org = getattr(actor, "organization_id", None)
        if actor_org is None:
            # fail-closed：无组织归属无法确定可移交范围
            return []
        query = query.filter(User.organization_id == actor_org)
    if keyword:
        like = f"%{keyword}%"
        query = query.filter(or_(User.username.like(like), User.full_name.like(like)))
    safe_limit = max(1, min(int(limit or 200), 500))
    users = query.order_by(User.username.asc()).limit(safe_limit).all()
    return [
        {
            "id": user.id,
            "username": user.username,
            "full_name": user.full_name,
            "role": getattr(user, "role", None),
            "department": getattr(user, "department", None),
            "organization_id": getattr(user, "organization_id", None),
        }
        for user in users
    ]


# ════════════════════════════════════════════════════════════════════
#  资产清单
# ════════════════════════════════════════════════════════════════════


def _village_query(db: Session, actor: Any) -> Query:
    """我发起的帮扶村（本人 + 数据域）。"""
    query = db.query(SupportedVillage).filter(
        SupportedVillage.created_by == getattr(actor, "id", None),
        SupportedVillage.is_active == True,  # noqa: E712
    )
    return scoped_filter(query, SupportedVillage, actor)


def _project_query(db: Session, actor: Any) -> Query:
    """我发起的帮扶项目（本人 + 数据域）。"""
    query = db.query(Project).filter(
        Project.created_by == getattr(actor, "id", None),
        Project.is_active == True,  # noqa: E712
    )
    return scoped_filter(query, Project, actor)


def _todo_query(db: Session, actor: Any) -> Query:
    """我负责的未完成待办（待办是个人数据，天然按 user_id 收敛）。"""
    return db.query(Todo).filter(
        Todo.user_id == getattr(actor, "id", None),
        Todo.completed == False,  # noqa: E712
    )


def _approval_query(db: Session, actor: Any) -> Query:
    """我负责（待我审批）/ 我发起 的审批中申请。"""
    user_id = getattr(actor, "id", None)
    return db.query(ApprovalTask).filter(
        ApprovalTask.status == ApprovalStatus.PENDING.value,
        or_(
            ApprovalTask.current_approver_id == user_id,
            ApprovalTask.submitter_id == user_id,
        ),
    )


def _village_item(village: SupportedVillage) -> Dict[str, Any]:
    location = " / ".join(
        part for part in (village.province, village.city, village.county) if part
    )
    return {
        "type": "village",
        "id": village.id,
        "title": village.village_name,
        "subtitle": location or None,
        "role": "owner",
    }


def _project_item(project: Project) -> Dict[str, Any]:
    return {
        "type": "project",
        "id": project.id,
        "title": project.name,
        "subtitle": f"状态：{project.status}" if project.status else None,
        "role": "owner",
    }


def _todo_item(todo: Todo) -> Dict[str, Any]:
    return {
        "type": "todo",
        "id": todo.id,
        "title": todo.title,
        "subtitle": f"截止 {todo.deadline}" if todo.deadline else None,
        "role": "owner",
    }


def _approval_role(task: ApprovalTask, user_id: Any) -> str:
    """审批资产的归属角色：approver / submitter / both。"""
    is_approver = task.current_approver_id == user_id
    is_submitter = task.submitter_id == user_id
    if is_approver and is_submitter:
        return "both"
    if is_approver:
        return "approver"
    return "submitter"


_APPROVAL_ROLE_LABELS = {"approver": "待我审批", "submitter": "我发起", "both": "我发起且待我审批"}


def _approval_item(task: ApprovalTask, user_id: Any) -> Dict[str, Any]:
    role = _approval_role(task, user_id)
    title = task.title or f"{task.entity_type}#{task.entity_id}"
    return {
        "type": "approval",
        "id": task.id,
        "title": title,
        "subtitle": f"待审批 · {_APPROVAL_ROLE_LABELS[role]}",
        "role": role,
    }


def _asset_page(query: Query, model: Any) -> List[Any]:
    """按 id 倒序取上限条数（保持最近创建的优先展示）。"""
    return query.order_by(model.id.desc()).limit(_ASSET_QUERY_LIMIT).all()


def _collect_assets(
    db: Session, actor: Any, types: Iterable[str]
) -> Dict[str, List[Dict[str, Any]]]:
    """按类型收集「我的」资产清单（每类最多 _ASSET_QUERY_LIMIT 条）。"""
    user_id = getattr(actor, "id", None)
    collected: Dict[str, List[Dict[str, Any]]] = {}
    for asset_type in types:
        if asset_type == "village":
            rows = _asset_page(_village_query(db, actor), SupportedVillage)
            collected[asset_type] = [_village_item(row) for row in rows]
        elif asset_type == "project":
            rows = _asset_page(_project_query(db, actor), Project)
            collected[asset_type] = [_project_item(row) for row in rows]
        elif asset_type == "todo":
            rows = _asset_page(_todo_query(db, actor), Todo)
            collected[asset_type] = [_todo_item(row) for row in rows]
        elif asset_type == "approval":
            rows = _asset_page(_approval_query(db, actor), ApprovalTask)
            collected[asset_type] = [_approval_item(row, user_id) for row in rows]
    return collected


def build_inventory(db: Session, actor: Any) -> Dict[str, Any]:
    """「我负责/我发起」的资产清单预览（空结果返回 200 + 空分组，不报错）。"""
    collected = _collect_assets(db, actor, ASSET_TYPES)
    groups = [
        {
            "type": asset_type,
            "label": ASSET_LABELS[asset_type],
            "count": len(collected.get(asset_type, [])),
            "items": collected.get(asset_type, []),
        }
        for asset_type in ASSET_TYPES
    ]
    return {
        "groups": groups,
        "total": sum(group["count"] for group in groups),
        "generated_at": _iso(datetime.now(timezone.utc)),
    }


def _select_assets(
    collected: Dict[str, List[Dict[str, Any]]],
    scope: List[str],
    item_ids: Optional[Dict[str, Any]],
) -> Dict[str, List[Dict[str, Any]]]:
    """按勾选范围裁剪清单。

    语义：``item_ids`` 中**出现的类型**只移交列出的 ID（空数组 = 该类型不移交）；
    未出现的类型（在 scope 内）整类移交 —— 与前端「整组勾选/逐项勾选」一致。
    选中 ID 不在本人清单内 → 403（fail-closed，防前端篡改）。
    """
    selected: Dict[str, List[Dict[str, Any]]] = {}
    for asset_type in scope:
        items = collected.get(asset_type, [])
        if not items:
            continue
        raw_ids = (item_ids or {}).get(asset_type)
        if raw_ids is None:
            selected[asset_type] = list(items)
            continue
        by_id = {item["id"]: item for item in items}
        wanted = [int(raw) for raw in raw_ids]
        missing = [item_id for item_id in wanted if item_id not in by_id]
        if missing:
            raise HTTPException(
                status_code=403,
                detail=f"移交清单包含不属于当前用户或已变动的{ASSET_LABELS[asset_type]}: {missing}",
            )
        if wanted:
            selected[asset_type] = [by_id[item_id] for item_id in wanted]
    return selected


# ════════════════════════════════════════════════════════════════════
#  归属改写 / 消息 / 审计
# ════════════════════════════════════════════════════════════════════


def _assert_moved(asset_type: str, moved: int, expected: int) -> None:
    """行数不一致说明选中项在读取后被改动 —— 整单拒绝（fail-closed）。"""
    if int(moved) != int(expected):
        raise HTTPException(
            status_code=409,
            detail=f"{ASSET_LABELS[asset_type]}归属已变化，请刷新清单后重新发起移交",
        )


def _apply_ownership(
    db: Session,
    actor: Any,
    target: User,
    selected: Dict[str, List[Dict[str, Any]]],
    note: Optional[str],
) -> Dict[str, int]:
    """在**当前事务内**批量改写归属（不提交；由调用方统一提交/回滚）。"""
    actor_id = getattr(actor, "id", None)
    target_id = target.id
    counts: Dict[str, int] = {}
    if selected.get("village"):
        ids = [item["id"] for item in selected["village"]]
        moved = (
            db.query(SupportedVillage)
            .filter(
                SupportedVillage.id.in_(ids),
                SupportedVillage.created_by == actor_id,
                SupportedVillage.is_active == True,  # noqa: E712
            )
            .update({SupportedVillage.created_by: target_id}, synchronize_session=False)
        )
        _assert_moved("village", moved, len(ids))
        counts["village"] = int(moved)
    if selected.get("project"):
        ids = [item["id"] for item in selected["project"]]
        moved = (
            db.query(Project)
            .filter(
                Project.id.in_(ids),
                Project.created_by == actor_id,
                Project.is_active == True,  # noqa: E712
            )
            .update({Project.created_by: target_id}, synchronize_session=False)
        )
        _assert_moved("project", moved, len(ids))
        counts["project"] = int(moved)
    if selected.get("todo"):
        ids = [item["id"] for item in selected["todo"]]
        moved = (
            db.query(Todo)
            .filter(Todo.id.in_(ids), Todo.user_id == actor_id)
            .update({Todo.user_id: target_id}, synchronize_session=False)
        )
        _assert_moved("todo", moved, len(ids))
        counts["todo"] = int(moved)
    if selected.get("approval"):
        counts["approval"] = _transfer_approvals(
            db, actor, target, selected["approval"], note
        )
    return counts


def _transfer_approvals(
    db: Session,
    actor: Any,
    target: User,
    items: List[Dict[str, Any]],
    note: Optional[str],
) -> int:
    """转交审批中申请（改当前审批人/提交人），并写审批转交记录。"""
    actor_id = getattr(actor, "id", None)
    ids = [item["id"] for item in items]
    tasks = (
        db.query(ApprovalTask)
        .filter(
            ApprovalTask.id.in_(ids),
            ApprovalTask.status == ApprovalStatus.PENDING.value,
        )
        .all()
    )
    if len(tasks) != len(ids):
        raise HTTPException(
            status_code=409, detail="审批中申请状态已变化，请刷新清单后重新发起移交"
        )
    transferred = 0
    for task in tasks:
        touched = False
        if task.current_approver_id == actor_id:
            task.current_approver_id = target.id
            touched = True
        if task.submitter_id == actor_id:
            task.submitter_id = target.id
            touched = True
        if not touched:
            raise HTTPException(status_code=403, detail=f"无权移交审批申请 {task.id}")
        db.add(
            ApprovalRecord(
                task_id=task.id,
                level=task.current_level,
                approver_id=actor_id,
                action=ApprovalAction.TRANSFER.value,
                opinion=APPROVAL_TRANSFER_OPINION,
                transfer_to_id=target.id,
                transfer_reason=note or "工作移交",
            )
        )
        transferred += 1
    return transferred


def _summary_text(counts: Dict[str, int]) -> str:
    """「帮扶村 2 项、项目 1 项」形式的数量摘要。"""
    parts = [
        f"{ASSET_LABELS[asset_type]} {counts[asset_type]} 项"
        for asset_type in ASSET_TYPES
        if counts.get(asset_type)
    ]
    return "、".join(parts)


def _item_line(item: Dict[str, Any], target_username: str) -> str:
    return f"{ASSET_LABELS[item['type']]}#{item['id']}《{item['title']}》→{target_username}"


def _write_notifications(
    db: Session,
    actor: Any,
    target: User,
    record_no: str,
    counts: Dict[str, int],
    total: int,
    items: List[Dict[str, Any]],
    note: Optional[str],
) -> None:
    """双方站内消息（同一事务内 add，不单独 commit）。"""
    from_username = getattr(actor, "username", None) or "系统用户"
    to_username = getattr(target, "username", None) or "接任人"
    summary = _summary_text(counts)
    item_lines = "；".join(_item_line(item, to_username) for item in items)
    detail = f"共 {total} 项（{summary}）。逐项：{item_lines}"
    if note:
        detail += f"。备注：{note}"
    db.add(
        Message(
            user_id=target.id,
            message_type=MessageType.SYSTEM.value,
            title="工作移交接任通知",
            content=f"{from_username} 向你移交了 {detail}",
            link="/handover",
            is_read=False,
        )
    )
    db.add(
        Message(
            user_id=getattr(actor, "id", None),
            message_type=MessageType.SYSTEM.value,
            title="工作移交完成",
            content=f"你已向 {to_username} 移交 {detail}（交接单号 {record_no}）",
            link="/handover",
            is_read=False,
        )
    )


def _build_snapshot(
    *,
    record_no: str,
    actor: Any,
    target: User,
    note: Optional[str],
    items: List[Dict[str, Any]],
    counts: Dict[str, int],
    total: int,
) -> Dict[str, Any]:
    """交接单结构化快照（存 WorkLog.attachments，history/导出回放用）。"""
    return {
        "record_no": record_no,
        "from_user": _user_brief(actor),
        "to_user": _user_brief(target),
        "from_username": getattr(actor, "username", None),
        "to_username": getattr(target, "username", None),
        "note": note,
        "items": [
            {
                "type": item["type"],
                "id": item["id"],
                "title": item["title"],
                "role": item.get("role"),
            }
            for item in items
        ],
        "counts": {asset_type: counts.get(asset_type, 0) for asset_type in ASSET_TYPES},
        "total": total,
        "created_at": _iso(datetime.now(timezone.utc)),
    }


def _audit_detail(snapshot: Dict[str, Any], counts: Dict[str, int], total: int) -> str:
    """审计原文（work_logs.content 的 detail 段）：接任人 + 备注 + 逐项清单。"""
    to_username = snapshot.get("to_username") or "接任人"
    item_lines = "；".join(_item_line(item, to_username) for item in snapshot["items"])
    detail = (
        f"接任人：{to_username}（ID {snapshot['to_user']['id']}）；"
        f"共 {total} 项（{_summary_text(counts)}）；逐项清单：{item_lines}"
    )
    note = snapshot.get("note")
    if note:
        detail += f"；备注：{note}"
    return detail


# ════════════════════════════════════════════════════════════════════
#  执行移交
# ════════════════════════════════════════════════════════════════════


def execute_handover(
    db: Session,
    actor: Any,
    *,
    to_user_id: int,
    scope: Optional[Iterable[str]] = None,
    item_ids: Optional[Dict[str, Any]] = None,
    note: Optional[str] = None,
) -> Dict[str, Any]:
    """执行工作移交（单事务：归属改写 + 双方消息 + 审批转交记录 + 审计）。

    事务边界：本函数内**不主动 commit**；最后一步 ``write_work_log`` 的
    ``safe_commit`` 统一提交全部改动（含业务归属、消息、审批记录、审计行）。
    任一步抛异常 → 未提交 → 由调用方/依赖回滚 → 全量回滚。
    """
    selected_scope = _split_scope(scope)
    _validate_item_ids(item_ids, selected_scope)

    target = db.query(User).filter(User.id == int(to_user_id)).first()
    assert_handover_target(actor, target)

    collected = _collect_assets(db, actor, selected_scope)
    selected = _select_assets(collected, selected_scope, item_ids)
    total = sum(len(items) for items in selected.values())
    if total == 0:
        raise HTTPException(
            status_code=422, detail="没有可移交的工作项：请先确认清单或勾选其他资产类型"
        )

    counts = _apply_ownership(db, actor, target, selected, note)
    total = sum(counts.values())
    items = [
        item for asset_type in selected_scope for item in selected.get(asset_type, [])
    ]
    record_no = generate_record_no()
    snapshot = _build_snapshot(
        record_no=record_no,
        actor=actor,
        target=target,
        note=note,
        items=items,
        counts=counts,
        total=total,
    )
    _write_notifications(db, actor, target, record_no, counts, total, items, note)

    log = write_work_log(
        db,
        HANDOVER_LOG_CATEGORY,
        "execute",
        0,
        f"工作移交 {getattr(actor, 'username', '')} → {getattr(target, 'username', '')}（{total} 项）",
        user_id=getattr(actor, "id", None),
        username=getattr(actor, "username", "系统"),
        detail=_audit_detail(snapshot, counts, total),
        attachments=json.dumps(snapshot, ensure_ascii=False),
    )
    if log is None:  # 防御：write_work_log 在 user_id 缺失时不提交 → 由本层兜底提交
        safe_commit(db)

    return {
        "record_id": getattr(log, "id", None),
        "record_no": record_no,
        "from_user": snapshot["from_user"],
        "to_user": snapshot["to_user"],
        "created_at": snapshot["created_at"],
        "note": note,
        "items": snapshot["items"],
        "counts": counts,
        "total": total,
    }


# ════════════════════════════════════════════════════════════════════
#  历史交接单
# ════════════════════════════════════════════════════════════════════


def _parse_snapshot(row: WorkLog) -> Dict[str, Any]:
    """解析审计行里的交接单快照；历史/异常数据回退为空快照（不抛错）。"""
    raw = getattr(row, "attachments", None)
    if raw:
        try:
            payload = json.loads(raw)
        except (TypeError, ValueError):
            logger.warning("交接审计快照不是合法 JSON（work_log id=%s）", row.id)
            payload = None
        if isinstance(payload, dict):
            return payload
    return {}


def _history_item(row: WorkLog) -> Dict[str, Any]:
    snapshot = _parse_snapshot(row)
    counts = snapshot.get("counts")
    if not isinstance(counts, dict):
        counts = {}
    items = snapshot.get("items")
    if not isinstance(items, list):
        items = []
    from_user = snapshot.get("from_user")
    if not isinstance(from_user, dict):
        from_user = {}
    to_user = snapshot.get("to_user")
    if not isinstance(to_user, dict):
        to_user = {}
    return {
        "id": row.id,
        "record_no": snapshot.get("record_no"),
        "from_user_id": from_user.get("id"),
        "from_username": snapshot.get("from_username"),
        "to_user_id": to_user.get("id"),
        "to_username": snapshot.get("to_username"),
        "note": snapshot.get("note"),
        "counts": {
            asset_type: int(counts.get(asset_type, 0) or 0) for asset_type in ASSET_TYPES
        },
        "total": int(snapshot.get("total") or len(items)),
        "items": items,
        "content": row.content,
        "log_date": row.log_date.isoformat() if row.log_date else None,
        "created_at": _iso(row.created_at),
    }


def query_history(
    db: Session,
    actor: Any,
    *,
    page: int = 1,
    page_size: int = 20,
    date_from: Optional[Any] = None,
    date_to: Optional[Any] = None,
) -> Tuple[List[Dict[str, Any]], int]:
    """当前用户的移交历史（按 log_type=handover + 本人 + 时间过滤）。"""
    query = db.query(WorkLog).filter(
        WorkLog.category == HANDOVER_LOG_CATEGORY,
        WorkLog.user_id == getattr(actor, "id", None),
    )
    if date_from is not None:
        query = query.filter(WorkLog.log_date >= date_from)
    if date_to is not None:
        query = query.filter(WorkLog.log_date <= date_to)
    total = query.count()
    rows = (
        query.order_by(WorkLog.id.desc())
        .offset(max(0, page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return [_history_item(row) for row in rows], total
