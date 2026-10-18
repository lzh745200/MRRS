"""乡村工作服务"""

import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import extract, func
from sqlalchemy.orm import Session

from app.core.permission_utils import is_admin
from app.models.rural_work import RuralWork, WorkStatus, WorkType
from app.schemas.rural_work import RuralWorkStatistics
from app.services.work_log_service import write_work_log
from app.core.transaction import safe_commit
from app.utils.time_utils import utcnow

logger = logging.getLogger(__name__)


def _iso(val: Any) -> Optional[str]:
    """安全地将日期/时间值转换为 ISO 字符串"""
    return val.isoformat() if val else None


def _safe_enum_value(val: Any) -> Any:
    """安全获取枚举值：有 .value 则取 .value，否则返回原值"""
    return val.value if val and hasattr(val, "value") else val


def _apply_work_scope(query, current_user: Any, db: Any):
    """乡村工作数据权限过滤（与 apply_scope_filter 语义一致，兼容历史数据）

    - 管理员：不过滤
    - 部门范围（OWN_DEPT）：本组织 + 下级组织；organization_id 为空的历史记录按创建人可见
    - 仅本人（OWN）：按 created_by 过滤
    """
    from sqlalchemy import and_, or_

    from app.core.data_permission import DataScope, get_data_scope

    if current_user is None or is_admin(current_user):
        return query

    user_data_scope = getattr(current_user, "data_scope", None)
    owner_id = getattr(current_user, "id", None)
    if user_data_scope == "self":
        return query.filter(RuralWork.created_by == owner_id)

    scope = get_data_scope(current_user)
    # pragma: no cover —— 经论证逻辑不可达的防御性冗余分支：
    # get_data_scope() 仅当 is_superuser=True 或 role==super_admin 时返回 ALL，
    # 而这两类用户在上方 line 41 已被 is_admin() 判定为管理员并提前 return。
    # 故任何能执行到此处的非管理员用户，scope 恒不等于 ALL，此分支永不命中。
    if scope == DataScope.ALL:  # pragma: no cover - 论证见上：能到达此处的非管理员 scope 恒不等于 ALL
        return query

    org_id = getattr(current_user, "organization_id", None) or getattr(current_user, "org_id", None)
    if scope == DataScope.OWN_DEPT and org_id:
        from app.core.data_permission import _get_org_subtree

        org_ids, _names = _get_org_subtree(db, org_id)
        org_ids = org_ids if org_ids else [org_id]
        return query.filter(
            or_(
                RuralWork.organization_id.in_(org_ids),
                and_(RuralWork.organization_id.is_(None), RuralWork.created_by == owner_id),
            )
        )

    return query.filter(RuralWork.created_by == owner_id)


def _can_access_work(work, current_user: Any, db: Any) -> bool:
    """单条乡村工作记录访问校验（与 _apply_work_scope 同口径）"""
    if current_user is None or is_admin(current_user):
        return True
    owner_id = getattr(current_user, "id", None)
    if work.created_by == owner_id:
        return True
    user_data_scope = getattr(current_user, "data_scope", None)
    if user_data_scope == "self":
        return False
    from app.core.data_permission import DataScope, get_data_scope

    if get_data_scope(current_user) == DataScope.OWN_DEPT:
        org_id = getattr(current_user, "organization_id", None) or getattr(current_user, "org_id", None)
        if org_id and work.organization_id:
            from app.core.data_permission import _get_org_subtree

            org_ids, _names = _get_org_subtree(db, org_id)
            if work.organization_id in (org_ids if org_ids else [org_id]):
                return True
    return False


def _to_work_type(val: Any) -> WorkType:
    """将任意输入转换为 WorkType 枚举，空值/非法值回退到默认值。"""
    if isinstance(val, WorkType):
        return val
    if not val:
        return WorkType.infrastructure
    try:
        return WorkType(str(val))
    except ValueError:
        return WorkType.infrastructure


def _to_work_status(val: Any) -> WorkStatus:
    """将任意输入转换为 WorkStatus 枚举，空值/非法值回退到默认值。"""
    if isinstance(val, WorkStatus):
        return val
    if not val:
        return WorkStatus.planned
    try:
        return WorkStatus(str(val))
    except ValueError:
        return WorkStatus.planned


# RuralWork 允许通过 schema/kwargs 批量赋值的字段白名单
# W22：DB 列 village_id 已改为 supported_village_id（FK supported_villages），
# 旧调用方仍可能传 village_id，由 update/create 内部归一。
_WRITABLE_FIELDS = {
    "name", "description", "type", "status", "supported_village_id",
    "responsible_person", "contact_phone", "start_date", "end_date",
    "target", "progress",
}


class RuralWorkService:
    """乡村工作服务"""

    def __init__(self, db: Session):
        self.db = db

    # ── 序列化辅助 ──
    @staticmethod
    def _to_dict(r: RuralWork) -> Dict[str, Any]:
        """将 RuralWork ORM 对象序列化为前端友好的字典。

        W22：关联对象由遗留 Village 改为 SupportedVillage（帮扶村）；
        响应同时给出 ``supported_village_id``（新）与 ``village_id``（旧前端兼容），
        村名取 ``supported_villages.village_name``。
        """
        supported_village_id = getattr(r, "supported_village_id", None)
        village_name = None
        supported_village = getattr(r, "supported_village", None)
        if supported_village is not None:
            village_name = getattr(supported_village, "village_name", None)
        return {
            "id": r.id,
            "code": r.code,
            "name": r.name,
            "type": _safe_enum_value(r.type),
            "status": _safe_enum_value(r.status),
            "supported_village_id": supported_village_id,
            "village_id": supported_village_id,  # 兼容旧前端字段（W22 契约偏差说明）
            "village_name": village_name,
            "responsible_person": r.responsible_person,
            "contact_phone": r.contact_phone,
            "start_date": _iso(r.start_date),
            "end_date": _iso(r.end_date),
            "description": r.description,
            "target": r.target,
            "progress": r.progress,
            "created_at": _iso(r.created_at),
            "updated_at": _iso(r.updated_at),
            "created_by": r.created_by,
            "updated_by": r.updated_by,
        }

    def get_rural_works(
        self,
        skip: int = 0,
        limit: int = 10,
        status: Optional[str] = None,
        type: Optional[str] = None,
        village_id: Optional[int] = None,
        search: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        year: Optional[int] = None,
        order_by: str = "created_at",
        order_desc: bool = True,
        current_user: Any = None,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """获取乡村工作列表（含筛选及数据权限）"""
        query = self.db.query(RuralWork)

        # 数据权限隔离：管理员全量；部门范围含下级组织；仅本人按创建人
        query = _apply_work_scope(query, current_user, self.db)

        if status:
            query = query.filter(RuralWork.status == status)
        if type:
            query = query.filter(RuralWork.type == type)
        if village_id:
            query = query.filter(RuralWork.supported_village_id == village_id)
        if search:
            like = f"%{search}%"
            query = query.filter(
                RuralWork.name.ilike(like) | RuralWork.description.ilike(like)
            )
        if start_date:
            try:
                dt = datetime.fromisoformat(start_date)
                query = query.filter(RuralWork.start_date >= dt)
            except ValueError:
                pass
        if end_date:
            try:
                dt = datetime.fromisoformat(end_date)
                query = query.filter(RuralWork.end_date <= dt)
            except ValueError:
                pass
        if year:
            query = query.filter(extract("year", RuralWork.start_date) == year)

        total = query.count()

        order_col = getattr(RuralWork, order_by, RuralWork.created_at)
        if order_desc:
            query = query.order_by(order_col.desc())
        else:
            query = query.order_by(order_col.asc())

        rows = query.offset(skip).limit(limit).all()

        items = [self._to_dict(r) for r in rows]

        return items, total

    # ── Backward-compat aliases (tests expect these method names) ──
    def get_rural_work_by_id(
        self, work_id: int, current_user: Any = None
    ) -> Optional[Dict[str, Any]]:
        work = self.db.query(RuralWork).filter(RuralWork.id == work_id).first()
        if not work:
            return None
        # 数据隔离：非管理员只能读取本组织或自己创建的记录
        if not _can_access_work(work, current_user, self.db):
            return None
        return self._to_dict(work)

    def delete_rural_work(
        self,
        work_id: int,
        user_id: Optional[int] = None,
        current_user: Any = None,
    ) -> bool:
        work = self.db.query(RuralWork).filter(RuralWork.id == work_id).first()
        if not work:
            return False
        # 数据隔离：非管理员只能删除本组织或自己创建的记录
        if not _can_access_work(work, current_user, self.db):
            return False
        work_name = work.name
        self.db.delete(work)
        safe_commit(self.db)
        if user_id is not None:
            try:
                write_work_log(
                    self.db, "rural_work", "delete", work_id, work_name,
                    user_id=user_id, detail=f"删除乡村工作: {work_name}",
                )
            except Exception:  # noqa: B902 - 审计日志失败不应影响业务操作
                logger.debug("记录工作日志失败")
        return True

    def _validate_village_id(self, village_id: Optional[int]) -> None:
        """校验 village_id 对应的帮扶村存在。

        W22：RuralWork.supported_village_id 的外键指向 ``supported_villages``
        （原遗留 villages 表已删除）；传入不存在的 id 时 INSERT 触发
        FOREIGN KEY constraint failed → 未处理 IntegrityError → 500。
        提前校验转为 ValueError，由路由层转 400。
        """
        if not village_id:
            return
        from app.models.supported_village import SupportedVillage

        if not self.db.query(SupportedVillage.id).filter(
            SupportedVillage.id == village_id
        ).first():
            raise ValueError(
                f"所选帮扶村不存在（village_id={village_id}）。"
                "请从乡村工作台的村庄下拉中选择。"
            )

    def create_rural_work(
        self,
        data: Any,
        user_id: Optional[int] = None,
        organization_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """基于 RuralWorkCreate schema 创建乡村工作记录。

        Args:
            data: RuralWorkCreate schema 实例（或字典）。
            user_id: 创建人ID，写入 created_by/updated_by 并记录审计日志。
            organization_id: 所属组织ID（数据权限隔离）。

        Returns:
            创建后的工作记录字典（与路由期望的 ``work.model_dump()`` 契约一致，
            即一个可被 ``ResponseModel(data=...)`` 直接序列化的 dict）。
        """
        payload = data.model_dump() if hasattr(data, "model_dump") else dict(data)

        # W22：DB 列改为 supported_village_id（FK supported_villages）；
        # 旧调用方/schema 仍可能传 village_id，这里兼容归一。
        village_id = payload.get("village_id") or payload.get("supported_village_id")
        self._validate_village_id(village_id)

        work = RuralWork(
            code=self._generate_code(),
            name=payload.get("name"),
            description=payload.get("description"),
            type=_to_work_type(payload.get("type")),
            status=_to_work_status(payload.get("status")),
            supported_village_id=village_id,
            responsible_person=payload.get("responsible_person"),
            contact_phone=payload.get("contact_phone"),
            start_date=payload.get("start_date"),
            end_date=payload.get("end_date"),
            target=payload.get("target"),
            progress=payload.get("progress") or 0,
            created_by=user_id,
            updated_by=user_id,
            organization_id=organization_id,
        )
        self.db.add(work)
        safe_commit(self.db)
        self.db.refresh(work)

        if user_id is not None:
            try:
                write_work_log(
                    self.db, "rural_work", "create", work.id, work.name,
                    user_id=user_id, detail=f"创建乡村工作: {work.name}",
                )
            except Exception:  # noqa: B902 - 审计日志失败不应影响业务操作
                logger.debug("记录工作日志失败")

        return self._to_dict(work)

    def update_rural_work(
        self,
        work_id: int,
        data: Any = None,
        user_id: Optional[int] = None,
        current_user: Any = None,
        **kwargs: Any,
    ) -> Optional[Dict[str, Any]]:
        """更新乡村工作记录。

        兼容两种调用方式：
            - 路由调用: ``update_rural_work(work_id, data, user_id)``，data 为
              RuralWorkUpdate schema 实例。
            - 旧式调用: ``update_rural_work(work_id, name="x", ...)``，字段通过
              kwargs 传入（向后兼容现有单元测试）。
        """
        work = self.db.query(RuralWork).filter(RuralWork.id == work_id).first()
        if not work:
            return None

        # 数据隔离：非管理员只能更新本组织或自己创建的记录
        if not _can_access_work(work, current_user, self.db):
            return None

        # 合并来源：Pydantic data（仅显式设置的字段）+ kwargs
        updates: Dict[str, Any] = {}
        if data is not None:
            if hasattr(data, "model_dump"):
                updates.update(data.model_dump(exclude_unset=True))
            else:
                updates.update(dict(data))
        updates.update(kwargs)

        # W22：旧字段 village_id → 新列 supported_village_id 归一后再校验/写入
        if "village_id" in updates and "supported_village_id" not in updates:
            updates["supported_village_id"] = updates.pop("village_id")
        else:
            updates.pop("village_id", None)
        if "supported_village_id" in updates:
            self._validate_village_id(updates.get("supported_village_id"))

        for key, value in updates.items():
            if key not in _WRITABLE_FIELDS:
                continue
            if key == "type":
                value = _to_work_type(value)
            elif key == "status":
                value = _to_work_status(value)
            setattr(work, key, value)

        if user_id is not None:
            work.updated_by = user_id

        safe_commit(self.db)
        self.db.refresh(work)

        if user_id is not None:
            try:
                write_work_log(
                    self.db, "rural_work", "update", work.id, work.name,
                    user_id=user_id, detail=f"更新乡村工作: {work.name}",
                )
            except Exception:  # noqa: B902 - 审计日志失败不应影响业务操作
                logger.debug("记录工作日志失败")

        return self._to_dict(work)

    def get_statistics(self, current_user: Any = None) -> RuralWorkStatistics:
        """获取乡村工作统计数据，返回 RuralWorkStatistics schema 实例。"""
        base = _apply_work_scope(self.db.query(RuralWork), current_user, self.db)
        total = base.count()
        planned = base.filter(RuralWork.status == WorkStatus.planned).count()
        in_progress = base.filter(RuralWork.status == WorkStatus.in_progress).count()
        completed = base.filter(RuralWork.status == WorkStatus.completed).count()
        delayed = base.filter(RuralWork.status == WorkStatus.delayed).count()

        # R20 复审：by_type 此前直接查全表，非管理员拿到跨组织类型分布
        rows = (
            _apply_work_scope(self.db.query(RuralWork.type, func.count(RuralWork.id)), current_user, self.db)
            .group_by(RuralWork.type)
            .all()
        )
        by_type = {_safe_enum_value(t): c for t, c in rows}

        completion_rate = round(completed / total, 4) if total else 0.0

        return RuralWorkStatistics(
            total=total,
            planned=planned,
            in_progress=in_progress,
            completed=completed,
            delayed=delayed,
            by_type=by_type,
            completion_rate=completion_rate,
        )

    def get_villages_for_select(self, current_user: Any = None) -> List[Dict[str, Any]]:
        """获取帮扶村下拉列表（id / 村名 / 县市）。

        W22：不再向遗留 villages 表 upsert 影子数据 —— 乡村工作直接外键
        ``supported_villages``，下拉 id 即帮扶村 id。非管理员按数据权限过滤。
        """
        from app.core.data_permission import apply_scope_filter
        from app.models.supported_village import SupportedVillage

        query = self.db.query(SupportedVillage).filter(
            SupportedVillage.is_active.is_(True)
        )
        if current_user is not None:
            query = apply_scope_filter(query, current_user, SupportedVillage, db=self.db)
        villages = query.order_by(SupportedVillage.village_name.asc()).all()
        return [
            {
                "id": sv.id,
                "name": sv.village_name,
                "county": getattr(sv, "county", None),
            }
            for sv in villages
        ]

    def generate_work_report(
        self,
        year: Optional[int] = None,
        start_date: Optional[Any] = None,
        end_date: Optional[Any] = None,
        current_user: Any = None,
    ) -> Dict[str, Any]:
        """生成工作报告汇总数据。"""
        query = _apply_work_scope(self.db.query(RuralWork), current_user, self.db)
        if year:
            query = query.filter(extract("year", RuralWork.start_date) == year)
        if start_date:
            query = query.filter(RuralWork.start_date >= _coerce_datetime(start_date))
        if end_date:
            query = query.filter(RuralWork.end_date <= _coerce_datetime(end_date))

        rows = query.all()
        total = len(rows)

        by_status: Dict[str, int] = {}
        by_type: Dict[str, int] = {}
        for r in rows:
            s = _safe_enum_value(r.status) or "unknown"
            t = _safe_enum_value(r.type) or "unknown"
            by_status[s] = by_status.get(s, 0) + 1
            by_type[t] = by_type.get(t, 0) + 1

        completed = by_status.get("completed", 0)
        completion_rate = round(completed / total, 4) if total else 0.0

        return {
            "total": total,
            "by_status": by_status,
            "by_type": by_type,
            "completion_rate": completion_rate,
            # 前端统计卡兼容字段
            "summary": {
                "total": total,
                "completed": completed,
                "in_progress": by_status.get("in_progress", 0),
                "delayed": by_status.get("delayed", 0),
                "planned": by_status.get("planned", 0),
            },
            "items": [self._to_dict(r) for r in rows],
        }

    def get_available_years(self) -> List[int]:
        """获取可用年份列表（按降序）。"""
        year_col = extract("year", RuralWork.start_date).label("year")
        rows = (
            self.db.query(year_col)
            .filter(RuralWork.start_date.isnot(None))
            .distinct()
            .order_by(year_col.desc())
            .all()
        )
        return [int(r.year) for r in rows if r.year is not None]

    def batch_delete(self, ids: List[int], current_user: Any = None) -> int:
        """批量删除乡村工作，返回实际删除条数。

        数据隔离：非管理员只能删除本组织或自己创建的记录。
        """
        if not ids:
            return 0
        query = _apply_work_scope(
            self.db.query(RuralWork).filter(RuralWork.id.in_(list(ids))),
            current_user,
            self.db,
        )
        deleted = query.delete(synchronize_session=False)
        safe_commit(self.db)
        return int(deleted or 0)

    @staticmethod
    def _generate_code() -> str:
        return f"RW-{uuid.uuid4().hex[:8].upper()}"


def _coerce_datetime(val: Any) -> datetime:
    """将字符串/datetime 统一转换为 datetime；无法解析时返回当前 UTC 时刻。

    本函数仅用作 RuralWork.start_date/end_date（UtcDateTime 列）的**比较边界**，
    因此回退值必须是 aware UTC——旧实现返回本地 naive 的 ``datetime.now()``，
    在无法解析的入参下会与 UTC 列相差一个本机时区偏移。
    """
    if isinstance(val, datetime):
        return val
    if val:
        try:
            return datetime.fromisoformat(str(val))
        except ValueError:
            pass
    return utcnow()
